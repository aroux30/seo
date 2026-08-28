"""Content calendar endpoints — slots, grid views, board, and the AI scheduler.

Conventions carried over from `internal_links.py` and `categories.py`, all
load-bearing:

* Every `website_id` query param goes through `assert_website_in_org` **before**
  any read or write. Path ids (`entry_id`) are scoped inside the service with an
  explicit `organization_id` filter that raises NotFoundError (404, never 403),
  so a UUID cannot be used as an existence oracle.
* Route declaration order matters: FastAPI matches in order, so the literal
  `/month`, `/week`, `/board`, `/summary` and `/auto-schedule` are all declared
  **before** `/{entry_id}`. Reversed, "summary" would be parsed as a UUID and
  the request would 422.
* Services flush; routers commit. Every mutating endpoint below ends with
  `await db.commit()`.

Two shape adaptations happen here rather than in the service, because they are
presentation concerns:

* `website_id` is required on the month/week views. The service tolerates
  `None` (org-wide), but `CalendarMonthView.website_id` is a non-optional UUID —
  a grid is always drawn for one site.
* `auto_schedule_from_opportunities` returns `skipped_existing` and the created
  ORM rows; `CalendarAutoScheduleResult` wants `skipped` and a single
  `scheduled_through` timestamp. The last slot's date is derived here.
"""

from datetime import date as date_cls
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scoping import assert_website_in_org
from app.database import get_db
from app.dependencies import require_role
from app.models import OrganizationMember
from app.schemas.calendar import (
    CalendarAutoScheduleRequest,
    CalendarAutoScheduleResult,
    CalendarBoardView,
    CalendarEntryCreate,
    CalendarEntryMove,
    CalendarEntryRead,
    CalendarEntryUpdate,
    CalendarMonthView,
    CalendarSummary,
    CalendarWeekView,
)
from app.services import calendar_service

router = APIRouter(prefix="/calendar", tags=["content calendar"])


# ------------------------------------------------------------------------ writes

@router.post("", response_model=dict, status_code=201)
async def create_entry_endpoint(
    body: CalendarEntryCreate,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Plan a new slot on the calendar.

    `source` is not accepted from the client — the service forces "manual" so a
    hand-made slot cannot impersonate an AI-scheduled one and get skipped by the
    scheduler's dedup check.
    """
    await assert_website_in_org(db, body.website_id, member.organization_id)
    row = await calendar_service.create_entry(
        db,
        org_id=member.organization_id,
        website_id=body.website_id,
        title=body.title,
        brief_id=body.brief_id,
        article_id=body.article_id,
        opportunity_id=body.opportunity_id,
        status=body.status,
        priority=body.priority,
        scheduled_for=body.scheduled_for,
        deadline=body.deadline,
        assigned_to=body.assigned_to,
        target_keyword=body.target_keyword,
        notes=body.notes,
        details=body.details,
    )
    await db.commit()
    await db.refresh(row)
    return {"data": CalendarEntryRead.model_validate(row)}


# ------------------------------------------------------------------------- reads

@router.get("", response_model=dict)
async def list_entries_endpoint(
    website_id: UUID | None = Query(None),
    status: str | None = Query(None),
    priority: str | None = Query(None),
    assigned_to: UUID | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    overdue_only: bool = Query(False),
    unscheduled_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Filtered slot list plus the total, for the table view and the backlog.

    `website_id` is optional here (unlike the grid views): the list doubles as an
    org-wide "everything assigned to me" queue.
    """
    if website_id is not None:
        await assert_website_in_org(db, website_id, member.organization_id)
    rows, total = await calendar_service.list_entries(
        db,
        org_id=member.organization_id,
        website_id=website_id,
        status=status,
        priority=priority,
        assigned_to=assigned_to,
        date_from=date_from,
        date_to=date_to,
        overdue_only=overdue_only,
        unscheduled_only=unscheduled_only,
        limit=limit,
        offset=offset,
    )
    return {
        "data": [CalendarEntryRead.model_validate(r) for r in rows],
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


# Literal paths below are declared before /{entry_id} — see module docstring.

@router.get("/month", response_model=dict)
async def month_view_endpoint(
    website_id: UUID = Query(...),
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """One Tehran calendar month, bucketed by local day (empty days included)."""
    await assert_website_in_org(db, website_id, member.organization_id)
    view = await calendar_service.get_month_view(
        db,
        org_id=member.organization_id,
        year=year,
        month=month,
        website_id=website_id,
    )
    return {"data": CalendarMonthView.model_validate(view)}


@router.get("/week", response_model=dict)
async def week_view_endpoint(
    website_id: UUID = Query(...),
    start_date: date_cls = Query(...),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Seven local days starting at `start_date`, fixed seven buckets."""
    await assert_website_in_org(db, website_id, member.organization_id)
    view = await calendar_service.get_week_view(
        db,
        org_id=member.organization_id,
        start_date=start_date,
        website_id=website_id,
    )
    # The service leaves website_id as passed in; the schema requires it.
    view["website_id"] = website_id
    return {"data": CalendarWeekView.model_validate(view)}


@router.get("/board", response_model=dict)
async def board_view_endpoint(
    website_id: UUID | None = Query(None),
    limit_per_column: int = Query(100, ge=1, le=200),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Kanban columns in canonical status order, empty columns included."""
    if website_id is not None:
        await assert_website_in_org(db, website_id, member.organization_id)
    view = await calendar_service.get_board_view(
        db,
        org_id=member.organization_id,
        website_id=website_id,
        limit_per_column=limit_per_column,
    )
    return {"data": CalendarBoardView.model_validate(view)}


@router.get("/summary", response_model=dict)
async def summary_endpoint(
    website_id: UUID | None = Query(None),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Counters for the dashboard card: by status, overdue, due this week, unassigned."""
    if website_id is not None:
        await assert_website_in_org(db, website_id, member.organization_id)
    summary = await calendar_service.get_calendar_summary(
        db,
        org_id=member.organization_id,
        website_id=website_id,
    )
    return {"data": CalendarSummary.model_validate(summary)}


@router.post("/auto-schedule", response_model=dict)
async def auto_schedule_endpoint(
    website_id: UUID = Query(...),
    body: CalendarAutoScheduleRequest = CalendarAutoScheduleRequest(),
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Turn the highest-impact open opportunities into planned slots.

    Idempotent on `opportunity_id`, so re-running it cannot double-book the same
    opportunity. Requires seo_manager: it writes a publishing plan, which is a
    heavier act than editing a single slot.
    """
    await assert_website_in_org(db, website_id, member.organization_id)
    result = await calendar_service.auto_schedule_from_opportunities(
        db,
        org_id=member.organization_id,
        website_id=website_id,
        max_entries=body.max_entries,
        start_from=body.start_from,
    )
    await db.commit()

    # The service returns the created rows; the schema wants the far edge of the
    # plan it just laid down.
    created_rows = result.get("entries") or []
    scheduled_dates = [r.scheduled_for for r in created_rows if r.scheduled_for]
    return {
        "data": CalendarAutoScheduleResult(
            website_id=website_id,
            created=result.get("created", 0),
            skipped=result.get("skipped_existing", 0),
            scheduled_through=max(scheduled_dates) if scheduled_dates else None,
        )
    }


@router.get("/{entry_id}", response_model=dict)
async def get_entry_endpoint(
    entry_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """One slot. 404 (not 403) on a cross-tenant id."""
    row = await calendar_service.get_entry(db, entry_id, member.organization_id)
    return {"data": CalendarEntryRead.model_validate(row)}


@router.patch("/{entry_id}", response_model=dict)
async def update_entry_endpoint(
    entry_id: UUID,
    body: CalendarEntryUpdate,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Partial edit.

    `exclude_unset` is what makes the PATCH partial: without it, every field the
    client omitted would arrive as None and blank out the row.
    """
    row = await calendar_service.update_entry(
        db,
        entry_id,
        member.organization_id,
        changes=body.model_dump(exclude_unset=True),
    )
    await db.commit()
    await db.refresh(row)
    return {"data": CalendarEntryRead.model_validate(row)}


@router.post("/{entry_id}/move", response_model=dict)
async def move_entry_endpoint(
    entry_id: UUID,
    body: CalendarEntryMove,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Drag-and-drop: reschedule and/or change column, nothing else.

    Deliberately narrower than PATCH so a drag cannot carry along stale form
    fields from the client.
    """
    row = await calendar_service.move_entry(
        db,
        entry_id,
        member.organization_id,
        scheduled_for=body.scheduled_for,
        status=body.status,
    )
    await db.commit()
    await db.refresh(row)
    return {"data": CalendarEntryRead.model_validate(row)}


@router.delete("/{entry_id}", response_model=dict)
async def delete_entry_endpoint(
    entry_id: UUID,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a slot.

    Soft rather than hard so a cancelled plan stays auditable and the
    auto-scheduler still sees that this opportunity was once planned and declined.
    """
    await calendar_service.delete_entry(db, entry_id, member.organization_id)
    await db.commit()
    return {"data": {"deleted": True, "id": str(entry_id)}}
