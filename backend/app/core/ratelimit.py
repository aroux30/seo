"""Fixed-window rate limiting for abuse-prone endpoints.

Backed by Redis so the limit holds across every uvicorn worker and container.
If Redis is unreachable the limiter falls back to a per-process in-memory
window: degraded (each worker counts separately) but never fails the request
open silently for a whole deployment, and never takes the API down with it.

Deliberately dependency-free (no slowapi) — Redis is already a project dep.
"""

from __future__ import annotations

import time
from threading import Lock

from fastapi import Request, status

from app.config import get_settings
from app.core.exceptions import AppException

settings = get_settings()


class RateLimitExceeded(AppException):
    def __init__(self, retry_after: int = 60):
        super().__init__(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many attempts. Try again in {retry_after} seconds.",
            "rate_limit_exceeded",
        )
        self.retry_after = retry_after


# ---------------------------------------------------------------- in-memory
# {bucket_key: (window_start_epoch, hits)}
_local_windows: dict[str, tuple[int, int]] = {}
_local_lock = Lock()


def _local_incr(key: str, window: int) -> int:
    now = int(time.time())
    bucket = now - (now % window)
    with _local_lock:
        start, hits = _local_windows.get(key, (bucket, 0))
        if start != bucket:
            start, hits = bucket, 0
        hits += 1
        _local_windows[key] = (start, hits)

        # Opportunistic cleanup so the dict can't grow without bound.
        if len(_local_windows) > 10_000:
            for k, (s, _) in list(_local_windows.items()):
                if s != bucket:
                    _local_windows.pop(k, None)
    return hits


# -------------------------------------------------------------------- redis
_redis_client = None
_redis_broken = False


def _get_redis():
    """Lazily build an async Redis client. Returns None if unavailable."""
    global _redis_client, _redis_broken
    if _redis_broken:
        return None
    if _redis_client is None:
        try:
            from redis.asyncio import from_url

            _redis_client = from_url(settings.REDIS_URL, decode_responses=True)
        except Exception:
            _redis_broken = True
            return None
    return _redis_client


async def _redis_incr(key: str, window: int) -> int | None:
    client = _get_redis()
    if client is None:
        return None
    now = int(time.time())
    bucket = now - (now % window)
    redis_key = f"rl:{key}:{bucket}"
    try:
        pipe = client.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window + 1)
        hits, _ = await pipe.execute()
        return int(hits)
    except Exception:
        # Redis down mid-flight: fall back rather than 500 the caller.
        return None


# ------------------------------------------------------------------- public
def client_ip(request: Request) -> str:
    """Best-effort client IP.

    Behind the project's nginx reverse proxy the real IP arrives in
    X-Forwarded-For; the leftmost entry is the original client. Only the
    first hop is trusted because everything downstream is ours.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


class RateLimiter:
    """FastAPI dependency enforcing `limit` requests per `window` seconds.

    Usage:
        @router.post("/login", dependencies=[Depends(RateLimiter("login", 5, 60))])
    """

    def __init__(self, name: str, limit: int, window: int = 60):
        self.name = name
        self.limit = limit
        self.window = window

    async def __call__(self, request: Request) -> None:
        key = f"{self.name}:{client_ip(request)}"

        hits = await _redis_incr(key, self.window)
        if hits is None:
            hits = _local_incr(key, self.window)

        if hits > self.limit:
            now = int(time.time())
            retry_after = self.window - (now % self.window)
            raise RateLimitExceeded(retry_after=retry_after)


# Shared instances. Login is stricter than register because credential
# stuffing is the higher-volume attack.
login_rate_limit = RateLimiter("auth_login", limit=5, window=60)
register_rate_limit = RateLimiter("auth_register", limit=3, window=300)
password_change_rate_limit = RateLimiter("auth_password", limit=5, window=300)
refresh_rate_limit = RateLimiter("auth_refresh", limit=30, window=60)
