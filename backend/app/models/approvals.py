"""Approval queue — human gate before high-risk actions are executed.

Three categories of actions require approval:
  * content   – publishing a sensitive article, bulk content operations
  * structural – site structure changes, category reorganisation
  * ai_action  – high-risk AI-driven operations (auto-publish, bulk rewrite)

The lifecycle is linear:
  pending → approved  (reviewer action, then the requester's task runs)
           → rejected  (reviewer action, task is cancelled)
           → cancelled  (requester withdraws before a decision)
  approved → executed  (background task marks it done)
           → failed     (background task errored)

`payload` carries everything the executing service needs to carry out the
action: it is written at request time and must not be changed after that.
`reviewer_comment` is the only field the reviewer may write beyond the status.

Every row carries `organization_id` at the top level (not derivable through a
join) because the approval list endpoint is org-scoped and a join would be
wasted on every page load.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


# ---------------------------------------------------------------- vocabularies
# Module constants, not DB enums: adding an action type needs no migration.

APPROVAL_ACTION_TYPES = (
    # content
    "publish_article",
    "bulk_publish",
    "bulk_delete_content",
    # structural
    "restructure_categories",
    "change_site_settings",
    "delete_website",
    # ai_action
    "ai_auto_publish",
    "ai_bulk_rewrite",
    "ai_keyword_campaign",
)

APPROVAL_STATUSES = (
    "pending",    # awaiting reviewer decision
    "approved",   # reviewer approved; task may now execute
    "rejected",   # reviewer rejected; task must not execute
    "cancelled",  # requester withdrew
    "executed",   # background task completed successfully
    "failed",     # background task errored after approval
)

APPROVAL_PRIORITIES = ("low", "normal", "high", "urgent")

APPROVAL_RISK_LEVELS = ("low", "medium", "high", "critical")

# Which broad category an action belongs to. The UI groups the queue by this and
# the notification body names it, so it is derived once here rather than
# re-mapped in every caller.
APPROVAL_ACTION_CATEGORIES = {
    "publish_article": "content",
    "bulk_publish": "content",
    "bulk_delete_content": "content",
    "restructure_categories": "structural",
    "change_site_settings": "structural",
    "delete_website": "structural",
    "ai_auto_publish": "ai_action",
    "ai_bulk_rewrite": "ai_action",
    "ai_keyword_campaign": "ai_action",
}

# Statuses a request can no longer move out of. The service refuses a second
# decision on any of these, so an approve/approve race cannot execute twice.
APPROVAL_TERMINAL_STATUSES = ("rejected", "cancelled", "executed", "failed")


class ApprovalRequest(BaseModel):
    """One item in the approval queue."""

    __tablename__ = "approval_requests"
    __table_args__ = (
        # Primary list query: pending items for this org, newest first.
        Index("idx_approval_org_status", "organization_id", "status"),
        # Secondary: what a specific reviewer was asked to look at.
        Index("idx_approval_reviewer", "reviewer_id", "status"),
        # Requester's own history.
        Index("idx_approval_requester", "requester_id", "status"),
        # Optional: one pending request per (website, action_type, subject).
        # Prevents the same AI campaign from being queued twice.
        # The index is partial (status = 'pending') at the DB level, but
        # SQLAlchemy Core can't express partial unique indexes inline; we
        # enforce the soft constraint in the service layer instead.
        Index("idx_approval_website_type", "website_id", "action_type"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    # Null allowed: some org-level actions are not tied to a specific website.
    website_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id"), nullable=True, index=True
    )

    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Who asked for approval.
    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # Specific reviewer requested. Null = any reviewer in the org may decide.
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # Frozen at request time. The executing service reads this to know what to do.
    payload: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    # Risk metadata: lets the UI show a warning badge without parsing payload.
    risk_level: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    affected_items_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Reviewer decision fields (null until a decision is made).
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Execution tracking (null until after approval).
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    execution_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    execution_result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Hard deadline: if not decided by this time, treat as auto-rejected.
    # Null = no deadline.
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Links back to the object that triggered this request.
    related_article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_articles.id"), nullable=True
    )
    related_brief_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_briefs.id"), nullable=True
    )
