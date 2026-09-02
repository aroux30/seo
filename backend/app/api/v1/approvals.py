"""Approval queue endpoints.

A gate in front of irreversible work: publishing, restructuring, and anything an
AI agent decided on its own. The queue is the audit trail — nothing is deleted,
every row keeps who asked, who decided, and what happened when it ran.

Three conventions in here are load-bearing:

* Every read and write is scoped through `approval_service`, which filters on
  `organization_id` and raises 404 (not 403) on a cross-tenant id, so a UUID
  cannot be used as an existence oracle. This platform has leaked across
  tenants once already.
* `user_id` and `member_role` always come from the authenticated membership,
  never from the request body. If a client could supply its own role the rank
  check in `_assert_can_decide` would be decorative.
* Route declaration order matters: FastAPI matches in order, so the literal
  `/summary` path is declared before `/{approval_id}`. Reversed, "summary"
  would be parsed as a UUID and 422.

Role floors: requesting is `editor` (the person doing the work asks), deciding
is `seo_manager` (the service additionally enforces `reviewer`+ and blocks
self-approval), and the expiry sweep is `admin` because it mutates many rows.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models import OrganizationMember
from app.schemas.approvals import (
    ApprovalCancel,
    ApprovalCreate,
    ApprovalDecision,
    ApprovalExpireResult,
    ApprovalRead,
    ApprovalReadWithNames,
    ApprovalSummary,
)
from app.core.scoping import (
    assert_website_in_org,
    assert_article_in_org,
    assert_brief_in_org,
)
from app.services import approval_service

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("", response_model=dict, status_code=201)
async def create_approval_endpoint(
    body: ApprovalCreate,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Queue a request for review.

    `requester_id` is taken from the session, so a member cannot file a request
    in someone else's name and then approve it themselves.
    """
    if body.website_id:
        await assert_website_in_org(db, body.website_id, member.organization_id)
    if body.related_article_id:
        await assert_article_in_org(db, body.related_article_id, member.organization_id)
    if body.related_brief_id:
        await assert_brief_in_org(db, body.related_brief_id, member.organization_id)

    row = await approval_service.create_approval_request(
        db,
        organization_id=member.organization_id,
        requester_id=member.user_id,
        action_type=body.action_type,
        title=body.title,
        description=body.description,
        website_id=body.website_id,
        reviewer_id=body.reviewer_id,
        priority=body.priority,
        risk_level=body.risk_level,
        affected_items_count=body.affected_items_count,
        payload=body.payload,
        expires_in_hours=body.expires_in_hours,
        related_article_id=body.related_article_id,
        related_brief_id=body.related_brief_id,
    )
    await db.commit()
    await db.refresh(row)
    return {"data": ApprovalRead.model_validate(row)}


@router.get("", response_model=dict)
async def list_approvals_endpoint(
    website_id: UUID | None = Query(None),
    status: str | None = Query(None),
    action_type: str | None = Query(None),
    priority: str | None = Query(None),
    mine_only: bool = Query(False, description="Only requests I filed"),
    assigned_to_me: bool = Query(
        False, description="Requests assigned to me, plus unclaimed ones"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """List the organization's queue, urgent first then newest.

    `mine_only` / `assigned_to_me` are booleans rather than user ids: resolving
    them from the session means one member cannot enumerate another's queue.
    """
    rows = await approval_service.list_approval_requests(
        db,
        organization_id=member.organization_id,
        website_id=website_id,
        status=status,
        action_type=action_type,
        priority=priority,
        mine_only_user_id=member.user_id if mine_only else None,
        assigned_to_user_id=member.user_id if assigned_to_me else None,
        limit=limit,
        offset=offset,
    )
    return {"data": [ApprovalReadWithNames.model_validate(r) for r in rows]}


# Declared before /{approval_id}: otherwise "summary" is matched as a UUID.
@router.get("/summary", response_model=dict)
async def approval_summary_endpoint(
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Queue counts for the badge and the dashboard card."""
    summary = await approval_service.get_approval_summary(
        db, member.organization_id
    )
    return {"data": ApprovalSummary.model_validate(summary)}


@router.post("/expire-stale", response_model=dict)
async def expire_stale_approvals_endpoint(
    member: OrganizationMember = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Mark overdue pending requests as expired.

    Also runs on a schedule; exposed here so an operator can clear the queue
    without waiting for the next beat tick.
    """
    result = await approval_service.expire_stale_requests(
        db, member.organization_id
    )
    await db.commit()
    return {"data": ApprovalExpireResult.model_validate(result)}


@router.get("/{approval_id}", response_model=dict)
async def get_approval_endpoint(
    approval_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Get a single request."""
    row = await approval_service.get_approval_request(
        db, approval_id, member.organization_id
    )
    return {"data": ApprovalRead.model_validate(row)}


@router.post("/{approval_id}/decide", response_model=dict)
async def decide_approval_endpoint(
    approval_id: UUID,
    body: ApprovalDecision,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Approve or reject a pending request.

    The service takes a row lock before writing, so two reviewers pressing
    Approve at the same instant cannot both record a decision.
    """
    row = await approval_service.decide_approval_request(
        db,
        approval_id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        member_role=member.role,
        decision=body.decision,
        reviewer_comment=body.reviewer_comment,
    )
    await db.commit()
    await db.refresh(row)
    return {"data": ApprovalRead.model_validate(row)}


@router.post("/{approval_id}/cancel", response_model=dict)
async def cancel_approval_endpoint(
    approval_id: UUID,
    body: ApprovalCancel = ApprovalCancel(),
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Withdraw a pending request.

    Role floor is `editor` because a requester must be able to cancel their own
    work; the service decides whether this particular member may cancel this
    particular row.
    """
    row = await approval_service.cancel_approval_request(
        db,
        approval_id,
        organization_id=member.organization_id,
        user_id=member.user_id,
        member_role=member.role,
        reason=body.reason,
    )
    await db.commit()
    await db.refresh(row)
    return {"data": ApprovalRead.model_validate(row)}
