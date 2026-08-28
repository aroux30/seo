"""Report generation service.

A report is assembled once and frozen. Everything in `content` is computed here,
at generation time, from whatever the source tables held at that moment; no read
path in this module recomputes anything. A client opening a March report in June
must see March's numbers, not June's re-query of March.

Four rules the whole module is built around:

1. **Never fabricate a number.** If a source table has no rows for the period the
   section is still emitted, with zeros/nulls plus an explicit
   `"has_data": false` and a Persian `note`. The frontend renders the note
   instead of a chart. Substituting a plausible figure into a document that gets
   emailed to a client is the worst failure mode available here.
2. **`gsc_dates` is the only real time series.** `gsc_queries` / `gsc_pages` are
   whole-account snapshots all stamped `date_metric = <sync day>`, so summing
   them over a range double-counts every earlier sync. Period totals and the
   period-over-period delta come from `GscDate` alone; the query/page tables are
   read as "the latest snapshot inside the period" and the payload carries that
   snapshot date so nobody reads those lists as period-bounded.
3. **Templates cannot drift from output.** `_SECTIONS_BY_TYPE` is the single
   source of truth: `generate_report` iterates it to build the sections and
   `get_report_templates` reads the same mapping to advertise them. The
   automation service has exactly the bug this avoids (it advertises template
   keys its own code never produces), so the coupling is deliberate rather than
   two hand-synced lists.
4. **Nothing user-identifying goes into `content`.** The payload is served
   verbatim on an unauthenticated share endpoint, so no emails, user names,
   organization ids or internal UUIDs are ever written into it. Website names and
   domains are included because they are the subject of the report and already
   public.

Share links: `secrets.token_urlsafe(32)` for the token, `secrets.compare_digest`
for the comparison, opt-in per report, expiring by default. See
`get_report_by_share_token`.
"""

import csv
import io
import logging
import secrets
from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models import (
    Alert,
    ContentArticle,
    GscDate,
    GscPage,
    GscQuery,
    Opportunity,
    SeoAudit,
    Website,
)
from app.models.reports import (
    DEFAULT_SHARE_TTL_DAYS,
    REPORT_TYPES,
    Report,
)

logger = logging.getLogger(__name__)

# How many rows the list-shaped sections carry. A frozen document is read by a
# human and never paginated, so the lists are capped rather than complete.
TOP_N = 10

# Default period length per report type, offered by the template list.
DEFAULT_PERIOD_DAYS = {
    "weekly": 7,
    "monthly": 30,
    "executive": 30,
    "custom": 30,
}

# Persian section headings. Shared by the generated payload and the template
# list, so the picker and the finished report show the same wording.
SECTION_TITLES_FA = {
    "overview": "خلاصه عملکرد",
    "traffic": "ترافیک ارگانیک",
    "top_queries": "پرکلیک‌ترین عبارت‌های جستجو",
    "top_pages": "پربازدیدترین صفحات",
    "audit": "سلامت فنی سایت",
    "alerts": "هشدارها",
    "opportunities": "فرصت‌های بهبود",
    "content": "محتوای منتشرشده",
    "websites": "تفکیک بر اساس وب‌سایت",
}

# THE contract. Iterated by generate_report to build `content["sections"]`, and
# read by get_report_templates to advertise them — one mapping, so an advertised
# section key cannot fail to appear in a generated document.
_SECTIONS_BY_TYPE: dict[str, tuple[str, ...]] = {
    "weekly": (
        "overview",
        "traffic",
        "top_queries",
        "top_pages",
        "alerts",
        "content",
        "websites",
    ),
    "monthly": (
        "overview",
        "traffic",
        "top_queries",
        "top_pages",
        "audit",
        "alerts",
        "opportunities",
        "content",
        "websites",
    ),
    "executive": (
        "overview",
        "traffic",
        "audit",
        "alerts",
        "opportunities",
        "websites",
    ),
    "custom": (
        "overview",
        "traffic",
        "top_queries",
        "top_pages",
        "audit",
        "alerts",
        "opportunities",
        "content",
        "websites",
    ),
}

TEMPLATE_TITLES_FA = {
    "weekly": "گزارش عملکرد هفتگی",
    "monthly": "گزارش ماهانه سئو",
    "executive": "خلاصه مدیریتی",
    "custom": "گزارش سفارشی",
}

TEMPLATE_DESCRIPTIONS_FA = {
    "weekly": (
        "نبض هفتگی سایت: کلیک و نمایش این هفته در مقابل هفته پیش، عبارت‌ها و "
        "صفحات برتر، هشدارهای این بازه و محتوای منتشرشده."
    ),
    "monthly": (
        "گزارش کامل ماهانه شامل ترافیک و مقایسه با ماه پیش، امتیاز سلامت فنی، "
        "هشدارها، فرصت‌های بهبود و کارنامه تولید محتوا."
    ),
    "executive": (
        "خلاصه یک‌صفحه‌ای برای مدیران و کارفرما: شاخص‌های کلیدی، روند رشد، "
        "سلامت سایت و مهم‌ترین فرصت‌ها، بدون جزئیات فنی."
    ),
    "custom": (
        "همه بخش‌ها برای یک بازه زمانی دلخواه؛ مناسب گزارش‌های موردی و "
        "بازه‌های غیرتقویمی."
    ),
}

# One constant so "no data" reads identically in every section.
_NO_DATA_NOTE = "داده‌ای برای این بازه ثبت نشده است."

# content_articles has no `published_at` column, so "published in this period" is
# approximated by `updated_at` on rows whose status is `published`. The payload
# states this rather than presenting it as an exact publication date.
_CONTENT_DATE_CAVEAT = (
    "تاریخ انتشار بر پایه آخرین به‌روزرسانی مقاله محاسبه شده است؛ "
    "جدول مقالات ستون تاریخ انتشار مستقل ندارد."
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ratio(numerator: float, denominator: float) -> float:
    """Safe division — GSC returns plenty of zero-impression rows."""
    if not denominator:
        return 0.0
    return float(numerator) / float(denominator)


def _pct_change(previous: float | None, current: float) -> float | None:
    """Percentage change, or None when there is no baseline.

    None rather than 0.0: "nothing last period" and "flat versus last period" are
    different facts, and collapsing them prints a confident 0% delta on a site
    that only just connected Search Console.
    """
    if previous is None or float(previous) <= 0:
        return None
    return round(((float(current) - float(previous)) / float(previous)) * 100, 2)


def _previous_period(period_start: date, period_end: date) -> tuple[date, date]:
    """The equally long window immediately before the reported one.

    The span counts both endpoints, so a Mon-Sun report compares against the
    previous Mon-Sun rather than against six days.
    """
    span_days = (period_end - period_start).days + 1
    previous_end = period_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=span_days - 1)
    return previous_start, previous_end


def _day_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """Inclusive UTC timestamp bounds for a date range.

    Timestamp columns (`triggered_at`, `resolved_at`, ...) are compared against
    these; using the bare dates would drop everything that happened after
    midnight on the final day.
    """
    return (
        datetime.combine(start, time.min, tzinfo=timezone.utc),
        datetime.combine(end, time.max, tzinfo=timezone.utc),
    )


def _section(key: str, *, has_data: bool, **payload) -> dict:
    """Wrap a section body with its heading and an explicit presence flag."""
    body = {
        "key": key,
        "title_fa": SECTION_TITLES_FA.get(key, key),
        "has_data": has_data,
    }
    if not has_data:
        body["note"] = _NO_DATA_NOTE
    body.update(payload)
    return body


# ------------------------------------------------------------------- scoping

def _private_report_stmt(report_id: UUID, organization_id: UUID):
    """The only way this module addresses a single report.

    Both predicates always travel together, so no code path can accidentally
    fetch a report by id alone.
    """
    return select(Report).where(
        Report.id == report_id,
        Report.organization_id == organization_id,
    )


async def _get_report_or_404(
    db: AsyncSession, report_id: UUID, organization_id: UUID
) -> Report:
    """Fetch one report scoped to the caller's org, else 404.

    404 rather than 403 on a cross-tenant id, matching `app.core.scoping`: a
    status-code difference would turn this endpoint into an existence oracle for
    other tenants' report ids.
    """
    result = await db.execute(_private_report_stmt(report_id, organization_id))
    row = result.scalar_one_or_none()
    if not row:
        raise NotFoundError("Report", str(report_id))
    return row


async def _scope_website_ids(
    db: AsyncSession, organization_id: UUID, website_id: UUID | None
) -> list[UUID]:
    """The websites this report covers.

    A non-null `website_id` is verified against the org here as well as at the
    router boundary, because the service is also reachable from workers where no
    request ever passed through `assert_website_in_org`.
    """
    stmt = select(Website.id).where(
        Website.organization_id == organization_id,
        Website.deleted_at.is_(None),
    )
    if website_id is not None:
        stmt = stmt.where(Website.id == website_id)

    result = await db.execute(stmt)
    ids = list(result.scalars().all())

    if website_id is not None and not ids:
        raise NotFoundError("Website", str(website_id))
    return ids


async def _website_labels(
    db: AsyncSession, website_ids: list[UUID]
) -> dict[UUID, dict]:
    """name/domain per website, for the breakdown rows."""
    if not website_ids:
        return {}
    result = await db.execute(
        select(Website.id, Website.name, Website.domain)
        .where(Website.id.in_(website_ids))
        .order_by(Website.name)
    )
    return {row[0]: {"name": row[1], "domain": row[2]} for row in result.all()}


# ------------------------------------------------------------ data gathering

async def _traffic_totals(
    db: AsyncSession, website_ids: list[UUID], start: date, end: date
) -> dict:
    """Clicks/impressions/weighted position over a window, from the daily series.

    Position is impression-weighted. A plain average lets one obscure query at
    position 90 drag the headline position down as hard as a query with ten
    thousand impressions at position 3.

    `days_with_data` comes back so the payload can state how much of the period
    Search Console actually covered: GSC lags two to three days, and a monthly
    report generated on the 1st legitimately holds 28 days of data.
    """
    if not website_ids:
        return {
            "clicks": 0,
            "impressions": 0,
            "position_weighted": 0.0,
            "days_with_data": 0,
        }

    result = await db.execute(
        select(
            func.coalesce(func.sum(GscDate.clicks), 0),
            func.coalesce(func.sum(GscDate.impressions), 0),
            func.coalesce(
                func.sum(
                    cast(GscDate.position, Float) * cast(GscDate.impressions, Float)
                ),
                0.0,
            ),
            func.count(func.distinct(GscDate.date_metric)),
        ).where(
            GscDate.website_id.in_(website_ids),
            GscDate.date_metric >= start,
            GscDate.date_metric <= end,
        )
    )
    clicks, impressions, position_weight, day_count = result.one()
    return {
        "clicks": int(clicks or 0),
        "impressions": int(impressions or 0),
        "position_weighted": float(position_weight or 0.0),
        "days_with_data": int(day_count or 0),
    }


def _traffic_kpis(current: dict, previous: dict) -> dict:
    """The four headline KPIs plus their period-over-period deltas."""
    clicks = current["clicks"]
    impressions = current["impressions"]
    return {
        "clicks": clicks,
        "impressions": impressions,
        "ctr": round(_ratio(clicks, impressions), 4),
        "avg_position": round(_ratio(current["position_weighted"], impressions), 1),
        "previous_clicks": previous["clicks"],
        "previous_impressions": previous["impressions"],
        "previous_ctr": round(
            _ratio(previous["clicks"], previous["impressions"]), 4
        ),
        "previous_avg_position": round(
            _ratio(previous["position_weighted"], previous["impressions"]), 1
        ),
        "clicks_change_percent": _pct_change(previous["clicks"], clicks),
        "impressions_change_percent": _pct_change(
            previous["impressions"], impressions
        ),
        "days_with_data": current["days_with_data"],
        "previous_days_with_data": previous["days_with_data"],
    }


async def _daily_series(
    db: AsyncSession, website_ids: list[UUID], start: date, end: date
) -> list[dict]:
    """Per-day clicks/impressions across the period, for the trend line."""
    if not website_ids:
        return []
    result = await db.execute(
        select(
            GscDate.date_metric,
            func.coalesce(func.sum(GscDate.clicks), 0),
            func.coalesce(func.sum(GscDate.impressions), 0),
        )
        .where(
            GscDate.website_id.in_(website_ids),
            GscDate.date_metric >= start,
            GscDate.date_metric <= end,
        )
        .group_by(GscDate.date_metric)
        .order_by(GscDate.date_metric)
    )
    return [
        {
            "date": row[0].isoformat(),
            "clicks": int(row[1] or 0),
            "impressions": int(row[2] or 0),
        }
        for row in result.all()
    ]


async def _latest_snapshot_date(
    db: AsyncSession, model, website_ids: list[UUID], not_after: date
) -> date | None:
    """Newest snapshot stamp at or before `not_after`.

    `gsc_queries` / `gsc_pages` are snapshots, so "the data for this period" is
    the single most recent sync that landed inside it — never a SUM across
    stamps, which would add every earlier sync's copy of every row.
    """
    if not website_ids:
        return None
    result = await db.execute(
        select(func.max(model.date_metric)).where(
            model.website_id.in_(website_ids),
            model.date_metric <= not_after,
        )
    )
    return result.scalar_one_or_none()


async def _top_queries(
    db: AsyncSession, website_ids: list[UUID], period_end: date
) -> dict:
    """Best queries from the latest snapshot at or before the period end."""
    snapshot = await _latest_snapshot_date(db, GscQuery, website_ids, period_end)
    if snapshot is None:
        return {"snapshot_date": None, "rows": []}

    result = await db.execute(
        select(
            GscQuery.query,
            func.coalesce(func.sum(GscQuery.clicks), 0),
            func.coalesce(func.sum(GscQuery.impressions), 0),
            func.avg(GscQuery.position),
        )
        .where(
            GscQuery.website_id.in_(website_ids),
            GscQuery.date_metric == snapshot,
        )
        .group_by(GscQuery.query)
        .order_by(func.coalesce(func.sum(GscQuery.clicks), 0).desc())
        .limit(TOP_N)
    )

    rows = []
    for query_text, clicks, impressions, position in result.all():
        clicks = int(clicks or 0)
        impressions = int(impressions or 0)
        rows.append({
            "query": query_text,
            "clicks": clicks,
            "impressions": impressions,
            "ctr": round(_ratio(clicks, impressions), 4),
            "position": round(float(position or 0.0), 1),
        })
    return {"snapshot_date": snapshot.isoformat(), "rows": rows}


async def _top_pages(
    db: AsyncSession, website_ids: list[UUID], period_end: date
) -> dict:
    """Best pages from the latest snapshot at or before the period end."""
    snapshot = await _latest_snapshot_date(db, GscPage, website_ids, period_end)
    if snapshot is None:
        return {"snapshot_date": None, "rows": []}

    result = await db.execute(
        select(
            GscPage.page_url,
            func.coalesce(func.sum(GscPage.clicks), 0),
            func.coalesce(func.sum(GscPage.impressions), 0),
            func.avg(GscPage.position),
        )
        .where(
            GscPage.website_id.in_(website_ids),
            GscPage.date_metric == snapshot,
        )
        .group_by(GscPage.page_url)
        .order_by(func.coalesce(func.sum(GscPage.clicks), 0).desc())
        .limit(TOP_N)
    )

    rows = []
    for page_url, clicks, impressions, position in result.all():
        clicks = int(clicks or 0)
        impressions = int(impressions or 0)
        rows.append({
            "page_url": page_url,
            "clicks": clicks,
            "impressions": impressions,
            "ctr": round(_ratio(clicks, impressions), 4),
            "position": round(float(position or 0.0), 1),
        })
    return {"snapshot_date": snapshot.isoformat(), "rows": rows}


async def _latest_audits(
    db: AsyncSession, website_ids: list[UUID], period_end: date
) -> dict[UUID, dict]:
    """Most recent completed audit per website, as of the end of the period.

    Bounded by `period_end` so the report stays true to its window: an audit run
    after the period closed is not part of what was true then. One grouped
    subquery rather than a query per website — on a thirty-site organization the
    loop version was thirty round trips for one section.
    """
    if not website_ids:
        return {}

    _, cutoff = _day_bounds(period_end, period_end)

    latest = (
        select(
            SeoAudit.website_id.label("website_id"),
            func.max(SeoAudit.created_at).label("latest_at"),
        )
        .where(
            SeoAudit.website_id.in_(website_ids),
            SeoAudit.status == "completed",
            SeoAudit.created_at <= cutoff,
        )
        .group_by(SeoAudit.website_id)
        .subquery()
    )

    result = await db.execute(
        select(
            SeoAudit.website_id,
            SeoAudit.overall_score,
            SeoAudit.technical_score,
            SeoAudit.content_score,
            SeoAudit.ux_score,
            SeoAudit.pages_crawled,
            SeoAudit.created_at,
        ).join(
            latest,
            (SeoAudit.website_id == latest.c.website_id)
            & (SeoAudit.created_at == latest.c.latest_at),
        )
    )

    out: dict[UUID, dict] = {}
    for row in result.all():
        out[row[0]] = {
            "overall_score": int(row[1] or 0),
            "technical_score": int(row[2] or 0),
            "content_score": int(row[3] or 0),
            "ux_score": int(row[4] or 0),
            "pages_crawled": int(row[5] or 0),
            "audited_at": row[6].isoformat() if row[6] else None,
        }
    return out


async def _alert_activity(
    db: AsyncSession, website_ids: list[UUID], start: date, end: date
) -> dict:
    """Alerts raised and resolved inside the period, plus what is still open."""
    empty = {
        "raised": 0,
        "resolved": 0,
        "still_active": 0,
        "raised_by_severity": {},
        "rows": [],
        "per_website": {},
    }
    if not website_ids:
        return empty

    start_at, end_at = _day_bounds(start, end)

    raised_result = await db.execute(
        select(Alert.severity, func.count())
        .where(
            Alert.website_id.in_(website_ids),
            Alert.triggered_at >= start_at,
            Alert.triggered_at <= end_at,
        )
        .group_by(Alert.severity)
    )
    raised_by_severity = {row[0]: int(row[1]) for row in raised_result.all()}

    per_site_result = await db.execute(
        select(Alert.website_id, func.count())
        .where(
            Alert.website_id.in_(website_ids),
            Alert.triggered_at >= start_at,
            Alert.triggered_at <= end_at,
        )
        .group_by(Alert.website_id)
    )
    per_website = {row[0]: int(row[1]) for row in per_site_result.all()}

    resolved_result = await db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.website_id.in_(website_ids),
            Alert.resolved_at.is_not(None),
            Alert.resolved_at >= start_at,
            Alert.resolved_at <= end_at,
        )
    )
    active_result = await db.execute(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.website_id.in_(website_ids),
            Alert.status == "active",
        )
    )

    rows_result = await db.execute(
        select(
            Alert.title,
            Alert.severity,
            Alert.status,
            Alert.alert_type,
            Alert.triggered_at,
        )
        .where(
            Alert.website_id.in_(website_ids),
            Alert.triggered_at >= start_at,
            Alert.triggered_at <= end_at,
        )
        .order_by(Alert.triggered_at.desc())
        .limit(TOP_N)
    )

    return {
        "raised": sum(raised_by_severity.values()),
        "resolved": int(resolved_result.scalar_one() or 0),
        "still_active": int(active_result.scalar_one() or 0),
        "raised_by_severity": raised_by_severity,
        "rows": [
            {
                "title": row[0],
                "severity": row[1],
                "status": row[2],
                "alert_type": row[3],
                "triggered_at": row[4].isoformat() if row[4] else None,
            }
            for row in rows_result.all()
        ],
        "per_website": per_website,
    }


async def _opportunity_activity(
    db: AsyncSession, website_ids: list[UUID], start: date, end: date
) -> dict:
    """Opportunities detected and actioned in the period, plus the open backlog."""
    empty = {
        "detected": 0,
        "actioned": 0,
        "open": 0,
        "estimated_traffic_gain": 0,
        "by_type": {},
        "rows": [],
        "per_website": {},
    }
    if not website_ids:
        return empty

    start_at, end_at = _day_bounds(start, end)

    detected_result = await db.execute(
        select(Opportunity.opportunity_type, func.count())
        .where(
            Opportunity.website_id.in_(website_ids),
            Opportunity.detected_at >= start_at,
            Opportunity.detected_at <= end_at,
        )
        .group_by(Opportunity.opportunity_type)
    )
    by_type = {row[0]: int(row[1]) for row in detected_result.all()}

    actioned_result = await db.execute(
        select(func.count())
        .select_from(Opportunity)
        .where(
            Opportunity.website_id.in_(website_ids),
            Opportunity.actioned_at.is_not(None),
            Opportunity.actioned_at >= start_at,
            Opportunity.actioned_at <= end_at,
        )
    )

    # The open backlog is "as of generation time", not period-bounded: an
    # executive asking "what is still outstanding" means now, not then. The key
    # name says `open` and the section carries `as_of` to keep that explicit.
    open_result = await db.execute(
        select(
            Opportunity.website_id,
            func.count(),
            func.coalesce(func.sum(Opportunity.estimated_traffic_gain), 0),
        )
        .where(
            Opportunity.website_id.in_(website_ids),
            Opportunity.status.in_(["open", "in_progress"]),
        )
        .group_by(Opportunity.website_id)
    )
    per_website: dict[UUID, int] = {}
    open_total = 0
    gain_total = 0
    for website_id, count, gain in open_result.all():
        per_website[website_id] = int(count)
        open_total += int(count)
        gain_total += int(gain or 0)

    rows_result = await db.execute(
        select(
            Opportunity.title,
            Opportunity.opportunity_type,
            Opportunity.status,
            Opportunity.priority_score,
            Opportunity.estimated_traffic_gain,
        )
        .where(
            Opportunity.website_id.in_(website_ids),
            Opportunity.status.in_(["open", "in_progress"]),
        )
        .order_by(Opportunity.priority_score.desc())
        .limit(TOP_N)
    )

    return {
        "detected": sum(by_type.values()),
        "actioned": int(actioned_result.scalar_one() or 0),
        "open": open_total,
        "estimated_traffic_gain": gain_total,
        "by_type": by_type,
        "rows": [
            {
                "title": row[0],
                "opportunity_type": row[1],
                "status": row[2],
                "priority_score": int(row[3] or 0),
                "estimated_traffic_gain": int(row[4] or 0),
            }
            for row in rows_result.all()
        ],
        "per_website": per_website,
    }


async def _content_activity(
    db: AsyncSession, website_ids: list[UUID], start: date, end: date
) -> dict:
    """Articles published in the period, plus the work still outstanding.

    `content_articles` has no `published_at` column, so publication inside the
    period is approximated by `updated_at` on rows already in `published` status.
    The caveat travels with the data instead of being buried here.
    """
    empty = {
        "published_in_period": 0,
        "total_published": 0,
        "drafts": 0,
        "avg_seo_score": None,
        "rows": [],
        "per_website": {},
        "caveat": _CONTENT_DATE_CAVEAT,
    }
    if not website_ids:
        return empty

    start_at, end_at = _day_bounds(start, end)

    in_period = (
        ContentArticle.website_id.in_(website_ids),
        ContentArticle.status == "published",
        ContentArticle.updated_at >= start_at,
        ContentArticle.updated_at <= end_at,
    )

    counted = await db.execute(
        select(
            ContentArticle.website_id,
            func.count(),
            func.avg(cast(ContentArticle.seo_score, Float)),
        )
        .where(*in_period)
        .group_by(ContentArticle.website_id)
    )
    per_website: dict[UUID, int] = {}
    published_in_period = 0
    score_sum = 0.0
    score_rows = 0
    for website_id, count, avg_score in counted.all():
        count = int(count or 0)
        per_website[website_id] = count
        published_in_period += count
        if avg_score is not None:
            score_sum += float(avg_score) * count
            score_rows += count

    status_result = await db.execute(
        select(ContentArticle.status, func.count())
        .where(ContentArticle.website_id.in_(website_ids))
        .group_by(ContentArticle.status)
    )
    by_status = {row[0]: int(row[1]) for row in status_result.all()}

    rows_result = await db.execute(
        select(
            ContentArticle.title,
            ContentArticle.seo_score,
            ContentArticle.published_url,
            ContentArticle.updated_at,
        )
        .where(*in_period)
        .order_by(ContentArticle.updated_at.desc())
        .limit(TOP_N)
    )

    return {
        "published_in_period": published_in_period,
        "total_published": by_status.get("published", 0),
        "drafts": sum(c for s, c in by_status.items() if s != "published"),
        "avg_seo_score": round(score_sum / score_rows, 1) if score_rows else None,
        "rows": [
            {
                "title": row[0],
                "seo_score": int(row[1] or 0),
                "published_url": row[2],
                "published_at_approx": row[3].isoformat() if row[3] else None,
            }
            for row in rows_result.all()
        ],
        "per_website": per_website,
        "caveat": _CONTENT_DATE_CAVEAT,
    }


async def _per_website_breakdown(
    db: AsyncSession,
    website_ids: list[UUID],
    labels: dict[UUID, dict],
    start: date,
    end: date,
    previous_start: date,
    previous_end: date,
    audits: dict[UUID, dict],
    alerts: dict,
    opportunities: dict,
    content: dict,
) -> list[dict]:
    """One row per website: traffic, delta, audit score and open counts.

    Traffic is grouped in a single query over the daily series rather than one
    query per site, and the previous period is fetched the same way so the row
    can carry its own delta instead of only the org-wide one.
    """
    if not website_ids:
        return []

    async def _grouped(window_start: date, window_end: date) -> dict[UUID, dict]:
        result = await db.execute(
            select(
                GscDate.website_id,
                func.coalesce(func.sum(GscDate.clicks), 0),
                func.coalesce(func.sum(GscDate.impressions), 0),
                func.coalesce(
                    func.sum(
                        cast(GscDate.position, Float)
                        * cast(GscDate.impressions, Float)
                    ),
                    0.0,
                ),
            )
            .where(
                GscDate.website_id.in_(website_ids),
                GscDate.date_metric >= window_start,
                GscDate.date_metric <= window_end,
            )
            .group_by(GscDate.website_id)
        )
        return {
            row[0]: {
                "clicks": int(row[1] or 0),
                "impressions": int(row[2] or 0),
                "position_weighted": float(row[3] or 0.0),
            }
            for row in result.all()
        }

    current = await _grouped(start, end)
    previous = await _grouped(previous_start, previous_end)

    rows = []
    for website_id in website_ids:
        label = labels.get(website_id, {"name": "—", "domain": "—"})
        cur = current.get(
            website_id, {"clicks": 0, "impressions": 0, "position_weighted": 0.0}
        )
        prev = previous.get(
            website_id, {"clicks": 0, "impressions": 0, "position_weighted": 0.0}
        )
        audit = audits.get(website_id)
        rows.append({
            "website_id": str(website_id),
            "name": label["name"],
            "domain": label["domain"],
            "clicks": cur["clicks"],
            "impressions": cur["impressions"],
            "ctr": round(_ratio(cur["clicks"], cur["impressions"]), 4),
            "avg_position": round(
                _ratio(cur["position_weighted"], cur["impressions"]), 1
            ),
            "clicks_change_percent": _pct_change(prev["clicks"], cur["clicks"]),
            "impressions_change_percent": _pct_change(
                prev["impressions"], cur["impressions"]
            ),
            "audit_score": audit["overall_score"] if audit else None,
            "alerts_raised": alerts["per_website"].get(website_id, 0),
            "open_opportunities": opportunities["per_website"].get(website_id, 0),
            "articles_published": content["per_website"].get(website_id, 0),
        })

    rows.sort(key=lambda r: r["clicks"], reverse=True)
    return rows


# ---------------------------------------------------------------- generation

def _default_title(report_type: str, period_start: date, period_end: date) -> str:
    """Persian title used when the caller does not supply one."""
    base = TEMPLATE_TITLES_FA.get(report_type, "گزارش سئو")
    return f"{base} ({period_start.isoformat()} تا {period_end.isoformat()})"


def _build_overview(
    *,
    kpis: dict,
    audits: dict[UUID, dict],
    alerts: dict,
    opportunities: dict,
    content: dict,
    website_count: int,
) -> dict:
    """Headline block: the numbers a stakeholder reads first.

    `avg_audit_score` is None (not 0) when no website has a completed audit, so
    the UI can print "بدون داده" instead of a zero that reads like a failing
    score.
    """
    scores = [a["overall_score"] for a in audits.values()]
    return {
        "website_count": website_count,
        "clicks": kpis["clicks"],
        "impressions": kpis["impressions"],
        "ctr": kpis["ctr"],
        "avg_position": kpis["avg_position"],
        "clicks_change_percent": kpis["clicks_change_percent"],
        "impressions_change_percent": kpis["impressions_change_percent"],
        "avg_audit_score": round(sum(scores) / len(scores), 1) if scores else None,
        "audited_websites": len(scores),
        "alerts_raised": alerts["raised"],
        "alerts_resolved": alerts["resolved"],
        "alerts_still_active": alerts["still_active"],
        "opportunities_detected": opportunities["detected"],
        "opportunities_actioned": opportunities["actioned"],
        "opportunities_open": opportunities["open"],
        "articles_published": content["published_in_period"],
    }


async def generate_report(
    db: AsyncSession,
    organization_id: UUID,
    report_type: str,
    period_start: date,
    period_end: date,
    website_id: UUID | None = None,
    generated_by: UUID | None = None,
    title: str | None = None,
) -> Report:
    """Assemble and freeze one report.

    The row is inserted as `generating` and flushed before the aggregation runs,
    so a crash mid-assembly leaves a visible failed report rather than nothing at
    all. On success the payload is written and the status flips to `ready`; on
    failure the exception is recorded in `error_message` and re-raised, because
    the caller (router or worker) still needs to know it broke.

    Vocabulary and period order are re-validated here even though
    `ReportGenerateRequest` already checked them: workers call this directly with
    no schema in the path.
    """
    if report_type not in REPORT_TYPES:
        raise ValidationError(f"report_type must be one of {sorted(REPORT_TYPES)}")
    if period_start > period_end:
        raise ValidationError("period_start must be on or before period_end")

    website_ids = await _scope_website_ids(db, organization_id, website_id)
    previous_start, previous_end = _previous_period(period_start, period_end)

    row = Report(
        organization_id=organization_id,
        website_id=website_id,
        report_type=report_type,
        status="generating",
        title=title or _default_title(report_type, period_start, period_end),
        period_start=period_start,
        period_end=period_end,
        generated_by=generated_by,
        content={},
        metrics_snapshot={},
        share_enabled=False,
        view_count=0,
    )
    db.add(row)
    await db.flush()

    try:
        labels = await _website_labels(db, website_ids)
        current = await _traffic_totals(db, website_ids, period_start, period_end)
        previous = await _traffic_totals(
            db, website_ids, previous_start, previous_end
        )
        kpis = _traffic_kpis(current, previous)

        series = await _daily_series(db, website_ids, period_start, period_end)
        queries = await _top_queries(db, website_ids, period_end)
        pages = await _top_pages(db, website_ids, period_end)
        audits = await _latest_audits(db, website_ids, period_end)
        alerts = await _alert_activity(db, website_ids, period_start, period_end)
        opportunities = await _opportunity_activity(
            db, website_ids, period_start, period_end
        )
        content_stats = await _content_activity(
            db, website_ids, period_start, period_end
        )
        breakdown = await _per_website_breakdown(
            db,
            website_ids,
            labels,
            period_start,
            period_end,
            previous_start,
            previous_end,
            audits,
            alerts,
            opportunities,
            content_stats,
        )

        overview = _build_overview(
            kpis=kpis,
            audits=audits,
            alerts=alerts,
            opportunities=opportunities,
            content=content_stats,
            website_count=len(website_ids),
        )

        # Every section this type advertises, built from the one mapping the
        # template list also reads. A section with no source rows is still
        # emitted, flagged `has_data: false`.
        builders = {
            "overview": lambda: _section(
                "overview", has_data=len(website_ids) > 0, **overview
            ),
            "traffic": lambda: _section(
                "traffic",
                has_data=current["days_with_data"] > 0,
                **kpis,
                daily=series,
                period_previous_start=previous_start.isoformat(),
                period_previous_end=previous_end.isoformat(),
            ),
            "top_queries": lambda: _section(
                "top_queries",
                has_data=bool(queries["rows"]),
                snapshot_date=queries["snapshot_date"],
                snapshot_note=(
                    "این جدول از آخرین همگام‌سازی سرچ کنسول در این بازه گرفته "
                    "شده و مجموع کل بازه نیست."
                ),
                rows=queries["rows"],
            ),
            "top_pages": lambda: _section(
                "top_pages",
                has_data=bool(pages["rows"]),
                snapshot_date=pages["snapshot_date"],
                snapshot_note=(
                    "این جدول از آخرین همگام‌سازی سرچ کنسول در این بازه گرفته "
                    "شده و مجموع کل بازه نیست."
                ),
                rows=pages["rows"],
            ),
            "audit": lambda: _section(
                "audit",
                has_data=bool(audits),
                avg_overall_score=overview["avg_audit_score"],
                audited_websites=overview["audited_websites"],
                rows=[
                    {
                        "website_id": str(wid),
                        "name": labels.get(wid, {}).get("name", "—"),
                        "domain": labels.get(wid, {}).get("domain", "—"),
                        **data,
                    }
                    for wid, data in audits.items()
                ],
            ),
            "alerts": lambda: _section(
                "alerts",
                has_data=alerts["raised"] > 0 or alerts["still_active"] > 0,
                raised=alerts["raised"],
                resolved=alerts["resolved"],
                still_active=alerts["still_active"],
                by_severity=alerts["raised_by_severity"],
                rows=alerts["rows"],
            ),
            "opportunities": lambda: _section(
                "opportunities",
                has_data=opportunities["detected"] > 0 or opportunities["open"] > 0,
                detected=opportunities["detected"],
                actioned=opportunities["actioned"],
                open=opportunities["open"],
                estimated_traffic_gain=opportunities["estimated_traffic_gain"],
                by_type=opportunities["by_type"],
                rows=opportunities["rows"],
                as_of=_now().isoformat(),
            ),
            "content": lambda: _section(
                "content",
                has_data=content_stats["published_in_period"] > 0
                or content_stats["total_published"] > 0,
                published_in_period=content_stats["published_in_period"],
                total_published=content_stats["total_published"],
                drafts=content_stats["drafts"],
                avg_seo_score=content_stats["avg_seo_score"],
                rows=content_stats["rows"],
                caveat=content_stats["caveat"],
            ),
            "websites": lambda: _section(
                "websites", has_data=bool(breakdown), rows=breakdown
            ),
        }

        sections = [
            builders[key]() for key in _SECTIONS_BY_TYPE[report_type] if key in builders
        ]

        row.content = {
            "report_type": report_type,
            "title": row.title,
            "period": {
                "start": period_start.isoformat(),
                "end": period_end.isoformat(),
                "previous_start": previous_start.isoformat(),
                "previous_end": previous_end.isoformat(),
                "days": (period_end - period_start).days + 1,
            },
            "scope": {
                "level": "website" if website_id is not None else "organization",
                "website_count": len(website_ids),
                # Names/domains only. No organization id, no user id: this
                # payload is served verbatim on the public share endpoint.
                "websites": [
                    {"name": v["name"], "domain": v["domain"]}
                    for v in labels.values()
                ],
            },
            "generated_at": _now().isoformat(),
            "data_sources": {
                "traffic": "gsc_dates (daily series)",
                "queries_pages": "gsc_queries / gsc_pages (latest snapshot in period)",
                "audit": "seo_audits (latest completed at period end)",
                "alerts": "alerts (triggered/resolved within period)",
                "opportunities": "opportunities (detected/actioned within period; open as of generation)",
                "content": "content_articles (published, updated_at within period)",
            },
            "sections": sections,
            "empty_sections": [
                s["key"] for s in sections if not s["has_data"]
            ],
        }

        row.metrics_snapshot = {
            "clicks": kpis["clicks"],
            "impressions": kpis["impressions"],
            "ctr": kpis["ctr"],
            "avg_position": kpis["avg_position"],
            "clicks_change_percent": kpis["clicks_change_percent"],
            "impressions_change_percent": kpis["impressions_change_percent"],
            "avg_audit_score": overview["avg_audit_score"],
            "alerts_raised": alerts["raised"],
            "opportunities_open": opportunities["open"],
            "articles_published": content_stats["published_in_period"],
            "website_count": len(website_ids),
        }
        row.status = "ready"
        row.generated_at = _now()
        row.error_message = None
        await db.flush()

        logger.info(
            "[reports] generated %s (%s) for org %s: %d website(s), %d empty section(s)",
            row.id,
            report_type,
            organization_id,
            len(website_ids),
            len(row.content["empty_sections"]),
        )
        return row

    except Exception as exc:  # noqa: BLE001 - recorded then re-raised
        row.status = "failed"
        row.error_message = str(exc)[:2000]
        await db.flush()
        logger.exception(
            "[reports] generation failed for org %s (%s)", organization_id, report_type
        )
        raise


# ---------------------------------------------------------------------- read

async def list_reports(
    db: AsyncSession,
    *,
    organization_id: UUID,
    website_id: UUID | None = None,
    report_type: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Report]:
    """Reports for the org, most recent period first.

    `website_id` filters to one site's reports; org-level reports (null
    `website_id`) are a separate scope and are not folded in, because "the report
    for this site" and "the report covering everything" are different documents.
    """
    stmt = select(Report).where(Report.organization_id == organization_id)

    if website_id is not None:
        stmt = stmt.where(Report.website_id == website_id)
    if report_type:
        stmt = stmt.where(Report.report_type == report_type)
    if status:
        stmt = stmt.where(Report.status == status)

    stmt = stmt.order_by(
        Report.period_start.desc(), Report.created_at.desc()
    ).limit(limit).offset(offset)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_report(
    db: AsyncSession, report_id: UUID, organization_id: UUID
) -> Report:
    """One report with its full frozen payload, scoped to the org."""
    return await _get_report_or_404(db, report_id, organization_id)


async def delete_report(
    db: AsyncSession, report_id: UUID, organization_id: UUID
) -> None:
    """Hard-delete a report.

    A hard delete rather than a soft one: the row is a derived artefact that can
    be regenerated from the same period, and leaving revoked-but-present share
    tokens around is a liability the table does not need.
    """
    row = await _get_report_or_404(db, report_id, organization_id)
    await db.delete(row)
    await db.flush()
    logger.info("[reports] deleted %s from org %s", report_id, organization_id)


async def get_report_summary(db: AsyncSession, organization_id: UUID) -> dict:
    """Counts by type and status, plus the newest report of each type."""
    status_result = await db.execute(
        select(Report.status, func.count())
        .where(Report.organization_id == organization_id)
        .group_by(Report.status)
    )
    by_status = {row[0]: int(row[1]) for row in status_result.all()}

    type_result = await db.execute(
        select(Report.report_type, func.count())
        .where(Report.organization_id == organization_id)
        .group_by(Report.report_type)
    )
    counts_by_type = {row[0]: int(row[1]) for row in type_result.all()}

    # Latest per type. Ordered by period then creation so a backfilled report of
    # an older period does not displace the current one.
    latest_result = await db.execute(
        select(
            Report.id,
            Report.report_type,
            Report.generated_at,
            Report.period_start,
            Report.created_at,
        )
        .where(Report.organization_id == organization_id)
        .order_by(Report.period_start.desc(), Report.created_at.desc())
    )
    latest_by_type: dict[str, tuple] = {}
    for row in latest_result.all():
        latest_by_type.setdefault(row[1], row)

    by_type = []
    for report_type in REPORT_TYPES:
        count = counts_by_type.get(report_type, 0)
        latest = latest_by_type.get(report_type)
        by_type.append({
            "report_type": report_type,
            "count": count,
            "latest_report_id": latest[0] if latest else None,
            "latest_generated_at": latest[2] if latest else None,
        })

    return {
        "total": sum(counts_by_type.values()),
        "by_type": by_type,
        "ready": by_status.get("ready", 0),
        "generating": by_status.get("generating", 0),
        "failed": by_status.get("failed", 0),
    }


def get_report_templates() -> list[dict]:
    """The predefined report shapes offered by the UI.

    Sections are read from `_SECTIONS_BY_TYPE`, the same mapping
    `generate_report` iterates, so an advertised key always corresponds to a
    section the generator actually writes.
    """
    templates = []
    for report_type in REPORT_TYPES:
        templates.append({
            "report_type": report_type,
            "title_fa": TEMPLATE_TITLES_FA[report_type],
            "description_fa": TEMPLATE_DESCRIPTIONS_FA[report_type],
            "default_period_days": DEFAULT_PERIOD_DAYS[report_type],
            "sections": [
                {"key": key, "title_fa": SECTION_TITLES_FA[key]}
                for key in _SECTIONS_BY_TYPE[report_type]
            ],
        })
    return templates


# --------------------------------------------------------------------- share

async def enable_share(
    db: AsyncSession,
    report_id: UUID,
    organization_id: UUID,
    ttl_days: int | None = None,
) -> Report:
    """Mint a public share link for a ready report.

    Only `ready` reports can be shared: publishing a `generating` row would put
    an empty document behind a public URL, and a `failed` one would publish an
    error.

    Calling this on an already-shared report rotates the token. That is the
    intended way to invalidate a link that was pasted somewhere wrong without
    losing the report.
    """
    row = await _get_report_or_404(db, report_id, organization_id)

    if row.status != "ready":
        raise ConflictError(
            f"فقط گزارش آماده را می‌توان به اشتراک گذاشت (وضعیت فعلی: {row.status})"
        )

    # 32 bytes of urandom, url-safe. This token is the ONLY credential on the
    # public endpoint, so it must be unguessable rather than derived from the
    # report id or any other value a visitor could know.
    row.share_token = secrets.token_urlsafe(32)
    row.share_enabled = True
    row.share_expires_at = _now() + timedelta(
        days=ttl_days if ttl_days is not None else DEFAULT_SHARE_TTL_DAYS
    )
    await db.flush()

    logger.info(
        "[reports] share enabled for %s (org %s) until %s",
        report_id, organization_id, row.share_expires_at,
    )
    return row


async def revoke_share(
    db: AsyncSession, report_id: UUID, organization_id: UUID
) -> Report:
    """Kill the public link.

    The token is cleared, not just flagged off: a leaked URL must stay dead even
    if somebody re-enables sharing later. Re-enabling mints a fresh token.
    """
    row = await _get_report_or_404(db, report_id, organization_id)

    row.share_enabled = False
    row.share_token = None
    row.share_expires_at = None
    await db.flush()

    logger.info("[reports] share revoked for %s (org %s)", report_id, organization_id)
    return row


async def get_report_by_share_token(db: AsyncSession, share_token: str) -> Report:
    """Resolve a public share link. **Unauthenticated path.**

    The token is looked up on the indexed column and then re-compared with
    `secrets.compare_digest`. The database comparison alone would already be
    correct, but the constant-time re-check means the response time of this
    endpoint does not vary with how many leading characters of a guess were
    right, which is the only side channel an anonymous caller has here.

    Every failure raises the same `NotFoundError`: a revoked link, an expired
    link and a fabricated token must be indistinguishable, otherwise the
    endpoint confirms which tokens once existed.
    """
    if not share_token or len(share_token) > 64:
        raise NotFoundError("Report", "shared")

    result = await db.execute(
        select(Report).where(
            Report.share_token == share_token,
            Report.share_enabled.is_(True),
        )
    )
    row = result.scalar_one_or_none()

    if not row or not row.share_token:
        raise NotFoundError("Report", "shared")
    if not secrets.compare_digest(row.share_token, share_token):
        raise NotFoundError("Report", "shared")
    if row.share_expires_at is not None and row.share_expires_at <= _now():
        raise NotFoundError("Report", "shared")
    if row.status != "ready":
        raise NotFoundError("Report", "shared")

    row.view_count = (row.view_count or 0) + 1
    await db.flush()
    return row


# -------------------------------------------------------------------- export

# Column order for the CSV. Fixed and explicit rather than derived from dict
# keys, so a spreadsheet built against last month's export still lines up.
_CSV_KPI_ROWS = (
    ("clicks", "کلیک"),
    ("impressions", "نمایش"),
    ("ctr", "نرخ کلیک"),
    ("avg_position", "میانگین رتبه"),
    ("clicks_change_percent", "تغییر کلیک (درصد)"),
    ("impressions_change_percent", "تغییر نمایش (درصد)"),
    ("avg_audit_score", "امتیاز سلامت فنی"),
    ("alerts_raised", "هشدارهای ثبت‌شده"),
    ("opportunities_open", "فرصت‌های باز"),
    ("articles_published", "مقالات منتشرشده"),
    ("website_count", "تعداد وب‌سایت"),
)


def build_report_csv(report: Report) -> str:
    """Render a report as CSV, using the stdlib writer.

    Built from `metrics_snapshot` and the frozen `content`, never by re-querying:
    the export must match the document on screen exactly.

    A UTF-8 BOM is prepended because the audience opens these in Excel, which
    otherwise renders Persian headers as mojibake. `csv.writer` handles the
    quoting, so a query containing a comma or a newline cannot break the row
    structure.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    content = report.content or {}
    period = content.get("period", {})

    writer.writerow(["گزارش", report.title or ""])
    writer.writerow(["نوع گزارش", report.report_type])
    writer.writerow(["از تاریخ", period.get("start", report.period_start.isoformat())])
    writer.writerow(["تا تاریخ", period.get("end", report.period_end.isoformat())])
    writer.writerow([
        "زمان تولید",
        report.generated_at.isoformat() if report.generated_at else "",
    ])
    writer.writerow([])

    snapshot = report.metrics_snapshot or {}
    writer.writerow(["شاخص", "مقدار"])
    for key, label in _CSV_KPI_ROWS:
        value = snapshot.get(key)
        writer.writerow([label, "" if value is None else value])
    writer.writerow([])

    for section in content.get("sections", []):
        rows = section.get("rows")
        if not isinstance(rows, list) or not rows:
            # Sections with no tabular body (or no data at all) still get a line,
            # so the export shows the reader that the section existed and was
            # empty rather than silently omitting it.
            writer.writerow([section.get("title_fa", section.get("key", ""))])
            if not section.get("has_data", True):
                writer.writerow([_NO_DATA_NOTE])
            writer.writerow([])
            continue

        writer.writerow([section.get("title_fa", section.get("key", ""))])
        # Union of keys across rows, first-seen order: rows in a section are
        # homogeneous in practice, but a missing optional key must not shift
        # every later column.
        headers: list[str] = []
        for row in rows:
            for key in row.keys():
                if key not in headers:
                    headers.append(key)
        writer.writerow(headers)
        for row in rows:
            writer.writerow(["" if row.get(h) is None else row.get(h) for h in headers])
        writer.writerow([])

    return "﻿" + buffer.getvalue()


def build_print_payload(report: Report) -> dict:
    """Print-optimised payload for the browser's own PDF export.

    There is deliberately no server-side PDF renderer: none of weasyprint /
    reportlab / wkhtmltopdf is installed and adding one is a heavy dependency for
    a document the browser can already produce. The frontend renders this with a
    print stylesheet and calls `window.print()`, which yields a real PDF through
    the OS print dialog with correct RTL shaping and embedded Persian fonts —
    something the pure-python renderers handle poorly anyway.
    """
    return {
        "title": report.title,
        "report_type": report.report_type,
        "period_start": report.period_start.isoformat(),
        "period_end": report.period_end.isoformat(),
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "metrics_snapshot": report.metrics_snapshot or {},
        "content": report.content or {},
        "print_hint": "برای دریافت PDF از گزینه چاپ مرورگر استفاده کنید.",
    }


__all__ = [
    "generate_report",
    "list_reports",
    "get_report",
    "delete_report",
    "get_report_summary",
    "get_report_templates",
    "enable_share",
    "revoke_share",
    "get_report_by_share_token",
    "build_report_csv",
    "build_print_payload",
    "REPORT_TYPES",
    "SECTION_TITLES_FA",
    "DEFAULT_PERIOD_DAYS",
]
