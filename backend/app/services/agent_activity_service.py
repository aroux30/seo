"""Agent Activity Center — the write path and read queries for `ai_agent_logs`.

`log_agent_activity` is the single write path. Other services (ai_service,
opportunity_service, alert_service, automation_service, ...) should call it
instead of constructing `AiAgentLog` rows themselves, so every run ends up with
a consistent `agent_type`, a computed `estimated_cost_usd`, and an
`organization_id` — none of that existed before migration 0015.

organization_id and pre-migration rows
---------------------------------------
`AiAgentLog.organization_id` is nullable (rows written before 0015 have NULL).
This module's policy, applied consistently everywhere below, is: **resolve the
organization through a join to `Website` rather than trusting the denormalised
column alone.** `Website.organization_id` is always populated and is the source
of truth; `AiAgentLog.organization_id` is a read-optimisation that the write
path keeps in sync going forward. Filtering on the join means a legacy NULL row
still shows up in the activity feed instead of silently disappearing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models import AiAgentLog, Website

logger = logging.getLogger(__name__)


# --------------------------------------------------------------- cost pricing
# USD per 1,000 tokens, split prompt/completion. Deliberately a small, explicit
# table rather than a formula: prices change per model, not just per provider,
# and hard-coding a guess for an unknown provider would silently misreport spend
# on every future integration. An unpriced provider costs nothing to report
# wrong, so `_cost_per_1k` returns None for anything not listed here and the
# caller treats "unknown" as unknown rather than $0.
#
# Rates are approximate blended list prices as of this writing and are meant
# for relative cost tracking (which agents are expensive), not for billing
# reconciliation.
PROVIDER_PRICING_PER_1K_TOKENS: dict[str, dict[str, float]] = {
    "openai": {"prompt": 0.0050, "completion": 0.0150},
    "anthropic": {"prompt": 0.0030, "completion": 0.0150},
    "google": {"prompt": 0.0010, "completion": 0.0040},
    # The audit/opportunity/alert detectors run with no LLM call at all.
    "algorithmic_fallback": {"prompt": 0.0, "completion": 0.0},
}


def _estimate_cost_usd(
    provider: str, prompt_tokens: int, completion_tokens: int
) -> float | None:
    """Cost for one run, or None when the provider has no known price.

    A wrong number is worse than no number: a guessed price compounds silently
    into the cost KPI and nobody notices until the total is off by an order of
    magnitude. None surfaces as "unpriced" in the summary instead.
    """
    pricing = PROVIDER_PRICING_PER_1K_TOKENS.get(provider)
    if pricing is None:
        return None
    cost = (prompt_tokens / 1000.0) * pricing["prompt"] + (
        completion_tokens / 1000.0
    ) * pricing["completion"]
    return round(cost, 6)


# ------------------------------------------------------------------- write

async def log_agent_activity(
    db: AsyncSession,
    *,
    website_id: UUID,
    organization_id: UUID,
    agent_name: str,
    agent_type: str,
    provider: str,
    action_taken: str,
    status: str = "success",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    confidence_score: float | None = None,
    decision_summary: str | None = None,
    input_context: dict | None = None,
    output_result: dict | None = None,
    duration_ms: int | None = None,
    error_message: str | None = None,
    related_entity_type: str | None = None,
    related_entity_id: UUID | None = None,
) -> AiAgentLog:
    """Record one agent run. The single write path for `ai_agent_logs`.

    Callers pass raw `UUID` objects, never `str(uuid)` — the columns are
    `UUID(as_uuid=True)` and a string silently never matches on read.
    """
    estimated_cost_usd = _estimate_cost_usd(provider, prompt_tokens, completion_tokens)

    log = AiAgentLog(
        website_id=website_id,
        organization_id=organization_id,
        agent_name=agent_name,
        agent_type=agent_type,
        provider=provider,
        action_taken=action_taken,
        status=status,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        confidence_score=confidence_score,
        decision_summary=decision_summary,
        input_context=input_context,
        output_result=output_result,
        duration_ms=duration_ms,
        error_message=error_message,
        estimated_cost_usd=estimated_cost_usd,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    )
    db.add(log)
    await db.flush()
    return log


# -------------------------------------------------------------------- list

async def list_agent_activity(
    db: AsyncSession,
    *,
    organization_id: UUID,
    website_id: UUID | None = None,
    agent_name: str | None = None,
    agent_type: str | None = None,
    provider: str | None = None,
    status: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int,
    offset: int,
) -> list[AiAgentLog]:
    """Newest-first activity feed.

    The organization filter is applied in both branches (with and without
    `website_id`) so a website-scoped call can never widen past the caller's
    tenant even if `website_id` belonged to another organization — the router
    already guards that with `assert_website_in_org`, but the service does not
    rely solely on the router getting it right.

    `since`/`until` are inclusive bounds on `created_at`. They are passed as
    datetimes rather than dates so the caller decides the timezone; the router
    builds them in UTC.
    """
    query = (
        select(AiAgentLog)
        .join(Website, Website.id == AiAgentLog.website_id)
        .where(Website.organization_id == organization_id)
    )

    if website_id is not None:
        query = query.where(
            AiAgentLog.website_id == website_id,
            Website.organization_id == organization_id,
        )
    if agent_name is not None:
        query = query.where(AiAgentLog.agent_name == agent_name)
    if agent_type is not None:
        query = query.where(AiAgentLog.agent_type == agent_type)
    if provider is not None:
        query = query.where(AiAgentLog.provider == provider)
    if status is not None:
        query = query.where(AiAgentLog.status == status)
    if since is not None:
        query = query.where(AiAgentLog.created_at >= since)
    if until is not None:
        query = query.where(AiAgentLog.created_at <= until)

    query = query.order_by(AiAgentLog.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(query)
    return list(result.scalars().all())


async def count_agent_activity(
    db: AsyncSession,
    *,
    organization_id: UUID,
    website_id: UUID | None = None,
    agent_name: str | None = None,
    agent_type: str | None = None,
    provider: str | None = None,
    status: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> int:
    """Total matching rows, for the pager.

    Same predicates and the same org join as `list_agent_activity`, minus
    limit/offset. Kept as its own function rather than a second return value so
    the list path does not pay for a COUNT it does not always need.
    """
    query = (
        select(func.count())
        .select_from(AiAgentLog)
        .join(Website, Website.id == AiAgentLog.website_id)
        .where(Website.organization_id == organization_id)
    )

    if website_id is not None:
        query = query.where(AiAgentLog.website_id == website_id)
    if agent_name is not None:
        query = query.where(AiAgentLog.agent_name == agent_name)
    if agent_type is not None:
        query = query.where(AiAgentLog.agent_type == agent_type)
    if provider is not None:
        query = query.where(AiAgentLog.provider == provider)
    if status is not None:
        query = query.where(AiAgentLog.status == status)
    if since is not None:
        query = query.where(AiAgentLog.created_at >= since)
    if until is not None:
        query = query.where(AiAgentLog.created_at <= until)

    result = await db.execute(query)
    return int(result.scalar_one() or 0)


# --------------------------------------------------------------- single row

async def get_agent_activity(
    db: AsyncSession, log_id: UUID, organization_id: UUID
) -> AiAgentLog:
    """Single row, org-scoped. 404 (never 403) on a cross-tenant hit — see
    app.core.scoping module docstring for why: the status code must not be an
    existence oracle.
    """
    result = await db.execute(
        select(AiAgentLog)
        .join(Website, Website.id == AiAgentLog.website_id)
        .where(
            AiAgentLog.id == log_id,
            Website.organization_id == organization_id,
        )
    )
    log = result.scalar_one_or_none()
    if not log:
        raise NotFoundError("AgentActivity", str(log_id))
    return log


# ------------------------------------------------------------------ summary

async def get_activity_summary(
    db: AsyncSession, organization_id: UUID, *, days: int = 30
) -> dict:
    """Headline numbers for the KPI cards, one organization, one window."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    base = (
        select(AiAgentLog)
        .join(Website, Website.id == AiAgentLog.website_id)
        .where(
            Website.organization_id == organization_id,
            AiAgentLog.created_at >= since,
        )
    )
    result = await db.execute(base)
    rows = list(result.scalars().all())

    total_runs = len(rows)
    successful_runs = sum(1 for r in rows if r.status == "success")
    failed_runs = sum(1 for r in rows if r.status == "failed")
    success_rate = round((successful_runs / total_runs) * 100, 2) if total_runs else 0.0

    total_prompt_tokens = sum(r.prompt_tokens or 0 for r in rows)
    total_completion_tokens = sum(r.completion_tokens or 0 for r in rows)
    total_tokens = total_prompt_tokens + total_completion_tokens

    for r in rows:
        if r.estimated_cost_usd is None:
            r.estimated_cost_usd = _estimate_cost_usd(r.provider, r.prompt_tokens or 0, r.completion_tokens or 0)
    costed = [r for r in rows if r.estimated_cost_usd is not None]
    total_cost_usd = round(sum(float(r.estimated_cost_usd) for r in costed), 6)
    unpriced_runs = total_runs - len(costed)

    confidences = [float(r.confidence_score) for r in rows if r.confidence_score is not None]
    avg_confidence = round(sum(confidences) / len(confidences), 2) if confidences else None

    durations = [r.duration_ms for r in rows if r.duration_ms is not None]
    avg_duration_ms = round(sum(durations) / len(durations), 2) if durations else None

    by_agent_type: dict[str, int] = {}
    by_provider: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_agent_name: dict[str, int] = {}
    last_run_at: datetime | None = None

    for r in rows:
        by_agent_type[r.agent_type] = by_agent_type.get(r.agent_type, 0) + 1
        by_provider[r.provider] = by_provider.get(r.provider, 0) + 1
        by_status[r.status] = by_status.get(r.status, 0) + 1
        by_agent_name[r.agent_name] = by_agent_name.get(r.agent_name, 0) + 1
        if last_run_at is None or r.created_at > last_run_at:
            last_run_at = r.created_at

    most_active_agent = (
        max(by_agent_name.items(), key=lambda kv: kv[1])[0] if by_agent_name else None
    )

    return {
        "days": days,
        "total_runs": total_runs,
        "successful_runs": successful_runs,
        "failed_runs": failed_runs,
        "success_rate": success_rate,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "total_tokens": total_tokens,
        "total_cost_usd": total_cost_usd,
        "unpriced_runs": unpriced_runs,
        "avg_confidence": avg_confidence,
        "avg_duration_ms": avg_duration_ms,
        "by_agent_type": by_agent_type,
        "by_provider": by_provider,
        "by_status": by_status,
        "most_active_agent": most_active_agent,
        "last_run_at": last_run_at,
    }


# ------------------------------------------------------------- token usage

async def get_token_usage_timeseries(
    db: AsyncSession, organization_id: UUID, *, days: int = 30
) -> dict:
    """Daily token/cost/run buckets for the chart, zero-filled for gap days.

    `func.date_trunc('day', ...)` groups in Postgres; days with no runs at all
    never appear in the SQL result, so the gap-fill happens in Python against a
    complete date range instead of trusting the query to produce every day.
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=days - 1)
    since_day = since.date()

    day_col = func.date_trunc("day", AiAgentLog.created_at)
    query = (
        select(
            day_col.label("day"),
            func.count().label("runs"),
            func.coalesce(func.sum(AiAgentLog.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(AiAgentLog.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(AiAgentLog.estimated_cost_usd), 0).label("cost_usd"),
        )
        .join(Website, Website.id == AiAgentLog.website_id)
        .where(
            Website.organization_id == organization_id,
            AiAgentLog.created_at >= since,
        )
        .group_by(day_col)
    )
    result = await db.execute(query)

    by_day: dict[str, dict] = {}
    for day, runs, prompt_tokens, completion_tokens, cost_usd in result.all():
        key = day.date().isoformat()
        by_day[key] = {
            "runs": int(runs or 0),
            "prompt_tokens": int(prompt_tokens or 0),
            "completion_tokens": int(completion_tokens or 0),
            "cost_usd": float(cost_usd or 0.0),
        }

    points = []
    total_tokens = 0
    total_cost_usd = 0.0
    peak_tokens = 0
    for offset in range(days):
        d = since_day + timedelta(days=offset)
        key = d.isoformat()
        bucket = by_day.get(
            key,
            {"runs": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0},
        )
        day_total_tokens = bucket["prompt_tokens"] + bucket["completion_tokens"]
        total_tokens += day_total_tokens
        total_cost_usd += bucket["cost_usd"]
        peak_tokens = max(peak_tokens, day_total_tokens)
        points.append(
            {
                "date": key,
                "runs": bucket["runs"],
                "prompt_tokens": bucket["prompt_tokens"],
                "completion_tokens": bucket["completion_tokens"],
                "total_tokens": day_total_tokens,
                "cost_usd": round(bucket["cost_usd"], 6),
            }
        )

    return {
        "days": days,
        "points": points,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost_usd, 6),
        "peak_tokens": peak_tokens,
    }


# --------------------------------------------------------------- breakdowns

# Aggregate expressions shared by the grouped queries below. Defined once so the
# "runs / success / failure / tokens / cost" tuple cannot drift between the
# by-agent and by-provider groupings, which are rendered side by side.
def _aggregate_columns() -> tuple:
    return (
        func.count().label("runs"),
        func.coalesce(
            func.sum(case((AiAgentLog.status == "success", 1), else_=0)), 0
        ).label("successful_runs"),
        func.coalesce(
            func.sum(case((AiAgentLog.status == "failed", 1), else_=0)), 0
        ).label("failed_runs"),
        func.coalesce(func.sum(AiAgentLog.prompt_tokens), 0).label("prompt_tokens"),
        func.coalesce(func.sum(AiAgentLog.completion_tokens), 0).label(
            "completion_tokens"
        ),
        func.coalesce(func.sum(AiAgentLog.estimated_cost_usd), 0).label("cost_usd"),
        # COUNT over a nullable column counts only non-NULL rows, so this is the
        # number of runs that actually carried a price. `runs - priced_runs` is
        # therefore the unpriced count, which the cost column needs in order to
        # explain itself instead of looking understated.
        func.count(AiAgentLog.estimated_cost_usd).label("priced_runs"),
        func.avg(AiAgentLog.confidence_score).label("avg_confidence"),
        func.avg(AiAgentLog.duration_ms).label("avg_duration_ms"),
        func.max(AiAgentLog.created_at).label("last_run_at"),
    )


def _aggregate_row_to_dict(key_name: str, key_value: str, row) -> dict:
    """Shape one grouped row. `row` starts at the aggregate columns."""
    runs = int(row.runs or 0)
    successful = int(row.successful_runs or 0)
    failed = int(row.failed_runs or 0)
    prompt_tokens = int(row.prompt_tokens or 0)
    completion_tokens = int(row.completion_tokens or 0)
    priced_runs = int(row.priced_runs or 0)
    return {
        key_name: key_value,
        "runs": runs,
        "successful_runs": successful,
        "failed_runs": failed,
        "success_rate": round((successful / runs) * 100, 2) if runs else 0.0,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "cost_usd": round(float(row.cost_usd or 0.0), 6),
        "unpriced_runs": runs - priced_runs,
        # None, not 0.0: "no agent reported a confidence" and "every agent
        # reported zero confidence" must not render identically.
        "avg_confidence": (
            round(float(row.avg_confidence), 2) if row.avg_confidence is not None else None
        ),
        "avg_duration_ms": (
            round(float(row.avg_duration_ms), 2)
            if row.avg_duration_ms is not None
            else None
        ),
        "last_run_at": row.last_run_at,
    }


async def get_agent_breakdown(
    db: AsyncSession, organization_id: UUID, *, days: int = 30
) -> dict:
    """Per-agent and per-provider aggregates for the same window.

    Two grouped queries rather than loading every row and folding in Python:
    an organization with months of agent history has tens of thousands of logs
    and the KPI strip must not pull them all into memory to add up nine numbers.

    Both groupings are returned together because the UI shows them side by side
    and computing them in one call keeps the two panels consistent with each
    other even if a run lands between requests.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    scope = (
        Website.organization_id == organization_id,
        AiAgentLog.created_at >= since,
    )

    by_agent_result = await db.execute(
        select(AiAgentLog.agent_name, AiAgentLog.agent_type, *_aggregate_columns())
        .join(Website, Website.id == AiAgentLog.website_id)
        .where(*scope)
        .group_by(AiAgentLog.agent_name, AiAgentLog.agent_type)
        .order_by(func.count().desc())
    )
    agents = []
    for row in by_agent_result.all():
        entry = _aggregate_row_to_dict("agent_name", row.agent_name, row)
        entry["agent_type"] = row.agent_type
        agents.append(entry)

    by_provider_result = await db.execute(
        select(AiAgentLog.provider, *_aggregate_columns())
        .join(Website, Website.id == AiAgentLog.website_id)
        .where(*scope)
        .group_by(AiAgentLog.provider)
        .order_by(func.count().desc())
    )
    providers = [
        _aggregate_row_to_dict("provider", row.provider, row)
        for row in by_provider_result.all()
    ]

    return {
        "days": days,
        "agents": agents,
        "providers": providers,
        "agent_count": len(agents),
        "provider_count": len(providers),
    }


# ------------------------------------------------------------ agent timeline

async def get_agent_timeline(
    db: AsyncSession,
    organization_id: UUID,
    agent_name: str,
    *,
    days: int = 30,
    limit: int = 50,
) -> dict:
    """One agent's own stats plus its most recent runs.

    `agent_name` is a client-supplied string, not an id, so there is nothing to
    scope by itself — the org filter on the `Website` join is what keeps this
    from reading another tenant's runs. An unknown name is NOT a 404: an agent
    that has simply not run inside the window is a legitimate empty timeline,
    and 404-ing would make the UI show an error for a valid quiet agent.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)
    scope = (
        Website.organization_id == organization_id,
        AiAgentLog.agent_name == agent_name,
        AiAgentLog.created_at >= since,
    )

    stats_result = await db.execute(
        select(*_aggregate_columns())
        .join(Website, Website.id == AiAgentLog.website_id)
        .where(*scope)
    )
    stats_row = stats_result.one()
    stats = _aggregate_row_to_dict("agent_name", agent_name, stats_row)

    runs_result = await db.execute(
        select(AiAgentLog)
        .join(Website, Website.id == AiAgentLog.website_id)
        .where(*scope)
        .order_by(AiAgentLog.created_at.desc())
        .limit(limit)
    )
    runs = list(runs_result.scalars().all())

    # The agent families this name has run under. Normally exactly one, but a
    # renamed/retyped agent can legitimately span two, so it is a list rather
    # than a scalar that would silently pick a winner.
    agent_types = sorted({r.agent_type for r in runs if r.agent_type})
    providers = sorted({r.provider for r in runs if r.provider})

    return {
        "agent_name": agent_name,
        "days": days,
        "stats": stats,
        "agent_types": agent_types,
        "providers": providers,
        "runs": runs,
    }


__all__ = [
    "log_agent_activity",
    "list_agent_activity",
    "count_agent_activity",
    "get_agent_activity",
    "get_activity_summary",
    "get_token_usage_timeseries",
    "get_agent_breakdown",
    "get_agent_timeline",
    "PROVIDER_PRICING_PER_1K_TOKENS",
]
