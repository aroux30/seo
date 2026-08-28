"""Dashboard aggregation.

The dashboard home used to count rows the frontend already had in memory
(`organizations.length`, `websites.length`) and call that a dashboard. This
module produces the numbers it actually promised: traffic, trend, health, and
the badge counts for alerts and opportunities, for one organization, in a
handful of aggregate queries rather than one query per website.

Two data-shape facts drive the whole design:

1. `gsc_dates` is the only true daily time series. `gsc_queries` / `gsc_pages`
   are whole-account **snapshots** all stamped with the sync date, so summing
   them across dates double-counts every row of every previous sync. Traffic
   totals and the period-over-period delta therefore come from `GscDate` only.
2. Per-website rows still need a query/page breakdown, and for those the
   correct unit is "the latest snapshot", never a date range.

Everything is scoped by `organization_id` reached through the `Website` join, so
a soft-deleted website drops out of every number at once instead of being
filtered in some queries and not others.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Alert,
    ContentArticle,
    GscDate,
    Opportunity,
    Project,
    SeoAudit,
    Website,
)

logger = logging.getLogger(__name__)

# Window used for the headline traffic numbers and the trend arrow. Seven days
# compared against the seven before it: short enough to react, long enough that
# a single quiet weekend does not read as a collapse.
DEFAULT_WINDOW_DAYS = 7

# Health score weights. Kept arithmetic and inspectable for the same reason the
# opportunity priority is: the number is shown to users, so it has to be
# explainable rather than a tuned constant nobody can defend.
_CRITICAL_ALERT_PENALTY = 8
_WARNING_ALERT_PENALTY = 3
_NO_DATA_HEALTH = 0


def _ratio(numerator: float, denominator: float) -> float:
    """Safe division — GSC gives plenty of zero-impression rows."""
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _pct_change(previous: float, current: float) -> float | None:
    """Percentage change, or None when there is no baseline to compare against.

    Returning None rather than 0 matters: "no data last week" and "flat vs last
    week" render differently, and collapsing them would show a fake 0% trend on
    a website that only just connected.
    """
    if previous is None or previous <= 0:
        return None
    return round(((float(current) - float(previous)) / float(previous)) * 100, 2)


async def _org_website_ids(db: AsyncSession, organization_id: UUID) -> list[UUID]:
    """Live websites in this organization. The population for every other query."""
    result = await db.execute(
        select(Website.id).where(
            Website.organization_id == organization_id,
            Website.deleted_at.is_(None),
        )
    )
    return list(result.scalars().all())


async def _traffic_totals(
    db: AsyncSession, website_ids: list[UUID], start: date, end: date
) -> dict:
    """Clicks/impressions/position over a date window, from the daily series.

    `avg_position` is impression-weighted. A plain average would let a single
    obscure query sitting at position 90 drag the site's headline position down
    as hard as a query with ten thousand impressions at position 3.
    """
    if not website_ids:
        return {"clicks": 0, "impressions": 0, "position_weighted": 0.0}

    result = await db.execute(
        select(
            func.coalesce(func.sum(GscDate.clicks), 0),
            func.coalesce(func.sum(GscDate.impressions), 0),
            func.coalesce(
                func.sum(cast(GscDate.position, Float) * cast(GscDate.impressions, Float)),
                0.0,
            ),
        ).where(
            GscDate.website_id.in_(website_ids),
            GscDate.date_metric >= start,
            GscDate.date_metric <= end,
        )
    )
    clicks, impressions, position_weight = result.one()
    return {
        "clicks": int(clicks or 0),
        "impressions": int(impressions or 0),
        "position_weighted": float(position_weight or 0.0),
    }


async def _alert_counts(db: AsyncSession, organization_id: UUID) -> dict:
    """Active alerts by severity, plus a per-website breakdown for the table."""
    result = await db.execute(
        select(Alert.website_id, Alert.severity, func.count())
        .join(Website, Website.id == Alert.website_id)
        .where(
            Website.organization_id == organization_id,
            Website.deleted_at.is_(None),
            Alert.status == "active",
        )
        .group_by(Alert.website_id, Alert.severity)
    )

    per_website: dict[UUID, int] = {}
    total = critical = warning = 0
    for website_id, severity, count in result.all():
        per_website[website_id] = per_website.get(website_id, 0) + count
        total += count
        if severity == "critical":
            critical += count
        elif severity == "warning":
            warning += count

    return {
        "total": total,
        "critical": critical,
        "warning": warning,
        "per_website": per_website,
    }


async def _opportunity_counts(db: AsyncSession, organization_id: UUID) -> dict:
    """Open opportunities and their combined estimated gain."""
    result = await db.execute(
        select(
            Opportunity.website_id,
            func.count(),
            func.coalesce(func.sum(Opportunity.estimated_traffic_gain), 0),
        )
        .join(Website, Website.id == Opportunity.website_id)
        .where(
            Website.organization_id == organization_id,
            Website.deleted_at.is_(None),
            Opportunity.status.in_(["open", "in_progress"]),
        )
        .group_by(Opportunity.website_id)
    )

    per_website: dict[UUID, int] = {}
    total = 0
    total_gain = 0
    for website_id, count, gain in result.all():
        per_website[website_id] = count
        total += count
        total_gain += int(gain or 0)

    return {"total": total, "estimated_gain": total_gain, "per_website": per_website}


async def _article_counts(db: AsyncSession, organization_id: UUID) -> dict:
    """Published vs still-in-progress articles.

    Anything not yet live counts as a draft for dashboard purposes — "review"
    and "draft" are both work the user still owes, and splitting them here would
    add a card nobody asked for.
    """
    result = await db.execute(
        select(ContentArticle.status, func.count())
        .join(Website, Website.id == ContentArticle.website_id)
        .where(
            Website.organization_id == organization_id,
            Website.deleted_at.is_(None),
        )
        .group_by(ContentArticle.status)
    )
    by_status = {row[0]: row[1] for row in result.all()}
    published = by_status.get("published", 0)
    drafts = sum(count for status, count in by_status.items() if status != "published")
    return {"published": published, "drafts": drafts}


async def _latest_audit_scores(
    db: AsyncSession, website_ids: list[UUID]
) -> dict[UUID, int]:
    """Most recent completed audit score per website.

    Done as one grouped subquery instead of a query per website: on an
    organization with thirty sites the loop version was thirty round trips to
    render one card.
    """
    if not website_ids:
        return {}

    latest = (
        select(
            SeoAudit.website_id.label("website_id"),
            func.max(SeoAudit.created_at).label("latest_at"),
        )
        .where(
            SeoAudit.website_id.in_(website_ids),
            SeoAudit.status == "completed",
        )
        .group_by(SeoAudit.website_id)
        .subquery()
    )

    result = await db.execute(
        select(SeoAudit.website_id, SeoAudit.overall_score).join(
            latest,
            (SeoAudit.website_id == latest.c.website_id)
            & (SeoAudit.created_at == latest.c.latest_at),
        )
    )
    return {row[0]: int(row[1] or 0) for row in result.all()}


async def _per_website_traffic(
    db: AsyncSession, website_ids: list[UUID], start: date, end: date
) -> dict[UUID, dict]:
    """Same window as the headline totals, grouped per website."""
    if not website_ids:
        return {}

    result = await db.execute(
        select(
            GscDate.website_id,
            func.coalesce(func.sum(GscDate.clicks), 0),
            func.coalesce(func.sum(GscDate.impressions), 0),
            func.coalesce(
                func.sum(cast(GscDate.position, Float) * cast(GscDate.impressions, Float)),
                0.0,
            ),
        )
        .where(
            GscDate.website_id.in_(website_ids),
            GscDate.date_metric >= start,
            GscDate.date_metric <= end,
        )
        .group_by(GscDate.website_id)
    )

    out: dict[UUID, dict] = {}
    for website_id, clicks, impressions, position_weight in result.all():
        impressions = int(impressions or 0)
        out[website_id] = {
            "clicks": int(clicks or 0),
            "impressions": impressions,
            "ctr": round(_ratio(int(clicks or 0), impressions), 4),
            "avg_position": round(_ratio(float(position_weight or 0.0), impressions), 1),
        }
    return out


async def _last_sync_at(db: AsyncSession, website_ids: list[UUID]) -> datetime | None:
    """When GSC data last landed for any website in the organization."""
    if not website_ids:
        return None
    result = await db.execute(
        select(func.max(GscDate.created_at)).where(GscDate.website_id.in_(website_ids))
    )
    return result.scalar_one_or_none()


def _health_score(audit_scores: list[int], critical_alerts: int, warning_alerts: int) -> int:
    """Blend audit quality with how much is currently on fire.

    Audits describe the site's built quality; active alerts describe whether it
    is working right now. A site with a clean audit and a live traffic collapse
    is not healthy, so alerts subtract from the audit baseline rather than being
    reported separately and left for the user to mentally combine.
    """
    valid_scores = [s for s in audit_scores if s > 0]
    if not valid_scores:
        return _NO_DATA_HEALTH
    baseline = sum(valid_scores) / len(valid_scores)
    penalty = (critical_alerts * _CRITICAL_ALERT_PENALTY) + (
        warning_alerts * _WARNING_ALERT_PENALTY
    )
    return int(max(0, min(100, round(baseline - penalty))))


async def get_dashboard_summary(
    db: AsyncSession,
    organization_id: UUID,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict:
    """Everything the dashboard home needs, for one organization, in one call.

    Returns a plain dict matching `DashboardSummary`; the router validates it.
    An organization with no websites returns a fully-populated zero summary
    rather than raising, because "you have not added a website yet" is a normal
    first-run state and the page has an empty-state design for it.
    """
    website_ids = await _org_website_ids(db, organization_id)

    project_count = await db.execute(
        select(func.count())
        .select_from(Project)
        .where(
            Project.organization_id == organization_id,
            Project.deleted_at.is_(None),
        )
    )

    today = date.today()
    current_start = today - timedelta(days=window_days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=window_days - 1)

    current = await _traffic_totals(db, website_ids, current_start, today)
    previous = await _traffic_totals(db, website_ids, previous_start, previous_end)

    alerts = await _alert_counts(db, organization_id)
    opportunities = await _opportunity_counts(db, organization_id)
    articles = await _article_counts(db, organization_id)
    audit_scores = await _latest_audit_scores(db, website_ids)
    per_site_traffic = await _per_website_traffic(db, website_ids, current_start, today)
    last_sync_at = await _last_sync_at(db, website_ids)

    websites_result = await db.execute(
        select(Website.id, Website.name, Website.domain)
        .where(
            Website.organization_id == organization_id,
            Website.deleted_at.is_(None),
        )
        .order_by(Website.name)
    )

    rows = []
    for website_id, name, domain in websites_result.all():
        traffic = per_site_traffic.get(
            website_id, {"clicks": 0, "impressions": 0, "ctr": 0.0, "avg_position": 0.0}
        )
        rows.append({
            "website_id": website_id,
            "name": name,
            "domain": domain,
            "clicks": traffic["clicks"],
            "impressions": traffic["impressions"],
            "ctr": traffic["ctr"],
            "avg_position": traffic["avg_position"],
            "health_score": audit_scores.get(website_id, _NO_DATA_HEALTH),
            "open_alerts": alerts["per_website"].get(website_id, 0),
            "open_opportunities": opportunities["per_website"].get(website_id, 0),
        })

    scores = [audit_scores.get(w_id, _NO_DATA_HEALTH) for w_id in website_ids]

    return {
        "organization_id": organization_id,
        "website_count": len(website_ids),
        "project_count": int(project_count.scalar_one() or 0),
        "health_score": _health_score(scores, alerts["critical"], alerts["warning"]),
        "total_clicks": current["clicks"],
        "total_impressions": current["impressions"],
        "avg_ctr": round(_ratio(current["clicks"], current["impressions"]), 4),
        "avg_position": round(
            _ratio(current["position_weighted"], current["impressions"]), 1
        ),
        "clicks_change_percent": _pct_change(previous["clicks"], current["clicks"]),
        "impressions_change_percent": _pct_change(
            previous["impressions"], current["impressions"]
        ),
        "active_alerts": alerts["total"],
        "critical_alerts": alerts["critical"],
        "open_opportunities": opportunities["total"],
        "estimated_traffic_gain": opportunities["estimated_gain"],
        "published_articles": articles["published"],
        "draft_articles": articles["drafts"],
        "last_audit_score": max(scores) if scores else None,
        "last_gsc_sync_at": last_sync_at,
        "websites": rows,
    }


__all__ = ["get_dashboard_summary"]
