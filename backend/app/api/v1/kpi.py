from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models import OrganizationMember
from app.services.kpi_service import get_kpi_summary

router = APIRouter(prefix="/kpi", tags=["KPI & Quality"])


@router.get("/summary", response_model=dict)
async def kpi_summary_endpoint(
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("viewer")),
):
    """Organization-level KPI snapshot: content production & quality, AI agent
    reliability, automation health, and SEO pipeline state."""
    return {"data": await get_kpi_summary(db, member.organization_id)}
