from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.core.scoping import assert_strategy_in_org, assert_website_in_org
from app.models import OrganizationMember
from app.schemas import (
    AiSeoStrategyRead, AiSeoStrategyGenerateRequest, AiAgentLogRead,
)
from app.services.ai_service import (
    generate_seo_strategy, get_website_strategies, get_strategy_detail, get_website_ai_logs,
)
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.post("/generate", response_model=dict, status_code=status.HTTP_201_CREATED)
async def generate_strategy_endpoint(
    website_id: UUID = Query(...),
    body: AiSeoStrategyGenerateRequest = AiSeoStrategyGenerateRequest(),
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Generate AI SEO Strategy Roadmap with keyword clusters and content gaps."""
    await assert_website_in_org(db, website_id, member.organization_id)
    strategy = await generate_seo_strategy(
        db,
        website_id=website_id,
        provider=body.provider,
        focus_area=body.focus_area,
    )
    return {"data": AiSeoStrategyRead.model_validate(strategy)}


@router.get("", response_model=dict)
async def list_strategies_endpoint(
    website_id: UUID = Query(...),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """List historical AI SEO strategies for a website."""
    await assert_website_in_org(db, website_id, member.organization_id)
    strategies = await get_website_strategies(db, website_id=website_id)
    data = [AiSeoStrategyRead.model_validate(s) for s in strategies]
    return {"data": data}


@router.get("/ai-logs", response_model=dict)
async def list_ai_logs_endpoint(
    website_id: UUID = Query(...),
    limit: int = Query(20, ge=1, le=100),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Get audit trail of AI Agent executions and token usage."""
    await assert_website_in_org(db, website_id, member.organization_id)
    logs = await get_website_ai_logs(db, website_id=website_id, limit=limit)
    data = [AiAgentLogRead.model_validate(l) for l in logs]
    return {"data": data}


@router.get("/{strategy_id}", response_model=dict)
async def get_strategy_detail_endpoint(
    strategy_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed AI SEO Strategy roadmap."""
    await assert_strategy_in_org(db, strategy_id, member.organization_id)
    strategy = await get_strategy_detail(db, strategy_id=strategy_id)
    if not strategy:
        raise NotFoundError("AiSeoStrategy", str(strategy_id))
    return {"data": AiSeoStrategyRead.model_validate(strategy)}
