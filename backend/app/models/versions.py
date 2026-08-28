"""Content versioning — the immutable revision history of an article.

`content_articles` holds exactly one state: whatever was last written. Every
edit, every AI rewrite and every publish overwrote the previous body with no way
back, and "the agent rewrote my article overnight" had no answer other than
re-writing it by hand. This table is that answer.

A version is a **full snapshot**, not a delta. Storing deltas would make reading
any single revision an O(n) replay over the chain and would make a corrupt row
poison every later one; article bodies are a few tens of KB, so the disk cost of
duplication is cheaper than the reconstruction complexity. `diff_stats` is the
only derived field, computed once at write time against the immediately previous
version, because the history list wants "+340 / -12" per row and recomputing a
diff per row on every page load is not affordable.

The history is **append-only and immutable**. Deliberately no SoftDeleteMixin
and no update path: a revision log that can be edited or hidden is not a log.
Rollback therefore moves *forward* — it copies an old snapshot onto the article
and appends a new version with change_type="rollback" — so `version_number`
never rewinds and the fact that someone rolled back is itself recorded.

`is_current` is a denormalised flag rather than a `max(version_number)` lookup:
the article editor needs "which revision am I looking at" on every open, and the
partial index on (article_id, is_current) answers it without an aggregate. The
service is what keeps it to exactly one true row per article; it flips the old
one to False inside the same locked transaction that inserts the new one.

`organization_id` is stored on every row even though it is reachable through
article -> website: the list and diff endpoints scope by org on the hot path and
a two-hop join per request buys nothing.
"""

import uuid

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# --------------------------------------------------------------- vocabularies
# Module constants, not a DB enum: a new writer (say "translation") should not
# need a migration, and Alembic autogenerate handles native enums badly.

CONTENT_CHANGE_TYPES = (
    "created",     # first snapshot, taken when the article row is born
    "edited",      # a human saved the editor
    "ai_rewrite",  # an agent/worker replaced the body
    "rollback",    # an older snapshot was restored onto the article
    "published",   # state at the moment it went live (WordPress push)
    "imported",    # pulled in from an external source, e.g. existing WP post
)

# Change types that no user is credited for. `changed_by` is null on these
# because a worker or the AI made the write, and the UI shows "سیستم" instead of
# a blank author cell.
CONTENT_SYSTEM_CHANGE_TYPES = ("ai_rewrite", "imported")


class ContentVersion(BaseModel):
    """One immutable snapshot of a `content_articles` row at a point in time."""

    __tablename__ = "content_versions"
    __table_args__ = (
        # The version number is the user-visible identity of a revision, so it
        # must be unique per article. This is also the backstop for the
        # numbering race the service locks against: if two writers somehow both
        # compute the same next number, the second INSERT fails loudly instead
        # of silently producing two "version 4"s.
        Index("uq_content_version_article_number", "article_id", "version_number", unique=True),
        # "Which revision is live" — read on every article open.
        Index("idx_content_version_article_current", "article_id", "is_current"),
        # History list for one article, newest first.
        Index("idx_content_version_article_created", "article_id", "created_at"),
        Index("idx_content_version_org", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    website_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id"), nullable=False, index=True
    )
    # CASCADE: deleting an article must take its history with it, otherwise the
    # FK blocks the delete and orphan snapshots accumulate.
    article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_articles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Monotonic per article, starting at 1. Never reused, never rewound.
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # ------------------------------------------------------------- the snapshot
    # Mirrors the scalar content columns of ContentArticle. `slug` and `status`
    # are intentionally absent: they are article-level routing/workflow state,
    # not content, and restoring an old slug would break the published URL.
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    seo_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seo_metadata: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    # ---------------------------------------------------------------- provenance
    change_type: Mapped[str] = mapped_column(String(30), nullable=False)
    change_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Null when a worker or the AI wrote this version — there is no user to blame
    # and a sentinel user row would lie about authorship.
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # {"added_chars": N, "removed_chars": N, "added_words": N, "removed_words": N}
    # against the previous version. Computed at write time (see the module
    # docstring) — the first version of an article diffs against empty, so its
    # "added" counts equal the size of the initial body.
    diff_stats: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    # Exactly one true per article, maintained by version_service inside the
    # locked insert. Not a DB constraint: Postgres cannot express "one true per
    # group" without a partial unique index, which Core cannot declare inline.
    is_current: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    # No updated_at semantics are used and there is no deleted_at: history rows
    # are written once and read forever. `created_at` from BaseModel is the
    # revision timestamp.
