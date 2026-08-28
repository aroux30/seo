"""Agent Activity Center endpoints.

Read-only by design. `ai_agent_logs` is an audit trail: rows are written by
`agent_activity_service.log_agent_activity` from inside whichever service ran the
agent, never by a client. Exposing a POST here would let a caller forge the
record of what an AI agent decided, which is exactly the thing this feature
exists to make trustworthy.

Route declaration order matters: FastAPI matches in order, so the literal
`/summary`, `/token-usage` and `/agents` paths are declared before `/{log_id}`.
Reversed, "summary" would be parsed as a UUID and 422. `/agents/{agent_name}` is
parametric but sits under a literal first segment, so it cannot collide with
`/{log_id}` either way.

Everything is org-scoped from the resolved membership. When a `website_id` query
param is supplied it goes through `assert_website_in_org` first, so a UUID from
another tenant 404s instead of confirming its own existence. `/{log_id}` is
scoped inside `agent_activity_service.get_agent_activity` (which filters on the
`Website` join and raises 404), because `app.core.scoping` is owned elsewhere and
cannot yet grow an `assert_agent_log_in_org` — see the module note in
`versions.py` for the same arrangement.

Date filtering: `days` is the common case and is translated to a `since` cutoff
here rather than in the service, so the service keeps taking explicit datetimes
and stays usable from workers that already know their own window. `from_date` /
`to_date` accept calendar dates and are widened to inclusive UTC day bounds —
comparing a bare date against a timestamp column would silently drop everything
that happened after midnight on the final day.
"""

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scoping import assert_website_in_org
from app.database import get_db
from app.dependencies import require_role
from app.models import OrganizationMember
from app.schemas.agent_activity import (
    AgentActivityRead,
    AgentActivitySummary,
    AgentTokenUsageSeries,
)
from app.services import agent_activity_service

router = APIRouter(prefix="/agent-activity", tags=["agent-activity"])


def _day_bounds(
    from_date: date | None, to_date: date | None
) -> tuple[datetime | None, datetime | None]:
    """Inclusive UTC timestamp bounds for an optional calendar-date range.

    `created_at` is a timestamp, so `to_date` is widened to the end of its day.
    Passing the bare date would exclude every run after midnight on that day and
    make the last day of any range look empty.
    """
    since = (
        datetime.combine(from_date, time.min, tzinfo=timezone.utc)
        if from_date is not None
        else None
    )
    until = (
        datetime.combine(to_date, time.max, tzinfo=timezone.utc)
        if to_date is not None
        else None
    )
    return since, until


@router.get("", response_model=dict)
async def list_agent_activity_endpoint(
    website_id: UUID | None = Query(None),
    agent_name: str | None = Query(None),
    agent_type: str | None = Query(None),
    provider: str | None = Query(None),
    status: str | None = Query(None),
    days: int | None = Query(None, ge=1, le=365),
    from_date: date | None = Query(None, description="از تاریخ (شامل همان روز)"),
    to_date: date | None = Query(None, description="تا تاریخ (شامل همان روز)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Agent runs for one website, or across the caller's whole organization.

    An explicit `from_date` wins over `days`: a caller who names a range means
    that range, and silently intersecting it with a default rolling window would
    return fewer rows than asked for with no way to tell why.
    """
    if website_id is not None:
        await assert_website_in_org(db, website_id, member.organization_id)

    since, until = _day_bounds(from_date, to_date)
    if since is None and days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = await agent_activity_service.list_agent_activity(
        db,
        organization_id=member.organization_id,
        website_id=website_id,
        agent_name=agent_name,
        agent_type=agent_type,
        provider=provider,
        status=status,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return {"data": [AgentActivityRead.model_validate(r) for r in rows]}


# Declared before /{log_id}: otherwise "summary" is matched as a UUID.
@router.get("/summary", response_model=dict)
async def agent_activity_summary_endpoint(
    days: int = Query(30, ge=1, le=365),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Runs, success rate, token spend, cost and average confidence for the org."""
    summary = await agent_activity_service.get_activity_summary(
        db, member.organization_id, days=days
    )
    return {"data": AgentActivitySummary.model_validate(summary)}


# Declared before /{log_id} for the same reason as /summary.
@router.get("/token-usage", response_model=dict)
async def agent_token_usage_endpoint(
    days: int = Query(30, ge=1, le=365),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Daily token/cost buckets for the usage chart, zero-filled for gap days."""
    series = await agent_activity_service.get_token_usage_timeseries(
        db, member.organization_id, days=days
    )
    return {"data": AgentTokenUsageSeries.model_validate(series)}


# Literal first segment, so it is matched before /{log_id} regardless of order —
# declared here anyway to keep the literal-before-parametric rule visible.
@router.get("/agents", response_model=dict)
async def agent_breakdown_endpoint(
    days: int = Query(30, ge=1, le=365),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Per-agent and per-provider aggregates: runs, success rate, tokens, cost.

    Returned as a plain dict rather than a schema model: the grouped rows carry
    both the agent and provider breakdowns and there is no read model for that
    pair in `schemas/agent_activity.py`, which is complete and owned elsewhere.
    """
    breakdown = await agent_activity_service.get_agent_breakdown(
        db, member.organization_id, days=days
    )
    return {"data": breakdown}


@router.get("/agents/{agent_name}", response_model=dict)
async def agent_timeline_endpoint(
    agent_name: str,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """One agent's aggregate stats plus its most recent runs.

    `agent_name` is a free-form string rather than an id, so there is nothing to
    scope on its own — the org filter on the `Website` join inside the service is
    what keeps this from reading another tenant's runs. An agent that has not run
    inside the window returns an empty timeline, not a 404: a quiet agent is a
    valid answer, and 404-ing would render an error for it.
    """
    timeline = await agent_activity_service.get_agent_timeline(
        db, member.organization_id, agent_name, days=days, limit=limit
    )
    return {
        "data": {
            "agent_name": timeline["agent_name"],
            "days": timeline["days"],
            "stats": timeline["stats"],
            "agent_types": timeline["agent_types"],
            "providers": timeline["providers"],
            "runs": [
                AgentActivityRead.model_validate(r) for r in timeline["runs"]
            ],
        }
    }


@router.get("/{log_id}", response_model=dict)
async def get_agent_activity_endpoint(
    log_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """One agent run with its full audit trail (input context / output result).

    Org scoping happens in the service, which joins through `Website` and raises
    404 (never 403) on a cross-tenant id so the status code is not an existence
    oracle.
    """
    log = await agent_activity_service.get_agent_activity(
        db, log_id, member.organization_id
    )
    return {"data": AgentActivityRead.model_validate(log)}
