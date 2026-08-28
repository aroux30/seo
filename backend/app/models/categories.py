"""Content categories — the site structure tree.

One table backs the whole "website → category → subcategory → content" view.
The tree is a plain self-referencing parent_id edge, but two derived columns
(`path` and `depth`) are stored alongside it so the UI can render the entire
structure from a single flat SELECT. Postgres could do this with a recursive
CTE instead; the materialised path is preferred here because the tree is read
on every content screen and written only when someone renames or moves a node.

The cost of materialising is that `path` and `depth` are duplicated state and
can drift. They are therefore *only* written by `category_service`, which
rewrites the whole affected subtree on create / rename / move. Nothing else
should assign to them.

Like every other table in this platform, a category carries
`organization_id` directly even though it is reachable through
`website_id → websites.organization_id`. Scoping filters on organization_id on
the hot path and a join per guard would be wasted work.

Soft delete (not hard) because categories are referenced by content: deleting
the row outright would orphan every article that points at it. `deleted_at`
also lets an accidental cascade delete be reasoned about after the fact.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import BaseModel, SoftDeleteMixin


# ---------------------------------------------------------------- vocabularies
# Module constants rather than DB enums: the limits below are policy, not
# schema, and changing policy should not need a migration.

# How deep the tree may go. WordPress itself has no limit, but a path longer
# than this is almost always an import bug rather than a real taxonomy, and an
# unbounded depth makes the cascade rewrites unbounded too.
MAX_CATEGORY_DEPTH = 6

# Separator used to build `path`. A leading separator is always present, so a
# root category's path is "/news" and its child's is "/news/politics". Storing
# the leading slash means `LIKE '/news/%'` matches descendants without also
# matching a sibling called "/newsletter".
CATEGORY_PATH_SEPARATOR = "/"

# Where a category row came from. Kept for the WP importer: a row it created
# may be re-synced, a hand-made row must never be clobbered by an import.
CATEGORY_SOURCES = ("manual", "wordpress")


class ContentCategory(BaseModel, SoftDeleteMixin):
    """One node of a website's category tree."""

    __tablename__ = "content_categories"
    __table_args__ = (
        # The tree query: "every category of this website", then assembled in
        # Python. Also serves the flat list ordered by depth.
        Index("idx_category_website_parent", "website_id", "parent_id"),
        Index("idx_category_org", "organization_id"),
        # Sibling ordering within one parent.
        Index("idx_category_sort", "website_id", "parent_id", "sort_order"),
        # Descendant lookups use `path LIKE '<prefix>/%'`, which needs the
        # leading column of a btree on (website_id, path) to be useful.
        Index("idx_category_path", "website_id", "path"),
        # WP import idempotency: re-importing updates the row it created last
        # time instead of inserting a duplicate. Not declared unique because
        # wp_term_id is null for every hand-made category and Postgres would
        # allow only one such row per website under a plain unique index.
        Index("idx_category_wp_term", "website_id", "wp_term_id"),
        # NOTE: slug uniqueness per website is NOT enforced here. The real rule
        # is "unique among *non-deleted* rows of one website", which a plain
        # unique index cannot express (a soft-deleted "/news" would keep
        # blocking a new "/news" forever). `category_service._assert_slug_free`
        # enforces it instead — same tradeoff as the dedup check in
        # approval_service._assert_no_duplicate_pending.
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    website_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id"), nullable=False, index=True
    )

    # Self-FK. Null means a root category. ondelete is deliberately left at the
    # default: rows are soft-deleted, so the database never removes a parent out
    # from under its children.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_categories.id"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Materialised ancestor path, e.g. "/news/politics". Derived from the slugs
    # of this row and every ancestor; rewritten for the whole subtree whenever a
    # slug changes or a node is reparented. Wide enough for MAX_CATEGORY_DEPTH
    # full-length slugs.
    path: Mapped[str] = mapped_column(String(2000), nullable=False)

    # 0 for a root category. Redundant with `path` (it is the separator count)
    # but stored so ordering and depth filters do not need string work.
    depth: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Ordering among siblings. Not unique: two siblings sharing a value simply
    # fall back to a stable secondary sort by name.
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # WordPress term id, set only for imported rows. Nullable because a category
    # created in this platform has no WP counterpart until it is pushed.
    wp_term_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)

    # Cached count of articles filed under this category. Denormalised so the
    # tree view does not need an aggregate per node.
    #
    # It stays 0 for now: `content_articles` has no category_id column yet, so
    # there is nothing to count. The column exists already because adding it
    # later would mean a second migration over a table the UI is already
    # reading, and because the tree schema is the natural place for it.
    content_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


__all__ = [
    "ContentCategory",
    "MAX_CATEGORY_DEPTH",
    "CATEGORY_PATH_SEPARATOR",
    "CATEGORY_SOURCES",
]
