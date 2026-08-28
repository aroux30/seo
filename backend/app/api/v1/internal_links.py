"""Internal links endpoints.

Two resources, one module: detector output (`/suggestions`) and the links that
were actually applied (`/links`).

Conventions carried over from insights.py, both load-bearing:

* Every `website_id` query param goes through `assert_website_in_org` **before**
  any data is read or written. Path ids (`suggestion_id`, `link_id`) are scoped
  inside the service with an explicit `organization_id` filter that raises
  NotFoundError (404, never 403), so a UUID cannot be used as an existence
  oracle. This platform has already leaked across tenants once.
* Route declaration order matters: FastAPI matches in order, so the literal
  `/suggestions/summary` is declared before `/suggestions/{suggestion_id}`.
  Reversed, "summary" would be parsed as a UUID and 422.

Services flush; routers commit. Every mutating endpoint below ends with
`await db.commit()`.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scoping import assert_website_in_org
from app.database import get_db
from app.dependencies import require_role
from app.models import ContentArticle, OrganizationMember
from app.schemas.internal_links import (
    BulkSuggestionAction,
    InternalLinkRead,
    InternalLinkSuggestionRead,
    LinkDetectRequest,
    LinkDetectResult,
    SuggestionDecision,
    SuggestionSummary,
)
from app.services import internal_link_service

router = APIRouter(prefix="/internal-links", tags=["internal links"])


async def _article_titles(
    db: AsyncSession, article_ids: set[UUID]
) -> dict[UUID, ContentArticle]:
    """Resolve article ids to rows in one query.

    A suggestion list shows "A should link to B" by title; without this the UI
    would have to fetch each article separately (N+1 over the network). One
    explicit select, never a relationship walk — lazy loading under asyncio
    raises MissingGreenlet.
    """
    if not article_ids:
        return {}
    result = await db.execute(
        select(ContentArticle).where(ContentArticle.id.in_(article_ids))
    )
    return {a.id: a for a in result.scalars().all()}


def _suggestion_payload(row, articles: dict) -> InternalLinkSuggestionRead:
    """ORM row + resolved titles -> read model."""
    source = articles.get(row.source_article_id)
    target = articles.get(row.target_article_id)
    model = InternalLinkSuggestionRead.model_validate(row)
    model.source_title = source.title if source else None
    model.target_title = target.title if target else None
    model.target_url = target.published_url if target else None
    return model


def _link_payload(row, articles: dict) -> InternalLinkRead:
    source = articles.get(row.source_article_id)
    target = articles.get(row.target_article_id)
    model = InternalLinkRead.model_validate(row)
    model.source_title = source.title if source else None
    model.target_title = target.title if target else None
    return model


@router.post("/detect", response_model=dict)
async def detect_internal_links_endpoint(
    website_id: UUID = Query(...),
    body: LinkDetectRequest = LinkDetectRequest(),
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Scan a website's articles and upsert internal link suggestions."""
    await assert_website_in_org(db, website_id, member.organization_id)
    result = await internal_link_service.detect_link_suggestions(
        db,
        website_id,
        min_relevance=body.min_relevance,
        max_per_article=body.max_per_article,
    )
    await db.commit()
    return {"data": LinkDetectResult.model_validate(result)}


@router.get("/suggestions", response_model=dict)
async def list_suggestions_endpoint(
    website_id: UUID = Query(...),
    status: str | None = Query(None),
    reason: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """List link suggestions for a website, highest relevance first."""
    await assert_website_in_org(db, website_id, member.organization_id)
    rows = await internal_link_service.list_suggestions(
        db,
        website_id,
        status=status,
        reason=reason,
        limit=limit,
        offset=offset,
    )
    article_ids: set[UUID] = set()
    for row in rows:
        article_ids.add(row.source_article_id)
        article_ids.add(row.target_article_id)
    articles = await _article_titles(db, article_ids)
    return {"data": [_suggestion_payload(r, articles) for r in rows]}


# Declared before /suggestions/{suggestion_id}: otherwise "summary" is matched
# as a UUID and the request 422s.
@router.get("/suggestions/summary", response_model=dict)
async def suggestion_summary_endpoint(
    website_id: UUID = Query(...),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Suggestion counts by reason and status, orphan count and average relevance."""
    await assert_website_in_org(db, website_id, member.organization_id)
    summary = await internal_link_service.get_suggestion_summary(db, website_id)
    return {"data": SuggestionSummary.model_validate(summary)}


@router.patch("/suggestions/{suggestion_id}", response_model=dict)
async def decide_suggestion_endpoint(
    suggestion_id: UUID,
    body: SuggestionDecision,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Accept or reject a suggestion.

    Accepting also records the link in `internal_links` and moves the suggestion
    to "applied" — see decide_suggestion for why there is no separate step.
    """
    suggestion = await internal_link_service.get_suggestion_in_org(
        db, suggestion_id, member.organization_id
    )
    updated = await internal_link_service.decide_suggestion(
        db,
        suggestion,
        body.status,
        user_id=member.user_id,
    )
    await db.commit()
    articles = await _article_titles(
        db, {updated.source_article_id, updated.target_article_id}
    )
    return {"data": _suggestion_payload(updated, articles)}


@router.post("/suggestions/bulk", response_model=dict)
async def bulk_suggestions_endpoint(
    website_id: UUID = Query(...),
    body: BulkSuggestionAction = None,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Bulk reject or delete suggestions: body = {ids: [uuid], action: "reject"|"delete"}."""
    await assert_website_in_org(db, website_id, member.organization_id)
    result = await internal_link_service.bulk_decide_suggestions(
        db,
        website_id,
        member.organization_id,
        body.ids,
        body.action,
        user_id=member.user_id,
    )
    await db.commit()
    return {"data": result}


@router.delete("/suggestions/{suggestion_id}", response_model=dict)
async def delete_suggestion_endpoint(
    suggestion_id: UUID,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete one suggestion, whatever its status."""
    suggestion = await internal_link_service.get_suggestion_in_org(
        db, suggestion_id, member.organization_id
    )
    result = await internal_link_service.delete_suggestion(db, suggestion)
    await db.commit()
    return {"data": result}


@router.get("/links", response_model=dict)
async def list_links_endpoint(
    website_id: UUID = Query(...),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """List internal links recorded for a website."""
    await assert_website_in_org(db, website_id, member.organization_id)
    rows = await internal_link_service.list_links(
        db, website_id, limit=limit, offset=offset
    )
    article_ids: set[UUID] = set()
    for row in rows:
        article_ids.add(row.source_article_id)
        article_ids.add(row.target_article_id)
    articles = await _article_titles(db, article_ids)
    return {"data": [_link_payload(r, articles) for r in rows]}


@router.delete("/links/{link_id}", response_model=dict)
async def deactivate_link_endpoint(
    link_id: UUID,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate a link.

    Soft removal: the row survives so the detector knows the pair was
    deliberately unlinked. See deactivate_link.
    """
    link = await internal_link_service.get_link_in_org(
        db, link_id, member.organization_id
    )
    updated = await internal_link_service.deactivate_link(
        db, link, user_id=member.user_id
    )
    await db.commit()
    articles = await _article_titles(
        db, {updated.source_article_id, updated.target_article_id}
    )
    return {"data": _link_payload(updated, articles)}
