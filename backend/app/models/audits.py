from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    String, Text, Boolean, Integer, Float, ForeignKey, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

# Added for the Agent Activity Center (migration 0015). Kept as separate import
# lines so the original imports above stay byte-identical.
from sqlalchemy import Numeric
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from app.models.base import BaseModel


# --------------------------------------------------- agent log vocabularies
# Module constants rather than DB enums: a new agent family should not need a
# migration, and Alembic autogenerate handles native enums badly. Mirrors the
# convention already used in models/insights.py and models/approvals.py.

AGENT_TYPES = (
    "audit",        # technical crawl / scoring agents
    "strategy",     # strategy architect
    "brief",        # content brief generation
    "article",      # article drafting / rewriting
    "opportunity",  # opportunity detectors
    "alert",        # alert detectors
    "automation",   # workflow / n8n driven runs
    "other",        # anything not yet classified
)

AGENT_STATUSES = ("success", "failed", "partial", "skipped")

# Entity kinds an agent run can point back at, for the "what did this produce"
# link in the activity table.
AGENT_RELATED_ENTITY_TYPES = (
    "seo_audit",
    "ai_seo_strategy",
    "content_brief",
    "content_article",
    "opportunity",
    "alert",
    "automation_workflow",
)


class SeoAudit(BaseModel):
    """SEO Technical Audit session for a website."""
    __tablename__ = "seo_audits"

    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, running, completed, failed
    overall_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    technical_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    content_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ux_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    # Relationships
    issues: Mapped[list["SeoAuditIssue"]] = relationship(
        "SeoAuditIssue",
        back_populates="audit",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_seo_audit_website_status", "website_id", "status"),
    )


class SeoAuditIssue(BaseModel):
    """Specific SEO issues detected during an audit."""
    __tablename__ = "seo_audit_issues"

    audit_id: Mapped[UUID] = mapped_column(
        ForeignKey("seo_audits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # technical, meta, indexing, speed, content
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # critical, warning, info
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    # Raw Lighthouse evidence: display_value, affected items (URLs/snippets),
    # strategy and doc link. JSON so the UI can render exactly what Google
    # produced without another request.
    details: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    audit: Mapped["SeoAudit"] = relationship("SeoAudit", back_populates="issues")

    __table_args__ = (
        Index("idx_audit_issue_severity", "website_id", "severity", "is_resolved"),
    )


class AiSeoStrategy(BaseModel):
    """AI-generated SEO Strategic Plan for a website."""
    __tablename__ = "ai_seo_strategies"

    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    target_audience: Mapped[str | None] = mapped_column(String(500), nullable=True)
    keyword_clusters: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    content_gaps: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    action_items: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    provider_used: Mapped[str] = mapped_column(String(50), default="openai", nullable=False)

    __table_args__ = (
        Index("idx_ai_strategy_website", "website_id"),
    )


class AiAgentLog(BaseModel):
    """Log of AI agent executions and token usage.

    Extended by migration 0015 into a real audit trail: before that the row said
    an agent ran and how many tokens it burned, but not what it decided, how
    confident it was, what it was handed, what it produced, or what it cost.

    Every column added in 0015 is nullable (or has a server_default) because the
    table already had rows in production; a NOT NULL column with no default
    cannot be satisfied by an existing row.
    """
    __tablename__ = "ai_agent_logs"

    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    action_taken: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)

    # --- added in 0015 -----------------------------------------------------
    # Denormalised tenant. Nullable: rows written before 0015 have no value and
    # are backfillable from websites. Readers must cope with NULL (the service
    # resolves the org through Website instead of trusting this column alone).
    organization_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=True,
        index=True,
    )

    # Coarse family of the agent, for grouping the activity feed. Defaults to
    # "other" so legacy rows land in a valid bucket instead of NULL.
    agent_type: Mapped[str] = mapped_column(
        String(50), server_default="other", default="other", nullable=False
    )

    # 0-100. NULL when the agent reported no confidence at all, which is
    # different from "reported zero confidence".
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # What the agent decided, in Persian, for the human reading the feed.
    decision_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The audit trail proper: what went in, what came out.
    input_context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Six decimal places: a single cheap call can cost well under a cent and
    # rounding it to 2dp would report every such run as $0.00.
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)

    # Loose back-pointer to whatever the run produced. Deliberately not an FK:
    # it spans several tables and a hard FK would block deleting the target.
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index("idx_ai_agent_log_website", "website_id"),
        # Org-level feed: this tenant, newest first.
        Index("idx_ai_agent_log_org_created", "organization_id", "created_at"),
        # Per-website drill-down grouped by agent.
        Index("idx_ai_agent_log_website_agent", "website_id", "agent_name"),
        # Failure filter on the activity page.
        Index("idx_ai_agent_log_status", "status"),
    )
