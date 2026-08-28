"""Schemas for the Opportunities / Alerts / Notifications layer.

Read models mirror the ORM rows; the Numeric columns come back as Decimal from
asyncpg, so they are declared `float | None` and pydantic coerces them. Write
models are deliberately narrow: a client may only change lifecycle fields
(dismiss, acknowledge, resolve, mark read). Everything else is detector output
and must not be user-editable, otherwise the fingerprint dedup breaks.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, computed_field

from app.models.insights import (
    ALERT_SEVERITIES,
    ALERT_STATUSES,
    NOTIFICATION_CHANNELS,
    OPPORTUNITY_STATUSES,
    OPPORTUNITY_TYPES,
)


# --------------------------------------------------------------- opportunities

class OpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    website_id: UUID
    opportunity_type: str
    status: str
    title: str
    description: str | None = None
    query: str | None = None
    page_url: str | None = None
    keyword_id: UUID | None = None
    priority_score: int
    estimated_traffic_gain: int
    current_position: float | None = None
    current_clicks: int
    current_impressions: int
    current_ctr: float | None = None
    details: dict = Field(default_factory=dict)
    recommended_action: str | None = None
    detected_at: datetime
    last_seen_at: datetime | None = None
    actioned_at: datetime | None = None
    dismissed_at: datetime | None = None
    dismiss_reason: str | None = None
    linked_brief_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class OpportunityStatusUpdate(BaseModel):
    """Move an opportunity along its lifecycle."""
    status: str
    dismiss_reason: str | None = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: str) -> str:
        # Only human-driven transitions are accepted here. "expired" is set by
        # the detector when a finding stops reproducing, never by a client.
        allowed = {"open", "in_progress", "actioned", "dismissed"}
        if v not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")
        return v


class OpportunityDetectRequest(BaseModel):
    """Run the detectors for one website over a lookback window."""
    lookback_days: int = Field(default=28, ge=7, le=180)
    min_impressions: int = Field(default=1, ge=1, le=100_000)


class OpportunityDetectResult(BaseModel):
    website_id: UUID
    scanned_queries: int
    scanned_pages: int
    created: int
    updated: int
    expired: int
    by_type: dict[str, int] = Field(default_factory=dict)


class OpportunitySummary(BaseModel):
    total_open: int
    by_type: dict[str, int] = Field(default_factory=dict)
    total_estimated_traffic_gain: int = 0
    top: list[OpportunityRead] = Field(default_factory=list)


# ---------------------------------------------------------------------- alerts

class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    website_id: UUID
    alert_type: str
    severity: str
    status: str
    title: str
    message: str
    metric_name: str | None = None
    current_value: float | None = None
    previous_value: float | None = None
    change_percent: float | None = None
    entity_type: str | None = None
    entity_id: UUID | None = None
    details: dict = Field(default_factory=dict)
    occurrence_count: int
    triggered_at: datetime
    last_seen_at: datetime | None = None
    acknowledged_at: datetime | None = None
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    muted_until: datetime | None = None
    notified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AlertStatusUpdate(BaseModel):
    status: str
    resolution_note: str | None = Field(default=None, max_length=1000)
    mute_hours: int | None = Field(default=None, ge=1, le=720)

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: str) -> str:
        if v not in ALERT_STATUSES:
            raise ValueError(f"status must be one of {sorted(ALERT_STATUSES)}")
        return v


class AlertDetectRequest(BaseModel):
    """Compare the recent window against the one before it."""
    window_days: int = Field(default=7, ge=1, le=90)
    drop_threshold_percent: float = Field(default=20.0, ge=1.0, le=99.0)


class AlertDetectResult(BaseModel):
    website_id: UUID
    created: int
    updated: int
    resolved: int
    by_type: dict[str, int] = Field(default_factory=dict)
    skipped_reason: str | None = None


class AlertSummary(BaseModel):
    """Active-alert counts for the badge, one organization.

    `active` is the total and the three named severities are broken out because
    the header badge colours itself on `critical` alone without walking the map.
    `by_severity` is kept as well so a new severity added to ALERT_SEVERITIES
    still surfaces without a schema change.
    """
    active: int = 0
    critical: int = 0
    warning: int = 0
    info: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)


# --------------------------------------------------------------- notifications

class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    user_id: UUID | None = None
    website_id: UUID | None = None
    channel: str
    status: str
    event_type: str
    title: str
    body: str | None = None
    action_url: str | None = None
    alert_id: UUID | None = None
    opportunity_id: UUID | None = None
    payload: dict = Field(default_factory=dict)
    read_at: datetime | None = None
    sent_at: datetime | None = None
    failed_at: datetime | None = None
    error_message: str | None = None
    attempt_count: int
    created_at: datetime

    @computed_field
    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    @computed_field
    @property
    def type(self) -> str:
        return self.event_type




class NotificationMarkReadRequest(BaseModel):
    """Empty body marks everything unread as read for the caller."""
    notification_ids: list[UUID] | None = None


class NotificationMarkReadResult(BaseModel):
    marked: int


class UnreadCountResult(BaseModel):
    unread: int


# ------------------------------------------------------------------- dashboard

class DashboardWebsiteRow(BaseModel):
    website_id: UUID
    name: str
    domain: str
    clicks: int
    impressions: int
    ctr: float
    avg_position: float
    health_score: int
    open_alerts: int
    open_opportunities: int


class DashboardSummary(BaseModel):
    """Everything the dashboard home needs in one round trip."""
    organization_id: UUID
    website_count: int
    project_count: int
    health_score: int
    total_clicks: int
    total_impressions: int
    avg_ctr: float
    avg_position: float
    clicks_change_percent: float | None = None
    impressions_change_percent: float | None = None
    active_alerts: int
    critical_alerts: int
    open_opportunities: int
    estimated_traffic_gain: int
    published_articles: int
    draft_articles: int
    last_audit_score: int | None = None
    last_gsc_sync_at: datetime | None = None
    websites: list[DashboardWebsiteRow] = Field(default_factory=list)


__all__ = [
    "OpportunityRead",
    "OpportunityStatusUpdate",
    "OpportunityDetectRequest",
    "OpportunityDetectResult",
    "OpportunitySummary",
    "AlertRead",
    "AlertStatusUpdate",
    "AlertDetectRequest",
    "AlertDetectResult",
    "AlertSummary",
    "NotificationRead",
    "NotificationMarkReadRequest",
    "NotificationMarkReadResult",
    "UnreadCountResult",
    "DashboardWebsiteRow",
    "DashboardSummary",
    "OPPORTUNITY_TYPES",
    "OPPORTUNITY_STATUSES",
    "ALERT_SEVERITIES",
    "NOTIFICATION_CHANNELS",
]
