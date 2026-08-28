import re
import json
from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from fastapi import HTTPException

from app.models.content import ContentBrief, ContentArticle
from app.models import Website
from app.core.exceptions import AppException
from app.core.html import markdown_to_html, sanitize_html
from app.core.scoping import assert_article_in_org, assert_brief_in_org
from app.core.seo_score import score_article, score_article_detailed
from app.core.banner import gradient_banner_b64
from app.services.wordpress_service import publish_post_to_wordpress
from app.services.version_service import create_version
from app.core.ai_router import call_ai_with_rotation
from app.config import get_settings

settings = get_settings()


async def _article_target_keyword(db: AsyncSession, article: ContentArticle) -> str:
    """Best-effort target keyword for scoring an article.

    ContentArticle has no target_keyword column of its own; the keyword lives on
    the brief it was generated from. The brief is loaded with an explicit query
    rather than via `article.brief` — touching a lazy relationship under asyncio
    raises MissingGreenlet. Falls back to stored metadata, then the title, so
    briefless articles still score.
    """
    meta = article.seo_metadata or {}
    if meta.get("target_keyword"):
        return meta["target_keyword"]
    if article.brief_id:
        result = await db.execute(
            select(ContentBrief.target_keyword).where(ContentBrief.id == article.brief_id)
        )
        kw = result.scalar_one_or_none()
        if kw:
            return kw
    return article.title or ""


_PERSIAN_TO_ENGLISH_MAP = {
    "آموزش": "tutorial-guide",
    "راهنمای جامع": "complete-guide",
    "راهنما": "guide",
    "صفر تا صد": "step-by-step",
    "خرید": "buy",
    "گوشی": "smartphone",
    "موبایل": "mobile-phone",
    "تلفن همراه": "phone",
    "بهترین": "best",
    "قیمت": "price",
    "سئو": "seo",
    "سایت": "website",
    "وردپرس": "wordpress",
    "سرور مجازی": "vps-server",
    "سرور": "server",
    "هاست": "hosting",
    "دامنه": "domain",
    "افزایش رتبه": "rank-boost",
    "تکنیک": "techniques",
    "ترفند": "tips",
    "استراتژی": "strategy",
    "تولید محتوا": "content-creation",
    "محتوا": "content",
    "لینک سازی": "link-building",
    "بک لینک": "backlinks",
    "ابزار": "tools",
    "هوش مصنوعی": "ai",
    "دیجیتال مارکتینگ": "digital-marketing",
    "فروشگاه": "ecommerce-shop",
    "طراحی": "design",
    "برنامه نویسی": "programming",
    "نکته": "tips",
    "راهکار": "solutions",
    "مقایسه": "comparison",
    "بررسی": "review",
    "سامسونگ": "samsung",
    "آیفون": "iphone",
    "شیائومی": "xiaomi",
    "لپ تاپ": "laptop",
    "دوربین": "camera",
    "باتری": "battery",
    "پردازنده": "cpu-processor",
}

_PERSIAN_CHAR_TRANSLIT = {
    'ا': 'a', 'آ': 'a', 'ب': 'b', 'پ': 'p', 'ت': 't', 'ث': 's', 'ج': 'j', 'چ': 'ch',
    'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'z', 'ر': 'r', 'ز': 'z', 'ژ': 'zh', 'س': 's',
    'ش': 'sh', 'ص': 's', 'ض': 'z', 'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh', 'ف': 'f',
    'ق': 'gh', 'ک': 'k', 'گ': 'g', 'ل': 'l', 'م': 'm', 'ن': 'n', 'و': 'v', 'ه': 'h',
    'ی': 'y', 'ئ': 'e', 'ي': 'y', 'ك': 'k', '۰': '0', '۱': '1', '۲': '2', '۳': '3',
    '۴': '4', '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9'
}

def _generate_english_slug(title: str, keyword: str = "") -> str:
    """Generate clean, human-readable English SEO slug for Google Search Console."""
    combined = f"{keyword} {title}".strip()
    
    # 1. If text already has 2+ English words, use them
    eng_words = re.findall(r"[a-zA-Z0-9]+", combined)
    if len(eng_words) >= 2:
        return "-".join(w.lower() for w in eng_words[:6])
    
    # 2. Semantic dictionary replacement
    text = combined.lower()
    for per, eng in sorted(_PERSIAN_TO_ENGLISH_MAP.items(), key=lambda x: -len(x[0])):
        text = text.replace(per, f" {eng} ")
    
    # 3. Transliterate remaining Persian characters
    out_chars = []
    for ch in text:
        if ch in _PERSIAN_CHAR_TRANSLIT:
            out_chars.append(_PERSIAN_CHAR_TRANSLIT[ch])
        elif re.match(r"[a-zA-Z0-9\s-]", ch):
            out_chars.append(ch)
    
    cleaned = "".join(out_chars)
    cleaned = re.sub(r"[\s_-]+", "-", cleaned).strip("-").lower()
    
    # Remove duplicates and limit length
    tokens = [t for t in cleaned.split("-") if t]
    unique_tokens = []
    for t in tokens:
        if not unique_tokens or unique_tokens[-1] != t:
            unique_tokens.append(t)
    
    final_slug = "-".join(unique_tokens[:7])
    return final_slug or "seo-guide-post"


def _build_image_prompt(kw: str, title: str, custom_prompt: str | None = None) -> str:
    """Build high-relevance, photorealistic image prompts matching the article topic."""
    if custom_prompt and len(custom_prompt.strip()) > 20:
        return custom_prompt.strip()
    
    text = f"{kw} {title}".lower()
    if any(w in text for w in ["گوشی", "موبایل", "smartphone", "phone", "سامسونگ", "آیفون", "شیائومی"]):
        return "modern flagship smartphones and mobile devices arranged on a sleek modern tech table, illuminated screens showing high tech wallpapers, studio lighting, crisp 4k product photography, commercial shot, no text, no letters"
    elif any(w in text for w in ["سرور", "هاست", "vps", "hosting", "دیتاسنتر"]):
        return "modern high-tech datacenter server room with glowing blue and cyan LED lights, futuristic server racks, clean cable management, 4k ultra-realistic photography, cinematic lighting, no text"
    elif any(w in text for w in ["سئو", "seo", "رتبه", "گوگل", "گوگل سرچ", "ترافیک", "analytics"]):
        return "modern minimalist 3D SEO digital analytics dashboard with glowing charts and search performance graph on futuristic workstation, 4k tech photography, no text"
    elif any(w in text for w in ["وردپرس", "wordpress", "طراحی سایت", "وب سایت", "برنامه نویسی"]):
        return "modern developer workspace with dual monitors displaying web design wireframes and code editor, warm ambient lighting, 4k photography, no text"
    elif any(w in text for w in ["خرید", "فروشگاه", "ecommerce", "مارکتینگ"]):
        return "modern stylish e-commerce shopping scene with elegant product boxes, sleek digital devices, premium studio commercial lighting, 4k photorealistic, no text"
    else:
        slug_eng = _generate_english_slug(title, kw).replace("-", " ")
        return f"professional photography of {slug_eng}, high-end tech commercial photography, cinematic lighting, 4k photorealistic, no text, no watermarks"


def _slugify_persian(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text)
    cleaned = re.sub(r"[\s_-]+", "-", cleaned).strip("-")
    return cleaned.lower() or "seo-article-slug"



async def generate_content_brief(
    db: AsyncSession,
    website_id: UUID,
    target_keyword: str,
    title: str | None = None,
    secondary_keywords: list[str] | None = None,
    search_intent: str = "informational",
    target_word_count: int = 1500,
    keyword_id: UUID | None = None,
) -> ContentBrief:
    """Generate an AI-powered SEO Content Brief with Persian heading structure & FAQs."""
    stmt = select(Website).where(Website.id == website_id)
    result = await db.execute(stmt)
    website = result.scalar_one_or_none()
    if not website:
        raise AppException(status_code=404, detail="وب‌سایت یافت نشد.", error_type="website_not_found")

    final_title = title or f"راهنمای جامع {target_keyword}"
    sec_kws = secondary_keywords or []
    
    system_prompt = (
        "تو یک متخصص ارشد استراتژی محتوا و سئو (SEO Content Strategist) هستی. "
        "وظیفه تو تدوین بریف محتوایی (Content Brief) جامع، جذاب و سئو شده به زبان فارسی است. "
        "پاسخ باید صرفاً یک آبجکت JSON معتبر و بدون هیچ متن اضافی باشد با ساختار دقیق زیر:\n"
        "{\n"
        '  "title": "عنوان جذاب و سئو شده برای مقاله",\n'
        '  "outline": {\n'
        '    "h1": "عنوان اصلی مقاله",\n'
        '    "h2_sections": ["سرفصل اصلی ۱", "سرفصل اصلی ۲", "سرفصل اصلی ۳", "سرفصل اصلی ۴"],\n'
        '    "key_takeaways": ["نکته کلیدی ۱", "نکته کلیدی ۲"],\n'
        '    "faqs": [{"question": "پرسش متداول ۱؟", "answer": "پاسخ کوتاه و مفید"}]\n'
        '  }\n'
        "}"
    )
    user_prompt = (
        f"کلمه کلیدی اصلی: {target_keyword}\n"
        f"قصد کاربر از جستجو (Search Intent): {search_intent}\n"
        f"کلمات کلیدی فرعی: {', '.join(sec_kws) if sec_kws else 'ندارد'}\n"
        f"حجم هدف مقاله: {target_word_count} کلمه\n"
        f"لطفاً بریف محتوایی سئو شده را در قالب JSON خواسته شده تولید کن."
    )

    data = None
    try:
        raw_res, used_model, p_tok, c_tok = await call_ai_with_rotation(
            db=db,
            org_id=website.organization_id,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            json_mode=True,
        )
        if raw_res:
            try:
                data = json.loads(raw_res)
            except Exception:
                match = re.search(r"\{.*\}", raw_res, flags=re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
    except AppException:
        raise
    except Exception as e:
        raise AppException(
            status_code=503,
            detail=f"خطا در ارتباط با ارائه‌دهنده هوش مصنوعی: {str(e)}",
            error_type="ai_generation_error",
        )

    if not data or not isinstance(data, dict):
        raise AppException(
            status_code=502,
            detail="خروجی هوش مصنوعی نامعتبر بود. لطفاً دوباره تلاش کنید.",
            error_type="invalid_ai_response",
        )

    final_title = data.get("title", final_title)
    outline = data.get("outline", {})

    brief = ContentBrief(
        website_id=website_id,
        keyword_id=keyword_id,
        title=final_title,
        target_keyword=target_keyword,
        secondary_keywords=sec_kws,
        search_intent=search_intent,
        outline=outline,
        target_word_count=target_word_count,
        status="ready",
    )
    db.add(brief)
    await db.flush()
    await db.refresh(brief)
    return brief

async def get_content_briefs(db: AsyncSession, website_id: UUID) -> list[ContentBrief]:
    stmt = (
        select(ContentBrief)
        .where(ContentBrief.website_id == website_id, ContentBrief.deleted_at.is_(None))
        .order_by(ContentBrief.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_content_brief_by_id(db: AsyncSession, brief_id: UUID) -> ContentBrief | None:
    stmt = select(ContentBrief).where(
        ContentBrief.id == brief_id, ContentBrief.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


def _featured_img_tag(article_id: UUID, keyword: str) -> str:
    """<figure> pointing at the article's own featured-image endpoint.

    The image bytes live in seo_metadata (base64); embedding them as a data URI
    would bloat every article row and every WP payload, so the body references
    the streaming endpoint instead. WordPress publish rewrites this src to the
    sideloaded media URL.
    """
    alt = (keyword or "").replace('"', "")
    return (
        '<figure class="wp-block-image size-large">'
        f'<img src="/api/v1/content/articles/detail/{article_id}/featured-image" alt="{alt}" />'
        "</figure>"
    )


def _ensure_featured_img_in_body(
    content_html: str, article_id: UUID, keyword: str
) -> str:
    """Prepend the featured-image figure unless the body already carries one."""
    if "<img" in (content_html or "").lower():
        return content_html
    return _featured_img_tag(article_id, keyword) + "\n" + (content_html or "")

async def generate_seo_article(
    db: AsyncSession,
    website_id: UUID,
    brief_id: UUID | None = None,
    title: str | None = None,
    target_keyword: str | None = None,
    provider: str | None = None,
    user_id: UUID | None = None,
) -> ContentArticle:
    """Generate an AI-written, highly structured SEO Persian Article from Brief or Keyword."""
    stmt = select(Website).where(Website.id == website_id)
    res = await db.execute(stmt)
    website = res.scalar_one_or_none()
    if not website:
        raise AppException(status_code=404, detail="وب‌سایت یافت نشد.", error_type="website_not_found")

    brief = None
    if brief_id:
        brief = await get_content_brief_by_id(db, brief_id)

    kw = target_keyword or (brief.target_keyword if brief else "سئو وب‌سایت")
    req_title = title or (brief.title if brief else f"راهنمای جامع {kw}")
    outline = brief.outline if brief else None

    system_prompt = (
        "تو یک متخصص ارشد تولید محتوای سئو (Senior SEO Content Writer) و مسلط به نگارش فارسی روان، جذاب و رتبه‌گیر در موتورهای جستجو هستی. "
        "وظیفه تو تولید یک مقاله جامع، استاندارد و کامل سئو بر اساس کلمه کلیدی و ساختار ارائه‌شده است.\n"
        "قوانین تولید محتوا:\n"
        "1. ساختار بدنه (content_html) باید کاملاً فارسی، حرفه‌ای و شامل تگ‌های HTML مثل <h2>, <h3>, <p>, <ul>, <li>, <strong> باشد.\n"
        "2. در انتهای مقاله یک بخش سوالات متداول (FAQ) با حداقل ۳ پرسش و پاسخ کاربردی قرار بده.\n"
        "3. چگالی کلمه کلیدی اصلی باید حدود ۱٪ تا ۱.۵٪ و کاملاً طبیعی باشد.\n"
        "4. یک توضیحات متای استاندارد (meta_description) حداکثر ۱۶۰ کاراکتر حاوی کلمه کلیدی بنویس.\n"
        "5. یک پرامپت انگلیسی باکیفیت و بدون متن برای تولید تصویر شاخص (image_prompt_english) تهیه کن.\n"
        "پاسخ باید دقیقاً یک شیء JSON با ساختار زیر باشد:\n"
        "{\n"
        '  "title": "عنوان جذاب فارسی",\n'
        '  "slug_english": "english-seo-slug",\n'
        '  "content_html": "<p>مقدمه جذاب...</p><h2>...</h2>",\n'
        '  "seo_metadata": {\n'
        '    "meta_description": "توضیحات متا جذاب...",\n'
        '    "image_prompt_english": "high quality photorealistic 4k tech photography, cinematic lighting, no text"\n'
        '  }\n'
        "}"
    )
    user_prompt = (
        f"کلمه کلیدی هدف: {kw}\n"
        f"عنوان درخواستی: {req_title}\n"
        f"ساختار سرفصل‌ها و بریف: {json.dumps(outline, ensure_ascii=False) if outline else 'بر اساس بهترین ساختار سئو'}\n"
        f"لطفاً مقاله کامل، جامع و سئو شده را در قالب JSON تولید کن."
    )

    data = None
    try:
        raw_res, used_model, p_tok, c_tok = await call_ai_with_rotation(
            db=db,
            org_id=website.organization_id,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            provider_preference=provider,
            json_mode=True,
        )
        if raw_res:
            try:
                data = json.loads(raw_res)
            except Exception:
                match = re.search(r"\{.*\}", raw_res, flags=re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
    except AppException:
        raise
    except Exception as e:
        raise AppException(
            status_code=503,
            detail=f"خطا در ارتباط با ارائه‌دهنده هوش مصنوعی: {str(e)}",
            error_type="ai_generation_error",
        )

    if not data or not isinstance(data, dict):
        raise AppException(
            status_code=502,
            detail="خروجی هوش مصنوعی نامعتبر بود (عدم دریافت ساختار JSON). لطفا دوباره تلاش کنید.",
            error_type="invalid_ai_response",
        )

    article_title = data.get("title", req_title)
    slug = data.get("slug_english") or data.get("slug") or _generate_english_slug(article_title, kw)
    # The HTML came from an LLM (or the mock fallback). Sanitize before storing:
    # the frontend renders this with dangerouslySetInnerHTML, so a hostile tag
    # that reaches the database becomes stored XSS.
    content_html = sanitize_html(data.get("content_html", ""))

    # A generation whose body came back empty (unparseable LLM output) must not
    # become an empty 30-score article — fail loudly so the user can retry.
    if len((content_html or "").strip()) < 200:
        raise AppException(
            status_code=502,
            detail="خروجی هوش مصنوعی ناقص بود (بدنه مقاله خالی برگشت). لطفا دوباره تلاش کنید.",
            error_type="empty_generation",
        )

    # ---- deterministic SEO enforcement (LLMs ignore soft instructions) ----
    def _plain_text(h: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h or "")).strip()

    def _kw_count(h: str) -> int:
        return _plain_text(h).lower().count(kw.lower()) if kw else 0

    # (a) nofollow policy: 2-3 external links, at least ONE dofollow. If every
    # external link carries nofollow, strip the rel from the first one. Handles
    # both quote styles and any rel position inside the tag.
    anchor_tags = re.findall(r"<a\b[^>]*>", content_html, flags=re.IGNORECASE)
    external_tags = [
        t for t in anchor_tags
        if re.search(r'href="https?://', t, flags=re.IGNORECASE)
        and "arouxshop" not in t.lower()
    ]
    if external_tags and all("nofollow" in t.lower() for t in external_tags):
        first = external_tags[0]
        fixed = re.sub(r'(?i)\s*rel\s*=\s*(["\']?)[^"\'>]*\1', "", first, count=1)
        content_html = content_html.replace(first, fixed, 1)

    # (b) density floor: if the keyword barely appears, append a Persian
    # closing section that mentions it naturally until density clears ~1%.
    if kw:
        words = len(_plain_text(content_html).split())
        occ = _kw_count(content_html)
        density = (occ / words * 100) if words else 0
        if density < 1.0:
            mentions = min(8, max(3, int(words * 0.012) - occ))
            closing = (
                f"<h2>جمع‌بندی نهایی درباره {kw}</h2>"
                f"<p>در این مقاله تلاش کردیم تمام نکات کلیدی مربوط به {kw} را پوشش دهیم. "
                f"تجربه نشان داده انتخاب هوشمندانه هنگام {kw} تفاوت بزرگی ایجاد می‌کند؛ "
                f"پیش از هر تصمیمی، نیاز واقعی خودتان را بسنجید و بر اساس آن بین گزینه‌ها "
                f"مقایسه انجام دهید تا بهترین نتیجه را از {kw} بگیرید.</p>"
            )
            while mentions > 3:
                closing += (
                    f"<p>یادتان باشد {kw} را همیشه از فروشگاه‌های معتبر تهیه کنید و "
                    f"شرایط گارانتی {kw} را دقیق بخوانید؛ این دو عامل، رضایت شما را تضمین می‌کند.</p>"
                )
                mentions -= 3
            content_html = content_html + "\n" + closing

    # The old prompt made the LLM emit source.unsplash.com <img> tags, but that
    # service is dead — the tags render as broken images on WordPress. Images
    # are handled separately now (featured_image_b64), so strip any stragglers.
    content_html = re.sub(
        r"<img\b[^>]*source\.unsplash\.com[^>]*>\s*", "", content_html, flags=re.IGNORECASE
    )

    # basic markdown conversion for fallback (or we just use HTML)
    content_md = content_html.replace("<h2>", "## ").replace("</h2>", "\n").replace("<p>", "").replace("</p>", "\n\n").replace("<strong>", "**").replace("</strong>", "**").replace("<ul>", "").replace("</ul>", "").replace("<li>", "- ").replace("</li>", "\n")

    seo_metadata = data.get("seo_metadata", {})

    # Guarantee a usable meta description: the checklist's basic_meta check
    # requires the keyword inside it, but LLMs sometimes omit it entirely or
    # write it without the keyword. Derive from the first ~150 chars of body
    # text and force the keyword in.
    meta_desc = (seo_metadata.get("meta_description") or "").strip()
    if kw and kw.lower() not in meta_desc.lower():
        plain = re.sub(r"<[^>]+>", " ", content_html)
        plain = re.sub(r"\s+", " ", plain).strip()
        meta_desc = f"{kw} — {plain[:130]}".strip()
        seo_metadata["meta_description"] = meta_desc[:160]

    # Featured image: n8n attaches a Gemini-generated illustration as
    # featured_image_b64. When the image model is out of quota, try a
    # keyword-relevant AI image from Pollinations (needs a browser UA or it
    # 403s datacenter IPs); the local gradient banner is the last resort so
    # every article still ships with a real header image.
    featured_b64 = data.get("featured_image_b64")
    if not featured_b64:
        try:
            import base64 as _b64
            import random
            from urllib.parse import quote
            # A random seed per call: Pollinations is deterministic per prompt.
            # The English image prompt comes from the article LLM itself, so
            # the scene actually matches the topic instead of a generic blob.
            seed = random.randint(1, 999_999)
            img_prompt = _build_image_prompt(
                kw=kw or "",
                title=article_title,
                custom_prompt=data.get("image_prompt_english")
            )
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as img_client:
                img_res = await img_client.get(
                    "https://image.pollinations.ai/prompt/" + quote(img_prompt),
                    params={
                        "width": 1200,
                        "height": 630,
                        "nologo": "true",
                        "model": "flux",
                        "seed": seed,
                    },
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"},
                )
                if img_res.status_code == 200 and 0 < len(img_res.content) <= 5 * 1024 * 1024:
                    featured_b64 = _b64.b64encode(img_res.content).decode("ascii")
        except Exception:
            pass
    if not featured_b64:
        featured_b64 = gradient_banner_b64(kw or article_title)
    seo_metadata["featured_image_b64"] = featured_b64

    # Previously hardcoded to 92 regardless of content. Score the real output so
    # the number in the UI means something.
    computed_score = score_article(
        content_html=content_html,
        title=article_title,
        target_keyword=kw,
        meta_description=seo_metadata.get("meta_description", ""),
        slug=slug,
    )
    seo_metadata["score_breakdown"] = score_article_detailed(
        content_html=content_html,
        title=article_title,
        target_keyword=kw,
        meta_description=seo_metadata.get("meta_description", ""),
        slug=slug,
    )
    seo_metadata.setdefault("target_keyword", kw)

    article = ContentArticle(
        website_id=website_id,
        brief_id=brief_id,
        title=article_title,
        slug=slug,
        content_markdown=content_md,
        content_html=content_html,
        seo_score=computed_score,
        seo_metadata=seo_metadata,
        status="review",
    )
    db.add(article)
    await db.flush()

    # Now that the article has an id, prepend the featured-image figure so the
    # body itself carries the image (with keyword alt) — the SEO checklist's
    # image checks score against the body, and the editor preview shows it.
    article.content_html = _ensure_featured_img_in_body(
        article.content_html, article.id, kw
    )
    detailed_score = score_article_detailed(
        content_html=article.content_html,
        title=article.title or "",
        target_keyword=kw,
        meta_description=seo_metadata.get("meta_description", ""),
        slug=article.slug or "",
    )
    article.seo_score = detailed_score["score"]
    seo_metadata = dict(article.seo_metadata or {})
    seo_metadata["score_breakdown"] = detailed_score
    article.seo_metadata = seo_metadata

    await db.flush()
    await create_version(
        db,
        article,
        change_type="created",
        changed_by=user_id,
        change_summary="ایجاد اولیه محتوا توسط هوش مصنوعی",
    )
    await db.refresh(article)
    return article

async def get_content_articles(db: AsyncSession, website_id: UUID) -> list[ContentArticle]:
    stmt = (
        select(ContentArticle)
        .where(ContentArticle.website_id == website_id, ContentArticle.deleted_at.is_(None))
        .order_by(ContentArticle.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())

async def get_content_article_by_id(db: AsyncSession, article_id: UUID) -> ContentArticle | None:
    stmt = select(ContentArticle).where(
        ContentArticle.id == article_id, ContentArticle.deleted_at.is_(None)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def delete_content_article(
    db: AsyncSession,
    article_id: UUID,
    org_id: UUID,
) -> dict:
    """Soft-delete an article.

    Soft rather than hard so version history and internal-link suggestions that
    reference the article survive an accidental delete, matching how calendar
    slots are removed. The row disappears from every list/detail read because
    those now filter `deleted_at IS NULL`.
    """
    article = await assert_article_in_org(db, article_id, org_id)
    article.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return {"deleted": True, "id": str(article_id)}


async def delete_content_brief(
    db: AsyncSession,
    brief_id: UUID,
    org_id: UUID,
) -> dict:
    """Soft-delete a brief.

    Articles keep their `brief_id` FK (SET NULL on hard delete never fires), so
    the provenance of already-generated articles survives the brief's removal.
    """
    brief = await assert_brief_in_org(db, brief_id, org_id)
    brief.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    return {"deleted": True, "id": str(brief_id)}

async def update_content_article(
    db: AsyncSession,
    article_id: UUID,
    title: str | None = None,
    content_markdown: str | None = None,
    status: str | None = None,
    user_id: UUID | None = None,
) -> ContentArticle:
    article = await get_content_article_by_id(db, article_id)
    if not article:
        raise AppException(status_code=404, detail="مقاله یافت نشد.", error_type="article_not_found")

    if title:
        article.title = title
        article.slug = _slugify_persian(title)
    if content_markdown is not None: # explicitly check not None in case of empty string
        article.content_markdown = content_markdown
        article.content_html = markdown_to_html(content_markdown)

    # Older articles were generated before images were part of the body: give
    # any article that has a featured image but no body image the figure now,
    # so its SEO checklist (image + alt checks) reflects what will publish.
    if "<img" not in (article.content_html or "").lower() and (
        (article.seo_metadata or {}).get("featured_image_b64")
    ):
        article.content_html = _ensure_featured_img_in_body(
            article.content_html or "", article.id,
            await _article_target_keyword(db, article),
        )
        article.content_markdown = article.content_html.replace("<h2>", "## ").replace("</h2>", "\n").replace("<p>", "").replace("</p>", "\n\n").replace("<strong>", "**").replace("</strong>", "**").replace("<ul>", "").replace("</ul>", "").replace("<li>", "- ").replace("</li>", "\n")

    if title or content_markdown is not None:
        detailed_score = score_article_detailed(
            content_html=article.content_html or "",
            title=article.title or "",
            target_keyword=await _article_target_keyword(db, article),
            meta_description=article.seo_metadata.get("meta_description", "") if article.seo_metadata else "",
            slug=article.slug or "",
        )
        article.seo_score = detailed_score["score"]
        new_meta = dict(article.seo_metadata or {})
        new_meta["score_breakdown"] = detailed_score
        article.seo_metadata = new_meta
    if status:
        article.status = status

    await db.flush()
    await create_version(
        db,
        article,
        change_type="edited",
        changed_by=user_id,
        change_summary="ویرایش دستی محتوا",
    )
    await db.refresh(article)
    return article

async def publish_article_to_wp(
    db: AsyncSession,
    article_id: UUID,
    post_status: str = "draft",
) -> ContentArticle:
    """Publish this article directly to WordPress via REST API."""
    article = await get_content_article_by_id(db, article_id)
    if not article:
        raise AppException(status_code=404, detail="مقاله یافت نشد.", error_type="article_not_found")

    # Push the SEO layer along with the content: Rank Math reads these meta
    # keys over REST, and without them its focus-keyword/description fields
    # stay empty and its content score shows N/A on the WP side.
    seo = article.seo_metadata or {}
    meta_desc = seo.get("meta_description", "") or ""
    focus_kw = seo.get("target_keyword") or (await _article_target_keyword(db, article))
    wp_meta = {
        "rank_math_focus_keyword": focus_kw or "",
        "rank_math_description": meta_desc,
        "rank_math_title": article.title or "",
    }

    wp_res = await publish_post_to_wordpress(
        db=db,
        website_id=article.website_id,
        title=article.title,
        content_html=article.content_html,
        status=post_status,
        meta=wp_meta,
        excerpt=meta_desc or None,
        existing_post_id=article.wp_post_id,
        featured_image_b64=seo.get("featured_image_b64"),
        slug=article.slug,
    )

    article.wp_post_id = wp_res.get("id")
    article.published_url = wp_res.get("link")
    article.status = "published" if post_status == "publish" else "review"

    # Record what actually reached WordPress so the editor's WP card can show
    # more than a bare post id.
    new_meta = dict(article.seo_metadata or {})
    new_meta["wp_seo_meta_pushed"] = bool(wp_res.get("seo_meta_pushed"))
    if wp_res.get("featured_media_id"):
        new_meta["wp_featured_media_id"] = wp_res["featured_media_id"]
    if wp_res.get("featured_note"):
        new_meta["wp_featured_note"] = wp_res["featured_note"]
    article.seo_metadata = new_meta

    await db.flush()
    await db.refresh(article)
    return article
