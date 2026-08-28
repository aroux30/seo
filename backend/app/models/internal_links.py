"""Internal links — suggest and track links between a website's own articles.

Two tables, two different lifecycles:

* `InternalLinkSuggestion` is detector output. `detect_link_suggestions` scans
  a website's articles, scores candidate (source, target) pairs and upserts
  them by `fingerprint`. A suggestion that stops reproducing is marked
  `expired` rather than deleted, matching opportunity_service's audit-trail
  approach — a user who accepted a suggestion last week should still be able
  to see it existed.
* `InternalLink` is what actually got applied (or was independently detected
  as already present). Accepting a suggestion inserts one of these; nothing
  else does automatically, so "applied" always has a corresponding row here.

Every row carries `organization_id` even though it is derivable through
`website_id`, for the same reason as insights.py: scoping.py filters on
organization_id directly and a join per guard would be wasted work on the
hot path.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

# --------------------------------------------------------------- vocabularies
# Module constants rather than DB enums: adding a reason or status should not
# require a migration, and Alembic autogenerate handles native enums badly.

SUGGESTION_STATUSES = ("suggested", "accepted", "rejected", "applied", "expired")

SUGGESTION_REASONS = (
    "keyword_overlap",      # source and target share meaningful, rare-enough terms
    "same_category",        # both articles sit in the same taxonomy/category
    "orphan_target",        # target has no inbound internal links at all yet
    "topic_cluster",        # both articles cluster around the same head keyword
    "anchor_opportunity",   # target's title/keyword appears verbatim in source text
)

# Statuses a suggestion can no longer move out of via a human decision. The
# detector may still resurrect an "expired" row back to "suggested" if the
# same finding reproduces; a decided one is left alone.
SUGGESTION_DECIDED_STATUSES = ("accepted", "rejected", "applied")


class InternalLinkSuggestion(BaseModel):
    """One detector finding: "article A should link to article B"."""

    __tablename__ = "internal_link_suggestions"
    __table_args__ = (
        # Primary list query: this website, this status, best first.
        Index("idx_ils_website_status", "website_id", "status"),
        Index("idx_ils_org_status", "organization_id", "status"),
        Index("idx_ils_source", "source_article_id"),
        Index("idx_ils_target", "target_article_id"),
        # Dedup guard: a re-run of the detector updates instead of duplicating.
        Index("idx_ils_fingerprint", "website_id", "fingerprint", unique=True),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    website_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id"), nullable=False, index=True
    )

    source_article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_articles.id"), nullable=False
    )
    target_article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_articles.id"), nullable=False
    )

    anchor_text: Mapped[str] = mapped_column(String(500), nullable=False)
    context_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 0-100, computed from score_breakdown. See internal_link_service for the
    # exact weight table; kept arithmetic and inspectable, not a learned score.
    relevance_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    score_breakdown: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="suggested", nullable=False)
    reason: Mapped[str] = mapped_column(String(30), nullable=False)

    # Stable hash of (source, target, reason) so a re-run updates in place.
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class InternalLink(BaseModel):
    """A link that actually exists (or was applied) between two articles."""

    __tablename__ = "internal_links"
    __table_args__ = (
        Index("idx_il_website", "website_id"),
        Index("idx_il_org", "organization_id"),
        Index("idx_il_source", "source_article_id"),
        Index("idx_il_target", "target_article_id"),
        # A given source can link to a given target more than once with a
        # different anchor, but not twice with the same one — that would be
        # the same link recorded twice.
        Index(
            "idx_il_source_target_anchor",
            "source_article_id",
            "target_article_id",
            "anchor_text",
            unique=True,
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    website_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id"), nullable=False, index=True
    )

    source_article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_articles.id"), nullable=False
    )
    target_article_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_articles.id"), nullable=False
    )

    anchor_text: Mapped[str] = mapped_column(String(500), nullable=False)
    target_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Null when the link was recorded some other way than accepting a suggestion.
    suggestion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("internal_link_suggestions.id"), nullable=True
    )

    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "InternalLinkSuggestion",
    "InternalLink",
    "SUGGESTION_STATUSES",
    "SUGGESTION_REASONS",
    "SUGGESTION_DECIDED_STATUSES",
]
