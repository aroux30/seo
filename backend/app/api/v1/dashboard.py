"""Dashboard aggregation endpoint.

One endpoint, one round trip: the dashboard home needs website counts, traffic
totals, alert and opportunity badges, and content status all at once, and firing
eight requests to build one screen was making the page feel broken on slow
connections.

No scoping guard is called here on purpose. `assert_org_matches` exists for
endpoints that take an `{org_id}` path param, where the role check would pass
against the caller's own membership while the service read someone else's org.
This endpoint has no path param at all — the organization comes from the
membership resolved out of the `X-Organization-Id` header, which `require_role`
has already verified the caller belongs to. There is nothing client-supplied
left to validate.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models import OrganizationMember
from app.schemas.insights import DashboardSummary
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=dict)
async def dashboard_summary_endpoint(
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Everything the dashboard home needs for the caller's organization."""
    summary = await dashboard_service.get_dashboard_summary(db, member.organization_id)
    return {"data": DashboardSummary.model_validate(summary)}
