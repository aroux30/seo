"""Opportunity detection engine.

The GSC tables were already being filled by gsc_service; nothing read them back
looking for *actionable* findings. This module is that reader.

How the data actually looks matters here. `sync_gsc_data` writes every query and
page row of one sync with `date_metric = today`, so the tables are a series of
whole-account **snapshots**, not a per-day time series (only `gsc_dates` is a
true daily series). Every detector therefore works off "latest snapshot" and,
where it needs a trend, "the snapshot before that" — comparing arbitrary date
ranges would silently mix two syncs of the same period and invent growth.

Findings are idempotent: each one hashes to a `fingerprint`, and re-running the
detector updates the existing row instead of inserting a duplicate. A finding
that stops reproducing is marked `expired` rather than deleted, so the UI can
show "this resolved itself" and the audit trail survives.
"""

import hashlib
from datetime import date, datetime, timezone
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import GscPage, GscQuery, Opportunity, Website

# Rough organic CTR by position. Used only to decide whether a page underperforms
# *relative to where it already ranks* — an absolute CTR threshold would flag
# every position-30 query and drown the real wins.
EXPECTED_CTR_BY_POSITION = {
    1: 0.280, 2: 0.150, 3: 0.110, 4: 0.080, 5: 0.060,
    6: 0.050, 7: 0.040, 8: 0.033, 9: 0.028, 10: 0.025,
}
EXPECTED_CTR_11_20 = 0.015
EXPECTED_CTR_BEYOND = 0.008


def expected_ctr(position: float) -> float:
    """Expected CTR for an average result at `position`."""
    if position <= 0:
        return EXPECTED_CTR_BEYOND
    bucket = int(round(position))
    if bucket in EXPECTED_CTR_BY_POSITION:
        return EXPECTED_CTR_BY_POSITION[bucket]
    if bucket <= 20:
        return EXPECTED_CTR_11_20
    return EXPECTED_CTR_BEYOND


def make_fingerprint(opportunity_type: str, subject: str) -> str:
    """Stable id for a finding, so a re-run updates instead of duplicating.

    Subject is lowercased and stripped because GSC returns the same query with
    inconsistent casing/whitespace across exports, and two casings of one query
    are not two opportunities.
    """
    raw = f"{opportunity_type}|{(subject or '').strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _priority(
    *,
    impressions: int,
    position: float | None,
    gap_ctr: float,
    traffic_gain: int,
) -> int:
    """0-100 priority. Volume dominates, closeness to page 1 boosts, capped.

    Deliberately arithmetic and inspectable rather than a learned weight: the
    number is shown to users next to the evidence that produced it, so it has to
    be explainable.
    """
    volume = min(impressions / 1000.0, 1.0) * 45          # up to 45
    reachability = 0.0
    if position is not None:
        if position <= 3:
            reachability = 10
        elif position <= 10:
            reachability = 30
        elif position <= 20:
            reachability = 22
        else:
            reachability = 8
    gap = min(max(gap_ctr, 0.0) / 0.05, 1.0) * 15          # up to 15
    gain = min(traffic_gain / 500.0, 1.0) * 10             # up to 10
    return int(max(0, min(100, round(volume + reachability + gap + gain))))


async def _latest_two_snapshots(
    db: AsyncSession, model, website_id: UUID
) -> tuple[date | None, date | None]:
    """The two most recent `date_metric` values present for this website."""
    result = await db.execute(
        select(model.date_metric)
        .where(model.website_id == website_id)
        .group_by(model.date_metric)
        .order_by(model.date_metric.desc())
        .limit(2)
    )
    rows = [r[0] for r in result.all()]
    latest = rows[0] if rows else None
    previous = rows[1] if len(rows) > 1 else None
    return latest, previous


async def _snapshot_queries(
    db: AsyncSession, website_id: UUID, snapshot: date
) -> list:
    result = await db.execute(
        select(
            GscQuery.query,
            GscQuery.page_url,
            GscQuery.position,
            GscQuery.clicks,
            GscQuery.impressions,
            GscQuery.ctr,
        ).where(
            GscQuery.website_id == website_id,
            GscQuery.date_metric == snapshot,
        )
    )
    return list(result.all())


async def _snapshot_pages(
    db: AsyncSession, website_id: UUID, snapshot: date
) -> list:
    result = await db.execute(
        select(
            GscPage.page_url,
            GscPage.position,
            GscPage.clicks,
            GscPage.impressions,
            GscPage.ctr,
        ).where(
            GscPage.website_id == website_id,
            GscPage.date_metric == snapshot,
        )
    )
    return list(result.all())


# ------------------------------------------------------------------- detectors
# Each detector is pure: it takes rows and returns candidate dicts. Persistence
# and dedup happen once, in detect_opportunities, so a new detector cannot get
# the upsert semantics wrong.


def _detect_low_ctr(queries: list[GscQuery], min_impressions: int) -> list[dict]:
    out = []
    for q in queries:
        if q.impressions < min_impressions or q.position > 20:
            continue
        exp = expected_ctr(q.position)
        # Only flag a real shortfall: half the expected rate or worse.
        if q.ctr >= exp * 0.5:
            continue
        gap = exp - q.ctr
        # What fixing the snippet could plausibly recover, not a promise.
        gain = int(q.impressions * gap * 0.5)
        out.append({
            "opportunity_type": "low_ctr_high_impressions",
            "subject": q.query,
            "title": f"CTR پایین برای «{q.query}» با {q.impressions} نمایش",
            "description": (
                f"این عبارت در جایگاه {q.position:.1f} است و {q.impressions} بار نمایش "
                f"داده شده، ولی نرخ کلیک آن {q.ctr * 100:.2f}٪ است در حالی که برای این "
                f"جایگاه حدود {exp * 100:.2f}٪ انتظار می‌رود."
            ),
            "query": q.query,
            "page_url": q.page_url,
            "current_position": float(q.position),
            "current_clicks": int(q.clicks),
            "current_impressions": int(q.impressions),
            "current_ctr": float(q.ctr),
            "estimated_traffic_gain": gain,
            "recommended_action": (
                "بازنویسی تگ عنوان و توضیحات متا برای جذاب‌تر شدن در نتایج جستجو؛ "
                "افزودن عدد، سال یا مزیت مشخص به عنوان."
            ),
            "details": {
                "expected_ctr": round(exp, 4),
                "actual_ctr": round(float(q.ctr), 4),
                "ctr_gap": round(gap, 4),
            },
            "_gap_ctr": gap,
        })
    return out


def _detect_striking_distance(queries: list[GscQuery], min_impressions: int) -> list[dict]:
    out = []
    for q in queries:
        if q.impressions < min_impressions:
            continue
        if not (3.5 <= q.position <= 15.0):
            continue
        exp_top3 = EXPECTED_CTR_BY_POSITION[3]
        gain = max(int(q.impressions * (exp_top3 - q.ctr)), 0)
        out.append({
            "opportunity_type": "striking_distance",
            "subject": q.query,
            "title": f"«{q.query}» در آستانه صفحه اول — جایگاه {q.position:.1f}",
            "description": (
                f"این عبارت با {q.impressions} نمایش در جایگاه {q.position:.1f} قرار دارد. "
                "با تقویت محتوا و لینک داخلی، رسیدن به سه جایگاه اول در دسترس است."
            ),
            "query": q.query,
            "page_url": q.page_url,
            "current_position": float(q.position),
            "current_clicks": int(q.clicks),
            "current_impressions": int(q.impressions),
            "current_ctr": float(q.ctr),
            "estimated_traffic_gain": gain,
            "recommended_action": (
                "گسترش بخش مرتبط با این عبارت، افزودن پرسش‌های متداول، "
                "و ساخت دو تا سه لینک داخلی از صفحات پربازدید به این صفحه."
            ),
            "details": {
                "position": round(float(q.position), 2),
                "target_position": 3,
                "expected_ctr_at_target": exp_top3,
            },
            "_gap_ctr": max(exp_top3 - float(q.ctr), 0.0),
        })
    return out


def _detect_content_gap(queries: list[GscQuery], min_impressions: int) -> list[dict]:
    """Impressions exist but nothing ranks — no page really covers the topic."""
    out = []
    for q in queries:
        if q.impressions < min_impressions or q.position <= 20:
            continue
        if q.clicks > 0:
            continue
        gain = int(q.impressions * EXPECTED_CTR_BY_POSITION[5])
        out.append({
            "opportunity_type": "content_gap",
            "subject": q.query,
            "title": f"شکاف محتوا: «{q.query}» بدون صفحه هدفمند",
            "description": (
                f"گوگل سایت را برای این عبارت {q.impressions} بار نمایش داده اما جایگاه "
                f"{q.position:.1f} و کلیک صفر است؛ یعنی صفحه‌ای که دقیقاً به این نیاز "
                "پاسخ دهد وجود ندارد."
            ),
            "query": q.query,
            "page_url": q.page_url,
            "current_position": float(q.position),
            "current_clicks": int(q.clicks),
            "current_impressions": int(q.impressions),
            "current_ctr": float(q.ctr),
            "estimated_traffic_gain": gain,
            "recommended_action": "تولید یک مقاله اختصاصی برای این عبارت با بریف محتوا.",
            "details": {"position": round(float(q.position), 2), "clicks": 0},
            "_gap_ctr": EXPECTED_CTR_BY_POSITION[5],
        })
    return out


def _detect_rising_queries(
    current: list[GscQuery], previous: list[GscQuery], min_impressions: int
) -> list[dict]:
    prev_by_query = {}
    for q in previous:
        key = q.query.strip().lower()
        # Keep the strongest row if a snapshot has the query more than once.
        if key not in prev_by_query or q.impressions > prev_by_query[key].impressions:
            prev_by_query[key] = q

    out = []
    for q in current:
        if q.impressions < min_impressions:
            continue
        prev = prev_by_query.get(q.query.strip().lower())
        if not prev or prev.impressions <= 0:
            continue
        growth = (q.impressions - prev.impressions) / prev.impressions
        if growth < 0.3:
            continue
        gain = int(q.impressions * max(expected_ctr(q.position) - q.ctr, 0.0))
        out.append({
            "opportunity_type": "rising_query",
            "subject": q.query,
            "title": f"عبارت در حال رشد: «{q.query}» (+{growth * 100:.0f}٪ نمایش)",
            "description": (
                f"نمایش این عبارت از {prev.impressions} به {q.impressions} رسیده "
                f"({growth * 100:.0f}٪ رشد). تقویت زودهنگام محتوا بازده بالایی دارد."
            ),
            "query": q.query,
            "page_url": q.page_url,
            "current_position": float(q.position),
            "current_clicks": int(q.clicks),
            "current_impressions": int(q.impressions),
            "current_ctr": float(q.ctr),
            "estimated_traffic_gain": gain,
            "recommended_action": "به‌روزرسانی و گسترش محتوای مرتبط پیش از رقبا.",
            "details": {
                "previous_impressions": int(prev.impressions),
                "current_impressions": int(q.impressions),
                "growth_percent": round(growth * 100, 1),
            },
            "_gap_ctr": max(expected_ctr(q.position) - float(q.ctr), 0.0),
        })
    return out


def _detect_decaying_content(
    current: list[GscPage], previous: list[GscPage], min_clicks: int = 5
) -> list[dict]:
    prev_by_url = {}
    for p in previous:
        key = (p.page_url or "").strip().lower()
        if key not in prev_by_url or p.clicks > prev_by_url[key].clicks:
            prev_by_url[key] = p

    out = []
    for p in current:
        prev = prev_by_url.get((p.page_url or "").strip().lower())
        if not prev or prev.clicks < min_clicks:
            continue
        drop = (prev.clicks - p.clicks) / prev.clicks
        if drop < 0.3:
            continue
        out.append({
            "opportunity_type": "decaying_content",
            "subject": p.page_url,
            "title": f"افت عملکرد صفحه ({drop * 100:.0f}٪ کاهش کلیک)",
            "description": (
                f"کلیک این صفحه از {prev.clicks} به {p.clicks} کاهش یافته. "
                "محتوا احتمالاً کهنه شده یا رقبا جلو زده‌اند."
            ),
            "query": None,
            "page_url": p.page_url,
            "current_position": float(p.position),
            "current_clicks": int(p.clicks),
            "current_impressions": int(p.impressions),
            "current_ctr": float(p.ctr),
            "estimated_traffic_gain": int(prev.clicks - p.clicks),
            "recommended_action": (
                "به‌روزرسانی محتوا، تازه‌سازی آمار و تاریخ، و بازبینی عنوان و متا."
            ),
            "details": {
                "previous_clicks": int(prev.clicks),
                "current_clicks": int(p.clicks),
                "drop_percent": round(drop * 100, 1),
            },
            "_gap_ctr": 0.0,
        })
    return out


def _detect_cannibalization(queries: list[GscQuery], min_impressions: int) -> list[dict]:
    """Several URLs competing for one query.

    Only possible when the sync stored `page_url` alongside the query. A
    query-dimension-only export leaves it null, and in that case this detector
    correctly finds nothing rather than guessing.
    """
    by_query: dict[str, set[str]] = {}
    agg: dict[str, dict] = {}
    for q in queries:
        if not q.page_url:
            continue
        key = q.query.strip().lower()
        by_query.setdefault(key, set()).add(q.page_url)
        entry = agg.setdefault(key, {
            "query": q.query, "impressions": 0, "clicks": 0,
            "position": float(q.position), "ctr": float(q.ctr),
        })
        entry["impressions"] += int(q.impressions)
        entry["clicks"] += int(q.clicks)
        entry["position"] = min(entry["position"], float(q.position))

    out = []
    for key, urls in by_query.items():
        if len(urls) < 2:
            continue
        entry = agg[key]
        if entry["impressions"] < min_impressions:
            continue
        out.append({
            "opportunity_type": "cannibalization",
            "subject": entry["query"],
            "title": f"رقابت داخلی روی «{entry['query']}» ({len(urls)} صفحه)",
            "description": (
                f"{len(urls)} صفحه از سایت برای یک عبارت رقابت می‌کنند و اعتبار بین "
                "آن‌ها تقسیم شده است."
            ),
            "query": entry["query"],
            "page_url": sorted(urls)[0],
            "current_position": entry["position"],
            "current_clicks": entry["clicks"],
            "current_impressions": entry["impressions"],
            "current_ctr": entry["ctr"],
            "estimated_traffic_gain": int(entry["impressions"] * 0.02),
            "recommended_action": (
                "ادغام صفحات مشابه یا تعیین صفحه اصلی با canonical و اصلاح لینک‌های داخلی."
            ),
            "details": {"competing_urls": sorted(urls)[:10], "url_count": len(urls)},
            "_gap_ctr": 0.0,
        })
    return out


# ------------------------------------------------------------------ persistence

async def detect_opportunities(
    db: AsyncSession,
    website_id: UUID,
    lookback_days: int = 28,
    min_impressions: int = 1,
) -> dict:
    """Run every detector for one website and upsert the findings.

    Returns counts, not rows: callers (API, Celery beat) only report progress,
    and the list endpoint is the way to read results.
    """
    website = await db.get(Website, website_id)
    if not website:
        return {
            "website_id": website_id, "scanned_queries": 0, "scanned_pages": 0,
            "created": 0, "updated": 0, "expired": 0, "by_type": {},
        }

    q_latest, q_previous = await _latest_two_snapshots(db, GscQuery, website_id)
    p_latest, p_previous = await _latest_two_snapshots(db, GscPage, website_id)

    cur_queries = await _snapshot_queries(db, website_id, q_latest) if q_latest else []
    prev_queries = await _snapshot_queries(db, website_id, q_previous) if q_previous else []
    cur_pages = await _snapshot_pages(db, website_id, p_latest) if p_latest else []
    prev_pages = await _snapshot_pages(db, website_id, p_previous) if p_previous else []

    candidates: list[dict] = []
    candidates += _detect_low_ctr(cur_queries, min_impressions)
    candidates += _detect_striking_distance(cur_queries, min_impressions)
    candidates += _detect_content_gap(cur_queries, min_impressions)
    candidates += _detect_rising_queries(cur_queries, prev_queries, min_impressions)
    candidates += _detect_decaying_content(cur_pages, prev_pages)
    candidates += _detect_cannibalization(cur_queries, min_impressions)

    now = datetime.now(timezone.utc)
    created = updated = 0
    by_type: dict[str, int] = {}
    seen_fingerprints: set[str] = set()

    for cand in candidates:
        fingerprint = make_fingerprint(cand["opportunity_type"], cand["subject"] or "")
        # One finding per fingerprint per run; the first detector to claim it wins.
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        priority = _priority(
            impressions=cand["current_impressions"],
            position=cand["current_position"],
            gap_ctr=cand.pop("_gap_ctr", 0.0),
            traffic_gain=cand["estimated_traffic_gain"],
        )

        existing = await db.execute(
            select(Opportunity).where(
                Opportunity.website_id == website_id,
                Opportunity.fingerprint == fingerprint,
            )
        )
        row = existing.scalar_one_or_none()

        if row:
            row.title = cand["title"]
            row.description = cand["description"]
            row.query = cand["query"]
            row.page_url = cand["page_url"]
            row.priority_score = priority
            row.estimated_traffic_gain = cand["estimated_traffic_gain"]
            row.current_position = cand["current_position"]
            row.current_clicks = cand["current_clicks"]
            row.current_impressions = cand["current_impressions"]
            row.current_ctr = cand["current_ctr"]
            row.details = cand["details"]
            row.recommended_action = cand["recommended_action"]
            row.last_seen_at = now
            # A finding the user dismissed stays dismissed; one that had expired
            # and is back is genuinely open again.
            if row.status == "expired":
                row.status = "open"
            updated += 1
        else:
            db.add(Opportunity(
                organization_id=website.organization_id,
                website_id=website_id,
                opportunity_type=cand["opportunity_type"],
                status="open",
                title=cand["title"],
                description=cand["description"],
                query=cand["query"],
                page_url=cand["page_url"],
                priority_score=priority,
                estimated_traffic_gain=cand["estimated_traffic_gain"],
                current_position=cand["current_position"],
                current_clicks=cand["current_clicks"],
                current_impressions=cand["current_impressions"],
                current_ctr=cand["current_ctr"],
                fingerprint=fingerprint,
                details=cand["details"],
                recommended_action=cand["recommended_action"],
                detected_at=now,
                last_seen_at=now,
            ))
            created += 1

        by_type[cand["opportunity_type"]] = by_type.get(cand["opportunity_type"], 0) + 1

    # Anything still open that this run did not reproduce has resolved itself.
    expired = 0
    if q_latest or p_latest:
        stmt = (
            update(Opportunity)
            .where(
                Opportunity.website_id == website_id,
                Opportunity.status.in_(["open", "in_progress"]),
                Opportunity.fingerprint.notin_(seen_fingerprints or {""}),
            )
            .values(status="expired", last_seen_at=now)
        )
        result = await db.execute(stmt)
        expired = result.rowcount or 0

    await db.flush()

    return {
        "website_id": website_id,
        "scanned_queries": len(cur_queries),
        "scanned_pages": len(cur_pages),
        "created": created,
        "updated": updated,
        "expired": expired,
        "by_type": by_type,
    }


async def list_opportunities(
    db: AsyncSession,
    website_id: UUID,
    status: str | None = None,
    opportunity_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Opportunity]:
    stmt = select(Opportunity).where(Opportunity.website_id == website_id)
    if status:
        stmt = stmt.where(Opportunity.status == status)
    if opportunity_type:
        stmt = stmt.where(Opportunity.opportunity_type == opportunity_type)
    stmt = (
        stmt.order_by(Opportunity.priority_score.desc(), Opportunity.detected_at.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_opportunity_summary(
    db: AsyncSession, website_id: UUID, top_n: int = 5
) -> dict:
    counts = await db.execute(
        select(Opportunity.opportunity_type, func.count())
        .where(Opportunity.website_id == website_id, Opportunity.status == "open")
        .group_by(Opportunity.opportunity_type)
    )
    by_type = {row[0]: row[1] for row in counts.all()}

    gain = await db.execute(
        select(func.coalesce(func.sum(Opportunity.estimated_traffic_gain), 0)).where(
            Opportunity.website_id == website_id, Opportunity.status == "open"
        )
    )
    top = await list_opportunities(db, website_id, status="open", limit=top_n)

    return {
        "total_open": sum(by_type.values()),
        "by_type": by_type,
        "total_estimated_traffic_gain": int(gain.scalar_one() or 0),
        "top": top,
    }


async def update_opportunity_status(
    db: AsyncSession,
    opportunity: Opportunity,
    status: str,
    user_id: UUID | None = None,
    dismiss_reason: str | None = None,
) -> Opportunity:
    """Apply a human lifecycle transition, stamping who and when."""
    now = datetime.now(timezone.utc)
    opportunity.status = status
    if status == "dismissed":
        opportunity.dismissed_at = now
        opportunity.dismissed_by = user_id
        opportunity.dismiss_reason = dismiss_reason
    elif status == "actioned":
        opportunity.actioned_at = now
    elif status == "open":
        # Reopening clears the previous dismissal so the record is not
        # simultaneously "open" and "dismissed by X".
        opportunity.dismissed_at = None
        opportunity.dismissed_by = None
        opportunity.dismiss_reason = None
    await db.flush()
    await db.refresh(opportunity)
    return opportunity


__all__ = [
    "detect_opportunities",
    "list_opportunities",
    "get_opportunity_summary",
    "update_opportunity_status",
    "make_fingerprint",
    "expected_ctr",
]
