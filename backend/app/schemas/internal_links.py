"""Schemas for the Internal Links module.

Read models mirror the ORM rows and add the resolved article titles, because a
suggestion list is unreadable as two UUIDs — the service fills `source_title` /
`target_title` from the same article load the detector already did.

Write models are deliberately narrow: a client may only decide (accept/reject)
a suggestion. Everything else is detector output; letting a client edit the
anchor or the score would break fingerprint dedup and make `relevance_score`
un-auditable.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.internal_links import SUGGESTION_REASONS, SUGGESTION_STATUSES


# ----------------------------------------------------------------- suggestions

class InternalLinkSuggestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    website_id: UUID
    source_article_id: UUID
    target_article_id: UUID
    anchor_text: str
    context_snippet: str | None = None
    relevance_score: int
    score_breakdown: dict = Field(default_factory=dict)
    status: str
    reason: str
    fingerprint: str
    detected_at: datetime
    last_seen_at: datetime | None = None
    decided_at: datetime | None = None
    decided_by: UUID | None = None
    applied_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    # Resolved by the service so the UI never has to fetch articles separately.
    # Optional because a plain ORM row (e.g. straight after a decision) has no
    # titles attached yet.
    source_title: str | None = None
    target_title: str | None = None
    target_url: str | None = None


class SuggestionDecision(BaseModel):
    """Accept or reject a suggestion.

    "applied" and "expired" are not accepted from a client: "applied" is set by
    the service when accepting produces an InternalLink row, and "expired" is
    set by the detector when a finding stops reproducing.
    """

    status: str

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: str) -> str:
        allowed = {"accepted", "rejected", "suggested"}
        if v not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return v


class LinkDetectRequest(BaseModel):
    """Tuning knobs for one detector run over one website."""

    min_relevance: int = Field(default=30, ge=0, le=100)
    max_per_article: int = Field(default=5, ge=1, le=50)


class BulkSuggestionAction(BaseModel):
    """Bulk reject or hard-delete suggestions from the list UI.

    ids are re-verified against the org in the service, so stale rows in the
    client's selection are skipped rather than erroring the whole batch.
    """

    ids: list[UUID] = Field(..., min_length=1, max_length=200)
    action: str

    @field_validator("action")
    @classmethod
    def _known_action(cls, v: str) -> str:
        if v not in {"reject", "delete"}:
            raise ValueError("action must be reject or delete")
        return v


class LinkDetectResult(BaseModel):
    website_id: UUID
    scanned_articles: int
    created: int
    updated: int
    expired: int
    orphan_article_count: int = 0
    by_reason: dict[str, int] = Field(default_factory=dict)


class OrphanArticleRow(BaseModel):
    """An article with no inbound internal links — the highest-value fix."""

    article_id: UUID
    title: str
    slug: str | None = None
    published_url: str | None = None
    status: str | None = None


class SuggestionSummary(BaseModel):
    total_suggested: int = 0
    by_reason: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    orphan_article_count: int = 0
    avg_relevance: float = 0.0
    # Context for the UI's orphan callout. Capped by the service, because a
    # brand-new site where nothing is linked yet would otherwise return every
    # article it has.
    orphan_articles: list[OrphanArticleRow] = Field(default_factory=list)
    total_articles: int = 0
    active_link_count: int = 0


# ----------------------------------------------------------------------- links

class InternalLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    website_id: UUID
    source_article_id: UUID
    target_article_id: UUID
    anchor_text: str
    target_url: str | None = None
    is_active: bool
    suggestion_id: UUID | None = None
    first_seen_at: datetime
    last_verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    source_title: str | None = None
    target_title: str | None = None


__all__ = [
    "InternalLinkSuggestionRead",
    "SuggestionDecision",
    "LinkDetectRequest",
    "LinkDetectResult",
    "OrphanArticleRow",
    "SuggestionSummary",
    "InternalLinkRead",
    "SUGGESTION_STATUSES",
    "SUGGESTION_REASONS",
]
