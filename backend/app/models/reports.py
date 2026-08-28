"""Generated SEO reports — weekly / monthly / executive.

A report is a **frozen artefact**, not a saved query. `content` holds the fully
rendered payload assembled at generation time and nothing in this module ever
recomputes it. That is the whole point: a monthly report emailed to a client in
March must still show March's numbers when opened in June, even though GSC has
since backfilled, an audit has re-scored the site, and half the alerts have been
resolved. A "report" that re-queries on read is a dashboard with a date picker.

`website_id` is nullable. Null means an organization-level report spanning every
live website, which is the shape the executive summary wants; a non-null value
scopes the whole payload to one site. `organization_id` is carried directly on
the row (not reached through the website join) because the scoping filter runs on
every read and an org-level report has no website to join through.

Share links live on this table rather than in a side table because a report has
at most one live link and revocation must be a single-row update. The security
properties the service depends on:

* `share_token` is unique and generated with `secrets.token_urlsafe(32)`, so it
  is unguessable — it is the *only* credential on the public endpoint.
* `share_enabled` defaults to False. Sharing is opt-in per report; a generated
  report is never publicly readable until somebody explicitly says so.
* `share_expires_at` bounds the exposure even if nobody remembers to revoke.

Revoking clears the token instead of only flipping the flag, so a leaked URL
cannot be reactivated by re-enabling sharing later.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel

# --------------------------------------------------------------- vocabularies
# Module constants, not DB enums: adding a report shape should not need a
# migration, and Alembic autogenerate handles native enums badly.

REPORT_TYPES = (
    "weekly",     # 7-day performance pulse
    "monthly",    # full month, deeper breakdown
    "executive",  # stakeholder-facing summary, light on detail
    "custom",     # arbitrary period chosen by the user
)

REPORT_STATUSES = (
    "pending",     # row created, generation not started
    "generating",  # assembling data
    "ready",       # `content` is populated and frozen
    "failed",      # generation raised; see error_message
)

# Statuses a report can no longer move out of by itself. The frontend hides the
# share controls on anything not `ready` — sharing a half-built payload would
# publish an empty document.
REPORT_TERMINAL_STATUSES = ("ready", "failed")

# Default lifetime for a newly enabled share link, in days. Bounded exposure by
# default: a link nobody revokes still stops working.
DEFAULT_SHARE_TTL_DAYS = 30


class Report(BaseModel):
    """One generated report, with its rendered payload frozen inside it."""

    __tablename__ = "reports"
    __table_args__ = (
        # The list view is always "this org, this type, most recent period".
        Index("idx_report_org_type_period", "organization_id", "report_type", "period_start"),
        Index("idx_report_org_status", "organization_id", "status"),
        Index("idx_report_website", "website_id"),
        # The public endpoint looks a report up by token alone, so this index is
        # on the hot path of an unauthenticated route. Unique because a token
        # collision would hand one tenant's report to another's link.
        Index("idx_report_share_token", "share_token", unique=True),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    # Null = organization-level report covering every live website.
    website_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id"), nullable=True
    )

    report_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)

    # The window the report describes. Dates, not timestamps: a report covers
    # calendar days, and GscDate.date_metric is a DATE.
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # The frozen document: sections, KPI blocks, per-website rows, notes about
    # missing sources. Never rewritten after status becomes `ready`.
    content: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    # Flat headline numbers lifted out of `content` so the list view and the CSV
    # export do not have to walk the nested payload.
    metrics_snapshot: Mapped[dict] = mapped_column(
        JSONB, server_default="{}", nullable=False
    )

    # ------------------------------------------------------------- sharing
    share_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    share_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    share_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = [
    "Report",
    "REPORT_TYPES",
    "REPORT_STATUSES",
    "REPORT_TERMINAL_STATUSES",
    "DEFAULT_SHARE_TTL_DAYS",
]
