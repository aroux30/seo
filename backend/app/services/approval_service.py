"""Approval queue service.

The gate this module implements is only as strong as its transitions, so the
rules live here rather than in the router:

* **Only `pending` can be decided.** Every mutation re-reads the row inside the
  transaction with `SELECT ... FOR UPDATE` and re-checks the status. Without the
  lock, two reviewers hitting Approve simultaneously would both read `pending`
  and both write a decision; the second would silently overwrite the first and
  the execution side would run once per write.
* **A requester cannot approve their own request.** That is the entire point of
  the queue. `reviewer` (20) is enough rank to decide, but self-approval is
  refused regardless of rank — an owner asking for a bulk delete still needs a
  second pair of eyes.
* **`payload` is frozen at creation.** Nothing in this module writes to it after
  the insert, so the action a reviewer approves is the action that was queued.

`expires_at` is enforced lazily. A request whose deadline has passed is treated
as rejected on read (`_is_expired`) and swept to `rejected` by
`expire_overdue()` from the Celery beat. Enforcing it only in the sweep would
leave a window where a stale request is still approvable; enforcing it only on
read would leave rows pending forever in the list counts.
"""

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import ROLE_HIERARCHY
from app.models import (
    ApprovalRequest,
    OrganizationMember,
    User,
    Website,
)
from app.models.approvals import (
    APPROVAL_ACTION_TYPES,
    APPROVAL_PRIORITIES,
    APPROVAL_RISK_LEVELS,
)

# Rank that may cancel someone else's request. The requester can always cancel
# their own; anyone below this cannot touch a colleague's.
MIN_CANCEL_OTHERS_ROLE = "admin"

logger = logging.getLogger(__name__)

# Statuses that still occupy the queue. Used by the dedup check and the summary.
OPEN_STATUSES = ("pending",)

# Rank required to decide on a request. Kept here (not in the router) so the
# self-approval rule and the rank rule cannot drift apart.
MIN_REVIEWER_ROLE = "reviewer"

# How close to `expires_at` counts as "expiring soon" on the summary card.
EXPIRING_SOON_HOURS = 24


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(row: ApprovalRequest, at: datetime | None = None) -> bool:
    """True when a still-pending request has passed its deadline."""
    if row.status != "pending" or row.expires_at is None:
        return False
    return row.expires_at <= (at or _now())


# ------------------------------------------------------------------ create

async def create_approval_request(
    db: AsyncSession,
    *,
    organization_id: UUID,
    requester_id: UUID,
    action_type: str,
    title: str,
    description: str | None = None,
    website_id: UUID | None = None,
    reviewer_id: UUID | None = None,
    priority: str = "normal",
    risk_level: str = "medium",
    affected_items_count: int = 1,
    payload: dict | None = None,
    expires_in_hours: int | None = None,
    related_article_id: UUID | None = None,
    related_brief_id: UUID | None = None,
) -> ApprovalRequest:
    """Queue a request. Refuses a duplicate of an already-pending action.

    The vocabulary is re-validated here even though the pydantic schema already
    did it, because services are also called from workers and from other
    services where no schema was involved.
    """
    if action_type not in APPROVAL_ACTION_TYPES:
        raise ForbiddenError(f"Unknown action_type '{action_type}'")
    if priority not in APPROVAL_PRIORITIES:
        raise ForbiddenError(f"Unknown priority '{priority}'")
    if risk_level not in APPROVAL_RISK_LEVELS:
        raise ForbiddenError(f"Unknown risk_level '{risk_level}'")

    # A named reviewer must actually be a member of this org with enough rank,
    # otherwise the request is addressed to someone who can never act on it and
    # sits pending until it expires.
    if reviewer_id is not None:
        await _assert_can_be_reviewer(db, organization_id, reviewer_id)

    await _assert_no_duplicate_pending(
        db,
        organization_id=organization_id,
        website_id=website_id,
        action_type=action_type,
        related_article_id=related_article_id,
    )

    expires_at = (
        _now() + timedelta(hours=expires_in_hours)
        if expires_in_hours is not None
        else None
    )

    row = ApprovalRequest(
        organization_id=organization_id,
        website_id=website_id,
        action_type=action_type,
        status="pending",
        priority=priority,
        title=title,
        description=description,
        requester_id=requester_id,
        reviewer_id=reviewer_id,
        payload=payload or {},
        risk_level=risk_level,
        affected_items_count=affected_items_count,
        expires_at=expires_at,
        related_article_id=related_article_id,
        related_brief_id=related_brief_id,
    )
    db.add(row)
    await db.flush()
    logger.info(
        "[approvals] queued %s (%s/%s) for org %s by %s",
        row.id, action_type, risk_level, organization_id, requester_id,
    )
    return row


async def _assert_can_be_reviewer(
    db: AsyncSession, organization_id: UUID, user_id: UUID
) -> OrganizationMember:
    """The named reviewer must be a member of this org with reviewer+ rank."""
    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user_id,
        )
    )
    member = result.scalar_one_or_none()
    # 404 not 403: an id that is not in this org must not be distinguishable
    # from one that does not exist (no cross-tenant user enumeration).
    if not member:
        raise NotFoundError("User", str(user_id))
    if ROLE_HIERARCHY.get(member.role, 0) < ROLE_HIERARCHY[MIN_REVIEWER_ROLE]:
        raise ForbiddenError(
            f"Role '{member.role}' cannot be assigned as an approval reviewer"
        )
    return member


async def _assert_no_duplicate_pending(
    db: AsyncSession,
    *,
    organization_id: UUID,
    website_id: UUID | None,
    action_type: str,
    related_article_id: UUID | None,
) -> None:
    """Refuse a second pending request for the same subject.

    Enforced in the service rather than as a unique index: the constraint is
    "one *pending* row per subject", and a plain unique index would also block
    re-requesting after a rejection, which is legitimate.
    """
    stmt = select(ApprovalRequest.id).where(
        ApprovalRequest.organization_id == organization_id,
        ApprovalRequest.action_type == action_type,
        ApprovalRequest.status.in_(OPEN_STATUSES),
    )
    stmt = (
        stmt.where(ApprovalRequest.website_id == website_id)
        if website_id is not None
        else stmt.where(ApprovalRequest.website_id.is_(None))
    )
    stmt = (
        stmt.where(ApprovalRequest.related_article_id == related_article_id)
        if related_article_id is not None
        else stmt.where(ApprovalRequest.related_article_id.is_(None))
    )

    existing = (await db.execute(stmt.limit(1))).scalar_one_or_none()
    if existing:
        raise ConflictError(
            f"A pending '{action_type}' approval request already exists for this subject"
        )


# -------------------------------------------------------------------- read

async def get_approval_request(
    db: AsyncSession, approval_id: UUID, organization_id: UUID
) -> ApprovalRequest:
    """Fetch one request, scoped to the caller's organization.

    404 rather than 403 on a cross-tenant id, matching `app.core.scoping`.
    """
    result = await db.execute(
        select(ApprovalRequest).where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.organization_id == organization_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise NotFoundError("ApprovalRequest", str(approval_id))
    return row


def _with_names(base: Select) -> Select:
    """Join requester / reviewer / decider / website for the list view.

    Three aliases of `users` are needed because one row can reference three
    different people. Outer joins throughout: reviewer_id and decided_by are
    null on a fresh pending row, and an inner join would hide it.
    """
    requester = aliased(User)
    reviewer = aliased(User)
    decider = aliased(User)
    return (
        base.add_columns(
            requester.full_name.label("requester_name"),
            requester.email.label("requester_email"),
            reviewer.full_name.label("reviewer_name"),
            decider.full_name.label("decided_by_name"),
            Website.name.label("website_name"),
        )
        .outerjoin(requester, requester.id == ApprovalRequest.requester_id)
        .outerjoin(reviewer, reviewer.id == ApprovalRequest.reviewer_id)
        .outerjoin(decider, decider.id == ApprovalRequest.decided_by)
        .outerjoin(Website, Website.id == ApprovalRequest.website_id)
    )


async def list_approval_requests(
    db: AsyncSession,
    *,
    organization_id: UUID,
    website_id: UUID | None = None,
    status: str | None = None,
    action_type: str | None = None,
    priority: str | None = None,
    mine_only_user_id: UUID | None = None,
    assigned_to_user_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List requests for the org, newest first, with display names resolved.

    Returns dicts (not ORM rows) because the joined names are not model columns;
    `ApprovalReadWithNames.model_validate` consumes them directly.
    """
    stmt = _with_names(select(ApprovalRequest)).where(
        ApprovalRequest.organization_id == organization_id
    )

    if website_id is not None:
        stmt = stmt.where(ApprovalRequest.website_id == website_id)
    if status:
        stmt = stmt.where(ApprovalRequest.status == status)
    if action_type:
        stmt = stmt.where(ApprovalRequest.action_type == action_type)
    if priority:
        stmt = stmt.where(ApprovalRequest.priority == priority)
    if mine_only_user_id is not None:
        stmt = stmt.where(ApprovalRequest.requester_id == mine_only_user_id)
    if assigned_to_user_id is not None:
        # Unassigned requests are open to any reviewer, so "assigned to me"
        # includes them — otherwise the reviewer's own queue looks empty while
        # unclaimed work piles up.
        stmt = stmt.where(
            (ApprovalRequest.reviewer_id == assigned_to_user_id)
            | (ApprovalRequest.reviewer_id.is_(None))
        )

    # Urgent first, then newest. `priority` is a string, so the ordering is
    # spelled out rather than alphabetical (which would put "high" before
    # "urgent" and "low" before "normal").
    priority_rank = case(
        (ApprovalRequest.priority == "urgent", 0),
        (ApprovalRequest.priority == "high", 1),
        (ApprovalRequest.priority == "normal", 2),
        (ApprovalRequest.priority == "low", 3),
        else_=99,
    )
    stmt = stmt.order_by(priority_rank, ApprovalRequest.created_at.desc())
    stmt = stmt.limit(limit).offset(offset)

    result = await db.execute(stmt)
    rows: list[dict] = []
    for row in result.all():
        obj: ApprovalRequest = row[0]
        data = {
            c.name: getattr(obj, c.name) for c in obj.__table__.columns
        }
        data.update({
            "requester_name": row.requester_name,
            "requester_email": row.requester_email,
            "reviewer_name": row.reviewer_name,
            "decided_by_name": row.decided_by_name,
            "website_name": row.website_name,
        })
        rows.append(data)
    return rows


# ----------------------------------------------------------------- decisions

async def _lock_pending(
    db: AsyncSession, request_id: UUID, organization_id: UUID
) -> ApprovalRequest:
    """Re-read the row under a row lock and prove it is still decidable.

    The lock is the whole point: two reviewers pressing Approve at the same
    instant both read `pending` without it, and both write a decision. The
    second write wins silently and the executor sees one approval per write.
    """
    result = await db.execute(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.id == request_id,
            ApprovalRequest.organization_id == organization_id,
        )
        .with_for_update()
    )
    row = result.scalar_one_or_none()
    if not row:
        raise NotFoundError("ApprovalRequest", str(request_id))

    if row.status != "pending":
        raise ConflictError(
            f"این درخواست قبلاً رسیدگی شده است (وضعیت فعلی: {row.status})"
        )
    if _is_expired(row):
        raise ConflictError("مهلت این درخواست به پایان رسیده و قابل تأیید نیست")
    return row


def _assert_can_decide(
    row: ApprovalRequest, *, user_id: UUID, member_role: str
) -> None:
    """Prove this caller may decide *this* row.

    Two separate rules, both required:

    * Rank. Below `MIN_REVIEWER_ROLE` nobody decides anything, regardless of who
      the request names.
    * Self-approval. A requester may not approve their own request even with
      owner rank — that is the entire point of a gate. Withdrawing is still
      allowed via `cancel_approval_request`.

    A named `reviewer_id` is treated as an assignment, not an exclusive lock: any
    sufficiently ranked member may still act, otherwise a request addressed to
    someone on leave blocks until it expires.
    """
    if ROLE_HIERARCHY.get(member_role, 0) < ROLE_HIERARCHY[MIN_REVIEWER_ROLE]:
        raise ForbiddenError(
            f"Role '{member_role}' cannot decide approval requests"
        )
    if row.requester_id == user_id:
        raise ForbiddenError(
            "درخواست‌دهنده نمی‌تواند درخواست خودش را تأیید یا رد کند"
        )


async def decide_approval_request(
    db: AsyncSession,
    request_id: UUID,
    *,
    organization_id: UUID,
    user_id: UUID,
    member_role: str,
    decision: str,
    reviewer_comment: str | None = None,
) -> ApprovalRequest:
    """Approve or reject a pending request.

    `decision` is already narrowed to {"approved", "rejected"} by
    `ApprovalDecision`, so no vocabulary check is repeated here.
    """
    row = await _lock_pending(db, request_id, organization_id)
    _assert_can_decide(row, user_id=user_id, member_role=member_role)

    now = _now()
    row.status = decision
    row.decided_by = user_id
    row.decided_at = now
    row.reviewer_comment = reviewer_comment
    await db.flush()

    logger.info(
        "[Approvals] %s %s by %s (action=%s)",
        request_id, decision, user_id, row.action_type,
    )
    return row


async def cancel_approval_request(
    db: AsyncSession,
    request_id: UUID,
    *,
    organization_id: UUID,
    user_id: UUID,
    member_role: str,
    reason: str | None = None,
) -> ApprovalRequest:
    """Withdraw a pending request.

    Cancelling is the requester's own escape hatch, so unlike deciding it is
    *not* gated on reviewer rank: the person who asked may always take it back.
    Anyone else needs admin rank, otherwise a peer editor could silently kill
    another editor's queued publish.
    """
    row = await _lock_pending(db, request_id, organization_id)

    if row.requester_id != user_id and ROLE_HIERARCHY.get(
        member_role, 0
    ) < ROLE_HIERARCHY["admin"]:
        raise ForbiddenError(
            "فقط درخواست‌دهنده یا مدیر سازمان می‌تواند این درخواست را لغو کند"
        )

    row.status = "cancelled"
    row.decided_by = user_id
    row.decided_at = _now()
    # Reuse `reviewer_comment` for the cancellation reason rather than adding a
    # column: both are "the free-text note attached to the terminal decision",
    # and the status already says which of the two it is.
    if reason:
        row.reviewer_comment = reason
    await db.flush()

    logger.info("[Approvals] %s cancelled by %s", request_id, user_id)
    return row


# ---------------------------------------------------------------- execution

async def record_execution_result(
    db: AsyncSession,
    request_id: UUID,
    *,
    organization_id: UUID,
    success: bool,
    result: dict | None = None,
    error: str | None = None,
) -> ApprovalRequest:
    """Close the loop after the approved task ran.

    Called by workers, not by a router: there is no rank check here because
    there is no user. Only an `approved` row may move on — a pending row
    reaching this function means a task executed before its gate opened, which
    is a bug worth surfacing rather than recording silently.
    """
    row = await get_approval_request(db, request_id, organization_id)

    if row.status != "approved":
        raise ConflictError(
            f"Cannot record execution for a request in status '{row.status}'"
        )

    row.status = "executed" if success else "failed"
    row.executed_at = _now()
    row.execution_result = result
    row.execution_error = None if success else (error or "Unknown error")
    await db.flush()

    logger.info(
        "[Approvals] %s execution %s", request_id, "succeeded" if success else "failed"
    )
    return row


# ------------------------------------------------------------------ summary

async def get_approval_summary(
    db: AsyncSession, organization_id: UUID
) -> dict:
    """Queue counters for the org, in one round trip.

    Everything is computed as conditional aggregates over a single scan instead
    of one query per counter: the summary is polled by the header badge, so it
    runs far more often than any other approval query.

    Expiry is evaluated against the clock, not against `status`, because rows
    are only flipped to expired by the periodic sweep — between two sweeps a
    row can be past its deadline while still stored as `pending`. Counting it
    as pending would show reviewers work they cannot act on.
    """
    now = _now()
    soon = now + timedelta(hours=EXPIRING_SOON_HOURS)

    still_open = (ApprovalRequest.status == "pending") & (
        (ApprovalRequest.expires_at.is_(None)) | (ApprovalRequest.expires_at > now)
    )

    result = await db.execute(
        select(
            func.count().filter(still_open).label("pending"),
            func.count()
            .filter(still_open & (ApprovalRequest.priority == "urgent"))
            .label("pending_urgent"),
            func.count()
            .filter(
                still_open & ApprovalRequest.risk_level.in_(("high", "critical"))
            )
            .label("pending_high_risk"),
            func.count()
            .filter(ApprovalRequest.status == "approved")
            .label("approved_awaiting_execution"),
            func.count()
            .filter(
                still_open
                & ApprovalRequest.expires_at.is_not(None)
                & (ApprovalRequest.expires_at <= soon)
            )
            .label("expiring_soon"),
        ).where(ApprovalRequest.organization_id == organization_id)
    )
    counts = result.one()

    # Breakdowns stay separate: they are grouped rows, not scalars, so they
    # cannot share the aggregate query above.
    by_action = await db.execute(
        select(ApprovalRequest.action_type, func.count())
        .where(ApprovalRequest.organization_id == organization_id)
        .where(still_open)
        .group_by(ApprovalRequest.action_type)
    )
    by_priority = await db.execute(
        select(ApprovalRequest.priority, func.count())
        .where(ApprovalRequest.organization_id == organization_id)
        .where(still_open)
        .group_by(ApprovalRequest.priority)
    )

    return {
        "pending": counts.pending or 0,
        "pending_urgent": counts.pending_urgent or 0,
        "pending_high_risk": counts.pending_high_risk or 0,
        "approved_awaiting_execution": counts.approved_awaiting_execution or 0,
        "expiring_soon": counts.expiring_soon or 0,
        "by_action_type": {k: v for k, v in by_action.all()},
        "by_priority": {k: v for k, v in by_priority.all()},
    }


# ------------------------------------------------------------------- sweep

async def expire_stale_requests(
    db: AsyncSession, organization_id: UUID | None = None
) -> dict:
    """Flip pending requests past their deadline to `cancelled`.

    `cancelled` rather than a dedicated "expired" status: `APPROVAL_STATUSES`
    has no such member, and widening the vocabulary would need a migration for
    a state that behaves identically to a withdrawal. The comment records why
    it closed, so the audit trail keeps the distinction.

    `organization_id` is optional so the periodic worker can sweep every tenant
    in one pass while a router can still scope the sweep to one org.
    """
    now = _now()
    stmt = select(ApprovalRequest).where(
        ApprovalRequest.status == "pending",
        ApprovalRequest.expires_at.is_not(None),
        ApprovalRequest.expires_at <= now,
    )
    if organization_id is not None:
        stmt = stmt.where(ApprovalRequest.organization_id == organization_id)

    rows = (await db.execute(stmt)).scalars().all()
    for row in rows:
        row.status = "cancelled"
        row.decided_at = now
        row.reviewer_comment = (
            row.reviewer_comment or "به‌صورت خودکار به دلیل پایان مهلت بسته شد"
        )
    await db.flush()

    if rows:
        logger.info("[Approvals] expired %d stale request(s)", len(rows))
    return {"expired": len(rows)}
