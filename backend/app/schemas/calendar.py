"""Schemas for the content calendar.

Write models are narrow on purpose. `organization_id` always comes from the
authenticated membership (never the body) and `published_at` / `source` are
system-set: `published_at` is stamped by `move_entry` when a slot reaches
`published`, and `source` is `manual` for anything created through this API —
only `auto_schedule_from_opportunities` may write `ai_auto`. If a client could
set either directly, a human-created slot could impersonate an AI one (or
fake a publish timestamp that never happened).
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.calendar import (
    CALENDAR_ENTRY_PRIORITIES,
    CALENDAR_ENTRY_SOURCES,
    CALENDAR_ENTRY_STATUSES,
)


# -------------------------------------------------------------------- read model

class CalendarEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    website_id: UUID
    title: str
    brief_id: UUID | None = None
    article_id: UUID | None = None
    opportunity_id: UUID | None = None
    status: str
    priority: str
    source: str
    scheduled_for: datetime | None = None
    deadline: datetime | None = None
    published_at: datetime | None = None
    assigned_to: UUID | None = None
    target_keyword: str | None = None
    notes: str | None = None
    details: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------- write models

class CalendarEntryCreate(BaseModel):
    """Plan a new slot. `website_id` comes from the query/body, not inferred."""

    website_id: UUID
    title: str = Field(min_length=3, max_length=500)
    brief_id: UUID | None = None
    article_id: UUID | None = None
    opportunity_id: UUID | None = None
    status: str = "planned"
    priority: str = "normal"
    scheduled_for: datetime | None = None
    deadline: datetime | None = None
    assigned_to: UUID | None = None
    target_keyword: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)
    details: dict = Field(default_factory=dict)

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: str) -> str:
        if v not in CALENDAR_ENTRY_STATUSES:
            raise ValueError(f"status must be one of {sorted(CALENDAR_ENTRY_STATUSES)}")
        return v

    @field_validator("priority")
    @classmethod
    def _known_priority(cls, v: str) -> str:
        if v not in CALENDAR_ENTRY_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(CALENDAR_ENTRY_PRIORITIES)}")
        return v


class CalendarEntryUpdate(BaseModel):
    """Edit an existing slot. Every field optional so a PATCH can be partial."""

    title: str | None = Field(default=None, min_length=3, max_length=500)
    brief_id: UUID | None = None
    article_id: UUID | None = None
    opportunity_id: UUID | None = None
    status: str | None = None
    priority: str | None = None
    scheduled_for: datetime | None = None
    deadline: datetime | None = None
    assigned_to: UUID | None = None
    target_keyword: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=5000)
    details: dict | None = None

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: str | None) -> str | None:
        if v is not None and v not in CALENDAR_ENTRY_STATUSES:
            raise ValueError(f"status must be one of {sorted(CALENDAR_ENTRY_STATUSES)}")
        return v

    @field_validator("priority")
    @classmethod
    def _known_priority(cls, v: str | None) -> str | None:
        if v is not None and v not in CALENDAR_ENTRY_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(CALENDAR_ENTRY_PRIORITIES)}")
        return v


class CalendarEntryMove(BaseModel):
    """What a drag on the board or calendar grid does: change date and/or status."""

    scheduled_for: datetime | None = None
    status: str | None = None

    @field_validator("status")
    @classmethod
    def _known_status(cls, v: str | None) -> str | None:
        if v is not None and v not in CALENDAR_ENTRY_STATUSES:
            raise ValueError(f"status must be one of {sorted(CALENDAR_ENTRY_STATUSES)}")
        return v


# ---------------------------------------------------------------- aggregate views

class CalendarDayBucket(BaseModel):
    """One calendar day and the entries scheduled on it."""

    date: str  # ISO date string, e.g. "2026-08-14"
    entries: list[CalendarEntryRead] = Field(default_factory=list)
    count: int = 0


class CalendarMonthView(BaseModel):
    website_id: UUID
    year: int
    month: int
    range_start: datetime
    range_end: datetime
    days: list[CalendarDayBucket] = Field(default_factory=list)


class CalendarWeekView(BaseModel):
    website_id: UUID
    range_start: datetime
    range_end: datetime
    days: list[CalendarDayBucket] = Field(default_factory=list)


class CalendarBoardView(BaseModel):
    """Kanban columns, keyed by status in CALENDAR_ENTRY_STATUSES order."""

    columns: dict[str, list[CalendarEntryRead]] = Field(default_factory=dict)


class CalendarAutoScheduleRequest(BaseModel):
    """Trigger the AI scheduler for one website."""

    start_from: datetime | None = None
    max_entries: int = Field(default=10, ge=1, le=100)


class CalendarAutoScheduleResult(BaseModel):
    website_id: UUID
    created: int
    skipped: int
    # Open opportunities still without a slot after this run (they stay for the
    # next click - the scheduler adds at most max_entries per call).
    remaining_open: int = 0
    # True when the website already holds >= max_entries outstanding AI slots,
    # so this run deliberately created nothing instead of flooding the calendar.
    throttled: bool = False
    scheduled_through: datetime | None = None


class CalendarSummary(BaseModel):
    by_status: dict[str, int] = Field(default_factory=dict)
    overdue: int = 0
    due_this_week: int = 0
    unassigned: int = 0


__all__ = [
    "CalendarEntryRead",
    "CalendarEntryCreate",
    "CalendarEntryUpdate",
    "CalendarEntryMove",
    "CalendarDayBucket",
    "CalendarMonthView",
    "CalendarWeekView",
    "CalendarBoardView",
    "CalendarAutoScheduleRequest",
    "CalendarAutoScheduleResult",
    "CalendarSummary",
    "CALENDAR_ENTRY_STATUSES",
    "CALENDAR_ENTRY_PRIORITIES",
    "CALENDAR_ENTRY_SOURCES",
]
