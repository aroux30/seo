"""Content calendar — publish planning, deadlines, and kanban board.

A calendar entry is a *slot*, not a copy of an article. It may exist long
before any brief or article does (a human plans "we publish about X on the
14th") and it keeps its own `deadline` (when the author must finish) distinct
from `scheduled_for` (when it goes live) — those two dates answer different
questions and collapsing them would make "overdue" ambiguous.

`source` distinguishes a slot a human typed in from one
`auto_schedule_from_opportunities` created, so the UI can visually tell them
apart and so the auto-scheduler can skip opportunities it already scheduled
(idempotency is enforced by matching on `opportunity_id`, not by this column).

`organization_id` is denormalised onto the row (also present on `Website`)
because `app.core.scoping` and the board/summary queries filter on it directly;
joining through Website on every read would cost a join per row on the
hottest screen in this module.

Overdue is never stored. `deadline < now() and status != published` is
computed at read time in the service — a boolean flag would go stale the
instant the clock passes the deadline without a write happening.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel, SoftDeleteMixin

# ------------------------------------------------------------------ vocabularies
# Module-level tuples, not DB enums: adding a status/priority/source should not
# need a migration, and Alembic autogenerate handles native enums badly.

CALENDAR_ENTRY_STATUSES = (
    "planned",      # slot exists, nothing produced yet
    "in_progress",  # author is writing
    "ready",        # drafted, awaiting review/approval
    "scheduled",    # approved, waiting for scheduled_for to arrive
    "published",    # live
    "cancelled",    # slot withdrawn, will not publish
)

CALENDAR_ENTRY_PRIORITIES = ("low", "normal", "high", "urgent")

# manual: a human created/moved this slot. ai_auto: created by
# auto_schedule_from_opportunities. Kept separate from `status` because a
# machine-scheduled slot still goes through the same human statuses above.
CALENDAR_ENTRY_SOURCES = ("manual", "ai_auto")

# Statuses that still count as "on the calendar to do" for the summary's
# unassigned/overdue counters. Published and cancelled are terminal.
CALENDAR_OPEN_STATUSES = ("planned", "in_progress", "ready", "scheduled")


class ContentCalendarEntry(BaseModel, SoftDeleteMixin):
    """One planned publish slot on the content calendar.

    Soft-deleted rather than hard-deleted: a cancelled plan stays auditable, and
    the auto-scheduler's `opportunity_id` dedup needs to still see that an
    opportunity was once planned and then declined — a hard delete would make it
    eligible for re-scheduling on the very next run.
    """

    __tablename__ = "content_calendar_entries"
    __table_args__ = (
        # Month/week grid: "this website, entries in this date range".
        Index("idx_calendar_website_scheduled", "website_id", "scheduled_for"),
        # Kanban board: "this org, grouped by status".
        Index("idx_calendar_org_status", "organization_id", "status"),
        # "My queue": "entries assigned to me, by status".
        Index("idx_calendar_assignee_status", "assigned_to", "status"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    website_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("websites.id"), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)

    # A slot may exist before any content does; both links are optional and
    # independent (an article can exist without a brief having gone through
    # this calendar at all).
    brief_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_briefs.id"), nullable=True
    )
    article_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_articles.id"), nullable=True
    )
    # Set when the slot was generated from a detected opportunity. Also the
    # dedup key auto_schedule_from_opportunities matches on to stay idempotent.
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id"), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(String(20), default="planned", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)

    # Publish plan vs. author deadline: two different questions, two columns.
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    target_keyword: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    details: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)


__all__ = [
    "ContentCalendarEntry",
    "CALENDAR_ENTRY_STATUSES",
    "CALENDAR_ENTRY_PRIORITIES",
    "CALENDAR_ENTRY_SOURCES",
    "CALENDAR_OPEN_STATUSES",
]
