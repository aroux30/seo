from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.core.scoping import assert_keyword_in_org, assert_website_in_org
from app.models import OrganizationMember
from app.schemas import KeywordCreate, KeywordRead, KeywordRankingRead
from app.services.keyword_service import (
    create_keyword, list_website_keywords, delete_keyword, get_keyword_rankings,
)

router = APIRouter(prefix="/keywords", tags=["keywords"])


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_keyword(
    website_id: UUID,
    body: KeywordCreate,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    await assert_website_in_org(db, website_id, member.organization_id)
    kw = await create_keyword(
        db=db,
        website_id=website_id,
        keyword=body.keyword,
        search_volume=body.search_volume,
        difficulty=body.difficulty,
        target_page_url=body.target_page_url,
        intent=body.intent,
        tags=body.tags,
    )
    await db.commit()
    return {"data": KeywordRead.model_validate(kw)}


@router.get("/{website_id}", response_model=dict)
async def list_keywords(
    website_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await assert_website_in_org(db, website_id, member.organization_id)
    keywords = await list_website_keywords(db, website_id)
    return {"data": [KeywordRead.model_validate(k) for k in keywords]}


@router.delete("/{keyword_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_keyword(
    keyword_id: UUID,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    await assert_keyword_in_org(db, keyword_id, member.organization_id)
    await delete_keyword(db, keyword_id)
    await db.commit()


@router.get("/{keyword_id}/rankings", response_model=dict)
async def get_rankings(
    keyword_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await assert_keyword_in_org(db, keyword_id, member.organization_id)
    rankings = await get_keyword_rankings(db, keyword_id)
    return {"data": [KeywordRankingRead.model_validate(r) for r in rankings]}
