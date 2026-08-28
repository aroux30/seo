"""Schemas for the category / site-structure tree.

Write models are narrow on purpose. `path`, `depth`, `organization_id` and
`content_count` are derived state that only `category_service` may compute —
see the invariant documented on `app.models.categories.ContentCategory`. If a
client could set `path` directly the materialised tree could drift from the
`parent_id` edges it is supposed to mirror, and every `LIKE '<prefix>/%'`
descendant lookup in the service would silently start missing rows.

`CategoryNode` is the one recursive shape: the tree endpoint returns nested
children, so `model_rebuild()` is required after the class body closes (a
forward reference to a not-yet-fully-defined class cannot be resolved by
pydantic until then).
"""

import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.categories import CATEGORY_SOURCES

# A slug is a URL path segment: lowercase ascii letters, digits and hyphens.
# Deliberately does not allow the leading/trailing hyphen or the path
# separator itself, since `path` is built by joining slugs with "/".
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


# --------------------------------------------------------------------- reads

class CategoryRead(BaseModel):
    """Flat row, as stored. Used by the flat list endpoint."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    website_id: UUID
    parent_id: UUID | None = None
    name: str
    slug: str
    description: str | None = None
    path: str
    depth: int
    sort_order: int
    wp_term_id: int | None = None
    source: str
    content_count: int


class CategoryNode(CategoryRead):
    """Recursive shape for the tree endpoint.

    Children are sorted by `sort_order` then `name` by the service, not here —
    this schema only describes the shape, not the ordering policy.
    """

    children: list["CategoryNode"] = Field(default_factory=list)


CategoryNode.model_rebuild()


# -------------------------------------------------------------------- writes

class CategoryCreate(BaseModel):
    """Create one node.

    `slug` is optional: the service derives it from `name` when absent. Note
    what is intentionally missing — `path`, `depth`, `organization_id`,
    `content_count` — those are always service-computed.
    """

    website_id: UUID
    parent_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    sort_order: int = Field(default=0, ge=0, le=1_000_000)
    source: str = "manual"

    @field_validator("slug")
    @classmethod
    def _valid_slug(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not SLUG_PATTERN.match(v):
            raise ValueError(
                "slug must be lowercase letters, digits and hyphens only"
            )
        return v

    @field_validator("source")
    @classmethod
    def _known_source(cls, v: str) -> str:
        if v not in CATEGORY_SOURCES:
            raise ValueError(f"source must be one of {sorted(CATEGORY_SOURCES)}")
        return v


class CategoryUpdate(BaseModel):
    """Rename / redescribe / reorder in place.

    Reparenting is a separate endpoint (`CategoryMove`) because it needs its
    own cycle guard and subtree rewrite; folding it into this schema would
    make "did the slug change" and "did the parent change" ambiguous to a
    caller sending both at once.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    sort_order: int | None = Field(default=None, ge=0, le=1_000_000)

    @field_validator("slug")
    @classmethod
    def _valid_slug(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not SLUG_PATTERN.match(v):
            raise ValueError(
                "slug must be lowercase letters, digits and hyphens only"
            )
        return v


class CategoryMove(BaseModel):
    """Reparent a node under a new parent (or to the root)."""

    new_parent_id: UUID | None = None


class CategoryReorder(BaseModel):
    """Reassign `sort_order` for every sibling of one parent, in one call.

    `ordered_ids` is the full sibling list in the caller's desired order —
    the service assigns 0..N-1 by position, so a partial list would silently
    leave the omitted siblings' `sort_order` untouched while the rest shift
    around them.
    """

    parent_id: UUID | None = None
    ordered_ids: list[UUID] = Field(min_length=1, max_length=1000)


# ---------------------------------------------------------------- aggregates

class CategoryDeleteResult(BaseModel):
    """Outcome of a (possibly cascading) soft delete."""

    deleted: int = 0


class CategoryImportResult(BaseModel):
    """Outcome of a WordPress category sync."""

    created: int = 0
    updated: int = 0
    skipped: int = 0


class CategorySummary(BaseModel):
    """Counts for the site-structure header card."""

    total: int = 0
    roots: int = 0
    max_depth: int = 0
    by_source: dict[str, int] = Field(default_factory=dict)


__all__ = [
    "CategoryRead",
    "CategoryNode",
    "CategoryCreate",
    "CategoryUpdate",
    "CategoryMove",
    "CategoryReorder",
    "CategoryDeleteResult",
    "CategoryImportResult",
    "CategorySummary",
]
