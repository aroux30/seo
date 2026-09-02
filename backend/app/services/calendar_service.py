"""Content calendar service — slots, board, and the auto-scheduler.

A calendar entry is a *slot*, not a copy of an article; see
`app.models.calendar` for why `deadline` and `scheduled_for` are separate
columns and why `overdue` is never stored.

Three things here are deliberate and easy to get wrong later:

* **Overdue is computed, never stored.** `_is_overdue` derives it at read time
  from `deadline < now()` plus a non-terminal status. A stored boolean would go
  stale the moment the clock passes a deadline with no write happening, which
  is exactly when the dashboard needs it to be right.
* **Day bucketing happens in Tehran local time.** Timestamps are stored
  timezone-aware in UTC, but a calendar grid is a human artifact: an entry at
  2026-08-14T21:00Z belongs to the 15th for a Tehran user, not the 14th. Every
  bucket boundary below is built in `CALENDAR_TZ` and only then converted to
  UTC for the query, so the month view never off-by-ones at the edges.
* **The auto-scheduler is idempotent on the finding.** Re-running it must
  not double-book the same opportunity: it skips an opportunity that already
  has a slot (by `opportunity_id`) *and* any opportunity whose `fingerprint`
  was ever scheduled, so a re-detected finding — new row, same subject — stays
  single-booked. It also never re-proposes a slot the user deleted; a run
  schedules at most `max_entries` new slots and reports what it skipped.

Scoping: every function takes `organization_id` and raises `NotFoundError`
(404) on a cross-tenant id, never `ForbiddenError`, so a UUID cannot be used as
an existence oracle.

Services flush; routers commit.
"""

from collections import defaultdict
from datetime import date as date_cls
from datetime import datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models import Website
from app.models.calendar import (
    CALENDAR_ENTRY_PRIORITIES,
    CALENDAR_ENTRY_STATUSES,
    ContentCalendarEntry,
)
from app.models.insights import Opportunity

__all__ = [
    "create_entry",
    "list_entries",
    "get_entry",
    "update_entry",
    "move_entry",
    "delete_entry",
    "get_month_view",
    "get_week_view",
    "get_board_view",
    "get_calendar_summary",
    "auto_schedule_from_opportunities",
    "collect_due_reminders",
]

# The product's operating timezone. Calendar grids and "due this week" are
# human-facing windows and must be cut on local day boundaries, not UTC ones.
CALENDAR_TZ = ZoneInfo("Asia/Tehran")

# Statuses that mean the slot is finished; excluded from overdue/open counters.
TERMINAL_STATUSES = ("published", "cancelled")

# Default spacing for the auto-scheduler: one slot every other day, so a burst
# of detected opportunities does not all land on the same publish date.
AUTO_SCHEDULE_DAY_STEP = 2

# How far ahead `collect_due_reminders` looks by default.
REMINDER_LOOKAHEAD_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------- day windows

def _local_day_bounds(day: date_cls) -> tuple[datetime, datetime]:
    """UTC half-open range [start, end) covering one Tehran calendar day.

    Built in local time first, then converted: constructing it in UTC and adding
    an offset would break on any DST-style transition and silently shift which
    day an entry falls on.
    """
    start_local = datetime.combine(day, time.min, tzinfo=CALENDAR_TZ)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _local_range_bounds(first_day: date_cls, last_day: date_cls) -> tuple[datetime, datetime]:
    """UTC half-open range covering the Tehran days first_day..last_day inclusive."""
    start, _ = _local_day_bounds(first_day)
    _, end = _local_day_bounds(last_day)
    return start, end


def _local_date_key(moment: datetime) -> str:
    """The Tehran calendar day an instant belongs to, as an ISO date string.

    Naive timestamps are treated as UTC rather than local: everything this
    service writes is tz-aware, so a naive value can only come from legacy rows,
    and assuming UTC matches how they were stored.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(CALENDAR_TZ).date().isoformat()


def _month_day_span(year: int, month: int) -> tuple[date_cls, date_cls]:
    """First and last day of a month, without calendar module rounding games."""
    if not 1 <= month <= 12:
        raise ValidationError("month must be between 1 and 12")
    first = date_cls(year, month, 1)
    # Jump into the next month, then step back one day.
    if month == 12:
        next_first = date_cls(year + 1, 1, 1)
    else:
        next_first = date_cls(year, month + 1, 1)
    return first, next_first - timedelta(days=1)


def _is_overdue(row: ContentCalendarEntry, at: datetime | None = None) -> bool:
    """Deadline passed and the slot is not finished. Never persisted."""
    if row.deadline is None or row.status in TERMINAL_STATUSES:
        return False
    deadline = row.deadline
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return deadline < (at or _now())


# ------------------------------------------------------------------- validation

def _assert_known_status(status: str) -> None:
    if status not in CALENDAR_ENTRY_STATUSES:
        raise ValidationError(
            f"status must be one of {sorted(CALENDAR_ENTRY_STATUSES)}"
        )


def _assert_known_priority(priority: str) -> None:
    if priority not in CALENDAR_ENTRY_PRIORITIES:
        raise ValidationError(
            f"priority must be one of {sorted(CALENDAR_ENTRY_PRIORITIES)}"
        )


def _assert_deadline_sane(
    scheduled_for: datetime | None, deadline: datetime | None
) -> None:
    """A deadline after the publish date is a data-entry slip, not a plan.

    Only checked when both are present; either one alone is legitimate (a slot
    can have a hard deadline with no date picked yet, or vice versa).
    """
    if scheduled_for is None or deadline is None:
        return
    sched = scheduled_for if scheduled_for.tzinfo else scheduled_for.replace(tzinfo=timezone.utc)
    due = deadline if deadline.tzinfo else deadline.replace(tzinfo=timezone.utc)
    if due > sched:
        raise ValidationError(
            "مهلت انجام نمی‌تواند بعد از تاریخ انتشار برنامه‌ریزی‌شده باشد."
        )


# ---------------------------------------------------------------------- lookups

async def _assert_website_in_org(
    db: AsyncSession, website_id: UUID, org_id: UUID
) -> Website:
    result = await db.execute(
        select(Website).where(
            Website.id == website_id,
            Website.organization_id == org_id,
            Website.deleted_at.is_(None),
        )
    )
    website = result.scalar_one_or_none()
    if not website:
        raise NotFoundError("Website", str(website_id))
    return website


async def get_entry(
    db: AsyncSession, entry_id: UUID, org_id: UUID
) -> ContentCalendarEntry:
    """Fetch one entry, scoped to the caller's organization.

    Joins through `Website` instead of trusting the denormalised
    `organization_id` alone, so an entry on a soft-deleted website stops being
    reachable.
    """
    result = await db.execute(
        select(ContentCalendarEntry)
        .join(Website, Website.id == ContentCalendarEntry.website_id)
        .where(
            ContentCalendarEntry.id == entry_id,
            ContentCalendarEntry.organization_id == org_id,
            Website.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise NotFoundError("ContentCalendarEntry", str(entry_id))
    return row


# ------------------------------------------------------------------------ writes

async def create_entry(
    db: AsyncSession,
    *,
    org_id: UUID,
    website_id: UUID,
    title: str,
    brief_id: UUID | None = None,
    article_id: UUID | None = None,
    opportunity_id: UUID | None = None,
    status: str = "planned",
    priority: str = "normal",
    scheduled_for: datetime | None = None,
    deadline: datetime | None = None,
    assigned_to: UUID | None = None,
    target_keyword: str | None = None,
    notes: str | None = None,
    details: dict | None = None,
) -> ContentCalendarEntry:
    """Plan a new slot.

    `source` is forced to "manual" here — only `auto_schedule_from_opportunities`
    may write "ai_auto", otherwise a hand-made slot could impersonate a
    machine-made one and be skipped by the scheduler's dedup check.
    """
    _assert_known_status(status)
    _assert_known_priority(priority)
    _assert_deadline_sane(scheduled_for, deadline)

    row = ContentCalendarEntry(
        organization_id=org_id,
        website_id=website_id,
        title=title.strip(),
        brief_id=brief_id,
        article_id=article_id,
        opportunity_id=opportunity_id,
        status=status,
        priority=priority,
        source="manual",
        scheduled_for=scheduled_for,
        deadline=deadline,
        assigned_to=assigned_to,
        target_keyword=target_keyword,
        notes=notes,
        details=details or {},
    )
    # A slot created directly as published still needs a truthful timestamp.
    if status == "published":
        row.published_at = _now()
    db.add(row)
    await db.flush()
    return row


async def update_entry(
    db: AsyncSession,
    entry_id: UUID,
    org_id: UUID,
    *,
    changes: dict,
) -> ContentCalendarEntry:
    """Patch a slot from a partial payload.

    Only keys actually present in `changes` are touched, so a PATCH that sends
    `{"status": "in_progress"}` cannot blank out the notes. `published_at` is
    maintained here rather than by the caller: it is set the first time the slot
    reaches "published" and cleared if the slot is moved back out of it, which is
    what makes it usable as "when did this actually ship".
    """
    row = await get_entry(db, entry_id, org_id)

    if "status" in changes and changes["status"] is not None:
        _assert_known_status(changes["status"])
    if "priority" in changes and changes["priority"] is not None:
        _assert_known_priority(changes["priority"])

    # Validate the deadline against the post-update pair, not the old one.
    next_scheduled = changes.get("scheduled_for", row.scheduled_for) if "scheduled_for" in changes else row.scheduled_for
    next_deadline = changes.get("deadline", row.deadline) if "deadline" in changes else row.deadline
    _assert_deadline_sane(next_scheduled, next_deadline)

    editable = (
        "title",
        "status",
        "priority",
        "scheduled_for",
        "deadline",
        "assigned_to",
        "target_keyword",
        "notes",
        "details",
        "brief_id",
        "article_id",
    )
    previous_status = row.status
    for field in editable:
        if field in changes:
            value = changes[field]
            if field == "title" and value is not None:
                value = value.strip()
            setattr(row, field, value)

    if row.status == "published" and previous_status != "published":
        row.published_at = _now()
    elif row.status != "published" and previous_status == "published":
        # Reopened. Leaving the old timestamp would claim it is still live.
        row.published_at = None

    await db.flush()
    return row


async def move_entry(
    db: AsyncSession,
    entry_id: UUID,
    org_id: UUID,
    *,
    scheduled_for: datetime | None = None,
    status: str | None = None,
) -> ContentCalendarEntry:
    """Drag-and-drop: reschedule and/or change column in one call.

    Separate from `update_entry` because the board and the month grid both need
    exactly this and nothing else — keeping it narrow means a drag can never
    accidentally carry along stale form fields from the client.
    """
    changes: dict = {}
    if scheduled_for is not None:
        changes["scheduled_for"] = scheduled_for
    if status is not None:
        changes["status"] = status
    if not changes:
        raise ValidationError("move requires scheduled_for and/or status")
    return await update_entry(db, entry_id, org_id, changes=changes)


async def delete_entry(db: AsyncSession, entry_id: UUID, org_id: UUID) -> None:
    """Soft-delete a slot.

    Soft rather than hard so a cancelled plan stays auditable, and so the
    scheduler's `opportunity_id` dedup still sees that this opportunity was once
    planned and declined.
    """
    row = await get_entry(db, entry_id, org_id)
    row.deleted_at = _now()
    await db.flush()


# ------------------------------------------------------------------------ reads

def _base_query(org_id: UUID, website_id: UUID | None):
    """Live entries for an org, optionally narrowed to one website.

    Every read below starts here so the soft-delete and tenant filters can never
    be forgotten at a call site.
    """
    stmt = (
        select(ContentCalendarEntry)
        .join(Website, Website.id == ContentCalendarEntry.website_id)
        .where(
            ContentCalendarEntry.organization_id == org_id,
            ContentCalendarEntry.deleted_at.is_(None),
            Website.deleted_at.is_(None),
        )
    )
    if website_id is not None:
        stmt = stmt.where(ContentCalendarEntry.website_id == website_id)
    return stmt


async def list_entries(
    db: AsyncSession,
    *,
    org_id: UUID,
    website_id: UUID | None = None,
    status: str | None = None,
    priority: str | None = None,
    assigned_to: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    overdue_only: bool = False,
    unscheduled_only: bool = False,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[ContentCalendarEntry], int]:
    """Filtered slot list plus the total count for pagination.

    `date_from`/`date_to` filter on `scheduled_for`. `unscheduled_only` is the
    complement — the backlog of slots with no date yet — so the two are mutually
    exclusive by construction rather than by a rule the caller has to remember.
    """
    stmt = _base_query(org_id, website_id)

    if status:
        _assert_known_status(status)
        stmt = stmt.where(ContentCalendarEntry.status == status)
    if priority:
        _assert_known_priority(priority)
        stmt = stmt.where(ContentCalendarEntry.priority == priority)
    if assigned_to:
        stmt = stmt.where(ContentCalendarEntry.assigned_to == assigned_to)

    if unscheduled_only:
        stmt = stmt.where(ContentCalendarEntry.scheduled_for.is_(None))
    else:
        if date_from:
            stmt = stmt.where(ContentCalendarEntry.scheduled_for >= date_from)
        if date_to:
            stmt = stmt.where(ContentCalendarEntry.scheduled_for < date_to)

    if overdue_only:
        # Mirrors _is_overdue in SQL so the filter and the computed flag agree.
        stmt = stmt.where(
            ContentCalendarEntry.deadline.is_not(None),
            ContentCalendarEntry.deadline < _now(),
            ContentCalendarEntry.status.not_in(TERMINAL_STATUSES),
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Nulls last: unscheduled backlog belongs after dated work, not before it.
    stmt = stmt.order_by(
        ContentCalendarEntry.scheduled_for.is_(None),
        ContentCalendarEntry.scheduled_for.asc(),
        ContentCalendarEntry.created_at.desc(),
    ).limit(limit).offset(offset)

    rows = list((await db.execute(stmt)).scalars().all())
    return rows, total


def is_entry_overdue(row: ContentCalendarEntry, at: datetime | None = None) -> bool:
    """Public form of `_is_overdue`, for callers assembling their own payloads.

    `CalendarEntryRead` reads straight off the ORM row via `from_attributes`, so
    the aggregate views below return rows rather than dicts. Overdue is not a
    column, so anything that wants to show it calls this.
    """
    return _is_overdue(row, at)


async def get_month_view(
    db: AsyncSession,
    *,
    org_id: UUID,
    year: int,
    month: int,
    website_id: UUID | None = None,
) -> dict:
    """Entries for one Tehran calendar month, bucketed by local day.

    The query window is built from local day boundaries converted to UTC, so an
    entry late on the 31st in Tehran lands in this month rather than leaking into
    the next one.
    """
    first_day, last_day = _month_day_span(year, month)
    start, end = _local_range_bounds(first_day, last_day)

    stmt = _base_query(org_id, website_id).where(
        ContentCalendarEntry.scheduled_for >= start,
        ContentCalendarEntry.scheduled_for < end,
    ).order_by(ContentCalendarEntry.scheduled_for.asc())

    rows = list((await db.execute(stmt)).scalars().all())

    buckets: dict[str, list[ContentCalendarEntry]] = defaultdict(list)
    for row in rows:
        buckets[_local_date_key(row.scheduled_for)].append(row)

    # Every day of the month is emitted, empty or not: the grid needs a cell per
    # day, and synthesising the gaps in the frontend would duplicate the timezone
    # logic there.
    days = []
    cursor = first_day
    while cursor <= last_day:
        key = cursor.isoformat()
        entries = buckets.get(key, [])
        days.append({"date": key, "entries": entries, "count": len(entries)})
        cursor += timedelta(days=1)

    return {
        "website_id": website_id,
        "year": year,
        "month": month,
        "range_start": start,
        "range_end": end,
        "days": days,
    }


async def get_week_view(
    db: AsyncSession,
    *,
    org_id: UUID,
    start_date: date_cls,
    website_id: UUID | None = None,
) -> dict:
    """Seven local days starting at `start_date`, bucketed by day.

    Every day in the span is emitted even when empty — the week strip needs a
    fixed seven columns, and letting the frontend synthesise the gaps would
    duplicate the timezone logic there.
    """
    last_day = start_date + timedelta(days=6)
    start, end = _local_range_bounds(start_date, last_day)

    stmt = _base_query(org_id, website_id).where(
        ContentCalendarEntry.scheduled_for >= start,
        ContentCalendarEntry.scheduled_for < end,
    ).order_by(ContentCalendarEntry.scheduled_for.asc())

    rows = list((await db.execute(stmt)).scalars().all())

    buckets: dict[str, list[ContentCalendarEntry]] = defaultdict(list)
    for row in rows:
        buckets[_local_date_key(row.scheduled_for)].append(row)

    days = []
    for day_offset in range(7):
        key = (start_date + timedelta(days=day_offset)).isoformat()
        entries = buckets.get(key, [])
        days.append({"date": key, "entries": entries, "count": len(entries)})

    return {
        "website_id": website_id,
        "range_start": start,
        "range_end": end,
        "days": days,
    }


async def get_board_view(
    db: AsyncSession,
    *,
    org_id: UUID,
    website_id: UUID | None = None,
    limit_per_column: int = 100,
) -> dict:
    """Kanban board: every status column, in the canonical vocabulary order.

    Empty columns are included on purpose. A board that hides "cancelled" until
    something is cancelled has no drop target for cancelling the first item.
    """
    stmt = _base_query(org_id, website_id).order_by(
        ContentCalendarEntry.scheduled_for.is_(None),
        ContentCalendarEntry.scheduled_for.asc(),
        ContentCalendarEntry.created_at.desc(),
    )
    rows = list((await db.execute(stmt)).scalars().all())

    grouped: dict[str, list[ContentCalendarEntry]] = defaultdict(list)
    for row in rows:
        grouped[row.status].append(row)

    # Dict comprehension over the vocabulary, not over what happened to be found:
    # a board that omits "cancelled" until something is cancelled has no drop
    # target for cancelling the first item. Insertion order follows
    # CALENDAR_ENTRY_STATUSES, which is the column order the UI draws.
    return {
        "columns": {
            status: grouped.get(status, [])[:limit_per_column]
            for status in CALENDAR_ENTRY_STATUSES
        }
    }


async def get_calendar_summary(
    db: AsyncSession,
    *,
    org_id: UUID,
    website_id: UUID | None = None,
) -> dict:
    """Counters for the dashboard card.

    Counts run as aggregate queries rather than by loading rows: this is called
    on every dashboard render and the row bodies are never used.
    """
    at = _now()
    base = _base_query(org_id, website_id).subquery()

    status_rows = (
        await db.execute(
            select(base.c.status, func.count())
            .select_from(base)
            .group_by(base.c.status)
        )
    ).all()
    by_status = {status: count for status, count in status_rows}

    overdue = (
        await db.execute(
            select(func.count())
            .select_from(base)
            .where(
                base.c.deadline.is_not(None),
                base.c.deadline < at,
                base.c.status.not_in(TERMINAL_STATUSES),
            )
        )
    ).scalar_one()

    # Open slots with nobody on the hook. Terminal statuses are excluded because
    # a published post with no assignee is finished work, not a staffing gap.
    unassigned = (
        await db.execute(
            select(func.count())
            .select_from(base)
            .where(
                base.c.assigned_to.is_(None),
                base.c.status.not_in(TERMINAL_STATUSES),
            )
        )
    ).scalar_one()

    # "This week" = the next seven local days, not an ISO week: the question the
    # card answers is "what is coming up", which does not reset on Saturday.
    today_local = at.astimezone(CALENDAR_TZ).date()
    week_start, week_end = _local_range_bounds(today_local, today_local + timedelta(days=6))
    due_this_week = (
        await db.execute(
            select(func.count())
            .select_from(base)
            .where(
                base.c.scheduled_for >= week_start,
                base.c.scheduled_for < week_end,
                base.c.status.not_in(TERMINAL_STATUSES),
            )
        )
    ).scalar_one()

    # The vocabulary is iterated rather than the query result, so a status with
    # zero rows still reports 0 instead of going missing from the response and
    # forcing the frontend to guess whether a key is absent or genuinely empty.
    return {
        "by_status": {status: by_status.get(status, 0) for status in CALENDAR_ENTRY_STATUSES},
        "overdue": overdue,
        "due_this_week": due_this_week,
        "unassigned": unassigned,
    }


# -------------------------------------------------------------- auto-scheduling

async def auto_schedule_from_opportunities(
    db: AsyncSession,
    *,
    org_id: UUID,
    website_id: UUID,
    max_entries: int = 10,
    start_from: datetime | None = None,
    day_step: int = AUTO_SCHEDULE_DAY_STEP,
    min_priority_score: int = 0,
) -> dict:
    """Turn the highest-impact open opportunities into planned slots.

    Idempotent on the *finding*, not the row: a slot blocks both its
    `opportunity_id` and that opportunity's `fingerprint` (type + subject hash),
    so a re-detected finding — new row, same subject — is never re-scheduled.
    Includes soft-deleted entries on purpose: a plan the user deleted stays
    declined instead of being re-proposed on the next click.

    Slots are spaced `day_step` days apart at 10:00 Tehran time so a burst of
    detections becomes a publishing cadence instead of twenty posts on one day.
    Each run schedules at most `max_entries` opportunities; the ones it could
    not (or did not) schedule are reported back so the caller can show the user
    exactly why nothing was added. When the site already holds at least
    `max_entries` outstanding AI slots (planned/in_progress, not deleted), the
    run creates nothing (`throttled: true`): repeated clicks must read as a
    no-op, not as a flood of the next-best findings.
    """
    await _assert_website_in_org(db, website_id, org_id)
    if max_entries < 1:
        raise ValidationError("max_entries must be at least 1")
    if day_step < 1:
        raise ValidationError("day_step must be at least 1")

    # Deliberately includes soft-deleted rows: a declined plan should stay
    # declined rather than being re-proposed on the next run.
    taken_ids: set[UUID] = set(
        (
            await db.execute(
                select(ContentCalendarEntry.opportunity_id).where(
                    ContentCalendarEntry.website_id == website_id,
                    ContentCalendarEntry.opportunity_id.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )

    # Fingerprints of everything ever scheduled on this site. Matching on the
    # fingerprint (not the row id) is what stops the same finding from coming
    # back after the detector re-creates its Opportunity row with a new id.
    taken_fingerprints: set[str] = set()
    if taken_ids:
        fp_rows = await db.execute(
            select(Opportunity.fingerprint).where(Opportunity.id.in_(taken_ids))
        )
        taken_fingerprints = {fp for fp in fp_rows.scalars().all() if fp}

    # Flood guard: outstanding AI slots the user has not finished yet. Without
    # this, every extra click schedules the *next* max_entries open findings,
    # which reads as "the button spams the calendar with more of the same".
    outstanding = (
        await db.execute(
            select(func.count())
            .select_from(ContentCalendarEntry)
            .where(
                ContentCalendarEntry.website_id == website_id,
                ContentCalendarEntry.deleted_at.is_(None),
                ContentCalendarEntry.source == "ai_auto",
                ContentCalendarEntry.status.in_(("planned", "in_progress")),
            )
        )
    ).scalar_one()
    if outstanding >= max_entries:
        return {
            "created": 0,
            "skipped_existing": len(taken_ids),
            "remaining_open": 0,
            "throttled": True,
            "entries": [],
        }

    # Opportunity is a plain BaseModel with no SoftDeleteMixin: dismissal is
    # recorded as status/dismissed_at, so there is no deleted_at to filter on.
    opp_stmt = (
        select(Opportunity)
        .where(
            Opportunity.website_id == website_id,
            Opportunity.status == "open",
        )
        .order_by(
            Opportunity.priority_score.desc(),
            Opportunity.created_at.desc(),
        )
    )
    open_opps = (await db.execute(opp_stmt)).scalars().all()

    candidates = [
        opp
        for opp in open_opps
        if opp.id not in taken_ids
        and (opp.fingerprint or "") not in taken_fingerprints
        and (opp.priority_score or 0) >= min_priority_score
    ][:max_entries]
    # Every open opportunity still without a slot after this run — reported so
    # the UI can tell "nothing to do" apart from "silently dropped".
    remaining_open = len(
        [
            opp
            for opp in open_opps
            if opp.id not in taken_ids and (opp.fingerprint or "") not in taken_fingerprints
        ]
    )
    skipped_existing = len(open_opps) - remaining_open

    # Default start is tomorrow local: scheduling the first slot for today would
    # hand someone a deadline that has already partly elapsed.
    if start_from is not None:
        anchor = start_from if start_from.tzinfo else start_from.replace(tzinfo=timezone.utc)
        base_day = anchor.astimezone(CALENDAR_TZ).date()
    else:
        base_day = _now().astimezone(CALENDAR_TZ).date() + timedelta(days=1)
    created: list[ContentCalendarEntry] = []

    for index, opp in enumerate(candidates):
        # 10:00 local, converted to UTC for storage.
        slot_local = datetime.combine(
            base_day + timedelta(days=index * day_step),
            time(hour=10),
            tzinfo=CALENDAR_TZ,
        )
        scheduled_for = slot_local.astimezone(timezone.utc)
        row = ContentCalendarEntry(
            organization_id=org_id,
            website_id=website_id,
            title=opp.title,
            status="planned",
            priority=_priority_from_score(opp.priority_score),
            scheduled_for=scheduled_for,
            # One working day of slack before the publish date.
            deadline=scheduled_for - timedelta(days=1),
            # Opportunity has no target_keyword column; `query` is the search term
            # the detector found, which is the same thing this slot should target.
            target_keyword=opp.query,
            opportunity_id=opp.id,
            source="ai_auto",
            notes=opp.recommended_action,
            details={
                "opportunity_type": opp.opportunity_type,
                "opportunity_fingerprint": opp.fingerprint,
                "priority_score": opp.priority_score,
                "estimated_traffic_gain": opp.estimated_traffic_gain,
                "page_url": opp.page_url,
            },
        )
        try:
            async with db.begin_nested():
                db.add(row)
                await db.flush()
            created.append(row)
        except IntegrityError:
            # Another concurrent request already created a slot for this opportunity
            pass

    # We already flushed inside the loop for successful rows, but this is safe
    # and flushes anything else if needed, or if we had rows outside the try block.
    await db.flush()
    return {
        "created": len(created),
        "skipped_existing": skipped_existing,
        "remaining_open": remaining_open,
        "throttled": False,
        "entries": created,
    }


def _priority_from_score(score: int | None) -> str:
    """Map an opportunity's 0-100 priority score onto the slot vocabulary.

    Thresholds are coarse on purpose — the score is itself an estimate, so four
    buckets carry as much signal as it actually has.
    """
    value = score or 0
    if value >= 80:
        return "urgent"
    if value >= 60:
        return "high"
    if value >= 30:
        # The vocabulary's middle value is "normal", not "medium".
        return "normal"
    return "low"


async def collect_due_reminders(
    db: AsyncSession,
    *,
    lookahead_hours: int = REMINDER_LOOKAHEAD_HOURS,
) -> list[dict]:
    """Slots that are overdue or fall due inside the lookahead window.

    Cross-tenant by design: this is the query a scheduled worker runs for the
    whole instance, so it takes no `org_id`. Each returned row carries its
    `organization_id` and `assigned_to` so the caller can fan notifications out
    per tenant. Read-only — it writes nothing and sends nothing, which keeps the
    "who gets notified" policy in the notification layer where it belongs.
    """
    at = _now()
    horizon = at + timedelta(hours=lookahead_hours)

    stmt = (
        select(ContentCalendarEntry)
        .join(Website, Website.id == ContentCalendarEntry.website_id)
        .where(
            ContentCalendarEntry.deleted_at.is_(None),
            Website.deleted_at.is_(None),
            ContentCalendarEntry.deadline.is_not(None),
            ContentCalendarEntry.deadline < horizon,
            ContentCalendarEntry.status.not_in(TERMINAL_STATUSES),
        )
        .order_by(ContentCalendarEntry.deadline.asc())
    )
    rows = list((await db.execute(stmt)).scalars().all())

    return [
        {
            "entry_id": row.id,
            "organization_id": row.organization_id,
            "website_id": row.website_id,
            "title": row.title,
            "status": row.status,
            "priority": row.priority,
            "deadline": row.deadline,
            "assigned_to": row.assigned_to,
            "is_overdue": _is_overdue(row, at),
        }
        for row in rows
    ]
