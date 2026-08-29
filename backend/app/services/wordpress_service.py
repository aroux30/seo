import base64
import hashlib
import re
from datetime import datetime, timezone
from uuid import UUID
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import encrypt_value, decrypt_value
from app.core.exceptions import AppException, NotFoundError
from app.models import WordPressIntegration, Website

_IMG_SRC_RE = re.compile(r'<img\b[^>]*src=["\']([^"\']+)["\']', flags=re.IGNORECASE)
_ALLOWED_IMG_SCHEMES = ("http://", "https://")
_MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB sideload cap
# The AI writes source.unsplash.com URLs, but that service was shut down — any
# such URL (and any URL that fails to download) falls back to a deterministic
# picsum photo so the post still gets a real featured image.
_DEAD_IMAGE_HOSTS = ("source.unsplash.com",)


def _candidate_image_urls(content_html: str, seed_text: str) -> list[str]:
    """Download candidates for the featured image, best first."""
    urls: list[str] = []
    first = _first_image_url(content_html)
    if first and not any(host in first for host in _DEAD_IMAGE_HOSTS):
        urls.append(first)
    seed = hashlib.md5((seed_text or "seo-article").encode("utf-8")).hexdigest()[:10]
    urls.append(f"https://picsum.photos/seed/{seed}/1200/630")
    return urls


async def connect_wordpress(
    db: AsyncSession,
    website_id: UUID,
    wp_url: str,
    username: str,
    app_password: str,
) -> WordPressIntegration:
    """
    Verify WordPress REST API credentials and save encrypted application password.
    """
    stmt = select(Website).where(Website.id == website_id)
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise NotFoundError("Website", str(website_id))

    clean_url = wp_url.rstrip("/")
    test_url = f"{clean_url}/wp-json/wp/v2/users/me"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(
                test_url,
                auth=(username, app_password),
            )
            if res.status_code == 401 or res.status_code == 403:
                raise AppException(
                    status_code=400,
                    detail="نام کاربری یا رمز عبور اپلیکیشن وردپرس (Application Password) معتبر نیست.",
                    error_type="wp_auth_error",
                )
            res.raise_for_status()
    except httpx.RequestError as e:
        raise AppException(
            status_code=400,
            detail=f"عدم امکان اتصال به سایت وردپرسی. آیا آدرس سایت صحیح است؟ خطای ارتباطی: {str(e)}",
            error_type="wp_connection_error",
        )
    except httpx.HTTPStatusError as e:
        raise AppException(
            status_code=400,
            detail=f"وردپرس پاسخ مناسبی نداد (کد وضعیت: {e.response.status_code}). بررسی کنید آیا REST API فعال است.",
            error_type="wp_api_error",
        )

    encrypted_pass = encrypt_value(app_password)

    stmt = select(WordPressIntegration).where(WordPressIntegration.website_id == website_id)
    result = await db.execute(stmt)
    integration = result.scalar_one_or_none()

    if not integration:
        integration = WordPressIntegration(
            website_id=website_id,
            wp_url=clean_url,
            username=username,
            encrypted_app_password=encrypted_pass,
            status="active",
            last_synced_at=datetime.now(timezone.utc),
        )
        db.add(integration)
    else:
        integration.wp_url = clean_url
        integration.username = username
        integration.encrypted_app_password = encrypted_pass
        integration.status = "active"
        integration.last_synced_at = datetime.now(timezone.utc)

    await db.flush()
    return integration


async def get_wordpress_integration(db: AsyncSession, website_id: UUID) -> WordPressIntegration | None:
    stmt = select(WordPressIntegration).where(WordPressIntegration.website_id == website_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def list_wp_categories(db: AsyncSession, website_id: UUID) -> list[dict]:
    """Fetch WordPress categories from connected site."""
    integration = await get_wordpress_integration(db, website_id)
    if not integration or integration.status != "active":
        raise AppException(
            status_code=400,
            detail="وب‌سایت به وردپرس متصل نیست یا اتصال آن غیرفعال است.",
            error_type="wp_not_connected",
        )

    clean_url = integration.wp_url.rstrip("/")
    url = f"{clean_url}/wp-json/wp/v2/categories"
    password = decrypt_value(integration.encrypted_app_password)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, auth=(integration.username, password))
            res.raise_for_status()
            data = res.json()
            return [{"id": c.get("id"), "name": c.get("name"), "slug": c.get("slug")} for c in data]
    except Exception as e:
        raise AppException(
            status_code=500,
            detail=f"خطا در دریافت دسته‌بندی‌ها از وردپرس: {str(e)}",
            error_type="wp_api_error"
        )


def _first_image_url(content_html: str) -> str | None:
    """First http(s) image in the article body, for the featured-image sideload."""
    for src in _IMG_SRC_RE.findall(content_html or ""):
        low = src.strip().lower()
        if low.startswith(_ALLOWED_IMG_SCHEMES):
            return src.strip()
    return None


def _guess_image_type(url: str, content_type: str | None) -> tuple[str, str]:
    """(content_type, extension) for the sideloaded image, from headers then URL."""
    if content_type and content_type.startswith("image/"):
        ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
        return content_type, ext_map.get(content_type, "jpg")
    low = url.lower()
    for ext, ctype in (
        (".png", "image/png"),
        (".webp", "image/webp"),
        (".gif", "image/gif"),
        (".jpg", "image/jpeg"),
        (".jpeg", "image/jpeg"),
    ):
        if ext in low:
            return ctype, ext.lstrip(".")
    return "image/jpeg", "jpg"


async def publish_post_to_wordpress(
    db: AsyncSession,
    website_id: UUID,
    title: str,
    content_html: str,
    status: str = "draft",
    meta: dict | None = None,
    excerpt: str | None = None,
    existing_post_id: int | None = None,
    featured_image_b64: str | None = None,
    slug: str | None = None,
) -> dict:
    """
    Publish (or update) an article on WordPress via REST API.

    Beyond title/content/status this pushes the SEO layer that on-site plugins
    like Rank Math read:
      - `slug` sets the clean English permalink on WordPress (e.g. guide-buy-smartphone).
      - `meta` dict is sent verbatim in the post's `meta` field.
      - `excerpt` feeds the native WP excerpt.
      - `featured_image_b64` is sideloaded into the WP media library and attached as
        featured_media. When attached as featured_media, duplicate body header images
        are stripped so WordPress themes only render the image once.
    """
    integration = await get_wordpress_integration(db, website_id)
    if not integration or integration.status != "active":
        raise AppException(
            status_code=400,
            detail="اتصال وردپرس فعال نیست. لطفا ابتدا اتصال وردپرس را در تنظیمات فعال کنید.",
            error_type="wp_not_connected"
        )

    clean_url = integration.wp_url.rstrip("/")
    posts_url = f"{clean_url}/wp-json/wp/v2/posts"
    password = decrypt_value(integration.encrypted_app_password)
    auth = (integration.username, password)

    payload: dict = {
        "title": title,
        "content": content_html,
        "status": status,
    }
    if slug:
        payload["slug"] = slug
    if excerpt:
        payload["excerpt"] = excerpt
    if meta:
        payload["meta"] = meta

    seo_meta_pushed = False
    featured_media_id: int | None = None
    featured_url: str | None = None
    featured_note: str | None = None

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            # --- featured image (base64 from the pipeline takes priority) ---
            _UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}
            body_image_candidates: list[str] = []
            focus_kw = (meta or {}).get("rank_math_focus_keyword") or (meta or {}).get("_yoast_wpseo_focuskw") or title or ""

            if featured_image_b64:
                try:
                    img_bytes = base64.b64decode(featured_image_b64)
                    if 0 < len(img_bytes) <= _MAX_IMAGE_BYTES:
                        media_res = await client.post(
                            f"{clean_url}/wp-json/wp/v2/media",
                            content=img_bytes,
                            headers={
                                "Content-Type": "image/png",
                                "Content-Disposition": 'attachment; filename="seo-article-featured.png"',
                            },
                            auth=auth,
                        )
                        media_res.raise_for_status()
                        media_json = media_res.json()
                        featured_media_id = media_json.get("id")
                        featured_url = media_json.get("source_url")

                        # Set alt_text, title, and description on the uploaded WordPress media object
                        if featured_media_id and focus_kw:
                            try:
                                await client.post(
                                    f"{clean_url}/wp-json/wp/v2/media/{featured_media_id}",
                                    json={
                                        "alt_text": focus_kw,
                                        "title": focus_kw,
                                        "caption": f"تصویر راهنمای {focus_kw}",
                                        "description": f"تصویر شاخص و کاربردی برای مقاله {focus_kw}",
                                    },
                                    auth=auth,
                                )
                            except Exception:
                                pass
                    else:
                        featured_note = "تصویر شاخص تولیدشده بیش از حد بزرگ بود."
                except Exception as img_exc:
                    featured_note = f"بارگذاری تصویر شاخص ناموفق بود ({type(img_exc).__name__})."

            if not featured_media_id:
                body_image_candidates = _candidate_image_urls(
                    content_html, focus_kw or title
                )
            for img_url in body_image_candidates:
                try:
                    img_res = await client.get(img_url, timeout=30.0, headers=_UA)
                    img_res.raise_for_status()
                    raw = img_res.content
                    if not (0 < len(raw) <= _MAX_IMAGE_BYTES):
                        featured_note = "تصویر مقاله برای بارگذاری بیش از حد بزرگ بود."
                        continue
                    ctype, ext = _guess_image_type(img_url, img_res.headers.get("content-type"))
                    media_res = await client.post(
                        f"{clean_url}/wp-json/wp/v2/media",
                        content=raw,
                        headers={
                            "Content-Type": ctype,
                            "Content-Disposition": f'attachment; filename="seo-article-{existing_post_id or "new"}.{ext}"',
                        },
                        auth=auth,
                    )
                    media_res.raise_for_status()
                    media_json = media_res.json()
                    featured_media_id = media_json.get("id")
                    featured_url = media_json.get("source_url")

                    # Set alt_text on sideloaded media
                    if featured_media_id and focus_kw:
                        try:
                            await client.post(
                                f"{clean_url}/wp-json/wp/v2/media/{featured_media_id}",
                                json={
                                    "alt_text": focus_kw,
                                    "title": focus_kw,
                                },
                                auth=auth,
                            )
                        except Exception:
                            pass
                    break
                except Exception as img_exc:
                    featured_note = f"بارگذاری تصویر شاخص ناموفق بود ({type(img_exc).__name__})."

            # Belt & suspenders nofollow policy at publish time: if every
            # external link is nofollow (older articles generated before the
            # prompt fix), strip the rel from the first one so Rank Math sees a
            # healthy dofollow/nofollow mix.
            anchor_tags = re.findall(r"<a\b[^>]*>", content_html or "", flags=re.IGNORECASE)
            external_tags = [
                t for t in anchor_tags
                if re.search(r'href="https?://', t, flags=re.IGNORECASE)
                and "arouxshop" not in t.lower()
            ]
            if external_tags and all("nofollow" in t.lower() for t in external_tags):
                first = external_tags[0]
                fixed = re.sub(r'(?i)\s*rel\s*=\s*(["\']?)[^"\'>]*\1', "", first, count=1)
                content_html = content_html.replace(first, fixed, 1)

            # Ensure Rank Math image requirement is 100% satisfied:
            # Rank Math on-page analyzer scans `post_content` for `<img ... alt="focus_kw">`.
            # We rewrite any internal streaming image URL to the real WordPress media URL,
            # and guarantee that an image with alt="{focus_kw}" exists inside the HTML body.
            if featured_media_id:
                payload["featured_media"] = featured_media_id

            # Rewrite internal backend streaming URL to real WordPress media URL
            internal_src = re.compile(
                r'(<img[^>]*src=")/api/v1/content/articles/detail/[^"]*/featured-image(")',
                flags=re.IGNORECASE,
            )
            if featured_url and internal_src.search(content_html or ""):
                content_html = internal_src.sub(
                    rf'\g<1>{featured_url}\g<2>', content_html
                )
            elif featured_url and "<img" not in (content_html or "").lower():
                # Inject featured image at the top of content so Rank Math on-page checks find it
                content_html = (
                    f'<figure class="wp-block-image size-large"><img src="{featured_url}" '
                    f'alt="{focus_kw}" /></figure>\n' + content_html
                )

            # Ensure every img tag has alt text containing focus keyword if missing
            if focus_kw:
                def _wp_fix_img_alt(m: re.Match) -> str:
                    tag = m.group(0)
                    alt_m = re.search(r'alt=["\']([^"\']*)["\']', tag, flags=re.IGNORECASE)
                    if alt_m:
                        cur = alt_m.group(1)
                        if focus_kw.lower() not in cur.lower():
                            new_alt = f"{focus_kw} - {cur}" if cur.strip() else focus_kw
                            tag = tag[:alt_m.start()] + f'alt="{new_alt}"' + tag[alt_m.end():]
                    else:
                        tag = tag[:4] + f' alt="{focus_kw}"' + tag[4:]
                    return tag
                content_html = re.sub(r"<img\b[^>]*>", _wp_fix_img_alt, content_html, flags=re.IGNORECASE)

            payload["content"] = content_html

            if existing_post_id:
                res = await client.post(
                    f"{posts_url}/{existing_post_id}",
                    json=payload,
                    auth=auth,
                )
            else:
                res = await client.post(posts_url, json=payload, auth=auth)
            res.raise_for_status()
            data = res.json()
            post_id = data.get("id")
            seo_meta_pushed = bool(meta)

            return {
                "id": post_id,
                "link": data.get("link"),
                "status": data.get("status", status),
                "simulated": False,
                "seo_meta_pushed": seo_meta_pushed,
                "featured_media_id": featured_media_id,
                "featured_url": featured_url,
                "featured_note": featured_note,
            }
    except httpx.HTTPStatusError as e:
        # The raw httpx string embeds the full WP endpoint URL (and would embed
        # the request target of every retry); surface only the status code so
        # internal infrastructure details never reach the client.
        raise AppException(
            status_code=502,
            detail=f"وردپرس درخواست انتشار را نپذیرفت (کد وضعیت {e.response.status_code}). "
                   "مقدار وضعیت انتشار و اتصال وردپرس را بررسی کنید.",
            error_type="wp_publish_error",
        )
    except Exception as e:
        raise AppException(
            status_code=502,
            detail=f"خطا در ارتباط با وردپرس جهت انتشار محتوا: {type(e).__name__}",
            error_type="wp_publish_error"
        )
