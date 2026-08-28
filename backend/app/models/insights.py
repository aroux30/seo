"""Opportunities, Alerts and Notifications — the "what should I do next" layer.

These three tables were named all over the spec and the UI strings but never
existed in the database. They share a file because they share a lifecycle:
the detector writes an Opportunity or an Alert, the dispatcher turns it into
Notifications, and the user resolves it back here.

Every row carries organization_id even where it is derivable through
website_id, because scoping.py filters on organization_id directly and a join
per guard would be wasted work on the hot path.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    String, Boolean, DateTime, Text, ForeignKey, Index, Numeric, Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, BaseModel


# --------------------------------------------------------------- vocabularies
# Kept as module constants rather than DB enums: adding a detector type should
# not require a migration, and Alembic autogenerate handles native enums badly.

OPPORTUNITY_TYPES = (
    "low_ctr_high_impressions",   # ranks fine, nobody clicks -> title/meta work
    "striking_distance",          # position 4-15, small push wins page 1
    "rising_query",               # impressions trending up, not yet optimised
    "content_gap",                # query has impressions but no matching page
    "decaying_content",           # was performing, now sliding
    "cannibalization",            # several pages competing for one query
)

OPPORTUNITY_STATUSES = ("open", "in_progress", "actioned", "dismissed", "expired")

ALERT_TYPES = (
    "traffic_drop",
    "ranking_drop",
    "ctr_drop",
    "content_decay",
    "gsc_sync_failure",
    "audit_score_drop",
    "indexing_issue",
)

ALERT_SEVERITIES = ("info", "warning", "critical")
ALERT_STATUSES = ("active", "acknowledged", "resolved", "muted")

NOTIFICATION_CHANNELS = ("dashboard", "telegram", "email", "webhook")
NOTIFICATION_STATUSES = ("pending", "sent", "failed", "skipped")


class Opportunity(BaseModel):
    """A detected, actionable SEO win with an estimated impact."""

    __tablename__ = "opportunities"
    __table_args__ = (
        # The list view is always "this website, still open, best first".
        Index("idx_opp_website_status", "website_id", "status"),
        Index("idx_opp_org_status", "organization_id", "status"),
        Index("idx_opp_type", "opportunity_type"),
        # Lets the detector skip re-inserting the same finding cheaply.
        Index("idx_opp_fingerprint", "website_id", "fingerprint", unique=True),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    website_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id"), nullable=False, index=True
    )

    opportunity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # What the finding is about. Query and URL are free text because GSC is the
    # source and it does not hand out ids.
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    keyword_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("keywords.id"), nullable=True
    )

    # Scoring. priority_score is what the UI sorts on; the rest is evidence so
    # the number is auditable instead of magic.
    priority_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    estimated_traffic_gain: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_position: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    current_clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_ctr: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)

    # Stable hash of (type + subject) so a re-run updates instead of duplicating.
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    # Free-form detector output: thresholds used, comparison window, suggestions.
    details: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actioned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    dismiss_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Set when acting on the opportunity spawned a brief/article.
    linked_brief_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_briefs.id"), nullable=True
    )


class Alert(BaseModel):
    """Something went wrong and a human should know."""

    __tablename__ = "alerts"
    __table_args__ = (
        Index("idx_alert_website_status", "website_id", "status"),
        Index("idx_alert_org_status", "organization_id", "status"),
        Index("idx_alert_severity", "severity"),
        # Dedup guard: one active alert per (website, type, subject).
        Index("idx_alert_fingerprint", "website_id", "fingerprint", unique=True),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    website_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id"), nullable=False, index=True
    )

    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="warning", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # The measurement that tripped the rule. Numeric so the UI can render a
    # delta without re-deriving it from details.
    metric_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    current_value: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    previous_value: Mapped[float | None] = mapped_column(Numeric(14, 4), nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    # How many times the detector saw this same condition. Lets the dispatcher
    # notify once and then stay quiet.
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Suppress re-notification until this time even if still failing.
    muted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Notification(BaseModel):
    """One delivery attempt of one message on one channel.

    Rows are kept after sending: the dashboard bell reads them, and a failed
    telegram send needs a record to retry against.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        # Bell icon query: mine, unread, newest first.
        Index("idx_notif_user_read", "user_id", "read_at"),
        Index("idx_notif_org", "organization_id"),
        # Worker query: what still needs sending.
        Index("idx_notif_status_channel", "status", "channel"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    # Null for org-wide broadcasts that are not addressed to one person.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    website_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id"), nullable=True
    )

    channel: Mapped[str] = mapped_column(String(20), default="dashboard", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    # Groups the message type, e.g. "alert.traffic_drop", "opportunity.new".
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Where clicking it should land, relative to the frontend root.
    action_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=True
    )

    payload: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
