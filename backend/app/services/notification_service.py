"""Notification fan-out and dispatch.

An Alert is a row in one table; a Notification is one delivery attempt on one
channel to one recipient. Turning the first into the second is not a 1:1 copy:
`Website.notification_preferences` decides which channels are even in play,
and the "dashboard" channel additionally fans out to every member of the
organization (each one needs their own row so their own bell can mark it read
independently — a single shared row could not have a per-user `read_at`).

`notify_alert` therefore always creates dashboard rows already "sent" (there
is nothing external to deliver, the row itself is the delivery), and leaves
external-channel rows "pending" for `dispatch_pending` to pick up later. This
split is what lets the Celery alert-detection task stay fast: it only writes
rows and stamps `alert.notified_at`, it never blocks on a Telegram or webhook
call.

`dispatch_pending` treats "channel is not configured for this website" as
"skipped", not "failed" — a website that never set up Telegram is not an
error condition, and treating it as one would light up error dashboards for
every tenant that simply does not use that channel.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, Notification, OrganizationMember, Website

logger = logging.getLogger(__name__)

# How many attempts before dispatch_pending stops re-trying an external
# delivery automatically. A stuck row still shows up as "failed" and can be
# retried by hand; this just stops burning a request every dispatch tick.
MAX_DELIVERY_ATTEMPTS = 5


def _dashboard_action_url(alert: Alert) -> str:
    return f"/websites/{alert.website_id}/alerts/{alert.id}"


def _enabled_channels(preferences: dict) -> list[str]:
    """Which channels this website wants notified on.

    Missing/empty preferences means "dashboard only" — a website that never
    configured anything should still show alerts in the bell, just not spam an
    unconfigured Telegram bot.
    """
    channels = preferences.get("channels") if isinstance(preferences, dict) else None
    if not channels:
        return ["dashboard"]
    # De-dupe while preserving order, and drop anything not in the vocabulary
    # so a typo in a stored preference cannot create a bogus Notification row.
    known = {"dashboard", "telegram", "email", "webhook"}
    seen: list[str] = []
    for ch in channels:
        if ch in known and ch not in seen:
            seen.append(ch)
    return seen or ["dashboard"]


async def notify_alert(db: AsyncSession, alert: Alert) -> list[Notification]:
    """Create one Notification per enabled channel (dashboard: per org member).

    Stamps `alert.notified_at` so the Celery sweep's `notified_at IS NULL`
    query will not pick this alert up again on the next run.
    """
    website = await db.get(Website, alert.website_id)
    preferences = (website.notification_preferences or {}) if website else {}
    channels = _enabled_channels(preferences)

    now = datetime.now(timezone.utc)
    event_type = f"alert.{alert.alert_type}"
    action_url = _dashboard_action_url(alert)
    payload = {
        "alert_type": alert.alert_type,
        "severity": alert.severity,
        "website_id": str(alert.website_id),
    }

    created: list[Notification] = []

    if "dashboard" in channels:
        members = await db.execute(
            select(OrganizationMember.user_id).where(
                OrganizationMember.organization_id == alert.organization_id
            )
        )
        for (user_id,) in members.all():
            row = Notification(
                organization_id=alert.organization_id,
                user_id=user_id,
                website_id=alert.website_id,
                channel="dashboard",
                status="sent",
                event_type=event_type,
                title=alert.title,
                body=alert.message,
                action_url=action_url,
                alert_id=alert.id,
                payload=payload,
                sent_at=now,
            )
            db.add(row)
            created.append(row)

    for channel in channels:
        if channel == "dashboard":
            continue
        row = Notification(
            organization_id=alert.organization_id,
            user_id=None,
            website_id=alert.website_id,
            channel=channel,
            status="pending",
            event_type=event_type,
            title=alert.title,
            body=alert.message,
            action_url=action_url,
            alert_id=alert.id,
            payload=payload,
        )
        db.add(row)
        created.append(row)

    alert.notified_at = now
    await db.flush()
    return created


async def _deliver_telegram(notification: Notification, preferences: dict) -> tuple[str, str | None]:
    """Send one row via the Telegram Bot API.

    Returns (status, error_message). Missing bot token/chat id is a setup gap,
    not a delivery failure, so it comes back "skipped".
    """
    telegram_cfg = preferences.get("telegram") if isinstance(preferences, dict) else None
    bot_token = (telegram_cfg or {}).get("bot_token") if telegram_cfg else None
    chat_id = (telegram_cfg or {}).get("chat_id") if telegram_cfg else None
    if not bot_token or not chat_id:
        return "skipped", "Telegram bot_token/chat_id is not configured for this website"

    text = notification.title
    if notification.body:
        text = f"{notification.title}\n\n{notification.body}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
        if response.status_code >= 400:
            return "failed", f"Telegram API HTTP {response.status_code}: {response.text[:300]}"
        return "sent", None
    except httpx.RequestError as exc:
        return "failed", f"Telegram request failed: {exc}"


async def _deliver_webhook(notification: Notification, preferences: dict) -> tuple[str, str | None]:
    """POST the notification payload to the website's configured webhook URL."""
    webhook_cfg = preferences.get("webhook") if isinstance(preferences, dict) else None
    url = (webhook_cfg or {}).get("url") if webhook_cfg else None
    if not url:
        return "skipped", "Webhook URL is not configured for this website"

    body = {
        "event_type": notification.event_type,
        "title": notification.title,
        "body": notification.body,
        "action_url": notification.action_url,
        "payload": notification.payload,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=body)
        if response.status_code >= 400:
            return "failed", f"Webhook HTTP {response.status_code}: {response.text[:300]}"
        return "sent", None
    except httpx.RequestError as exc:
        return "failed", f"Webhook request failed: {exc}"


def _deliver_email(notification: Notification, preferences: dict) -> tuple[str, str | None]:
    """Email has no SMTP configuration anywhere in this deployment.

    `app/config.py` carries no SMTP settings, so this is always a skip rather
    than a guess at credentials that do not exist.
    """
    return "skipped", "Email delivery is not configured (no SMTP settings in app.config)"


async def dispatch_pending(db: AsyncSession, limit: int = 100) -> dict:
    """Attempt delivery of queued external-channel notifications.

    Dashboard rows are never selected here: they are written already "sent"
    by notify_alert, since the row itself is the delivery.
    """
    result = await db.execute(
        select(Notification)
        .where(
            Notification.status == "pending",
            Notification.channel.in_(["telegram", "email", "webhook"]),
        )
        .order_by(Notification.created_at.asc())
        .limit(limit)
    )
    rows = list(result.scalars().all())

    counts = {"sent": 0, "failed": 0, "skipped": 0, "attempted": 0}
    website_cache: dict[UUID, Website | None] = {}

    for row in rows:
        counts["attempted"] += 1
        row.attempt_count = (row.attempt_count or 0) + 1

        website = website_cache.get(row.website_id) if row.website_id else None
        if row.website_id and row.website_id not in website_cache:
            website = await db.get(Website, row.website_id)
            website_cache[row.website_id] = website
        preferences = (website.notification_preferences or {}) if website else {}

        try:
            if row.channel == "telegram":
                status, error_message = await _deliver_telegram(row, preferences)
            elif row.channel == "webhook":
                status, error_message = await _deliver_webhook(row, preferences)
            else:  # email
                status, error_message = _deliver_email(row, preferences)
        except Exception as exc:  # noqa: BLE001 - one bad row must not abort the batch
            status, error_message = "failed", f"Unexpected delivery error: {exc}"
            logger.error(f"Notification {row.id} delivery raised unexpectedly: {exc}")

        now = datetime.now(timezone.utc)
        row.status = status
        row.error_message = error_message
        if status == "sent":
            row.sent_at = now
            row.failed_at = None
        elif status == "failed":
            row.failed_at = now
        # "skipped" leaves sent_at/failed_at untouched: it never attempted a
        # real delivery, so neither timestamp applies.

        counts[status] += 1

    await db.flush()
    return counts


async def list_notifications(
    db: AsyncSession,
    *,
    organization_id: UUID,
    user_id: UUID,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[Notification]:
    """The caller's own notifications, newest first.

    Scoped by both organization_id and user_id: a member of several
    organizations must only see the bell for the one they are currently
    acting as.
    """
    stmt = select(Notification).where(
        Notification.organization_id == organization_id,
        Notification.user_id == user_id,
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def count_unread(
    db: AsyncSession, *, organization_id: UUID, user_id: UUID
) -> int:
    result = await db.execute(
        select(Notification.id).where(
            Notification.organization_id == organization_id,
            Notification.user_id == user_id,
            Notification.read_at.is_(None),
        )
    )
    return len(result.all())


async def mark_read(
    db: AsyncSession,
    *,
    organization_id: UUID,
    user_id: UUID,
    notification_ids: list[UUID] | None = None,
) -> int:
    """Mark specific notifications read, or every unread one when ids is None.

    Filtered on the caller's own user_id regardless of what ids are passed, so
    supplying a colleague's notification id silently matches nothing instead
    of mutating their inbox.
    """
    stmt = select(Notification).where(
        Notification.organization_id == organization_id,
        Notification.user_id == user_id,
        Notification.read_at.is_(None),
    )
    if notification_ids is not None:
        stmt = stmt.where(Notification.id.in_(notification_ids))
    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    now = datetime.now(timezone.utc)
    for row in rows:
        row.read_at = now

    await db.flush()
    return len(rows)


__all__ = [
    "notify_alert",
    "dispatch_pending",
    "list_notifications",
    "count_unread",
    "mark_read",
]
