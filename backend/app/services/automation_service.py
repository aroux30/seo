import time
from datetime import datetime, timedelta, timezone
from uuid import UUID
import httpx
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.automations import AutomationWorkflow, AutomationLog
from app.models import Website
from app.models.insights import Notification
from app.core.exceptions import AppException
from app.core.url_security import validate_external_url
from app.config import get_settings
from app.schemas.automations import AutomationTemplateRead

settings = get_settings()


def _validate_n8n_url(url: str) -> str:
    if not url:
        raise AppException(status_code=400, detail="آدرس وب‌هوک الزامی است.", error_type="invalid_webhook_url")
    url = url.strip()
    base = (settings.N8N_WEBHOOK_BASE_URL or "http://n8n:5678").rstrip("/")
    if url.startswith(base) or url.startswith("http://n8n:5678"):
        return url
    return validate_external_url(url)


def _notify_automation_failure(db, website: Website | None, workflow: AutomationWorkflow,
                               error_message: str) -> None:
    """Drop an in-app notification so a broken automation is visible in the
    bell without anyone reading container logs. Dashboard-channel notifications
    are delivered inline (status=sent immediately)."""
    if website is None:
        return
    now = datetime.now(timezone.utc)
    db.add(Notification(
        organization_id=website.organization_id,
        website_id=website.id,
        channel="dashboard",
        status="sent",
        event_type="automation.failed",
        title=f"اتوماسیون «{workflow.name}» ناموفق بود",
        body=error_message[:500],
        action_url=f"/websites/{website.id}/automations",
        payload={"workflow_id": str(workflow.id)},
        sent_at=now,
    ))


def get_predefined_templates() -> list[AutomationTemplateRead]:
    """Return Built-in SEO OS Automation Templates for n8n."""
    return [
        AutomationTemplateRead(
            key="seo_audit",
            name="بررسی و آدیت فنی سئو",
            description="بررسی خودکار فنی وب‌سایت و تولید گزارش آدیت با استفاده از هوش مصنوعی.",
            category="technical_audit",
            default_trigger="cron",
            default_cron="0 2 * * 0",
            sample_webhook_url="https://n8n.yourdomain.com/webhook/seo-audit",
            parameters_schema=[
                {"name": "max_pages_scan", "label": "حداکثر صفحات بررسی", "default": 100},
            ],
        ),
        AutomationTemplateRead(
            key="seo_strategy",
            name="معمار استراتژی سئو",
            description="تدوین استراتژی محتوایی و کلمات کلیدی با هوش مصنوعی بر اساس رقبا و ترندها.",
            category="strategy",
            default_trigger="manual",
            default_cron="",
            sample_webhook_url="https://n8n.yourdomain.com/webhook/seo-strategy",
            parameters_schema=[],
        ),
        AutomationTemplateRead(
            key="seo_content_brief",
            name="تولید خودکار بریِف محتوا",
            description="تولید بریِف و پیش‌نویس محتوا برای کلمات کلیدی هدف.",
            category="content",
            default_trigger="webhook",
            default_cron="",
            sample_webhook_url="https://n8n.yourdomain.com/webhook/seo-content-brief",
            parameters_schema=[
                {"name": "default_word_count", "label": "تعداد کلمات پیش‌فرض", "default": 1500},
            ],
        ),
        AutomationTemplateRead(
            key="seo_article",
            name="نویسنده هوشمند مقاله",
            description="نوشتن کامل مقاله سئوشده بر اساس بریِف و کلمات کلیدی با ساختار مناسب.",
            category="content",
            default_trigger="manual",
            default_cron="",
            sample_webhook_url="https://n8n.yourdomain.com/webhook/seo-article",
            parameters_schema=[
                {"name": "tone", "label": "لحن مقاله", "default": "تخصصی و رسمی"},
            ],
        ),
    ]


async def create_automation_workflow(
    db: AsyncSession,
    website_id: UUID,
    name: str,
    n8n_webhook_url: str,
    description: str | None = None,
    template_key: str | None = None,
    trigger_type: str = "cron",
    cron_expression: str | None = None,
    is_active: bool = True,
    config_metadata: dict | None = None,
) -> AutomationWorkflow:
    """Create a new automation workflow connected to n8n."""
    website = await db.get(Website, website_id)
    if not website:
        raise AppException(status_code=404, detail="وب‌سایت یافت نشد.", error_type="website_not_found")

    safe_webhook_url = _validate_n8n_url(n8n_webhook_url)

    workflow = AutomationWorkflow(
        website_id=website_id,
        name=name,
        description=description,
        template_key=template_key,
        trigger_type=trigger_type,
        cron_expression=cron_expression,
        n8n_webhook_url=safe_webhook_url,
        is_active=is_active,
        config_metadata=config_metadata or {},
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def get_automation_workflows(
    db: AsyncSession,
    website_id: UUID,
) -> list[AutomationWorkflow]:
    """List all automation workflows for a website."""
    stmt = select(AutomationWorkflow).where(
        AutomationWorkflow.website_id == website_id
    ).order_by(AutomationWorkflow.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_automation_workflow_by_id(
    db: AsyncSession,
    workflow_id: UUID,
) -> AutomationWorkflow | None:
    """Get a specific automation workflow by ID."""
    return await db.get(AutomationWorkflow, workflow_id)


async def toggle_automation_workflow(
    db: AsyncSession,
    workflow_id: UUID,
    is_active: bool,
) -> AutomationWorkflow:
    """Toggle automation workflow status."""
    workflow = await get_automation_workflow_by_id(db, workflow_id)
    if not workflow:
        raise AppException(status_code=404, detail="اتوماسیون یافت نشد.", error_type="workflow_not_found")

    workflow.is_active = is_active
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def delete_automation_workflow(db: AsyncSession, workflow_id: UUID) -> dict:
    """Hard-delete a workflow.

    Workflows are operational configuration rather than content history; a
    removed automation has no reason to linger. Its execution logs cascade
    (AutomationLog.workflow_id ondelete=CASCADE), which is the intended
    behaviour — logs of a deleted integration are noise, not an audit trail.
    """
    workflow = await get_automation_workflow_by_id(db, workflow_id)
    if not workflow:
        raise AppException(status_code=404, detail="اتوماسیون یافت نشد.", error_type="workflow_not_found")

    await db.delete(workflow)
    await db.flush()
    return {"deleted": True, "id": str(workflow_id)}


async def trigger_automation_workflow(
    db: AsyncSession,
    workflow_id: UUID,
) -> AutomationLog:
    """Manually or scheduled trigger of an automation workflow to its n8n webhook URL."""
    workflow = await get_automation_workflow_by_id(db, workflow_id)
    if not workflow:
        raise AppException(status_code=404, detail="اتوماسیون یافت نشد.", error_type="workflow_not_found")

    website = await db.get(Website, workflow.website_id)
    domain = website.domain if website else ""

    start_time = time.time()
    payload = {
        "event": "seo_os_workflow_triggered",
        "workflow_id": str(workflow.id),
        "website_id": str(workflow.website_id),
        "domain": domain,
        "workflow_name": workflow.name,
        "template_key": workflow.template_key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": workflow.config_metadata,
    }

    log_entry = AutomationLog(
        workflow_id=workflow.id,
        website_id=workflow.website_id,
        status="running",
        payload_json=payload,
        result_json={},
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)

    # Call external n8n Webhook
    try:
        safe_url = _validate_n8n_url(workflow.n8n_webhook_url)
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(safe_url, json=payload)
            elapsed_ms = int((time.time() - start_time) * 1000)

            if res.status_code < 400:
                log_entry.status = "success"
                log_entry.execution_time_ms = elapsed_ms
                try:
                    log_entry.result_json = res.json()
                except Exception:
                    log_entry.result_json = {"response_text": res.text[:500], "status_code": res.status_code}
                workflow.last_run_status = "success"
            else:
                log_entry.status = "failed"
                log_entry.execution_time_ms = elapsed_ms
                log_entry.error_message = f"n8n Webhook Error HTTP {res.status_code}: {res.text[:300]}"
                workflow.last_run_status = "failed"
                _notify_automation_failure(db, website, workflow, log_entry.error_message)

    except Exception as exc:
        elapsed_ms = int((time.time() - start_time) * 1000)
        log_entry.status = "failed"
        log_entry.execution_time_ms = elapsed_ms
        log_entry.error_message = f"Connection Failed to n8n webhook: {str(exc)[:200]}"
        workflow.last_run_status = "failed"
        _notify_automation_failure(db, website, workflow, log_entry.error_message)

    workflow.last_run_at = datetime.utcnow()
    await db.commit()
    await db.refresh(log_entry)
    return log_entry


async def get_automation_logs(
    db: AsyncSession,
    website_id: UUID,
    limit: int = 50,
) -> list[AutomationLog]:
    """List recent execution logs for a website's automations.

    First reaps stale `running` rows: a run whose process died mid-flight (a
    backend restart during a deploy, a webhook that accepted the connection and
    then went silent past the httpx timeout) would otherwise sit in «در حال
    اجرا» forever. Anything still `running` after 10 minutes cannot still be
    running — the synchronous trigger path caps out around 15 seconds — so it
    is marked failed with an explanatory message. The webhook-callback endpoint
    remains the legitimate way a long n8n job resolves itself; 10 minutes
    comfortably exceeds any sane async job that will ever call back.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    stale_stmt = select(AutomationLog).where(
        AutomationLog.website_id == website_id,
        AutomationLog.status == "running",
        AutomationLog.created_at < cutoff,
    )
    stale_rows = (await db.execute(stale_stmt)).scalars().all()
    if stale_rows:
        for row in stale_rows:
            row.status = "failed"
            row.error_message = "اجرای ناتمام: پاسخی از وب‌هوک n8n دریافت نشد (timeout)."
        await db.flush()
        await db.commit()

    stmt = (
        select(AutomationLog)
        .where(AutomationLog.website_id == website_id)
        .order_by(desc(AutomationLog.created_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def handle_webhook_callback(
    db: AsyncSession,
    workflow_id: UUID,
    website_id: UUID,
    status: str,
    result_json: dict,
    execution_time_ms: int | None = None,
    error_message: str | None = None,
) -> AutomationLog:
    """Callback method for n8n to post back execution results asynchronously."""
    log_entry = AutomationLog(
        workflow_id=workflow_id,
        website_id=website_id,
        status=status,
        execution_time_ms=execution_time_ms,
        payload_json={"event": "n8n_async_callback"},
        result_json=result_json or {},
        error_message=error_message,
    )
    db.add(log_entry)

    workflow = await db.get(AutomationWorkflow, workflow_id)
    if workflow:
        workflow.last_run_at = datetime.utcnow()
        workflow.last_run_status = status

    await db.commit()
    await db.refresh(log_entry)
    return log_entry
