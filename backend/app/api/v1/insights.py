"""Opportunities / Alerts / Notifications endpoints.

Three routers live in one module because they are one feature: a detector writes
an Opportunity or an Alert, the dispatcher fans it out into Notifications, and
the user closes the loop from the same screen.

Two conventions in here are load-bearing:

* Every path id and every `website_id` query param goes through an `assert_*`
  guard from `app.core.scoping` **before** any data is read or written. The
  guards 404 on a cross-tenant hit so a UUID cannot be used as an existence
  oracle. This platform has already leaked across tenants once.
* Notifications are per-user. The `user_id` always comes from the authenticated
  membership (`member.user_id`), never from a client-supplied parameter —
  otherwise any member could read a colleague's inbox.

Route declaration order matters: FastAPI matches in order, so the literal
`/summary` and `/unread-count` paths are declared before their `/{id}`
siblings. Reversed, "summary" would be parsed as a UUID and 422.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.core.scoping import (
    assert_alert_in_org,
    assert_opportunity_in_org,
    assert_website_in_org,
)
from app.models import OrganizationMember
from app.schemas.insights import (
    AlertDetectRequest,
    AlertDetectResult,
    AlertRead,
    AlertStatusUpdate,
    AlertSummary,
    NotificationMarkReadRequest,
    NotificationMarkReadResult,
    NotificationRead,
    OpportunityDetectRequest,
    OpportunityDetectResult,
    OpportunityRead,
    OpportunityStatusUpdate,
    OpportunitySummary,
    UnreadCountResult,
)
from app.services import alert_service, notification_service, opportunity_service

opportunities_router = APIRouter(prefix="/opportunities", tags=["opportunities"])
alerts_router = APIRouter(prefix="/alerts", tags=["alerts"])
notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])


# =========================================================== opportunities

@opportunities_router.post("/detect", response_model=dict)
async def detect_opportunities_endpoint(
    website_id: UUID = Query(...),
    body: OpportunityDetectRequest = OpportunityDetectRequest(),
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Run every opportunity detector for a website and upsert the findings."""
    await assert_website_in_org(db, website_id, member.organization_id)
    result = await opportunity_service.detect_opportunities(
        db,
        website_id,
        lookback_days=body.lookback_days,
        min_impressions=body.min_impressions,
    )
    await db.commit()
    return {"data": OpportunityDetectResult.model_validate(result)}


@opportunities_router.get("", response_model=dict)
async def list_opportunities_endpoint(
    website_id: UUID = Query(...),
    status: str | None = Query(None),
    opportunity_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """List detected opportunities for a website, highest priority first."""
    await assert_website_in_org(db, website_id, member.organization_id)
    rows = await opportunity_service.list_opportunities(
        db,
        website_id,
        status=status,
        opportunity_type=opportunity_type,
        limit=limit,
        offset=offset,
    )
    return {"data": [OpportunityRead.model_validate(r) for r in rows]}


# Declared before /{opportunity_id}: otherwise "summary" is matched as a UUID.
@opportunities_router.get("/summary", response_model=dict)
async def opportunity_summary_endpoint(
    website_id: UUID = Query(...),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Open-opportunity counts, estimated gain and the top findings."""
    await assert_website_in_org(db, website_id, member.organization_id)
    summary = await opportunity_service.get_opportunity_summary(db, website_id)
    return {"data": OpportunitySummary.model_validate(summary)}


@opportunities_router.get("/{opportunity_id}", response_model=dict)
async def get_opportunity_endpoint(
    opportunity_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single opportunity."""
    opportunity = await assert_opportunity_in_org(
        db, opportunity_id, member.organization_id
    )
    return {"data": OpportunityRead.model_validate(opportunity)}


@opportunities_router.patch("/{opportunity_id}/status", response_model=dict)
async def update_opportunity_status_endpoint(
    opportunity_id: UUID,
    body: OpportunityStatusUpdate,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Move an opportunity along its lifecycle (in progress, actioned, dismissed)."""
    opportunity = await assert_opportunity_in_org(
        db, opportunity_id, member.organization_id
    )
    updated = await opportunity_service.update_opportunity_status(
        db,
        opportunity,
        body.status,
        user_id=member.user_id,
        dismiss_reason=body.dismiss_reason,
    )
    await db.commit()
    return {"data": OpportunityRead.model_validate(updated)}


# ================================================================== alerts

@alerts_router.post("/detect", response_model=dict)
async def detect_alerts_endpoint(
    website_id: UUID = Query(...),
    body: AlertDetectRequest = AlertDetectRequest(),
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Run every alert detector for a website, comparing window over window."""
    await assert_website_in_org(db, website_id, member.organization_id)
    result = await alert_service.detect_alerts(
        db,
        website_id,
        window_days=body.window_days,
        drop_threshold_percent=body.drop_threshold_percent,
    )
    await db.commit()
    return {"data": AlertDetectResult.model_validate(result)}


@alerts_router.get("", response_model=dict)
async def list_alerts_endpoint(
    website_id: UUID | None = Query(None),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """List alerts for one website, or across the caller's whole organization.

    Without `website_id` the list is scoped to `member.organization_id`; the
    organization filter is applied in both branches so a website-scoped call
    cannot widen past the caller's tenant either.
    """
    if website_id is not None:
        await assert_website_in_org(db, website_id, member.organization_id)
    rows = await alert_service.list_alerts(
        db,
        website_id=website_id,
        organization_id=member.organization_id,
        status=status,
        severity=severity,
        limit=limit,
        offset=offset,
    )
    return {"data": [AlertRead.model_validate(r) for r in rows]}


# Declared before /{alert_id}: otherwise "summary" is matched as a UUID.
@alerts_router.get("/summary", response_model=dict)
async def alert_summary_endpoint(
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Active-alert counts by severity for the caller's organization."""
    summary = await alert_service.get_alert_summary(db, member.organization_id)
    return {"data": AlertSummary.model_validate(summary)}


@alerts_router.get("/{alert_id}", response_model=dict)
async def get_alert_endpoint(
    alert_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single alert."""
    alert = await assert_alert_in_org(db, alert_id, member.organization_id)
    return {"data": AlertRead.model_validate(alert)}


@alerts_router.patch("/{alert_id}/status", response_model=dict)
async def update_alert_status_endpoint(
    alert_id: UUID,
    body: AlertStatusUpdate,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Acknowledge, resolve, mute or reopen an alert."""
    alert = await assert_alert_in_org(db, alert_id, member.organization_id)
    updated = await alert_service.update_alert_status(
        db,
        alert,
        body.status,
        user_id=member.user_id,
        resolution_note=body.resolution_note,
        mute_hours=body.mute_hours,
    )
    await db.commit()
    return {"data": AlertRead.model_validate(updated)}


# =========================================================== notifications
# No scoping guard is needed here because nothing is addressed by a client id:
# both organization_id and user_id come from the resolved membership.

@notifications_router.get("", response_model=dict)
async def list_notifications_endpoint(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """List the caller's own notifications."""
    rows = await notification_service.list_notifications(
        db,
        organization_id=member.organization_id,
        user_id=member.user_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return {"data": [NotificationRead.model_validate(r) for r in rows]}


# Declared before any /{...} sibling so "unread-count" is never parsed as an id.
@notifications_router.get("/unread-count", response_model=dict)
async def unread_count_endpoint(
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Unread notification count for the caller, for the header badge."""
    unread = await notification_service.count_unread(
        db,
        organization_id=member.organization_id,
        user_id=member.user_id,
    )
    return {"data": UnreadCountResult(unread=unread)}


@notifications_router.post("/mark-read", response_model=dict)
async def mark_notifications_read_endpoint(
    body: NotificationMarkReadRequest = NotificationMarkReadRequest(),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Mark specific notifications read, or all of the caller's when the body is empty.

    The service filters on the caller's own user_id, so ids belonging to another
    user are silently not matched rather than mutated.
    """
    marked = await notification_service.mark_read(
        db,
        organization_id=member.organization_id,
        user_id=member.user_id,
        notification_ids=body.notification_ids,
    )
    await db.commit()
    return {"data": NotificationMarkReadResult(marked=marked)}
