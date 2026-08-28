"""Schemas for the Agent Activity Center.

Read models mirror `AiAgentLog` after migration 0015. The Numeric columns
(`confidence_score`, `estimated_cost_usd`) come back from asyncpg as `Decimal`,
so they are declared `float | None` and pydantic coerces them — declaring them
`Decimal` would serialise as a string and the frontend charts would silently
receive text.

There is no write model here on purpose. Agent logs are an audit trail: they are
written by `agent_activity_service.log_agent_activity` from inside the service
that ran the agent, never by a client. A client-writable log would let anyone
forge the record of what an agent decided, which defeats the point of having one.

`organization_id` is `UUID | None` because rows written before 0015 have NULL —
see the service for how that is handled on read.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.audits import (
    AGENT_RELATED_ENTITY_TYPES,
    AGENT_STATUSES,
    AGENT_TYPES,
)


# ------------------------------------------------------------------ activity

class AgentActivityRead(BaseModel):
    """One agent run, as shown in the activity feed."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    website_id: UUID
    organization_id: UUID | None = None
    agent_name: str
    agent_type: str
    provider: str
    action_taken: str
    status: str

    prompt_tokens: int
    completion_tokens: int

    # Decimal -> float coercion; see module docstring.
    confidence_score: float | None = None
    decision_summary: str | None = None

    input_context: dict | None = None
    output_result: dict | None = None

    duration_ms: int | None = None
    error_message: str | None = None
    estimated_cost_usd: float | None = None

    related_entity_type: str | None = None
    related_entity_id: UUID | None = None

    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------- summary

class AgentActivitySummary(BaseModel):
    """Headline numbers for the KPI cards, one organization, one window.

    `avg_confidence` is None rather than 0 when no run in the window reported a
    confidence at all: "no agent told us how sure it was" and "every agent was
    0% sure" are different facts and must not render the same.

    `total_cost_usd` only sums runs whose provider is in the price table. A run
    on an unpriced provider contributes tokens but no cost, which is why
    `unpriced_runs` is reported alongside — otherwise the cost card would look
    understated with no explanation.
    """

    days: int
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    success_rate: float = 0.0

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    unpriced_runs: int = 0

    avg_confidence: float | None = None
    avg_duration_ms: float | None = None

    by_agent_type: dict[str, int] = Field(default_factory=dict)
    by_provider: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)

    most_active_agent: str | None = None
    last_run_at: datetime | None = None


# ---------------------------------------------------------------- timeseries

class AgentTokenUsagePoint(BaseModel):
    """One day in the token-usage chart. Zero-filled, never missing."""

    date: str  # ISO date (YYYY-MM-DD); the chart renders it as a Persian label
    runs: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class AgentTokenUsageSeries(BaseModel):
    days: int
    points: list[AgentTokenUsagePoint] = Field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    peak_tokens: int = 0


__all__ = [
    "AgentActivityRead",
    "AgentActivitySummary",
    "AgentTokenUsagePoint",
    "AgentTokenUsageSeries",
    "AGENT_TYPES",
    "AGENT_STATUSES",
    "AGENT_RELATED_ENTITY_TYPES",
]
