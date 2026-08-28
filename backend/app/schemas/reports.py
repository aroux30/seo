"""Schemas for the Reports module.

`ReportRead` carries the full frozen `content`/`metrics_snapshot` payload;
`ReportListItem` deliberately omits both — the list endpoint returns every
report in an org and shipping the whole rendered document per row would make
that response scale with total report volume instead of report *count*.

`PublicReportRead` is what an unauthenticated visitor with a share link sees.
It is built from scratch rather than by subclassing `ReportRead`, so that
adding a field to the internal schema can never silently leak it through the
public one.
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.reports import REPORT_STATUSES, REPORT_TYPES


# ------------------------------------------------------------------- reports

class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    website_id: UUID | None = None
    report_type: str
    status: str
    title: str
    period_start: date
    period_end: date
    generated_by: UUID | None = None
    generated_at: datetime | None = None
    content: dict = Field(default_factory=dict)
    metrics_snapshot: dict = Field(default_factory=dict)
    share_enabled: bool
    share_expires_at: datetime | None = None
    view_count: int
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ReportListItem(BaseModel):
    """Lightweight row for the list view. No `content` — see module docstring."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    website_id: UUID | None = None
    report_type: str
    status: str
    title: str
    period_start: date
    period_end: date
    generated_at: datetime | None = None
    metrics_snapshot: dict = Field(default_factory=dict)
    share_enabled: bool
    view_count: int
    created_at: datetime


class ReportGenerateRequest(BaseModel):
    report_type: str
    title: str | None = Field(default=None, max_length=500)
    period_start: date
    period_end: date
    website_id: UUID | None = None

    @field_validator("report_type")
    @classmethod
    def _known_type(cls, v: str) -> str:
        if v not in REPORT_TYPES:
            raise ValueError(f"report_type must be one of {sorted(REPORT_TYPES)}")
        return v

    @model_validator(mode="after")
    def _period_order(self) -> "ReportGenerateRequest":
        if self.period_start > self.period_end:
            raise ValueError("period_start must be on or before period_end")
        return self


class ReportSummaryTypeCount(BaseModel):
    report_type: str
    count: int
    latest_report_id: UUID | None = None
    latest_generated_at: datetime | None = None


class ReportSummary(BaseModel):
    total: int = 0
    by_type: list[ReportSummaryTypeCount] = Field(default_factory=list)
    ready: int = 0
    generating: int = 0
    failed: int = 0


class ReportTemplateSection(BaseModel):
    key: str
    title_fa: str


class ReportTemplate(BaseModel):
    """A predefined report shape.

    `sections` keys must match the section keys `report_service.generate_report`
    actually writes into `content["sections"]` for that `report_type` — this is
    the contract that keeps the template list truthful about what a generated
    report will contain.
    """

    report_type: str
    title_fa: str
    description_fa: str
    default_period_days: int
    sections: list[ReportTemplateSection] = Field(default_factory=list)


# ---------------------------------------------------------------------- share

class ReportShareRequest(BaseModel):
    """Optional TTL override for a newly enabled link, in days."""

    ttl_days: int | None = Field(default=None, ge=1, le=365)


class ReportShareResult(BaseModel):
    share_token: str
    share_enabled: bool
    share_expires_at: datetime | None = None


class PublicReportRead(BaseModel):
    """What an unauthenticated visitor sees through `/public/{share_token}`.

    Deliberately stripped of every internal id (report id, organization id,
    website id, generated_by) — only the rendered content and enough metadata
    to render a page is exposed.
    """

    report_type: str
    title: str
    period_start: date
    period_end: date
    generated_at: datetime | None = None
    content: dict = Field(default_factory=dict)
    metrics_snapshot: dict = Field(default_factory=dict)


__all__ = [
    "ReportRead",
    "ReportListItem",
    "ReportGenerateRequest",
    "ReportSummaryTypeCount",
    "ReportSummary",
    "ReportTemplateSection",
    "ReportTemplate",
    "ReportShareRequest",
    "ReportShareResult",
    "PublicReportRead",
    "REPORT_TYPES",
    "REPORT_STATUSES",
]
