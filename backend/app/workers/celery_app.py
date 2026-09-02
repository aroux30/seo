import os
from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "ai_seo_os_workers",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Tehran",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=1800,  # 30 minutes max per task
    task_soft_time_limit=1500,  # 25 minutes soft limit
)

# Scheduled background tasks
celery_app.conf.beat_schedule = {
    "daily-seo-data-sync-all-websites": {
        "task": "app.workers.tasks.sync_all_websites_gsc_task",
        "schedule": crontab(hour=3, minute=0),
    },
    "periodic-n8n-cron-automations-check": {
        "task": "app.workers.tasks.run_all_active_cron_automations_task",
        "schedule": crontab(hour="*/6", minute=15),
    },
    "daily-auto-mode-websites-processing": {
        "task": "app.workers.tasks.process_auto_mode_websites_task",
        "schedule": crontab(hour=4, minute=0),
    },
    # Detection runs AFTER the 03:00 GSC sync, never before: both detectors read
    # the gsc_* tables the sync fills, so running them earlier would analyse
    # yesterday's snapshot and report stale findings (and, for alerts, invent a
    # "traffic drop" from the missing day).
    "daily-alert-detection-all-websites": {
        # 05:00 — an hour after auto-mode audits at 04:00, because the
        # audit_score_drop detector compares the two most recent completed
        # audits and wants today's audit to be one of them.
        "task": "app.workers.tasks.detect_all_websites_alerts_task",
        "schedule": crontab(hour=5, minute=0),
    },
    "daily-opportunity-detection-all-websites": {
        # 05:30 — staggered behind alert detection so the two sweeps do not
        # contend for the same connection pool across every tenant at once.
        "task": "app.workers.tasks.detect_all_websites_opportunities_task",
        "schedule": crontab(hour=5, minute=30),
    },
    "frequent-notification-dispatch": {
        # Detectors only enqueue; this is what actually delivers. Every 15
        # minutes keeps a critical alert timely without hammering the channels.
        "task": "app.workers.tasks.dispatch_pending_notifications_task",
        "schedule": crontab(minute="*/15"),
    },
    "hourly-approval-queue-expiry-sweep": {
        # Hourly, not daily: `expires_in_hours` can be as low as 1, so a daily
        # sweep would leave a one-hour request sitting in the queue looking
        # actionable for most of a day. A reviewer must never be able to approve
        # a request whose deadline has already passed.
        "task": "app.workers.tasks.expire_stale_approvals_task",
        "schedule": crontab(minute=40),
    },
}
