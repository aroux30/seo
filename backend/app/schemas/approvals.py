"""Schemas for the approval queue.

Write models are split by actor, because the two sides of an approval must not
be able to touch each other's fields:

* `ApprovalCreate` — the requester. May set what the action is and what it
  affects, but not `status`, `decided_by`, or any execution field. If a client
  could post `status="approved"` the whole gate would be bypassable in one call.
* `ApprovalDecision` — the reviewer. May only approve or reject and leave a
  comment. `payload` is deliberately absent: the thing being approved must be
  exactly the thing that was requested, otherwise the reviewer signs off on one
  action and a different one executes.

`payload` is validated for size rather than shape. Each action_type carries its
own contract and the executing service checks it; a schema-level union over
nine action types would have to change every time a tenth is added.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.approvals import (
    APPROVAL_ACTION_TYPES,
    APPROVAL_PRIORITIES,
    APPROVAL_RISK_LEVELS,
    APPROVAL_STATUSES,
)


# ------------------------------------------------------------------- read model

class ApprovalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    website_id: UUID | None = None
    action_type: str
    status: str
    priority: str
    title: str
    description: str | None = None
    requester_id: UUID
    reviewer_id: UUID | None = None
    payload: dict = Field(default_factory=dict)
    risk_level: str
    affected_items_count: int
    decided_by: UUID | None = None
    decided_at: datetime | None = None
    reviewer_comment: str | None = None
    executed_at: datetime | None = None
    execution_error: str | None = None
    execution_result: dict | None = None
    expires_at: datetime | None = None
    related_article_id: UUID | None = None
    related_brief_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ApprovalReadWithNames(ApprovalRead):
    """List view rows, enriched with display names.

    The queue screen shows "who asked" and "who decided" on every row. Resolving
    those two ids per row in the frontend would be N+1 requests, so the service
    joins them once and fills these in.
    """
    requester_name: str | None = None
    requester_email: str | None = None
    reviewer_name: str | None = None
    decided_by_name: str | None = None
    website_name: str | None = None


# ------------------------------------------------------------- requester writes

class ApprovalCreate(BaseModel):
    """Queue a new approval request.

    Note what is *not* here: status, decided_*, executed_*, execution_result.
    Those belong to the reviewer and the executor respectively.
    """
    action_type: str
    title: str = Field(min_length=3, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    website_id: UUID | None = None
    reviewer_id: UUID | None = None
    priority: str = "normal"
    risk_level: str = "medium"
    affected_items_count: int = Field(default=1, ge=0, le=1_000_000)
    payload: dict = Field(default_factory=dict)
    expires_in_hours: int | None = Field(default=None, ge=1, le=8760)
    related_article_id: UUID | None = None
    related_brief_id: UUID | None = None

    @field_validator("action_type")
    @classmethod
    def _known_action(cls, v: str) -> str:
        if v not in APPROVAL_ACTION_TYPES:
            raise ValueError(
                f"action_type must be one of {sorted(APPROVAL_ACTION_TYPES)}"
            )
        return v

    @field_validator("priority")
    @classmethod
    def _known_priority(cls, v: str) -> str:
        if v not in APPROVAL_PRIORITIES:
            raise ValueError(f"priority must be one of {sorted(APPROVAL_PRIORITIES)}")
        return v

    @field_validator("risk_level")
    @classmethod
    def _known_risk(cls, v: str) -> str:
        if v not in APPROVAL_RISK_LEVELS:
            raise ValueError(f"risk_level must be one of {sorted(APPROVAL_RISK_LEVELS)}")
        return v

    @field_validator("payload")
    @classmethod
    def _bounded_payload(cls, v: dict) -> dict:
        # Guard against a client stuffing an article body (or worse) into a
        # JSONB column that every queue page load then has to read back.
        if len(v) > 50:
            raise ValueError("payload must not exceed 50 top-level keys")
        return v


# -------------------------------------------------------------- reviewer writes

class ApprovalDecision(BaseModel):
    """Approve or reject a pending request.

    `decision` is restricted to the two reviewer-reachable outcomes. "cancelled"
    is the requester's verb and has its own endpoint; "executed"/"failed" are
    written by the executor and are never client-settable.
    """
    decision: str
    reviewer_comment: str | None = Field(default=None, max_length=2000)

    @field_validator("decision")
    @classmethod
    def _reviewer_decision_only(cls, v: str) -> str:
        allowed = {"approved", "rejected"}
        if v not in allowed:
            raise ValueError(f"decision must be one of {sorted(allowed)}")
        return v


class ApprovalCancel(BaseModel):
    """Requester withdraws their own pending request."""
    reason: str | None = Field(default=None, max_length=1000)


# ---------------------------------------------------------------- aggregate views

class ApprovalSummary(BaseModel):
    """Counts for the queue badge and the dashboard card."""
    pending: int = 0
    pending_urgent: int = 0
    pending_high_risk: int = 0
    approved_awaiting_execution: int = 0
    expiring_soon: int = 0
    by_action_type: dict[str, int] = Field(default_factory=dict)
    by_priority: dict[str, int] = Field(default_factory=dict)


class ApprovalExpireResult(BaseModel):
    """Outcome of the periodic sweep over overdue requests."""
    expired: int = 0


__all__ = [
    "ApprovalRead",
    "ApprovalReadWithNames",
    "ApprovalCreate",
    "ApprovalDecision",
    "ApprovalCancel",
    "ApprovalSummary",
    "ApprovalExpireResult",
    "APPROVAL_ACTION_TYPES",
    "APPROVAL_STATUSES",
    "APPROVAL_PRIORITIES",
    "APPROVAL_RISK_LEVELS",
]
