"""Category / site-structure endpoints.

One resource, two shapes of it: `GET ""` returns the flat list (cheap, sortable,
what a picker needs) and `GET /tree` returns the same rows nested (what the
structure screen draws). Both come from a single SELECT in the service — see
`category_service` for why `path` and `depth` are materialised.

Conventions carried over from internal_links.py, both load-bearing:

* Every `website_id` goes through `assert_website_in_org` **before** any data is
  read or written. Path ids (`category_id`) are scoped inside the service with
  an explicit `organization_id` filter that raises NotFoundError (404, never
  403), so a UUID cannot be used as an existence oracle. This platform has
  already leaked across tenants once.
* Route declaration order matters: FastAPI matches in order, so the literal
  `/tree`, `/summary`, `/reorder` and `/import/wordpress` are declared before
  `/{category_id}`. Reversed, "tree" would be parsed as a UUID and 422.

`source` and `wp_term_id` are never taken from a request body: only
`import_wordpress_categories` may write them, otherwise a hand-made row could
impersonate an imported one and be clobbered by the next sync.

Services flush; routers commit. Every mutating endpoint below ends with
`await db.commit()`.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scoping import assert_website_in_org
from app.database import get_db
from app.dependencies import require_role
from app.models import OrganizationMember
from app.schemas.categories import (
    CategoryCreate,
    CategoryDeleteResult,
    CategoryImportResult,
    CategoryMove,
    CategoryNode,
    CategoryRead,
    CategoryReorder,
    CategorySummary,
    CategoryUpdate,
)
from app.services import category_service

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post("", response_model=dict, status_code=201)
async def create_category_endpoint(
    body: CategoryCreate,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Create a category, optionally under a parent.

    `website_id` comes from the body here (not a query param) because it is part
    of what is being created, and the guard below still runs before any write.
    """
    await assert_website_in_org(db, body.website_id, member.organization_id)
    row = await category_service.create_category(
        db,
        org_id=member.organization_id,
        website_id=body.website_id,
        name=body.name,
        slug=body.slug,
        description=body.description,
        parent_id=body.parent_id,
        sort_order=body.sort_order,
    )
    await db.commit()
    await db.refresh(row)
    return {"data": CategoryRead.model_validate(row)}


@router.get("", response_model=dict)
async def list_categories_endpoint(
    website_id: UUID = Query(...),
    parent_id: UUID | None = Query(None),
    include_descendants: bool = Query(
        True, description="With parent_id: whole subtree (true) or direct children only"
    ),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Flat category list for a website, ordered by depth then sibling order."""
    await assert_website_in_org(db, website_id, member.organization_id)
    rows = await category_service.list_categories(
        db,
        org_id=member.organization_id,
        website_id=website_id,
        parent_id=parent_id,
        include_descendants=include_descendants,
    )
    return {"data": [CategoryRead.model_validate(r) for r in rows]}


# Declared before /{category_id}: otherwise "tree" is matched as a UUID and 422s.
@router.get("/tree", response_model=dict)
async def category_tree_endpoint(
    website_id: UUID = Query(...),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Nested category tree for the site-structure screen."""
    await assert_website_in_org(db, website_id, member.organization_id)
    tree = await category_service.get_category_tree(
        db, org_id=member.organization_id, website_id=website_id
    )
    return {"data": [CategoryNode.model_validate(node) for node in tree]}


# Literal path — must precede /{category_id}.
@router.get("/summary", response_model=dict)
async def category_summary_endpoint(
    website_id: UUID = Query(...),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Category count, root count, max depth and a per-source breakdown."""
    await assert_website_in_org(db, website_id, member.organization_id)
    summary = await category_service.get_category_summary(
        db, org_id=member.organization_id, website_id=website_id
    )
    return {"data": CategorySummary.model_validate(summary)}


# Literal path — must precede /{category_id}.
@router.post("/reorder", response_model=dict)
async def reorder_categories_endpoint(
    body: CategoryReorder,
    website_id: UUID = Query(...),
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Renumber one parent's siblings. The complete sibling set must be sent."""
    await assert_website_in_org(db, website_id, member.organization_id)
    rows = await category_service.reorder_categories(
        db,
        member.organization_id,
        website_id=website_id,
        parent_id=body.parent_id,
        ordered_ids=body.ordered_ids,
    )
    await db.commit()
    return {"data": [CategoryRead.model_validate(r) for r in rows]}


# Literal path — must precede /{category_id}.
@router.post("/import/wordpress", response_model=dict)
async def import_wordpress_categories_endpoint(
    website_id: UUID = Query(...),
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Import the connected WordPress site's categories.

    Idempotent: matching on `wp_term_id` means a re-run updates the rows a
    previous import created instead of duplicating the tree. Hand-made
    categories are never touched.
    """
    await assert_website_in_org(db, website_id, member.organization_id)
    result = await category_service.import_wordpress_categories(
        db, org_id=member.organization_id, website_id=website_id
    )
    await db.commit()
    return {"data": CategoryImportResult.model_validate(result)}


@router.get("/{category_id}", response_model=dict)
async def get_category_endpoint(
    category_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Fetch one category."""
    row = await category_service.get_category(db, category_id, member.organization_id)
    return {"data": CategoryRead.model_validate(row)}


@router.patch("/{category_id}", response_model=dict)
async def update_category_endpoint(
    category_id: UUID,
    body: CategoryUpdate,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Rename, redescribe or reorder in place. Reparenting is /move."""
    row = await category_service.update_category(
        db,
        category_id,
        member.organization_id,
        name=body.name,
        slug=body.slug,
        description=body.description,
        sort_order=body.sort_order,
    )
    await db.commit()
    await db.refresh(row)
    return {"data": CategoryRead.model_validate(row)}


@router.post("/{category_id}/move", response_model=dict)
async def move_category_endpoint(
    category_id: UUID,
    body: CategoryMove,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Reparent a category, rewriting its whole subtree's paths."""
    row = await category_service.move_category(
        db,
        category_id,
        member.organization_id,
        new_parent_id=body.new_parent_id,
    )
    await db.commit()
    await db.refresh(row)
    return {"data": CategoryRead.model_validate(row)}


@router.delete("/{category_id}", response_model=dict)
async def delete_category_endpoint(
    category_id: UUID,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a category and every descendant."""
    result = await category_service.delete_category(
        db, category_id, member.organization_id
    )
    await db.commit()
    return {"data": CategoryDeleteResult.model_validate(result)}
