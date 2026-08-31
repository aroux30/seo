import asyncio
import logging
from uuid import UUID
from celery import shared_task

from app.database import async_session_factory, engine
from app.core.exceptions import AppException
from app.models import Website
from app.services.gsc_service import sync_gsc_data
from app.services.audit_service import run_website_audit
from app.services.ai_service import generate_seo_strategy
from app.services.content_service import (
    generate_content_brief,
    generate_seo_article,
    publish_article_to_wp,
)
from app.services.automation_service import trigger_automation_workflow
from app.models.automations import AutomationWorkflow
from sqlalchemy import select

logger = logging.getLogger(__name__)


def _run_async(coro):
    """
    Run an async task body on a private event loop.

    The engine in app.database is a module-level asyncpg pool, and asyncpg binds
    each pooled connection to the loop that opened it. Creating a fresh loop per
    task and leaving the pool populated meant the *second* task to run in a
    worker process picked up a connection owned by the first, now-closed loop and
    died with "Future attached to a different loop" / "Event loop is closed".
    Disposing the engine inside the same loop hands every connection back before
    the loop goes away, so the next task starts from a clean pool.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        try:
            loop.run_until_complete(engine.dispose())
        except Exception:  # noqa: BLE001 - never mask the task's own outcome
            logger.warning("[Celery] Engine dispose failed during loop teardown", exc_info=True)
        asyncio.set_event_loop(None)
        loop.close()


import httpx

@shared_task(
    name="app.workers.tasks.sync_website_gsc_task",
    bind=True,
    autoretry_for=(httpx.TimeoutException, httpx.NetworkError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=300,
    max_retries=3,
)
def sync_website_gsc_task(self, website_id_str: str) -> dict:
    """Celery background worker task to sync Search Console performance data for a website.

    Websites without a connected (or active) Google account are a normal,
    expected state — the cron fan-out hits every active site. Skipping them is
    an INFO, not an ERROR: raising here produced a full traceback every 30
    minutes per unconnected site and buried real failures in the logs.
    """
    logger.info(f"[Celery] Starting GSC data sync for website {website_id_str}...")

    async def _async_sync():
        async with async_session_factory() as db:
            result = await sync_gsc_data(db, UUID(website_id_str))
            await db.commit()
            return result

    try:
        res = _run_async(_async_sync())
        logger.info(f"[Celery] Successfully synced GSC data for {website_id_str}: {res}")
        return res
    except AppException as e:
        # Expected configuration gaps: no integration, expired/revoked access.
        logger.info(f"[Celery] Skipping GSC sync for {website_id_str}: {e.detail}")
        return {"status": "skipped", "reason": str(e.detail)}
    except Exception as e:
        logger.error(f"[Celery] Failed to sync GSC data for {website_id_str}: {e}")
        raise


@shared_task(name="app.workers.tasks.sync_all_websites_gsc_task")
def sync_all_websites_gsc_task() -> dict:
    """Cron task that iterates over all active websites and triggers sync."""
    logger.info("[Celery] Triggering daily GSC sync for all active websites...")

    async def _get_all_sites():
        async with async_session_factory() as db:
            stmt = select(Website.id).where(Website.status == "active")
            res = await db.execute(stmt)
            return [str(uid) for uid in res.scalars().all()]

    site_ids = _run_async(_get_all_sites())
    for site_id in site_ids:
        sync_website_gsc_task.delay(site_id)

    return {"status": "triggered", "total_websites": len(site_ids)}


@shared_task(name="app.workers.tasks.run_website_audit_task")
def run_website_audit_task(website_id_str: str, max_pages: int = 20) -> dict:
    """Celery background task to run a technical SEO audit."""
    logger.info(f"[Celery] Running SEO technical audit for website {website_id_str}...")

    async def _async_audit():
        async with async_session_factory() as db:
            audit = await run_website_audit(db, UUID(website_id_str), max_pages=max_pages)
            return {"audit_id": str(audit.id), "overall_score": audit.overall_score}

    try:
        res = _run_async(_async_audit())
        logger.info(f"[Celery] Successfully finished audit for {website_id_str}: {res}")
        return res
    except Exception as e:
        logger.error(f"[Celery] Failed SEO audit for {website_id_str}: {e}")
        raise


@shared_task(name="app.workers.tasks.generate_seo_strategy_task")
def generate_seo_strategy_task(website_id_str: str, provider: str | None = None) -> dict:
    """Celery background task to generate an AI SEO strategy."""
    logger.info(f"[Celery] Generating AI SEO strategy for website {website_id_str}...")

    async def _async_strategy():
        async with async_session_factory() as db:
            strategy = await generate_seo_strategy(db, UUID(website_id_str), provider=provider)
            return {"strategy_id": str(strategy.id), "title": strategy.title}

    try:
        res = _run_async(_async_strategy())
        logger.info(f"[Celery] Successfully generated AI strategy for {website_id_str}: {res}")
        return res
    except Exception as e:
        logger.error(f"[Celery] Failed AI Strategy generation for {website_id_str}: {e}")
        raise


# =====================================================================
# Phase 4: AI Content Engine & WordPress Publishing Tasks
# =====================================================================
@shared_task(name="app.workers.tasks.generate_content_brief_task")
def generate_content_brief_task(website_id_str: str, target_keyword: str, title: str | None = None) -> dict:
    """Celery background task to generate SEO content brief."""
    logger.info(f"[Celery] Generating content brief for '{target_keyword}'...")

    async def _async_brief():
        async with async_session_factory() as db:
            brief = await generate_content_brief(
                db, UUID(website_id_str), target_keyword=target_keyword, title=title
            )
            return {"brief_id": str(brief.id), "title": brief.title}

    try:
        res = _run_async(_async_brief())
        logger.info(f"[Celery] Successfully generated brief: {res}")
        return res
    except Exception as e:
        logger.error(f"[Celery] Failed brief generation: {e}")
        raise


@shared_task(name="app.workers.tasks.generate_article_task")
def generate_article_task(
    website_id_str: str,
    brief_id_str: str | None = None,
    title: str | None = None,
    target_keyword: str | None = None,
    provider: str = "openai"
) -> dict:
    """Celery background task to generate AI SEO Article."""
    logger.info(f"[Celery] Generating article for website {website_id_str}...")

    async def _async_article():
        async with async_session_factory() as db:
            brief_id = UUID(brief_id_str) if brief_id_str else None
            article = await generate_seo_article(
                db, UUID(website_id_str), brief_id=brief_id, title=title, target_keyword=target_keyword, provider=provider
            )
            return {"article_id": str(article.id), "title": article.title, "slug": article.slug}

    try:
        res = _run_async(_async_article())
        logger.info(f"[Celery] Successfully generated article: {res}")
        return res
    except Exception as e:
        logger.error(f"[Celery] Failed article generation: {e}")
        raise


@shared_task(name="app.workers.tasks.publish_article_to_wordpress_task")
def publish_article_to_wordpress_task(article_id_str: str, post_status: str = "draft") -> dict:
    """Celery background task to publish article to WordPress."""
    logger.info(f"[Celery] Publishing article {article_id_str} to WordPress ({post_status})...")

    async def _async_pub():
        async with async_session_factory() as db:
            article = await publish_article_to_wp(db, UUID(article_id_str), post_status=post_status)
            return {
                "article_id": str(article.id),
                "wp_post_id": article.wp_post_id,
                "published_url": article.published_url,
                "status": article.status,
            }

    try:
        res = _run_async(_async_pub())
        logger.info(f"[Celery] Successfully published article {article_id_str}: {res}")
        return res
    except Exception as e:
        logger.error(f"[Celery] Failed publishing article {article_id_str}: {e}")
        raise


# =====================================================================
# Phase 5: n8n Automation Workflows & SEO OS Automation Hub Tasks
# =====================================================================
@shared_task(name="app.workers.tasks.trigger_automation_workflow_task")
def trigger_automation_workflow_task(workflow_id_str: str) -> dict:
    """Celery background task to execute an n8n Automation Workflow via webhook."""
    logger.info(f"[Celery] Triggering automation workflow {workflow_id_str}...")

    async def _async_trigger():
        async with async_session_factory() as db:
            log_entry = await trigger_automation_workflow(db, UUID(workflow_id_str))
            return {
                "log_id": str(log_entry.id),
                "workflow_id": str(log_entry.workflow_id),
                "status": log_entry.status,
                "execution_time_ms": log_entry.execution_time_ms,
            }

    try:
        res = _run_async(_async_trigger())
        logger.info(f"[Celery] Successfully triggered workflow {workflow_id_str}: {res}")
        return res
    except Exception as e:
        logger.error(f"[Celery] Failed triggering workflow {workflow_id_str}: {e}")
        raise


@shared_task(name="app.workers.tasks.run_all_active_cron_automations_task")
def run_all_active_cron_automations_task() -> dict:
    """Celery scheduled task to check and run active cron automation workflows."""
    logger.info("[Celery] Checking active cron automation workflows...")

    async def _async_check():
        async with async_session_factory() as db:
            stmt = select(AutomationWorkflow).where(
                AutomationWorkflow.is_active == True,
                AutomationWorkflow.trigger_type == "cron",
            )
            result = await db.execute(stmt)
            workflows = result.scalars().all()
            triggered_ids = []
            for wf in workflows:
                try:
                    await trigger_automation_workflow(db, wf.id)
                    triggered_ids.append(str(wf.id))
                except Exception as ex:
                    logger.error(f"[Celery] Error running cron workflow {wf.id}: {ex}")
            return {"triggered_count": len(triggered_ids), "triggered_workflows": triggered_ids}

    try:
        res = _run_async(_async_check())
        return res
    except Exception as e:
        logger.error(f"[Celery] Failed cron automations check: {e}")
        raise


@shared_task(name="app.workers.tasks.process_auto_mode_websites_task")
def process_auto_mode_websites_task() -> dict:
    """Celery scheduled task to automatically audit and generate strategies for 'auto' mode websites."""
    logger.info("[Celery] Processing auto mode websites...")

    async def _async_process():
        async with async_session_factory() as db:
            stmt = select(Website.id).where(Website.status == "active", Website.automation_mode == "auto")
            res = await db.execute(stmt)
            site_ids = [str(uid) for uid in res.scalars().all()]
            return site_ids

    try:
        site_ids = _run_async(_async_process())
        for site_id in site_ids:
            # Trigger audit first, then strategy
            run_website_audit_task.delay(site_id)
            generate_seo_strategy_task.apply_async((site_id,), countdown=60) # delay strategy to ensure audit is done

        return {"processed_count": len(site_ids), "websites": site_ids}
    except Exception as e:
        logger.error(f"[Celery] Failed auto mode processing: {e}")
        raise


# =====================================================================
# Phase 6: Opportunity / Alert detection & Notification dispatch tasks
# =====================================================================
from app.models import Alert  # noqa: E402
from app.services import approval_service, notification_service  # noqa: E402
from app.services.alert_service import detect_alerts  # noqa: E402
from app.services.opportunity_service import detect_opportunities  # noqa: E402


def _active_website_ids_query():
    """Active, not soft-deleted websites — the population every sweep works on."""
    return select(Website.id).where(
        Website.status == "active",
        Website.deleted_at.is_(None),
    )


@shared_task(name="app.workers.tasks.detect_website_opportunities_task")
def detect_website_opportunities_task(website_id_str: str) -> dict:
    """Celery background task to run the opportunity detectors for one website."""
    logger.info(f"[Celery] Detecting SEO opportunities for website {website_id_str}...")

    async def _async_detect():
        async with async_session_factory() as db:
            result = await detect_opportunities(db, UUID(website_id_str))
            await db.commit()
            return {
                "website_id": website_id_str,
                "scanned_queries": result["scanned_queries"],
                "scanned_pages": result["scanned_pages"],
                "created": result["created"],
                "updated": result["updated"],
                "expired": result["expired"],
                "by_type": result["by_type"],
            }

    try:
        res = _run_async(_async_detect())
        logger.info(f"[Celery] Opportunity detection finished for {website_id_str}: {res}")
        return res
    except Exception as e:
        logger.error(f"[Celery] Failed opportunity detection for {website_id_str}: {e}")
        raise


@shared_task(name="app.workers.tasks.detect_all_websites_opportunities_task")
def detect_all_websites_opportunities_task() -> dict:
    """Cron task that fans opportunity detection out over every active website.

    Each website is dispatched as its own task, so one website with corrupt GSC
    data cannot abort the sweep for the rest of the tenant base.
    """
    logger.info("[Celery] Triggering opportunity detection for all active websites...")

    async def _get_all_sites():
        async with async_session_factory() as db:
            res = await db.execute(_active_website_ids_query())
            return [str(uid) for uid in res.scalars().all()]

    try:
        site_ids = _run_async(_get_all_sites())
        for site_id in site_ids:
            detect_website_opportunities_task.delay(site_id)
        return {"status": "triggered", "total_websites": len(site_ids)}
    except Exception as e:
        logger.error(f"[Celery] Failed opportunity detection sweep: {e}")
        raise


@shared_task(name="app.workers.tasks.detect_website_alerts_task")
def detect_website_alerts_task(website_id_str: str) -> dict:
    """Celery background task to run the alert detectors for one website.

    Detection alone only writes rows; without the notification fan-out below an
    alert would sit in the database and never reach a human. Rows are picked up
    by `notified_at IS NULL`, which covers both freshly created alerts and ones
    that re-fired after being resolved (detect_alerts clears notified_at when a
    condition comes back), so an escalation notifies again while a still-open
    alert stays quiet.
    """
    logger.info(f"[Celery] Detecting SEO alerts for website {website_id_str}...")

    async def _async_detect():
        async with async_session_factory() as db:
            website_id = UUID(website_id_str)
            result = await detect_alerts(db, website_id)

            pending = await db.execute(
                select(Alert).where(
                    Alert.website_id == website_id,
                    Alert.status == "active",
                    Alert.notified_at.is_(None),
                )
            )
            notified = 0
            for alert in pending.scalars().all():
                try:
                    await notification_service.notify_alert(db, alert)
                    notified += 1
                except Exception as ex:  # noqa: BLE001 - one bad channel must not lose the rest
                    logger.error(
                        f"[Celery] Failed notifying alert {alert.id} "
                        f"for website {website_id_str}: {ex}"
                    )

            await db.commit()
            return {
                "website_id": website_id_str,
                "created": result["created"],
                "updated": result["updated"],
                "resolved": result["resolved"],
                "by_type": result["by_type"],
                "skipped_reason": result["skipped_reason"],
                "notified": notified,
            }

    try:
        res = _run_async(_async_detect())
        logger.info(f"[Celery] Alert detection finished for {website_id_str}: {res}")
        return res
    except Exception as e:
        logger.error(f"[Celery] Failed alert detection for {website_id_str}: {e}")
        raise


@shared_task(name="app.workers.tasks.detect_all_websites_alerts_task")
def detect_all_websites_alerts_task() -> dict:
    """Cron task that fans alert detection out over every active website."""
    logger.info("[Celery] Triggering alert detection for all active websites...")

    async def _get_all_sites():
        async with async_session_factory() as db:
            res = await db.execute(_active_website_ids_query())
            return [str(uid) for uid in res.scalars().all()]

    try:
        site_ids = _run_async(_get_all_sites())
        for site_id in site_ids:
            detect_website_alerts_task.delay(site_id)
        return {"status": "triggered", "total_websites": len(site_ids)}
    except Exception as e:
        logger.error(f"[Celery] Failed alert detection sweep: {e}")
        raise


@shared_task(name="app.workers.tasks.dispatch_pending_notifications_task")
def dispatch_pending_notifications_task() -> dict:
    """Deliver queued notifications on their external channels.

    Detectors only enqueue rows; this is the task that actually sends them, so it
    runs far more often than the daily detectors.
    """
    logger.info("[Celery] Dispatching pending notifications...")

    async def _async_dispatch():
        async with async_session_factory() as db:
            result = await notification_service.dispatch_pending(db)
            await db.commit()
            return result

    try:
        res = _run_async(_async_dispatch())
        logger.info(f"[Celery] Notification dispatch finished: {res}")
        return res
    except Exception as e:
        logger.error(f"[Celery] Failed notification dispatch: {e}")
        raise



@shared_task(name="app.workers.tasks.expire_stale_approvals_task")
def expire_stale_approvals_task() -> dict:
    """Close approval requests whose deadline has passed.

    Swept for every tenant in one pass: `expire_stale_requests` takes an
    optional organization_id, so no fan-out over organizations is needed and the
    queue does not get one task per tenant every hour.
    """
    logger.info("[Celery] Expiring stale approval requests...")

    async def _async_expire():
        async with async_session_factory() as db:
            result = await approval_service.expire_stale_requests(db)
            await db.commit()
            return result

    try:
        res = _run_async(_async_expire())
        logger.info(f"[Celery] Approval expiry sweep finished: {res}")
        return res
    except Exception as e:
        logger.error(f"[Celery] Failed approval expiry sweep: {e}")
        raise
