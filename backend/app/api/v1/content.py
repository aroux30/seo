from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.core.scoping import (
    assert_article_in_org,
    assert_brief_in_org,
    assert_website_in_org,
)
from app.models import OrganizationMember
from app.schemas.content import (
    ContentBriefCreate,
    ContentBriefRead,
    ContentArticleCreate,
    ContentArticleUpdate,
    ContentArticlePublishRequest,
    ContentArticleRefineRequest,
    ContentArticleRead,
)
from app.services.content_service import (
    generate_content_brief,
    get_content_briefs,
    get_content_brief_by_id,
    generate_seo_article,
    refine_article_with_ai,
    get_content_articles,
    get_content_article_by_id,
    update_content_article,
    delete_content_article,
    delete_content_brief,
    publish_article_to_wp,
)
from app.core.exceptions import AppException

router = APIRouter(prefix="/content", tags=["Content Engine & WordPress"])


# --- BRIEFS ---

@router.post("/briefs/{website_id}/generate", response_model=ContentBriefRead, status_code=status.HTTP_201_CREATED)
async def generate_brief_endpoint(
    website_id: UUID,
    payload: ContentBriefCreate,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Generate a structured SEO content brief with H2/H3 outline and FAQ in Persian."""
    await assert_website_in_org(db, website_id, member.organization_id)
    brief = await generate_content_brief(
        db=db,
        website_id=website_id,
        target_keyword=payload.target_keyword,
        title=payload.title,
        secondary_keywords=payload.secondary_keywords,
        search_intent=payload.search_intent,
        target_word_count=payload.target_word_count,
        keyword_id=payload.keyword_id,
    )
    await db.commit()
    return brief


@router.get("/briefs/{website_id}", response_model=list[ContentBriefRead])
async def list_briefs_endpoint(
    website_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """List all SEO content briefs for a website."""
    await assert_website_in_org(db, website_id, member.organization_id)
    return await get_content_briefs(db, website_id)


@router.get("/briefs/detail/{brief_id}", response_model=ContentBriefRead)
async def get_brief_endpoint(
    brief_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Get a specific SEO content brief by ID."""
    await assert_brief_in_org(db, brief_id, member.organization_id)
    brief = await get_content_brief_by_id(db, brief_id)
    if not brief:
        raise AppException(status_code=404, detail="بریِف یافت نشد.", error_type="brief_not_found")
    return brief


@router.delete("/briefs/detail/{brief_id}", status_code=status.HTTP_200_OK)
async def delete_brief_endpoint(
    brief_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Soft-delete a brief (hidden from all lists; generated articles keep their link)."""
    result = await delete_content_brief(
        db=db,
        brief_id=brief_id,
        org_id=member.organization_id,
    )
    await db.commit()
    return {"data": result}


# --- ARTICLES ---

@router.post("/articles/{website_id}/generate", response_model=ContentArticleRead, status_code=status.HTTP_201_CREATED)
async def generate_article_endpoint(
    website_id: UUID,
    payload: ContentArticleCreate,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Generate an AI-written SEO Persian Article with full heading structure and SEO health score."""
    await assert_website_in_org(db, website_id, member.organization_id)
    article = await generate_seo_article(
        db=db,
        website_id=website_id,
        brief_id=payload.brief_id,
        title=payload.title,
        target_keyword=payload.target_keyword,
        provider=payload.provider,
        user_id=member.user_id,
    )
    await db.commit()
    return article


@router.get("/articles/{website_id}", response_model=list[ContentArticleRead])
async def list_articles_endpoint(
    website_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """List all SEO articles for a website."""
    await assert_website_in_org(db, website_id, member.organization_id)
    return await get_content_articles(db, website_id)


@router.get("/articles/detail/{article_id}", response_model=ContentArticleRead)
async def get_article_endpoint(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Get a specific SEO article by ID."""
    await assert_article_in_org(db, article_id, member.organization_id)
    article = await get_content_article_by_id(db, article_id)
    if not article:
        raise AppException(status_code=404, detail="مقاله یافت نشد.", error_type="article_not_found")
    return article


@router.get("/articles/detail/{article_id}/featured-image")
async def article_featured_image_endpoint(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Stream the generated featured image bytes.

    Deliberately unauthenticated: <img> tags cannot send Authorization headers,
    and the payload is a marketing illustration keyed by an unguessable UUID —
    there is nothing secret to protect. Without this the editor preview and the
    SEO checklist could not render the image.
    """
    from fastapi import Response

    article = await get_content_article_by_id(db, article_id)
    if not article:
        raise AppException(status_code=404, detail="مقاله یافت نشد.", error_type="article_not_found")

    import base64 as _b64

    b64 = (article.seo_metadata or {}).get("featured_image_b64") or ""
    if not b64:
        raise AppException(status_code=404, detail="تصویری برای این مقاله ثبت نشده.", error_type="no_featured_image")
    try:
        raw = _b64.b64decode(b64)
    except Exception:
        raise AppException(status_code=500, detail="تصویر مقاله قابل خواندن نبود.", error_type="bad_featured_image")
    return Response(content=raw, media_type="image/png")


@router.patch("/articles/detail/{article_id}", response_model=ContentArticleRead)
async def update_article_endpoint(
    article_id: UUID,
    payload: ContentArticleUpdate,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Update article title, markdown content, or status."""
    await assert_article_in_org(db, article_id, member.organization_id)
    article = await update_content_article(
        db=db,
        article_id=article_id,
        title=payload.title,
        content_markdown=payload.content_markdown,
        status=payload.status,
        user_id=member.user_id,
    )
    await db.commit()
    return article


@router.post("/articles/detail/{article_id}/refine", response_model=ContentArticleRead)
async def refine_article_endpoint(
    article_id: UUID,
    payload: ContentArticleRefineRequest,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Refine and upgrade an article with AI instructions and full PostgreSQL version history."""
    await assert_article_in_org(db, article_id, member.organization_id)
    article = await refine_article_with_ai(
        db=db,
        article_id=article_id,
        instruction=payload.instruction,
        mode=payload.mode or "auto_fix_100",
        user_id=member.user_id,
    )
    return article


@router.delete("/articles/detail/{article_id}", status_code=status.HTTP_200_OK)
async def delete_article_endpoint(
    article_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Soft-delete an article (hidden from all lists; history stays in DB)."""
    result = await delete_content_article(
        db=db,
        article_id=article_id,
        org_id=member.organization_id,
    )
    await db.commit()
    return {"data": result}


@router.post("/articles/detail/{article_id}/publish", response_model=ContentArticleRead)
async def publish_article_endpoint(
    article_id: UUID,
    payload: ContentArticlePublishRequest,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Publish an article directly to WordPress via REST API (as draft or published)."""
    await assert_article_in_org(db, article_id, member.organization_id)
    article = await publish_article_to_wp(
        db=db,
        article_id=article_id,
        post_status=payload.post_status,
    )
    await db.commit()
    return article
