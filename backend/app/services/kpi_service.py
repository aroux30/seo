"""Organization-level KPI aggregation.

One read-only endpoint that computes the numbers management actually steers by:
content production and quality, AI agent reliability, automation health, and
SEO pipeline state. Every query is org-scoped (directly via organization_id or
through the website join) so tenants can never see each other's numbers.

Kept deliberately free of AI/LLM calls — this must be fast and deterministic.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AiAgentLog,
    AiSeoStrategy,
    Alert,
    AutomationLog,
    ContentArticle,
    ContentBrief,
    Opportunity,
    SeoAudit,
    Website,
)


async def get_kpi_summary(db: AsyncSession, org_id: UUID) -> dict:
    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=now.weekday())  # Monday of this week

    # ---------------- content ----------------
    art_stmt = (
        select(
            func.count(ContentArticle.id),
            func.coalesce(func.avg(ContentArticle.seo_score), 0),
            func.count(case((ContentArticle.wp_post_id.isnot(None), 1))),
            func.count(case((ContentArticle.created_at >= week_start, 1))),
        )
        .select_from(ContentArticle)
        .join(Website, Website.id == ContentArticle.website_id)
        .where(Website.organization_id == org_id, ContentArticle.deleted_at.is_(None))
    )
    art_res = await db.execute(art_stmt)
    art_total, art_avg_score, art_published, art_this_week = art_res.one()

    brief_stmt = (
        select(func.count(ContentBrief.id))
        .select_from(ContentBrief)
        .join(Website, Website.id == ContentBrief.website_id)
        .where(Website.organization_id == org_id, ContentBrief.deleted_at.is_(None))
    )
    brief_total = (await db.execute(brief_stmt)).scalar_one()

    strategy_stmt = (
        select(func.count(AiSeoStrategy.id))
        .select_from(AiSeoStrategy)
        .join(Website, Website.id == AiSeoStrategy.website_id)
        .where(Website.organization_id == org_id)
    )
    strategy_total = (await db.execute(strategy_stmt)).scalar_one()

    # ---------------- weekly production (last 6 weeks, for the chart) --------
    weekly = []
    for i in range(5, -1, -1):
        start = week_start - timedelta(weeks=i)
        end = start + timedelta(weeks=1)
        cnt_stmt = (
            select(func.count(ContentArticle.id))
            .select_from(ContentArticle)
            .join(Website, Website.id == ContentArticle.website_id)
            .where(
                Website.organization_id == org_id,
                ContentArticle.deleted_at.is_(None),
                ContentArticle.created_at >= start,
                ContentArticle.created_at < end,
            )
        )
        cnt = (await db.execute(cnt_stmt)).scalar_one()
        weekly.append(
            {
                "week_start": start.date().isoformat(),
                "label": f"هفته {start.strftime('%m/%d')}",
                "articles": cnt,
            }
        )

    # ---------------- AI agents ----------------
    ai_stmt = select(
        func.count(AiAgentLog.id),
        func.count(case((AiAgentLog.status == "success", 1))),
        func.coalesce(func.avg(AiAgentLog.duration_ms), 0),
        func.coalesce(func.sum(AiAgentLog.prompt_tokens + AiAgentLog.completion_tokens), 0),
    ).where(AiAgentLog.organization_id == org_id)
    ai_res = (await db.execute(ai_stmt)).one()
    ai_total, ai_success, ai_avg_ms, ai_tokens = ai_res

    # ---------------- automations ----------------
    auto_stmt = (
        select(
            func.count(AutomationLog.id),
            func.count(case((AutomationLog.status == "success", 1))),
            func.coalesce(func.avg(AutomationLog.execution_time_ms), 0),
        )
        .select_from(AutomationLog)
        .join(Website, Website.id == AutomationLog.website_id)
        .where(Website.organization_id == org_id)
    )
    auto_total, auto_success, auto_avg_ms = (await db.execute(auto_stmt)).one()

    # ---------------- SEO pipeline ----------------
    audit_stmt = (
        select(func.count(SeoAudit.id))
        .select_from(SeoAudit)
        .join(Website, Website.id == SeoAudit.website_id)
        .where(Website.organization_id == org_id)
    )
    audit_total = (await db.execute(audit_stmt)).scalar_one()

    opp_open = (
        await db.execute(
            select(func.count(Opportunity.id)).where(
                Opportunity.organization_id == org_id, Opportunity.status == "open"
            )
        )
    ).scalar_one()

    alerts_active = (
        await db.execute(
            select(func.count(Alert.id)).where(
                Alert.organization_id == org_id, Alert.status == "active"
            )
        )
    ).scalar_one()

    def _rate(total: int, success: int) -> float:
        return round((success / total) * 100, 1) if total else 0.0

    def _avg_ms(v) -> int:
        return int(v or 0)

    return {
        "content": {
            "articles_total": art_total,
            "articles_published": art_published,
            "articles_this_week": art_this_week,
            "avg_seo_score": round(float(art_avg_score or 0), 1),
            "briefs_total": brief_total,
            "strategies_total": strategy_total,
            "weekly_production": weekly,
        },
        "ai": {
            "total_runs": ai_total,
            "success_rate": _rate(ai_total, ai_success),
            "avg_duration_ms": _avg_ms(ai_avg_ms),
            "total_tokens": int(ai_tokens or 0),
        },
        "automations": {
            "total_runs": auto_total,
            "success_rate": _rate(auto_total, auto_success),
            "avg_duration_ms": _avg_ms(auto_avg_ms),
        },
        "seo": {
            "audits_total": audit_total,
            "opportunities_open": opp_open,
            "alerts_active": alerts_active,
        },
        "generated_at": now.isoformat(),
    }
