"""Content version endpoints — revision history, diff and rollback.

The module is deliberately read-heavy: four of the five routes are GETs. A
version is never created by a client (see `app/schemas/versions.py` for why), so
the only mutation here is rollback, and even that does not accept content — it
names a revision and the server copies it.

Three conventions carried over from the rest of v1:

* **Every `article_id` is org-scoped through `assert_article_in_org`.** The
  version tables denormalise `organization_id`, but a caller-supplied
  `article_id` is still an untrusted UUID: without the guard, a viewer in org A
  could list org B's revision history — including full article bodies — by
  guessing an id. The guard raises 404, not 403, so the status code is not an
  existence oracle.
* **`version_id` is scoped inside `version_service`** (`get_version` filters on
  `organization_id`), because `app.core.scoping` is owned elsewhere and cannot
  yet grow an `assert_content_version_in_org`.
* **Literal paths before parametric ones.** `/summary` and `/diff` are declared
  above `/{version_id}`; reversed, FastAPI would try to parse "summary" as a
  UUID and answer 422.

Role floors: reading history is `viewer` (anyone who can read the article can see
how it got there), rollback is `editor` because it rewrites the live article.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scoping import assert_article_in_org
from app.database import get_db
from app.dependencies import require_role
from app.models import OrganizationMember
from app.schemas.versions import (
    ContentVersionDiff,
    ContentVersionListItem,
    ContentVersionRead,
    ContentVersionRollbackRequest,
    ContentVersionRollbackResult,
    ContentVersionSummary,
)
from app.services import version_service

router = APIRouter(prefix="/versions", tags=["content versions"])


@router.get("", response_model=dict)
async def list_versions_endpoint(
    article_id: UUID = Query(..., description="مقاله‌ای که تاریخچه‌اش خوانده می‌شود"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Revision history for one article, newest first.

    Returns list items without bodies: a 50-revision response carrying two
    copies (markdown + HTML) of every snapshot would be megabytes for a page
    that only renders timestamps and author names.
    """
    await assert_article_in_org(db, article_id, member.organization_id)
    rows = await version_service.list_versions(
        db, article_id, limit=limit, offset=offset
    )
    return {"data": [ContentVersionListItem.model_validate(r) for r in rows]}


# Declared before /{version_id}: otherwise "summary" is parsed as a UUID.
@router.get("/summary", response_model=dict)
async def version_summary_endpoint(
    article_id: UUID = Query(...),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Counters for the history panel header."""
    await assert_article_in_org(db, article_id, member.organization_id)
    summary = await version_service.get_version_summary(db, article_id)
    return {"data": ContentVersionSummary.model_validate(summary)}


# Also before /{version_id}, same reason.
@router.get("/diff", response_model=dict)
async def diff_versions_endpoint(
    article_id: UUID = Query(...),
    from_version: int = Query(..., ge=1, description="شماره نسخه مبنا"),
    to_version: int = Query(..., ge=1, description="شماره نسخه مقایسه‌شده"),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Compare two revisions of the same article.

    Versions are addressed by their per-article `version_number` rather than by
    UUID: that is the number the history list shows, and scoping the pair to one
    already-guarded `article_id` means neither number can reach another tenant's
    row even though the numbers themselves are guessable.
    """
    await assert_article_in_org(db, article_id, member.organization_id)
    diff = await version_service.diff_versions(
        db, article_id, from_version, to_version
    )
    return {"data": ContentVersionDiff.model_validate(diff)}


@router.get("/{version_id}", response_model=dict)
async def get_version_endpoint(
    version_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """One full snapshot, bodies included.

    Org scoping happens in the service, which filters on the denormalised
    `organization_id` and raises 404 on a cross-tenant id.
    """
    row = await version_service.get_version(db, version_id, member.organization_id)
    return {"data": ContentVersionRead.model_validate(row)}


@router.post("/{version_id}/rollback", response_model=dict)
async def rollback_version_endpoint(
    version_id: UUID,
    body: ContentVersionRollbackRequest = ContentVersionRollbackRequest(),
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Restore a revision onto the live article.

    The article is resolved *from the version* rather than taken as a parameter,
    so a caller cannot pair a version of one article with the id of another. The
    version is org-scoped first, then the article it belongs to is re-checked
    through `assert_article_in_org` — the version's own denormalised org column
    would miss an article whose website has since been soft-deleted.

    Rollback appends a new version instead of deleting the ones after the target;
    `version_service.rollback_to_version` explains why.
    """
    target = await version_service.get_version(
        db, version_id, member.organization_id
    )
    article = await assert_article_in_org(
        db, target.article_id, member.organization_id
    )
    new_version = await version_service.rollback_to_version(
        db,
        article,
        version_id,
        user_id=member.user_id,
        change_summary=body.change_summary,
    )
    await db.commit()
    await db.refresh(new_version)
    return {
        "data": ContentVersionRollbackResult(
            restored_from_version_number=target.version_number,
            new_version=ContentVersionRead.model_validate(new_version),
        )
    }
