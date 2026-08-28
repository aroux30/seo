import json
import httpx
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError
from fastapi import HTTPException
from app.models import Website, AiSeoStrategy, AiAgentLog, Keyword, SeoAudit, SeoAuditIssue
from app.services import agent_activity_service
import time

settings = get_settings()

async def generate_seo_strategy(
    db: AsyncSession,
    website_id: UUID,
    provider: str | None = None,
    focus_area: str | None = None,
) -> AiSeoStrategy:
    """
    Generate comprehensive AI SEO Strategy for a website.
    Analyzes target keywords and technical audit context; builds keyword clusters,
    content gaps, and actionable roadmap.
    """
    start_time = time.time()
    stmt = select(Website).where(Website.id == website_id)
    res = await db.execute(stmt)
    website = res.scalar_one_or_none()
    if not website:
        raise NotFoundError("Website", str(website_id))
    
    org_id = website.organization_id
    used_provider = provider or settings.DEFAULT_AI_PROVIDER or "openai"

    # Fetch top tracked keywords for context
    kw_stmt = select(Keyword).where(Keyword.website_id == website_id).limit(20)
    kw_res = await db.execute(kw_stmt)
    tracked_keywords = list(kw_res.scalars().all())

    kw_names = [k.keyword for k in tracked_keywords] if tracked_keywords else [
        "خدمات سئو", "آموزش سئو", "مشاوره تکنیکال"
    ]

    # Fetch latest audit for context
    audit_stmt = select(SeoAudit).where(SeoAudit.website_id == website_id).order_by(desc(SeoAudit.created_at)).limit(1)
    audit_res = await db.execute(audit_stmt)
    latest_audit = audit_res.scalar_one_or_none()
    
    issues_text = ""
    issues = []
    if latest_audit:
        issue_stmt = select(SeoAuditIssue).where(SeoAuditIssue.audit_id == latest_audit.id, SeoAuditIssue.is_resolved == False)
        issue_res = await db.execute(issue_stmt)
        issues = list(issue_res.scalars().all())
        issues_text = "\n".join([f"- {i.title} (Severity: {i.severity})" for i in issues])
    
    domain = website.domain
    kw_text = "، ".join(kw_names)
    
    title = f"استراتژی جامع سئو برای {domain}"
    
    # Real token usage, read back from the provider response. The algorithmic
    # fallback path costs nothing, so it stays at zero rather than reporting the
    # old hardcoded 850/1420 and inflating every cost report.
    prompt_tokens = 0
    completion_tokens = 0

    n8n_url = f"{settings.N8N_WEBHOOK_BASE_URL.rstrip('/')}/webhook/seo-strategy"
    
    payload = {
        "website_id": str(website_id),
        "domain": domain,
        "keywords": kw_names,
        "issues": [{"title": i.title, "severity": i.severity} for i in issues]
    }
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(n8n_url, json=payload)
            response.raise_for_status()
            data = response.json()
            result = data.get("data", data)
            
            if "text" in result and isinstance(result["text"], str):
                try:
                    parsed_text = json.loads(result["text"])
                    if isinstance(parsed_text, dict):
                        result = parsed_text
                except Exception:
                    pass
            
            def _as_str(v) -> str:
                """LLMs ignore "must be a string": target_audience came back as a
                dict once and the VARCHAR insert crashed with a 500. Coerce."""
                if v is None:
                    return ""
                if isinstance(v, str):
                    return v
                if isinstance(v, (dict, list)):
                    return json.dumps(v, ensure_ascii=False)
                return str(v)

            def _as_list(v) -> list:
                if v is None:
                    return []
                if isinstance(v, list):
                    return v
                return [v]

            executive_summary = _as_str(result.get("executive_summary", ""))
            target_audience = _as_str(result.get("target_audience", ""))
            keyword_clusters = _as_list(result.get("keyword_clusters", []))
            content_gaps = _as_list(result.get("content_gaps", []))
            action_items = _as_list(result.get("action_items", []))

            # Schema guard: the strategies page renders cluster_title /
            # main_keyword / secondary_keywords / intent. LLMs drift off-schema
            # (empty strings, wrong keys), and blank cards are worse than an
            # honest failure — drop malformed clusters and coerce the numeric
            # gap fields so the UI never renders placeholder junk.
            def _clamp_int(v, lo, hi, default):
                try:
                    return max(lo, min(hi, int(v)))
                except (TypeError, ValueError):
                    return default

            keyword_clusters = [
                c for c in keyword_clusters
                if isinstance(c, dict) and str(c.get("cluster_title") or "").strip()
                and str(c.get("main_keyword") or "").strip()
            ]
            for c in keyword_clusters:
                if not isinstance(c.get("secondary_keywords"), list):
                    c["secondary_keywords"] = []
                c.setdefault("priority", "متوسط")
                c.setdefault("intent", "اطلاعاتی")
            content_gaps = [
                g for g in content_gaps
                if isinstance(g, dict) and str(g.get("topic") or "").strip()
            ]
            for g in content_gaps:
                g["search_volume_estimate"] = _clamp_int(
                    g.get("search_volume_estimate"), 0, 1_000_000, 500
                )
                g["difficulty"] = _clamp_int(g.get("difficulty"), 0, 100, 50)
                g.setdefault("target_keyword", g.get("topic", ""))
                g.setdefault("suggested_title", g.get("topic", ""))
            action_items = [
                a for a in action_items
                if isinstance(a, dict) and str(a.get("step") or a.get("task") or "").strip()
            ]
            for a in action_items:
                a.setdefault("department", "تیم محتوا")
                a.setdefault("timeline", "هفته ۱")
                a.setdefault("impact", "متوسط")
                if not a.get("step"):
                    a["step"] = a.get("task", "")

            prompt_tokens = result.get("prompt_tokens", 0)
            completion_tokens = result.get("completion_tokens", 0)
            used_provider = result.get("provider", "n8n_workflow")

    except Exception as e:
        raise HTTPException(status_code=503, detail="ارتباط با سرور هوش مصنوعی قطع است (n8n workflow is down).")

    # Schema guard — deliberately OUTSIDE the try above: a malformed (but
    # successfully received) LLM payload must surface as its own error, not be
    # masked as "n8n workflow is down".
    def _clamp_int(v, lo, hi, default):
        try:
            return max(lo, min(hi, int(v)))
        except (TypeError, ValueError):
            return default

    keyword_clusters = [
        c for c in keyword_clusters
        if isinstance(c, dict) and str(c.get("cluster_title") or "").strip()
        and str(c.get("main_keyword") or "").strip()
    ]
    for c in keyword_clusters:
        if not isinstance(c.get("secondary_keywords"), list):
            c["secondary_keywords"] = []
        c.setdefault("priority", "متوسط")
        c.setdefault("intent", "اطلاعاتی")
    content_gaps = [
        g for g in content_gaps
        if isinstance(g, dict) and str(g.get("topic") or "").strip()
    ]
    for g in content_gaps:
        g["search_volume_estimate"] = _clamp_int(
            g.get("search_volume_estimate"), 0, 1_000_000, 500
        )
        g["difficulty"] = _clamp_int(g.get("difficulty"), 0, 100, 50)
        g.setdefault("target_keyword", g.get("topic", ""))
        g.setdefault("suggested_title", g.get("topic", ""))
    action_items = [
        a for a in action_items
        if isinstance(a, dict) and str(a.get("step") or a.get("task") or "").strip()
    ]
    for a in action_items:
        a.setdefault("department", "تیم محتوا")
        a.setdefault("timeline", "هفته ۱")
        a.setdefault("impact", "متوسط")
        if not a.get("step"):
            a["step"] = a.get("task", "")

    if not keyword_clusters:
        raise HTTPException(
            status_code=502,
            detail="خروجی هوش مصنوعی نامعتبر بود (خوشه کلمات کلیدی خالی). لطفا دوباره تلاش کنید.",
        )

    strategy = AiSeoStrategy(
        website_id=website_id,
        title=title,
        executive_summary=executive_summary,
        target_audience=target_audience,
        keyword_clusters=keyword_clusters,
        content_gaps=content_gaps,
        action_items=action_items,
        provider_used=used_provider,
    )
    db.add(strategy)
    await db.flush()

    duration_ms = int((time.time() - start_time) * 1000)

    # Log AI agent action
    input_context = {
        "domain": domain,
        "keywords": kw_names,
        "issues": [{"title": i.title, "severity": i.severity} for i in issues]
    }
    output_result = {
        "executive_summary": executive_summary,
        "target_audience": target_audience,
        "keyword_clusters": keyword_clusters,
        "content_gaps": content_gaps,
        "action_items": action_items
    }
    decision_summary = f"تولید استراتژی با {len(keyword_clusters)} خوشه کلمات کلیدی، {len(content_gaps)} شکاف محتوایی و {len(action_items)} اقدام اجرایی."

    await agent_activity_service.log_agent_activity(
        db,
        website_id=website_id,
        organization_id=org_id,
        agent_name="SEO Strategy Architect Agent",
        agent_type="strategy",
        provider=used_provider,
        action_taken="تولید استراتژی جامع سئو (هوش مصنوعی / الگوریتم پویا)",
        status="success",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        confidence_score=95.0,
        decision_summary=decision_summary,
        input_context=input_context,
        output_result=output_result,
        duration_ms=duration_ms,
        related_entity_type="ai_seo_strategy",
        related_entity_id=strategy.id,
    )

    await db.commit()
    await db.refresh(strategy)
    return strategy


async def get_website_strategies(
    db: AsyncSession,
    website_id: UUID,
) -> list[AiSeoStrategy]:
    stmt = (
        select(AiSeoStrategy)
        .where(AiSeoStrategy.website_id == website_id)
        .order_by(desc(AiSeoStrategy.created_at))
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_strategy_detail(
    db: AsyncSession,
    strategy_id: UUID,
) -> AiSeoStrategy | None:
    stmt = select(AiSeoStrategy).where(AiSeoStrategy.id == strategy_id)
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def get_website_ai_logs(
    db: AsyncSession,
    website_id: UUID,
    limit: int = 20,
) -> list[AiAgentLog]:
    stmt = (
        select(AiAgentLog)
        .where(AiAgentLog.website_id == website_id)
        .order_by(desc(AiAgentLog.created_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())
