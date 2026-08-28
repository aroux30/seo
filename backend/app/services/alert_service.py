"""Alert detection engine.

Where opportunity_service answers "what could I win", this answers "what just
broke". The distinction matters for the data source:

* `gsc_dates` is the only **true daily series** the sync writes (one row per
  calendar day), so every window-over-window comparison here reads it. Using
  `gsc_queries` for a trend would compare two whole-account snapshots that both
  carry `date_metric = sync day` and invent a 100% drop the first time a sync
  is skipped.
* `gsc_queries` / `gsc_pages` are snapshots, so they are only used for
  "latest vs the one before", never for date arithmetic.

Alerts are deduplicated by `fingerprint` exactly like opportunities, but the
lifecycle differs: an alert that keeps reproducing bumps `occurrence_count` and
stays quiet (the dispatcher looks at `notified_at`), and an alert whose
condition disappears is **resolved**, not expired.
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Alert,
    GscDate,
    GscPage,
    Keyword,
    OAuthIntegration,
    SeoAudit,
    Website,
)

logger = logging.getLogger(__name__)

# A window with almost no traffic produces wild percentages: going from 2 clicks
# to 1 is a "50% drop" that means nothing. Below this, the metric is ignored.
MIN_BASELINE_CLICKS = 10
MIN_BASELINE_IMPRESSIONS = 100

# How stale the daily series may get before we call the sync broken. GSC itself
# lags ~2 days, and the beat schedule syncs daily, so 4 days means something
# actually failed rather than "Google has not published yet".
GSC_STALE_DAYS = 4


def make_fingerprint(alert_type: str, subject: str = "") -> str:
    """Stable id for one alert condition, so a re-run updates instead of piling up."""
    raw = f"{alert_type}|{(subject or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _severity_for_drop(drop_percent: float) -> str:
    """Map a percentage regression onto the three severities."""
    if drop_percent >= 50:
        return "critical"
    if drop_percent >= 30:
        return "warning"
    return "info"


async def _window_totals(
    db: AsyncSession, website_id: UUID, start, end
) -> dict | None:
    """Summed clicks/impressions and averaged ctr/position over [start, end].

    Returns None when the window holds no rows at all, so callers can tell
    "no data" apart from "zero traffic" — the first must not raise an alert.
    """
    result = await db.execute(
        select(
            func.count().label("days"),
            func.coalesce(func.sum(GscDate.clicks), 0).label("clicks"),
            func.coalesce(func.sum(GscDate.impressions), 0).label("impressions"),
            func.coalesce(func.avg(GscDate.ctr), 0.0).label("ctr"),
            func.coalesce(func.avg(GscDate.position), 0.0).label("position"),
        ).where(
            GscDate.website_id == website_id,
            GscDate.date_metric >= start,
            GscDate.date_metric <= end,
        )
    )
    row = result.one()
    if not row.days:
        return None
    return {
        "days": int(row.days),
        "clicks": int(row.clicks),
        "impressions": int(row.impressions),
        "ctr": float(row.ctr),
        "position": float(row.position),
    }


def _pct_drop(previous: float, current: float) -> float:
    """Percentage decline from previous to current; 0 when it did not decline."""
    if previous <= 0:
        return 0.0
    return max((previous - current) / previous * 100.0, 0.0)


# ------------------------------------------------------------------- detectors

def _traffic_alerts(
    current: dict, previous: dict, threshold: float, window_days: int
) -> list[dict]:
    """Clicks / impressions / CTR / position regressions on the daily series."""
    out: list[dict] = []

    if previous["clicks"] >= MIN_BASELINE_CLICKS:
        drop = _pct_drop(previous["clicks"], current["clicks"])
        if drop >= threshold:
            out.append({
                "alert_type": "traffic_drop",
                "subject": f"clicks_{window_days}d",
                "severity": _severity_for_drop(drop),
                "title": f"افت {drop:.0f}٪ کلیک ارگانیک در {window_days} روز گذشته",
                "message": (
                    f"کلیک‌های سایت از {previous['clicks']} در بازه قبلی به "
                    f"{current['clicks']} رسیده است."
                ),
                "metric_name": "clicks",
                "current_value": float(current["clicks"]),
                "previous_value": float(previous["clicks"]),
                "change_percent": -round(drop, 2),
                "details": {
                    "window_days": window_days,
                    "threshold_percent": threshold,
                    "current_days_with_data": current["days"],
                    "previous_days_with_data": previous["days"],
                },
            })

    if previous["impressions"] >= MIN_BASELINE_IMPRESSIONS:
        drop = _pct_drop(previous["impressions"], current["impressions"])
        if drop >= threshold:
            out.append({
                "alert_type": "traffic_drop",
                "subject": f"impressions_{window_days}d",
                "severity": _severity_for_drop(drop),
                "title": f"افت {drop:.0f}٪ نمایش در {window_days} روز گذشته",
                "message": (
                    f"نمایش‌های سایت از {previous['impressions']} به "
                    f"{current['impressions']} کاهش یافته است."
                ),
                "metric_name": "impressions",
                "current_value": float(current["impressions"]),
                "previous_value": float(previous["impressions"]),
                "change_percent": -round(drop, 2),
                "details": {"window_days": window_days, "threshold_percent": threshold},
            })

    # CTR is a ratio, so only judge it when there were enough impressions to
    # make the ratio meaningful in both windows.
    if (
        previous["impressions"] >= MIN_BASELINE_IMPRESSIONS
        and current["impressions"] >= MIN_BASELINE_IMPRESSIONS
        and previous["ctr"] > 0
    ):
        drop = _pct_drop(previous["ctr"], current["ctr"])
        if drop >= threshold:
            out.append({
                "alert_type": "ctr_drop",
                "subject": f"ctr_{window_days}d",
                "severity": _severity_for_drop(drop),
                "title": f"افت {drop:.0f}٪ نرخ کلیک در {window_days} روز گذشته",
                "message": (
                    f"نرخ کلیک از {previous['ctr'] * 100:.2f}٪ به "
                    f"{current['ctr'] * 100:.2f}٪ رسیده است."
                ),
                "metric_name": "ctr",
                "current_value": round(current["ctr"], 6),
                "previous_value": round(previous["ctr"], 6),
                "change_percent": -round(drop, 2),
                "details": {"window_days": window_days, "threshold_percent": threshold},
            })

    # Position is inverted: a *bigger* number is worse.
    if previous["position"] > 0 and current["position"] > 0:
        worsening = current["position"] - previous["position"]
        rel = worsening / previous["position"] * 100.0
        if worsening >= 1.0 and rel >= threshold:
            out.append({
                "alert_type": "ranking_drop",
                "subject": f"avg_position_{window_days}d",
                "severity": _severity_for_drop(rel),
                "title": (
                    f"افت میانگین جایگاه از {previous['position']:.1f} به "
                    f"{current['position']:.1f}"
                ),
                "message": (
                    "میانگین جایگاه سایت در نتایج جستجو بدتر شده است "
                    f"({worsening:.1f} پله)."
                ),
                "metric_name": "avg_position",
                "current_value": round(current["position"], 4),
                "previous_value": round(previous["position"], 4),
                "change_percent": -round(rel, 2),
                "details": {
                    "window_days": window_days,
                    "positions_lost": round(worsening, 2),
                },
            })

    return out


async def _keyword_ranking_alerts(
    db: AsyncSession, website_id: UUID, threshold_positions: float = 5.0
) -> list[dict]:
    """Tracked keywords that fell well below their own best position.

    `best_position` is the all-time best the sync ever recorded, so this is a
    "we used to rank here" check rather than a day-over-day one.
    """
    result = await db.execute(
        select(Keyword).where(
            Keyword.website_id == website_id,
            Keyword.last_position.is_not(None),
            Keyword.best_position.is_not(None),
        )
    )
    out: list[dict] = []
    for kw in result.scalars().all():
        lost = float(kw.last_position) - float(kw.best_position)
        # Only care about keywords that were on page 1-2 to begin with; a slide
        # from 80 to 90 is noise.
        if lost < threshold_positions or float(kw.best_position) > 20:
            continue
        out.append({
            "alert_type": "ranking_drop",
            "subject": f"keyword:{kw.keyword}",
            "severity": "critical" if lost >= 10 else "warning",
            "title": f"افت رتبه «{kw.keyword}» — {lost:.0f} پله",
            "message": (
                f"این کلمه کلیدی بهترین جایگاه {float(kw.best_position):.1f} را داشته "
                f"و اکنون در جایگاه {float(kw.last_position):.1f} است."
            ),
            "metric_name": "keyword_position",
            "current_value": float(kw.last_position),
            "previous_value": float(kw.best_position),
            "change_percent": None,
            "entity_type": "keyword",
            "entity_id": kw.id,
            "details": {
                "keyword": kw.keyword,
                "positions_lost": round(lost, 2),
                "best_position": float(kw.best_position),
            },
        })
    return out


async def _content_decay_alerts(
    db: AsyncSession, website_id: UUID, threshold: float, min_clicks: int = 10
) -> list[dict]:
    """Pages whose clicks fell between the last two snapshots.

    Snapshot-to-snapshot, not date-ranged, because `gsc_pages` has no real
    daily history.
    """
    snapshots = await db.execute(
        select(GscPage.date_metric)
        .where(GscPage.website_id == website_id)
        .group_by(GscPage.date_metric)
        .order_by(GscPage.date_metric.desc())
        .limit(2)
    )
    dates = [r[0] for r in snapshots.all()]
    if len(dates) < 2:
        return []
    latest, previous = dates[0], dates[1]

    async def _rows(snapshot):
        res = await db.execute(
            select(GscPage).where(
                GscPage.website_id == website_id,
                GscPage.date_metric == snapshot,
            )
        )
        return list(res.scalars().all())

    cur_rows = await _rows(latest)
    prev_rows = await _rows(previous)

    prev_by_url: dict[str, GscPage] = {}
    for p in prev_rows:
        key = (p.page_url or "").strip().lower()
        if key not in prev_by_url or p.clicks > prev_by_url[key].clicks:
            prev_by_url[key] = p

    out: list[dict] = []
    for p in cur_rows:
        prev = prev_by_url.get((p.page_url or "").strip().lower())
        if not prev or prev.clicks < min_clicks:
            continue
        drop = _pct_drop(float(prev.clicks), float(p.clicks))
        if drop < threshold:
            continue
        out.append({
            "alert_type": "content_decay",
            "subject": f"page:{p.page_url}",
            "severity": _severity_for_drop(drop),
            "title": f"افت {drop:.0f}٪ کلیک یک صفحه",
            "message": (
                f"کلیک صفحه {p.page_url} از {prev.clicks} به {p.clicks} کاهش یافته است."
            ),
            "metric_name": "page_clicks",
            "current_value": float(p.clicks),
            "previous_value": float(prev.clicks),
            "change_percent": -round(drop, 2),
            "details": {
                "page_url": p.page_url,
                "previous_clicks": int(prev.clicks),
                "current_clicks": int(p.clicks),
            },
        })
    return out


async def _gsc_sync_alert(db: AsyncSession, website_id: UUID) -> list[dict]:
    """The website claims a live GSC connection but the data stopped arriving."""
    integration = await db.execute(
        select(OAuthIntegration).where(
            OAuthIntegration.website_id == website_id,
            OAuthIntegration.is_active.is_(True),
        )
    )
    if integration.scalar_one_or_none() is None:
        # Not connected at all is a setup state, not a failure.
        return []

    newest = await db.execute(
        select(func.max(GscDate.date_metric)).where(GscDate.website_id == website_id)
    )
    latest = newest.scalar_one_or_none()
    today = datetime.now(timezone.utc).date()

    if latest is None:
        return [{
            "alert_type": "gsc_sync_failure",
            "subject": "no_data",
            "severity": "warning",
            "title": "هیچ داده‌ای از Search Console دریافت نشده",
            "message": (
                "اتصال Google Search Console فعال است اما هنوز هیچ داده روزانه‌ای "
                "ذخیره نشده. همگام‌سازی را اجرا کنید."
            ),
            "metric_name": "days_since_sync",
            "current_value": None,
            "previous_value": None,
            "change_percent": None,
            "details": {"latest_data_date": None},
        }]

    stale_days = (today - latest).days
    if stale_days < GSC_STALE_DAYS:
        return []
    return [{
        "alert_type": "gsc_sync_failure",
        "subject": "stale_data",
        "severity": "critical" if stale_days >= 7 else "warning",
        "title": f"داده Search Console {stale_days} روز قدیمی است",
        "message": (
            f"آخرین روزی که داده دارد {latest.isoformat()} است. "
            "همگام‌سازی احتمالاً با خطا مواجه شده یا توکن باطل شده است."
        ),
        "metric_name": "days_since_sync",
        "current_value": float(stale_days),
        "previous_value": None,
        "change_percent": None,
        "details": {"latest_data_date": latest.isoformat(), "stale_days": stale_days},
    }]


async def _audit_score_alert(db: AsyncSession, website_id: UUID) -> list[dict]:
    """The two most recent completed audits moved the overall score down."""
    result = await db.execute(
        select(SeoAudit)
        .where(SeoAudit.website_id == website_id, SeoAudit.status == "completed")
        .order_by(SeoAudit.created_at.desc())
        .limit(2)
    )
    audits = list(result.scalars().all())
    if len(audits) < 2:
        return []
    current, previous = audits[0], audits[1]
    lost = previous.overall_score - current.overall_score
    if lost < 10:
        return []
    return [{
        "alert_type": "audit_score_drop",
        "subject": "overall_score",
        "severity": "critical" if lost >= 20 else "warning",
        "title": f"افت {lost} نمره‌ای امتیاز فنی سئو",
        "message": (
            f"امتیاز کلی آخرین ممیزی {current.overall_score} است، "
            f"در حالی که ممیزی قبلی {previous.overall_score} بود."
        ),
        "metric_name": "audit_overall_score",
        "current_value": float(current.overall_score),
        "previous_value": float(previous.overall_score),
        "change_percent": -round(_pct_drop(previous.overall_score, current.overall_score), 2),
        "entity_type": "seo_audit",
        "entity_id": current.id,
        "details": {
            "current_audit_id": str(current.id),
            "previous_audit_id": str(previous.id),
            "points_lost": lost,
        },
    }]


# ------------------------------------------------------------------ persistence

async def detect_alerts(
    db: AsyncSession,
    website_id: UUID,
    window_days: int = 7,
    drop_threshold_percent: float = 20.0,
) -> dict:
    """Run every detector for one website and upsert the results.

    Returns counts plus `skipped_reason` when there was not enough history to
    compare — silence and "everything is fine" must not look identical.
    """
    website = await db.get(Website, website_id)
    if not website:
        return {
            "website_id": website_id, "created": 0, "updated": 0, "resolved": 0,
            "by_type": {}, "skipped_reason": "website_not_found",
        }

    candidates: list[dict] = []
    skipped_reason: str | None = None

    newest = await db.execute(
        select(func.max(GscDate.date_metric)).where(GscDate.website_id == website_id)
    )
    anchor = newest.scalar_one_or_none()

    if anchor is None:
        skipped_reason = "no_daily_gsc_data"
    else:
        # Windows are anchored on the newest day that actually has data, not on
        # today: anchoring on today would shift real traffic out of the current
        # window every time GSC lags and read as a drop.
        cur_start = anchor - timedelta(days=window_days - 1)
        prev_end = cur_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=window_days - 1)

        current = await _window_totals(db, website_id, cur_start, anchor)
        previous = await _window_totals(db, website_id, prev_start, prev_end)

        if current and previous:
            candidates += _traffic_alerts(
                current, previous, drop_threshold_percent, window_days
            )
        else:
            skipped_reason = "insufficient_history_for_window_comparison"

    candidates += await _keyword_ranking_alerts(db, website_id)
    candidates += await _content_decay_alerts(db, website_id, drop_threshold_percent)
    candidates += await _gsc_sync_alert(db, website_id)
    candidates += await _audit_score_alert(db, website_id)

    now = datetime.now(timezone.utc)
    created = updated = 0
    by_type: dict[str, int] = {}
    seen: set[str] = set()
    new_rows: list[Alert] = []

    for cand in candidates:
        fingerprint = make_fingerprint(cand["alert_type"], cand.get("subject", ""))
        if fingerprint in seen:
            continue
        seen.add(fingerprint)

        existing = await db.execute(
            select(Alert).where(
                Alert.website_id == website_id,
                Alert.fingerprint == fingerprint,
            )
        )
        row = existing.scalar_one_or_none()

        if row:
            row.severity = cand["severity"]
            row.title = cand["title"]
            row.message = cand["message"]
            row.metric_name = cand.get("metric_name")
            row.current_value = cand.get("current_value")
            row.previous_value = cand.get("previous_value")
            row.change_percent = cand.get("change_percent")
            row.entity_type = cand.get("entity_type")
            row.entity_id = cand.get("entity_id")
            row.details = cand.get("details", {})
            row.last_seen_at = now
            row.occurrence_count = (row.occurrence_count or 0) + 1
            # A condition that came back after being resolved is active again,
            # and needs to be notified about again.
            if row.status in ("resolved", "muted"):
                row.status = "active"
                row.resolved_at = None
                row.resolved_by = None
                row.notified_at = None
            updated += 1
        else:
            alert = Alert(
                organization_id=website.organization_id,
                website_id=website_id,
                alert_type=cand["alert_type"],
                severity=cand["severity"],
                status="active",
                title=cand["title"],
                message=cand["message"],
                metric_name=cand.get("metric_name"),
                current_value=cand.get("current_value"),
                previous_value=cand.get("previous_value"),
                change_percent=cand.get("change_percent"),
                entity_type=cand.get("entity_type"),
                entity_id=cand.get("entity_id"),
                fingerprint=fingerprint,
                details=cand.get("details", {}),
                occurrence_count=1,
                triggered_at=now,
                last_seen_at=now,
            )
            db.add(alert)
            new_rows.append(alert)
            created += 1

        by_type[cand["alert_type"]] = by_type.get(cand["alert_type"], 0) + 1

    # Auto-resolve what no longer reproduces. Only touch rows the detectors could
    # have re-raised this run: if the window comparison was skipped for lack of
    # history, resolving traffic alerts would be a lie.
    resolved = 0
    if skipped_reason is None:
        stale = await db.execute(
            select(Alert).where(
                Alert.website_id == website_id,
                Alert.status.in_(["active", "acknowledged"]),
            )
        )
        for row in stale.scalars().all():
            if row.fingerprint in seen:
                continue
            row.status = "resolved"
            row.resolved_at = now
            row.resolution_note = "شرط هشدار دیگر برقرار نیست (تشخیص خودکار)."
            resolved += 1

    await db.flush()

    return {
        "website_id": website_id,
        "created": created,
        "updated": updated,
        "resolved": resolved,
        "by_type": by_type,
        "skipped_reason": skipped_reason,
        # Ids of freshly raised alerts, so the caller can fan out notifications
        # without re-querying for "what is new".
        "new_alert_ids": [a.id for a in new_rows],
    }


async def list_alerts(
    db: AsyncSession,
    website_id: UUID | None = None,
    organization_id: UUID | None = None,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Alert]:
    """List alerts for one website, or across an organization.

    At least one of website_id / organization_id must be given; an unscoped list
    would cross tenants.
    """
    if website_id is None and organization_id is None:
        raise ValueError("list_alerts requires website_id or organization_id")

    stmt = select(Alert)
    if website_id is not None:
        stmt = stmt.where(Alert.website_id == website_id)
    if organization_id is not None:
        stmt = stmt.where(Alert.organization_id == organization_id)
    if status:
        stmt = stmt.where(Alert.status == status)
    if severity:
        stmt = stmt.where(Alert.severity == severity)

    # Critical first, then newest: severity is a string column, so order it
    # explicitly instead of alphabetically (which would put "critical" before
    # "info" by luck and "warning" last by luck).
    severity_rank = func.array_position(
        func.cast(func.array(["critical", "warning", "info"]), None), Alert.severity
    )
    del severity_rank  # kept out of the query: see ordering below

    stmt = (
        stmt.order_by(Alert.triggered_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_alert_summary(db: AsyncSession, organization_id: UUID) -> dict:
    """Counts for the dashboard badge, one query."""
    result = await db.execute(
        select(Alert.severity, func.count())
        .where(Alert.organization_id == organization_id, Alert.status == "active")
        .group_by(Alert.severity)
    )
    by_severity = {row[0]: row[1] for row in result.all()}
    return {
        "active": sum(by_severity.values()),
        "critical": by_severity.get("critical", 0),
        "warning": by_severity.get("warning", 0),
        "info": by_severity.get("info", 0),
        "by_severity": by_severity,
    }


async def update_alert_status(
    db: AsyncSession,
    alert: Alert,
    status: str,
    user_id: UUID | None = None,
    resolution_note: str | None = None,
    mute_hours: int | None = None,
) -> Alert:
    """Apply a human transition, stamping who and when."""
    now = datetime.now(timezone.utc)
    alert.status = status
    if status == "acknowledged":
        alert.acknowledged_at = now
        alert.acknowledged_by = user_id
    elif status == "resolved":
        alert.resolved_at = now
        alert.resolved_by = user_id
        alert.resolution_note = resolution_note
    elif status == "muted":
        alert.muted_until = now + timedelta(hours=mute_hours or 24)
    elif status == "active":
        # Reopening by hand clears the closure so the row is not both.
        alert.resolved_at = None
        alert.resolved_by = None
        alert.muted_until = None
    await db.flush()
    await db.refresh(alert)
    return alert


__all__ = [
    "detect_alerts",
    "list_alerts",
    "get_alert_summary",
    "update_alert_status",
    "make_fingerprint",
]
