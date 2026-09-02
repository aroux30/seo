"""URL and SSRF validation utilities for external integrations and sideloading."""

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.exceptions import AppException

ALLOWED_SCHEMES = {"http", "https"}


def _is_public_ip(host_ip: str) -> bool:
    """Return True if the IP address is a routable public IP (not loopback, private, link-local, etc.)."""
    try:
        ip = ipaddress.ip_address(host_ip)
        return not (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return False


def validate_external_url(url: str, allow_http: bool = True) -> str:
    """Validate that a URL points to a public, safe external destination.

    Prevents Server-Side Request Forgery (SSRF) to internal network services
    (e.g., PostgreSQL, Redis, n8n, cloud metadata endpoints like 169.254.169.254).
    """
    if not url or not isinstance(url, str):
        raise AppException(
            status_code=400,
            detail="آدرس URL نامعتبر است.",
            error_type="invalid_url",
        )

    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise AppException(
            status_code=400,
            detail="فقط پروتکل‌های HTTP و HTTPS مجاز هستند.",
            error_type="invalid_url_scheme",
        )

    if not allow_http and parsed.scheme.lower() != "https":
        raise AppException(
            status_code=400,
            detail="فقط پروتکل امن HTTPS مجاز است.",
            error_type="https_required",
        )

    hostname = (parsed.hostname or "").strip().lower()
    if not hostname:
        raise AppException(
            status_code=400,
            detail="دامنه یا هاست در آدرس ارسالی نامعتبر است.",
            error_type="invalid_url_host",
        )

    # Disallow localhost / local hostnames
    forbidden_hosts = {
        "localhost",
        "localhost.localdomain",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "backend",
        "frontend",
        "postgres",
        "redis",
        "n8n",
        "certbot",
    }
    if hostname in forbidden_hosts or hostname.endswith(".local"):
        raise AppException(
            status_code=400,
            detail="اتصال به آدرس‌های لوکال و شبکه داخلی مجاز نیست.",
            error_type="forbidden_private_host",
        )

    # Resolve DNS to check IP addresses
    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
        addr_info = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, socket.herror) as e:
        raise AppException(
            status_code=400,
            detail=f"عدم امکان تحلیل دامنه (DNS Error): {str(e)}",
            error_type="dns_resolution_failed",
        )

    for item in addr_info:
        ip_str = item[4][0]
        if not _is_public_ip(ip_str):
            raise AppException(
                status_code=400,
                detail="اتصال به آدرس‌های شبکه خصوصی و داخلی سرور مسدود است.",
                error_type="ssrf_blocked",
            )

    return url.strip()


async def safe_fetch_external_image(
    url: str,
    max_bytes: int = 5 * 1024 * 1024,
    timeout: float = 15.0,
    headers: dict | None = None,
) -> tuple[bytes, str]:
    """Fetch external image with strict SSRF validation and redirect loop re-validation."""
    current_url = validate_external_url(url)
    max_redirects = 5

    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        for _ in range(max_redirects):
            res = await client.get(current_url, headers=headers)
            if res.status_code in {301, 302, 303, 307, 308}:
                location = res.headers.get("location")
                if not location:
                    raise AppException(400, "Redirect location header missing", "invalid_redirect")
                next_url = str(httpx.URL(current_url).join(location))
                current_url = validate_external_url(next_url)
                continue

            res.raise_for_status()
            content = res.content
            if len(content) > max_bytes:
                raise AppException(400, "Image payload exceeds size limit", "image_too_large")
            content_type = res.headers.get("content-type", "image/png")
            return content, content_type

    raise AppException(400, "Too many redirects during image fetch", "too_many_redirects")
