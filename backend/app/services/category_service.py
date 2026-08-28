"""Category tree service — the only writer of `path` and `depth`.

`ContentCategory` stores two derived columns (`path`, `depth`) next to the
`parent_id` edge so the whole tree can be rendered from one flat SELECT. That
duplication is only safe if exactly one place computes it. This module is that
place; see the invariant on `app.models.categories.ContentCategory`.

Three rules are load-bearing here:

* **Subtree rewrites.** Renaming a slug or reparenting a node changes the path
  of every descendant, not just the node itself. `_rewrite_subtree` rebuilds
  them in one UPDATE using the stored prefix. Skipping it would leave
  descendants pointing at a path that no longer exists, and every
  `LIKE '<prefix>/%'` lookup below would silently miss them.
* **Cycle guard.** A move is rejected if the new parent is the node itself or
  one of its own descendants. Without it the tree becomes a ring and
  `_rewrite_subtree` recurses until the path column overflows.
* **Slug/path freedom.** Uniqueness is enforced here rather than by a unique
  index, because the real rule is "unique among *non-deleted* rows" — a plain
  index would let one soft-deleted `/news` block that path forever. Same
  tradeoff as `approval_service._assert_no_duplicate_pending`.

Scoping: every read and write takes `organization_id` and raises
`NotFoundError` (404) on a cross-tenant id, never `ForbiddenError`, so a UUID
cannot be used as an existence oracle.
"""

import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import Website
from app.models.categories import (
    CATEGORY_PATH_SEPARATOR,
    CATEGORY_SOURCES,
    MAX_CATEGORY_DEPTH,
    ContentCategory,
)

__all__ = [
    "create_category",
    "list_categories",
    "get_category_tree",
    "get_category",
    "update_category",
    "move_category",
    "reorder_categories",
    "delete_category",
    "import_wordpress_categories",
    "get_category_summary",
]

SEP = CATEGORY_PATH_SEPARATOR


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------- slugs

def _slugify(text: str) -> str:
    """Turn a display name into one path segment.

    Unicode-aware on purpose: this platform's primary language is Persian and a
    Persian category name must not collapse to an empty slug. `\\w` with the
    default (unicode) flags keeps Persian letters and digits; everything unsafe
    for a path segment — including the separator itself — becomes a hyphen.

    Client-supplied slugs go through `SLUG_PATTERN` in the schema instead, which
    is deliberately stricter (ascii only). This function only runs when the
    caller did not supply one.
    """
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    slug = re.sub(r"[\s_]+", "-", text).strip("-")
    # A name made entirely of punctuation would slugify to "". Fall back to
    # something addressable rather than writing an empty path segment.
    return slug or "category"


def _build_path(parent_path: str | None, slug: str) -> str:
    """Compose a child path. Root paths are '/slug', children '/parent/slug'."""
    if not parent_path:
        return f"{SEP}{slug}"
    return f"{parent_path}{SEP}{slug}"


def _depth_of(path: str) -> int:
    """Depth from the path: '/news' is 0, '/news/politics' is 1."""
    return max(path.count(SEP) - 1, 0)


# -------------------------------------------------------------------- lookups

async def _assert_website_in_org(
    db: AsyncSession, website_id: UUID, org_id: UUID
) -> Website:
    result = await db.execute(
        select(Website).where(
            Website.id == website_id,
            Website.organization_id == org_id,
            Website.deleted_at.is_(None),
        )
    )
    website = result.scalar_one_or_none()
    if not website:
        raise NotFoundError("Website", str(website_id))
    return website


async def get_category(
    db: AsyncSession, category_id: UUID, org_id: UUID
) -> ContentCategory:
    """Fetch one live category, scoped to the caller's organization.

    Joins through `Website` rather than trusting the denormalised
    `organization_id` alone: a category on a soft-deleted website must not stay
    reachable just because its cached org column still matches.
    """
    result = await db.execute(
        select(ContentCategory)
        .join(Website, Website.id == ContentCategory.website_id)
        .where(
            ContentCategory.id == category_id,
            ContentCategory.deleted_at.is_(None),
            Website.organization_id == org_id,
            Website.deleted_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise NotFoundError("ContentCategory", str(category_id))
    return row


async def _assert_slug_free(
    db: AsyncSession,
    *,
    website_id: UUID,
    path: str,
    exclude_id: UUID | None = None,
) -> None:
    """Refuse a duplicate path among a website's non-deleted categories.

    Checking the composed `path` rather than the bare slug means two different
    branches may each have a "politics" child (`/news/politics` and
    `/sports/politics`) while a real collision under one parent is still
    caught. `exclude_id` lets an update re-validate a row against itself.
    """
    stmt = select(ContentCategory.id).where(
        ContentCategory.website_id == website_id,
        ContentCategory.path == path,
        ContentCategory.deleted_at.is_(None),
    )
    if exclude_id is not None:
        stmt = stmt.where(ContentCategory.id != exclude_id)
    if (await db.execute(stmt.limit(1))).scalar_one_or_none():
        raise ConflictError(
            f"دسته‌بندی دیگری با مسیر '{path}' در این وب‌سایت وجود دارد."
        )


def _assert_depth_ok(depth: int) -> None:
    """MAX_CATEGORY_DEPTH counts levels, so the deepest legal depth is N-1."""
    if depth > MAX_CATEGORY_DEPTH - 1:
        raise ValidationError(
            f"عمق دسته‌بندی از حد مجاز ({MAX_CATEGORY_DEPTH} سطح) بیشتر است."
        )


async def _descendants(
    db: AsyncSession, node: ContentCategory
) -> list[ContentCategory]:
    """Every live node strictly below `node`.

    The trailing separator in the LIKE prefix is what stops '/news' from also
    matching a sibling called '/newsletter'.
    """
    result = await db.execute(
        select(ContentCategory).where(
            ContentCategory.website_id == node.website_id,
            ContentCategory.path.like(f"{node.path}{SEP}%"),
            ContentCategory.deleted_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def _rewrite_subtree(
    db: AsyncSession, node: ContentCategory, old_path: str
) -> None:
    """Re-derive `path` and `depth` for everything under a moved/renamed node.

    Runs after `node.path` has already been set to its new value. Each
    descendant keeps the part of its path that hangs below `old_path` and gets
    the new prefix in front of it.
    """
    if node.path == old_path:
        return
    result = await db.execute(
        select(ContentCategory).where(
            ContentCategory.website_id == node.website_id,
            ContentCategory.path.like(f"{old_path}{SEP}%"),
            ContentCategory.deleted_at.is_(None),
            ContentCategory.id != node.id,
        )
    )
    for child in result.scalars().all():
        suffix = child.path[len(old_path):]
        child.path = f"{node.path}{suffix}"
        child.depth = _depth_of(child.path)
        _assert_depth_ok(child.depth)
    await db.flush()


# --------------------------------------------------------------------- create

async def create_category(
    db: AsyncSession,
    *,
    org_id: UUID,
    website_id: UUID,
    name: str,
    slug: str | None = None,
    description: str | None = None,
    parent_id: UUID | None = None,
    sort_order: int = 0,
    source: str = "manual",
    wp_term_id: int | None = None,
) -> ContentCategory:
    """Add one node. `path` and `depth` are derived from the parent, never given."""
    await _assert_website_in_org(db, website_id, org_id)

    if source not in CATEGORY_SOURCES:
        raise ValidationError(f"source must be one of {sorted(CATEGORY_SOURCES)}")

    parent: ContentCategory | None = None
    if parent_id is not None:
        parent = await get_category(db, parent_id, org_id)
        # A cross-website parent would produce a path that belongs to neither
        # tree and break every website-scoped descendant query.
        if parent.website_id != website_id:
            raise ValidationError("دسته‌بندی والد به وب‌سایت دیگری تعلق دارد.")

    final_slug = slug or _slugify(name)
    path = _build_path(parent.path if parent else None, final_slug)
    depth = _depth_of(path)
    _assert_depth_ok(depth)
    await _assert_slug_free(db, website_id=website_id, path=path)

    row = ContentCategory(
        organization_id=org_id,
        website_id=website_id,
        parent_id=parent_id,
        name=name,
        slug=final_slug,
        description=description,
        path=path,
        depth=depth,
        sort_order=sort_order,
        source=source,
        wp_term_id=wp_term_id,
        content_count=0,
    )
    db.add(row)
    await db.flush()
    return row


# ---------------------------------------------------------------------- reads

async def list_categories(
    db: AsyncSession,
    *,
    org_id: UUID,
    website_id: UUID,
    parent_id: UUID | None = None,
    include_descendants: bool = True,
) -> list[ContentCategory]:
    """Flat list, ordered so a client can rebuild the tree by walking it once."""
    await _assert_website_in_org(db, website_id, org_id)

    stmt = select(ContentCategory).where(
        ContentCategory.website_id == website_id,
        ContentCategory.deleted_at.is_(None),
    )
    if parent_id is not None:
        if include_descendants:
            parent = await get_category(db, parent_id, org_id)
            stmt = stmt.where(ContentCategory.path.like(f"{parent.path}{SEP}%"))
        else:
            stmt = stmt.where(ContentCategory.parent_id == parent_id)

    stmt = stmt.order_by(
        ContentCategory.depth,
        ContentCategory.sort_order,
        ContentCategory.name,
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_category_tree(
    db: AsyncSession, *, org_id: UUID, website_id: UUID
) -> list[dict]:
    """Nested tree for the site-structure screen.

    Assembled in Python from the single flat SELECT above — that is the whole
    reason `path` and `depth` are materialised. Ordering (sort_order, then name)
    comes from the query, so siblings arrive already in display order and the
    child lists inherit it.
    """
    rows = await list_categories(db, org_id=org_id, website_id=website_id)

    nodes: dict[UUID, dict] = {}
    for row in rows:
        nodes[row.id] = {
            "id": row.id,
            "organization_id": row.organization_id,
            "website_id": row.website_id,
            "parent_id": row.parent_id,
            "name": row.name,
            "slug": row.slug,
            "description": row.description,
            "path": row.path,
            "depth": row.depth,
            "sort_order": row.sort_order,
            "wp_term_id": row.wp_term_id,
            "source": row.source,
            "content_count": row.content_count,
            "children": [],
        }

    roots: list[dict] = []
    for row in rows:
        node = nodes[row.id]
        parent = nodes.get(row.parent_id) if row.parent_id else None
        # A node whose parent is missing (soft-deleted out from under it) is
        # surfaced at the root rather than dropped — losing it silently would
        # hide content from the only screen that lists it.
        if parent is None:
            roots.append(node)
        else:
            parent["children"].append(node)
    return roots


async def get_category_summary(
    db: AsyncSession, *, org_id: UUID, website_id: UUID
) -> dict:
    """Counts for the header card."""
    await _assert_website_in_org(db, website_id, org_id)

    base = (
        ContentCategory.website_id == website_id,
        ContentCategory.deleted_at.is_(None),
    )

    total = (
        await db.execute(select(func.count()).select_from(ContentCategory).where(*base))
    ).scalar() or 0
    roots = (
        await db.execute(
            select(func.count())
            .select_from(ContentCategory)
            .where(*base, ContentCategory.parent_id.is_(None))
        )
    ).scalar() or 0
    max_depth = (
        await db.execute(select(func.max(ContentCategory.depth)).where(*base))
    ).scalar() or 0

    by_source_rows = await db.execute(
        select(ContentCategory.source, func.count())
        .where(*base)
        .group_by(ContentCategory.source)
    )
    return {
        "total": total,
        "roots": roots,
        "max_depth": max_depth,
        "by_source": {src: cnt for src, cnt in by_source_rows.all()},
    }


# -------------------------------------------------------------------- updates

async def update_category(
    db: AsyncSession,
    category_id: UUID,
    org_id: UUID,
    *,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    sort_order: int | None = None,
) -> ContentCategory:
    """Rename / redescribe / reorder in place.

    A slug change rewrites this node's path and every descendant's. Reparenting
    is `move_category`, not this — folding the two together would make a request
    that changes both ambiguous about which rewrite ran first.
    """
    row = await get_category(db, category_id, org_id)
    old_path = row.path

    if description is not None:
        row.description = description
    if sort_order is not None:
        row.sort_order = sort_order
    if name is not None:
        row.name = name

    # An explicit slug wins; otherwise a rename only re-slugs when the old slug
    # was itself derived from the old name (never clobber a hand-set slug).
    new_slug = slug if slug is not None else None
    if new_slug is not None and new_slug != row.slug:
        parent_path = old_path.rsplit(SEP, 1)[0] if row.depth > 0 else None
        candidate = _build_path(parent_path or None, new_slug)
        await _assert_slug_free(
            db, website_id=row.website_id, path=candidate, exclude_id=row.id
        )
        row.slug = new_slug
        row.path = candidate
        row.depth = _depth_of(candidate)
        _assert_depth_ok(row.depth)

    await db.flush()
    await _rewrite_subtree(db, row, old_path)
    return row


async def move_category(
    db: AsyncSession,
    category_id: UUID,
    org_id: UUID,
    *,
    new_parent_id: UUID | None,
) -> ContentCategory:
    """Reparent a node (null parent = move to root) and rewrite its subtree."""
    row = await get_category(db, category_id, org_id)
    old_path = row.path

    if new_parent_id == row.id:
        raise ValidationError("یک دسته‌بندی نمی‌تواند والد خودش باشد.")

    new_parent: ContentCategory | None = None
    if new_parent_id is not None:
        new_parent = await get_category(db, new_parent_id, org_id)
        if new_parent.website_id != row.website_id:
            raise ValidationError("دسته‌بندی والد به وب‌سایت دیگری تعلق دارد.")
        # Cycle guard: moving a node under its own descendant would detach the
        # whole branch from the root and make _rewrite_subtree unbounded.
        if new_parent.path == old_path or new_parent.path.startswith(f"{old_path}{SEP}"):
            raise ValidationError(
                "نمی‌توان یک دسته‌بندی را به زیرمجموعه‌ی خودش منتقل کرد."
            )

    candidate = _build_path(new_parent.path if new_parent else None, row.slug)
    if candidate != old_path:
        await _assert_slug_free(
            db, website_id=row.website_id, path=candidate, exclude_id=row.id
        )

    new_depth = _depth_of(candidate)
    _assert_depth_ok(new_depth)
    # The deepest descendant moves by the same delta, so check the whole branch
    # before writing anything — a partially applied move cannot be undone here.
    descendants = await _descendants(db, row)
    if descendants:
        deepest = max(d.depth for d in descendants)
        _assert_depth_ok(deepest + (new_depth - row.depth))

    row.parent_id = new_parent_id
    row.path = candidate
    row.depth = new_depth
    await db.flush()
    await _rewrite_subtree(db, row, old_path)
    return row


async def reorder_categories(
    db: AsyncSession,
    org_id: UUID,
    *,
    website_id: UUID,
    parent_id: UUID | None,
    ordered_ids: list[UUID],
) -> list[ContentCategory]:
    """Assign `sort_order` 0..N-1 across one parent's siblings.

    `ordered_ids` must be the complete sibling set. A partial list is rejected
    rather than applied: renumbering a subset from zero would silently collide
    with the omitted siblings' existing values.
    """
    await _assert_website_in_org(db, website_id, org_id)

    stmt = select(ContentCategory).where(
        ContentCategory.website_id == website_id,
        ContentCategory.deleted_at.is_(None),
    )
    stmt = (
        stmt.where(ContentCategory.parent_id == parent_id)
        if parent_id is not None
        else stmt.where(ContentCategory.parent_id.is_(None))
    )
    siblings = {r.id: r for r in (await db.execute(stmt)).scalars().all()}

    unknown = [i for i in ordered_ids if i not in siblings]
    if unknown:
        raise NotFoundError("ContentCategory", str(unknown[0]))
    if len(ordered_ids) != len(siblings):
        raise ValidationError(
            "برای مرتب‌سازی باید همه‌ی دسته‌بندی‌های همان سطح ارسال شوند "
            f"({len(siblings)} مورد)."
        )

    for position, cid in enumerate(ordered_ids):
        siblings[cid].sort_order = position
    await db.flush()
    return [siblings[cid] for cid in ordered_ids]


# -------------------------------------------------------------------- deletes

async def delete_category(
    db: AsyncSession, category_id: UUID, org_id: UUID
) -> dict:
    """Soft-delete a node and everything under it.

    Cascading is deliberate: leaving orphaned children behind would strand them
    outside the tree with a `path` whose prefix no longer resolves. Soft rather
    than hard because content rows reference these ids.
    """
    row = await get_category(db, category_id, org_id)
    stamp = _now()

    affected = [row, *await _descendants(db, row)]
    for node in affected:
        node.deleted_at = stamp
    await db.flush()
    return {"deleted": len(affected)}


# ----------------------------------------------------------- wordpress import

async def import_wordpress_categories(
    db: AsyncSession, *, org_id: UUID, website_id: UUID
) -> dict:
    """Sync categories from the connected WordPress site.

    Matched on `wp_term_id`, so re-running updates the rows a previous import
    created instead of inserting duplicates. A hand-made category (null
    `wp_term_id`) is never touched, even when its slug collides — that case is
    counted as `skipped` rather than silently overwriting someone's work.

    The WP REST list this reads returns id/name/slug only, so imported nodes
    land flat at the root; a human arranges the hierarchy afterwards with
    `move_category`.
    """
    # Imported here rather than at module scope: wordpress_service reaches for
    # httpx and the crypto helpers, and the rest of this module must stay
    # importable without them.
    from app.services import wordpress_service

    await _assert_website_in_org(db, website_id, org_id)
    remote = await wordpress_service.list_wp_categories(db, website_id)

    existing = (
        await db.execute(
            select(ContentCategory).where(
                ContentCategory.website_id == website_id,
                ContentCategory.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    by_term = {c.wp_term_id: c for c in existing if c.wp_term_id is not None}
    manual_paths = {c.path for c in existing if c.wp_term_id is None}

    created = updated = skipped = 0
    for item in remote:
        term_id = item.get("id")
        name = (item.get("name") or "").strip()
        if term_id is None or not name:
            skipped += 1
            continue

        slug = (item.get("slug") or "").strip() or _slugify(name)
        path = _build_path(None, slug)

        found = by_term.get(term_id)
        if found is not None:
            found.name = name
            if found.slug != slug and path not in manual_paths:
                old_path = found.path
                found.slug = slug
                found.path = path
                found.depth = _depth_of(path)
                await db.flush()
                await _rewrite_subtree(db, found, old_path)
            updated += 1
            continue

        # Never clobber a hand-made row that already owns this path.
        if path in manual_paths:
            skipped += 1
            continue

        row = ContentCategory(
            organization_id=org_id,
            website_id=website_id,
            parent_id=None,
            name=name,
            slug=slug,
            path=path,
            depth=0,
            sort_order=0,
            source="wordpress",
            wp_term_id=term_id,
            content_count=0,
        )
        db.add(row)
        by_term[term_id] = row
        created += 1

    await db.flush()
    return {"created": created, "updated": updated, "skipped": skipped}
