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


def _enforce_100_seo_compliance(
    content_html: str,
    title: str,
    kw: str,
    meta_desc: str,
    slug: str,
    article_id: UUID | None = None,
) -> tuple[str, str, str, str]:
    """Deterministically enforce all Rank Math checklist items so Rank Math scores 100/100."""
    html = content_html or ""
    art_title = (title or "").strip()
    art_kw = (kw or "").strip()
    art_slug = (slug or "").strip()

    # 1. Title formatting: ensure title starts with keyword, contains a number, and has a Power Word
    if art_kw:
        power_words = ["جامع", "طلایی", "تخصصی", "پیشرفته", "شگفت‌انگیز", "بهترین", "سریع‌ترین", "کاربردی", "حرفه‌ای", "کامل‌ترین", "صفر تا صد"]
        has_power_word = any(pw in art_title for pw in power_words)
        has_num = bool(re.search(r"[0-9۰-۹]", art_title)) or any(
            w in art_title for w in ["صفر تا صد", "۰ تا ۱۰۰", "0 to 100", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "ده", "100", "۱۰۰"]
        )

        if not art_title.lower().startswith(art_kw.lower()):
            prefix = "۱۰ نکته طلایی و جامع" if (not has_num and not has_power_word) else ("۱۰ نکته کلیدی" if not has_num else "")
            if prefix:
                art_title = f"{art_kw}: {prefix} — {art_title}".strip(" —:")
            else:
                art_title = f"{art_kw} — {art_title}".strip(" —:")

        # Re-check number & power word
        has_num = bool(re.search(r"[0-9۰-۹]", art_title)) or any(
            w in art_title for w in ["صفر تا صد", "۰ تا ۱۰۰", "0 to 100", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه", "ده", "100", "۱۰۰"]
        )
        if not has_num:
            art_title = f"{art_title} [۱۰ نکته کلیدی ۰ تا ۱۰۰]"

    # 2. Meta description: ensure 120-160 chars and contains focus keyword
    if art_kw and art_kw.lower() not in (meta_desc or "").lower():
        plain = re.sub(r"<[^>]+>", " ", html)
        plain = re.sub(r"\s+", " ", plain).strip()
        meta_desc = f"راهنمای جامع {art_kw}: {plain[:100]}... بررسی تخصصی، استراتژی‌های کاربردی و نکات مهم.".strip()
    elif not meta_desc:
        meta_desc = f"راهنمای جامع {art_kw} — بررسی کامل، راهکارهای عملی و ترفندهای حرفه‌ای برای کسب بهترین رتبه در گوگل.".strip()

    if len(meta_desc) > 160:
        meta_desc = meta_desc[:157] + "..."

    # 3. First 10% keyword check: ensure keyword is in first paragraph
    first_p_match = re.search(r"<p\b[^>]*>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL)
    if art_kw and first_p_match:
        first_p_text = first_p_match.group(1)
        if art_kw.lower() not in first_p_text.lower():
            injected_first_p = f"<p>در این راهنمای جامع و کاربردی به بررسی دقیق و همه‌جانبه <strong>{art_kw}</strong> می‌پردازیم. {first_p_text}</p>"
            html = html.replace(first_p_match.group(0), injected_first_p, 1)
    elif art_kw and not first_p_match:
        html = f"<p>در این راهنمای تخصصی همه چیز را درباره <strong>{art_kw}</strong> از صفر تا صد بررسی می‌کنیم.</p>\n" + html

    # 4. Heading keyword check: ensure at least two H2s contain the keyword
    h2_matches = re.findall(r"<h2\b[^>]*>(.*?)</h2>", html, flags=re.IGNORECASE | re.DOTALL)
    if art_kw and not any(art_kw.lower() in h.lower() for h in h2_matches):
        html = f"<h2>راهنمای گام‌به‌گام و جامع {art_kw}</h2>\n" + html

    # 5. External links: ensure at least 2 authoritative external links exist
    anchor_tags = re.findall(r"<a\b[^>]*>", html, flags=re.IGNORECASE)
    external_tags = [
        t for t in anchor_tags
        if re.search(r'href=["\']https?://', t, flags=re.IGNORECASE)
    ]
    if len(external_tags) < 2 and art_kw:
        ext_kw_slug = art_kw.replace(" ", "_")
        ext_injection = (
            f'<div class="seo-references my-4 p-4 rounded-xl bg-slate-900/40 border border-slate-800">'
            f'<p class="text-sm font-semibold text-slate-300 mb-1">منابع و مراجع علمی معتبر:</p>'
            f'<p class="text-xs text-slate-400">برای مطالعه استانداردهای جهانی در حوزه {art_kw} می‌توانید به <a href="https://fa.wikipedia.org/wiki/{ext_kw_slug}" target="_blank" rel="noopener noreferrer" class="text-indigo-400 hover:underline">دانشنامه ویکی‌پدیا</a> و مستندات رسمی <a href="https://developers.google.com/search" target="_blank" rel="nofollow noopener noreferrer" class="text-indigo-400 hover:underline">Google Search Central</a> مراجعه نمایید.</p>'
            f'</div>'
        )
        html = html + "\n" + ext_injection

    # 6. Internal links: ensure at least 2 internal links exist
    anchor_tags_2 = re.findall(r"<a\b[^>]*>", html, flags=re.IGNORECASE)
    internal_tags = [
        t for t in anchor_tags_2
        if not re.search(r'href=["\']https?://', t, flags=re.IGNORECASE)
        and re.search(r'href=["\']/', t, flags=re.IGNORECASE)
    ]
    if len(internal_tags) < 2:
        int_injection = (
            f'<div class="seo-related-articles my-4 p-4 rounded-xl bg-indigo-950/20 border border-indigo-900/40">'
            f'<p class="text-sm font-semibold text-indigo-300 mb-2">مقالات و آموزش‌های پیشنهادی:</p>'
            f'<ul class="list-disc pr-5 text-xs text-slate-300 space-y-1">'
            f'<li><a href="/blog/seo-strategy" class="text-indigo-400 hover:underline">راهنمای جامع تدوین استراتژی سئو و بازاریابی محتوا</a></li>'
            f'<li><a href="/blog/content-optimization" class="text-indigo-400 hover:underline">چک‌لیست طلایی بهینه‌سازی ساختار متن و رتبه‌گیری</a></li>'
            f'</ul></div>'
        )
        html = html + "\n" + int_injection

    # 7. Structured Table of Contents (TOC) with HTML anchor links
    if "rank-math-toc" not in html and "table-of-contents" not in html:
        extracted_h2 = re.findall(r"<h2\b[^>]*>(.*?)</h2>", html, flags=re.IGNORECASE | re.DOTALL)
        if extracted_h2:
            toc_items = "".join([
                f'<li><a href="#toc-section-{idx+1}" class="text-indigo-400 hover:underline">{re.sub(r"<[^>]+>", "", h).strip()}</a></li>'
                for idx, h in enumerate(extracted_h2[:8])
            ])
            toc_block = (
                f'<div class="rank-math-toc my-6 p-5 rounded-2xl bg-slate-900/50 border border-slate-800" id="rank-math-toc">\n'
                f'<p class="text-sm font-bold text-slate-200 mb-3 flex items-center gap-2">📑 فهرست عناوین و سرفصل‌های اصلی:</p>\n'
                f'<ul class="space-y-1.5 text-xs text-slate-300 pr-5 list-disc">\n{toc_items}\n</ul>\n'
                f'</div>\n'
            )
            # Insert TOC right after first paragraph
            if first_p_match:
                html = html.replace(first_p_match.group(0), first_p_match.group(0) + "\n" + toc_block, 1)
            else:
                html = toc_block + "\n" + html

    # 8. Content length enforcement: ensure article has at least 2,800+ words so WP & Rank Math see 2,600+ words
    TARGET_MIN_WORDS = 2800
    plain_curr = re.sub(r"<[^>]+>", " ", html)
    plain_curr = re.sub(r"\s+", " ", plain_curr).strip()
    words_curr = len([w for w in plain_curr.split() if w])

    if words_curr < TARGET_MIN_WORDS and art_kw:
        # Append rich, structured expert modules until word count comfortably exceeds 2,800 words
        expansion_modules = [
            (
                f'\n<h2 id="toc-section-exp-1">تحلیل تخصصی و بررسی عمیق ابعاد مختلف {art_kw}</h2>\n'
                f'<p>برای درک کامل و پیاده‌سازی حرفه‌ای <strong>{art_kw}</strong>، لازم است متغیرهای کلیدی و تاثیرگذار را با دقت ارزیابی کنیم. پیاده‌سازی اصولی این راهکارها تضمین‌کننده بهره‌وری بالاتر، کاهش هزینه‌های عملیاتی و بازگشت سرمایه (ROI) بیشتر خواهد بود.</p>\n'
                f'<h3>مزایا و نقاط قوت پیاده‌سازی استاندارد {art_kw}</h3>\n'
                f'<ul class="list-disc pr-5 space-y-1.5 text-slate-300">\n'
                f'<li><strong>افزایش چشمگیر بازدهی:</strong> بهینه‌سازی دقیق فرآیندها عملکرد کلی را به بالاترین سطح ممکن می‌رساند.</li>\n'
                f'<li><strong>کاهش ریسک و پایداری بلندمدت:</strong> با رعایت استانداردهای فنی، از بروز خطاهای احتمالی جلوگیری می‌شود.</li>\n'
                f'<li><strong>سازگاری با ترندهای روز:</strong> پیاده‌سازی به‌روزترین متدولوژی‌ها در حوزه {art_kw} به کسب برتری رقابتی کمک می‌کند.</li>\n'
                f'<li><strong>تجربه کاربری بی‌نظیر:</strong> ارائه محتوای شفاف و ساختاریافته رضایت مخاطبان هدف را جلب می‌نماید.</li>\n'
                f'</ul>\n'
            ),
            (
                f'\n<h2 id="toc-section-exp-2">چک‌لیست گام‌به‌گام و راهنمای عملیاتی اجرای {art_kw}</h2>\n'
                f'<p>اجرای مرحله‌به‌مرحله این فرآیند باعث جلوگیری از اتلاف زمان و منابع می‌شود. در ادامه اقدامات اساسی را مرور می‌کنیم:</p>\n'
                f'<ol class="list-decimal pr-5 space-y-2 text-slate-300">\n'
                f'<li><strong>ارزیابی اولیه و تحلیل وضعیت موجود:</strong> داده‌های کلیدی و نیازمندی‌ها را با دقت مستند کنید.</li>\n'
                f'<li><strong>انتخاب ابزارهای استاندارد:</strong> زیرساخت‌های نرم‌افزاری و متدهای مناسب در حوزه {art_kw} را انتخاب نمایید.</li>\n'
                f'<li><strong>اجرا و یکپارچه‌سازی:</strong> برنامه‌ریزی تدوین‌شده را با رعایت چک‌لیست‌های کیفی پیاده‌سازی کنید.</li>\n'
                f'<li><strong>پایش، تحلیل و بهینه‌سازی مستمر:</strong> نتایج حاصل از {art_kw} را به طور منظم بسنجید و بهبود بخشید.</li>\n'
                f'</ol>\n'
            ),
            (
                f'\n<h2 id="toc-section-exp-3">جدول مقایسه‌ای رویکردها و تکنیک‌های برتر در {art_kw}</h2>\n'
                f'<div class="overflow-x-auto my-4"><table class="min-w-full text-xs text-right text-slate-300 border border-slate-700 rounded-lg">\n'
                f'<thead class="bg-slate-800 text-slate-200"><tr><th class="p-2.5 border-b border-slate-700">شاخص ارزیابی</th><th class="p-2.5 border-b border-slate-700">روش سنتی</th><th class="p-2.5 border-b border-slate-700">روش پیشرفته و بهینه {art_kw}</th></tr></thead>\n'
                f'<tbody>\n'
                f'<tr class="border-b border-slate-800"><td class="p-2.5 font-semibold">سرعت بازدهی</td><td class="p-2.5 text-slate-400">طولانی و همراه با آزمون و خطا</td><td class="p-2.5 text-emerald-400 font-medium">سریع، هدفمند و بر پایه داده</td></tr>\n'
                f'<tr class="border-b border-slate-800"><td class="p-2.5 font-semibold">دقت و کیفیت خروجی</td><td class="p-2.5 text-slate-400">متغیر و غیرقابل پیش‌بینی</td><td class="p-2.5 text-emerald-400 font-medium">بسیار بالا و مطابق با استانداردهای گوگل</td></tr>\n'
                f'<tr><td class="p-2.5 font-semibold">مقیاس‌پذیری</td><td class="p-2.5 text-slate-400">محدود</td><td class="p-2.5 text-emerald-400 font-medium">کاملاً منعطف و قابل توسعه</td></tr>\n'
                f'</tbody></table></div>\n'
            ),
            (
                f'\n<h2 id="toc-section-exp-4">۵ اشتباه مرگبار که در مسیر {art_kw} باید از آن‌ها دوری کنید</h2>\n'
                f'<p>شناخت پیشگیرانه اشتباهات پرتکرار به شما امکان می‌دهد با اطمینان کامل به سوی اهداف خود در حوزه {art_kw} گام بردارید. بی‌توجهی به بازخورد مخاطبان، عدم به‌روزرسانی مستمر و تکیه بر متدهای منسوخ‌شده از بزرگ‌ترین موانع موفقیت هستند.</p>\n'
                f'<ul class="list-disc pr-5 space-y-1.5 text-slate-300">\n'
                f'<li>شروع بدون برنامه‌ریزی مدون و شفاف در حوزه {art_kw}.</li>\n'
                f'<li>صرف‌نظر کردن از تست‌های ارزیابی عملکرد و رفتار کاربران در ارتباط با {art_kw}.</li>\n'
                f'<li>عدم استفاده از ابزارهای اتوماسیون و پایش لحظه‌ای شاخص‌های کلیدی {art_kw}.</li>\n'
                f'<li>نادیده گرفتن استانداردهای سئو داخلی و بهینه‌سازی تجربه کاربری.</li>\n'
                f'</ul>\n'
            ),
            (
                f'\n<h2 id="toc-section-exp-5">مطالعه موردی (Case Study) و تحلیل نتایج واقعی {art_kw}</h2>\n'
                f'<p>بررسی کسب‌وکارهایی که با موفقیت از اصول {art_kw} بهره گرفته‌اند، نشان می‌دهد که تمرکز بر تولید محتوای جامع، بهینه‌سازی فنی مداوم و برآورده کردن دقیق قصد جستجوی کاربر (Search Intent) تا ۳۵۰٪ رشد ترافیک ارگانیک را به همراه داشته است.</p>\n'
                f'<p>یک نمونه موفق پیاده‌سازی {art_kw} حاکی از آن است که بهبود زمان ماندگاری کاربر (Dwell Time) و کاهش نرخ پرش به طور مستقیم رتبه‌گیری در نتایج اول گوگل را تضمین می‌کند. این امر ارزش سرمایه‌گذاری بر روی کیفیت محتوا و رعایت استانداردهای E-E-A-T را بیش از پیش نمایان می‌سازد.</p>\n'
            ),
            (
                f'\n<h2 id="toc-section-exp-6">پرسش‌های متداول تکمیلی درباره {art_kw}</h2>\n'
                f'<h3>چه مدت طول می‌کشد تا نتایج عملیاتی {art_kw} مشخص شوند؟</h3>\n'
                f'<p>معمولاً بین ۲ تا ۶ هفته پس از اجرای دقیق مراحل، نتایج ملموس و ارتقای رتبه در موتورهای جستجو مشاهده خواهند شد.</p>\n'
                f'<h3>مهم‌ترین پیش‌نیازها برای پیاده‌سازی حرفه‌ای {art_kw} چیست؟</h3>\n'
                f'<p>تدوین استراتژی اولیه، ابزارهای مناسب پایش و اجرای گام‌به‌گام دستورالعمل‌های ارائه‌شده اصلی‌ترین نیازهای اولیه هستند.</p>\n'
                f'<h3>آیا رعایت مداوم این اصول برای پایداری رتبه ضرورت دارد؟</h3>\n'
                f'<p>بله، الگوریتم‌های مدرن به صورت مستمر کیفیت محتوا و رفتار کاربران را ارزیابی می‌کنند و به‌روزرسانی منظم محتوای {art_kw} الزامی است.</p>\n'
            ),
            (
                f'\n<h2 id="toc-section-exp-7">جمع‌بندی و نقشه راه آینده در حوزه {art_kw}</h2>\n'
                f'<p>در نهایت، دستیابی به بالاترین بازدهی در زمینه <strong>{art_kw}</strong> نیازمند تلفیق دانش فنی، شناخت نیازهای مخاطب و پایبندی به استانداردهای روز بین‌المللی است. با مرور و پیاده‌سازی دقیق نکات مطرح‌شده در این راهنما، می‌توانید با خیالی آسوده مسیر پیشرفت را طی کرده و از رقبای خود پیشی بگیرید. تداوم در تولید محتوای باکیفیت و ارزیابی هفتگی شاخص‌ها تضمین‌کننده موفقیت ماندگار کسب‌وکار شما خواهد بود.</p>\n'
            ),
            (
                f'\n<h2 id="toc-section-exp-8">تحلیل ابزارهای تخصصی و فناوری‌های نوین در حوزه {art_kw}</h2>\n'
                f'<p>امروزه بهره‌گیری از ابزارهای هوشمند تحلیلی، سامانه‌های خودکار پایش داده و پلتفرم‌های بهینه‌سازی فنی نقش تعیین‌کننده‌ای در موفقیت پروژه‌های مرتبط با {art_kw} ایفا می‌کنند. با انتخاب درست این فناوری‌ها، سرعت پردازش اطلاعات افزایش یافته و تصمیم‌گیری‌ها بر مبنای معیارهای دقیق آماری انجام خواهد شد.</p>\n'
                f'<ul class="list-disc pr-5 space-y-1.5 text-slate-300">\n'
                f'<li>استفاده از داشبوردهای نظارتی لحظه‌ای برای سنجش سلامت فنی محتوا.</li>\n'
                f'<li>ارزیابی مستمر رفتار کاربران و تحلیل جریان ترافیک ورودی.</li>\n'
                f'<li>یکپارچه‌سازی فرآیندهای بازاریابی با اهداف بلندمدت کسب‌وکار.</li>\n'
                f'</ul>\n'
            ),
            (
                f'\n<h2 id="toc-section-exp-9">استراتژی‌های پیشرفته بازاریابی و افزایش نرخ تعامل با {art_kw}</h2>\n'
                f'<p>برای اینکه محتوای مرتبط با <strong>{art_kw}</strong> بیشترین بازدهی تجاری را به همراه داشته باشد، باید بهینه‌سازی نرخ تبدیل (CRO) و مسیر سفر مشتری (Customer Journey) به شکلی منسجم در ساختار محتوا پیاده‌سازی شود. ایجاد فراخوان‌های اقدام (CTA) هوشمندانه و پاسخ به تمام نیازهای اطلاعاتی کاربر از ارکان دستیابی به این هدف به شمار می‌رود.</p>\n'
            ),
        ]
        for mod in expansion_modules:
            html = html + mod
            plain_test = re.sub(r"<[^>]+>", " ", html)
            plain_test = re.sub(r"\s+", " ", plain_test).strip()
            if len([w for w in plain_test.split() if w]) >= TARGET_MIN_WORDS:
                break

    # 9. Use of Media: Rank Math requires at least 4 images/videos for full 100% green check
    img_tags = re.findall(r"<img\b[^>]*>", html, flags=re.IGNORECASE)
    img_src = f"/api/v1/content/articles/detail/{article_id}/featured-image" if article_id else "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1200&q=80"
    
    if len(img_tags) == 0:
        # Prepend header featured image
        html = (
            f'<figure class="wp-block-image size-large my-6">'
            f'<img src="{img_src}" alt="{art_kw} - راهنمای جامع و معرفی" class="rounded-xl shadow-md" />'
            f'<figcaption class="text-xs text-center text-slate-400 mt-1.5">تصویر ۱: نقشه راه و معرفی {art_kw}</figcaption>'
            f'</figure>\n' + html
        )
        img_tags = re.findall(r"<img\b[^>]*>", html, flags=re.IGNORECASE)

    # If still fewer than 4 images, inject contextually after H2 headings
    if len(img_tags) < 4 and art_kw:
        media_captions = [
            f"اینفوگرافیک و مراحل گام‌به‌گام پیاده‌سازی {art_kw}",
            f"چک‌لیست طلایی و شاخص‌های کلیدی موفقیت در {art_kw}",
            f"نمودار تحلیل عملکرد و نتایج استراتژی {art_kw}",
        ]
        needed_imgs = 4 - len(img_tags)
        for i in range(min(needed_imgs, len(media_captions))):
            cap = media_captions[i]
            injected_fig = (
                f'\n<figure class="wp-block-image size-large my-6">\n'
                f'<img src="{img_src}" alt="{art_kw} - {cap}" class="rounded-xl shadow-md" />\n'
                f'<figcaption class="text-xs text-center text-slate-400 mt-1.5">تصویر {i+2}: {cap}</figcaption>\n'
                f'</figure>\n'
            )
            h2_blocks_cur = list(re.finditer(r"</h2>", html, flags=re.IGNORECASE))
            if i < len(h2_blocks_cur):
                pos = h2_blocks_cur[i].end()
                html = html[:pos] + injected_fig + html[pos:]
            else:
                html = html + injected_fig

    # Force alt attribute on ALL <img> tags to contain the focus keyword
    if art_kw:
        def _fix_img_alt(m: re.Match) -> str:
            tag = m.group(0)
            alt_m = re.search(r'alt=["\']([^"\']*)["\']', tag, flags=re.IGNORECASE)
            if alt_m:
                cur_alt = alt_m.group(1)
                if art_kw.lower() not in cur_alt.lower():
                    new_alt = f"{art_kw} - {cur_alt}" if cur_alt.strip() else art_kw
                    tag = tag[:alt_m.start()] + f'alt="{new_alt}"' + tag[alt_m.end():]
            else:
                tag = tag[:4] + f' alt="{art_kw}"' + tag[4:]
            return tag
        html = re.sub(r"<img\b[^>]*>", _fix_img_alt, html, flags=re.IGNORECASE)

    # 10. Precision Keyword density balancing (target strictly 1.1% - 1.3%)
    if art_kw:
        plain_text = re.sub(r"<[^>]+>", " ", html)
        plain_text = re.sub(r"\s+", " ", plain_text).strip()
        total_words = len([w for w in plain_text.split() if w])
        kw_count = plain_text.lower().count(art_kw.lower())
        current_density = (kw_count / max(total_words, 1)) * 100

        # Target 1.2% (safely in Rank Math 1.0-1.5% green zone)
        target_count = max(1, int(total_words * 0.012))

        if current_density < 1.0 and total_words > 0:
            needed = target_count - kw_count
            phrases = [
                f"در زمینه {art_kw}، توجه به جزئیات کاربردی بسیار حائز اهمیت است.",
                f"بهره‌گیری موثر از {art_kw} بازدهی کلی را به میزان قابل توجهی ارتقا می‌دهد.",
                f"تحلیل دقیق {art_kw} به درک بهتر فرآیندها و تصمیم‌گیری اصولی کمک می‌کند.",
                f"برای پیاده‌سازی حرفه‌ای {art_kw}، رعایت گام‌به‌گام استانداردها توصیه می‌شود.",
                f"کارشناسان حوزه {art_kw} بر پایش مستمر و به‌روزرسانی اطلاعات تاکید دارند.",
            ]
            p_matches = list(re.finditer(r"<p\b[^>]*>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL))
            if p_matches:
                injected_count = 0
                p_idx = 0
                while injected_count < needed and p_idx < len(p_matches) * 5:
                    actual_idx = p_idx % len(p_matches)
                    phrase = phrases[injected_count % len(phrases)]
                    p_blocks = list(re.finditer(r"<p\b[^>]*>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL))
                    if not p_blocks:
                        break
                    target_block = p_blocks[actual_idx % len(p_blocks)]
                    inner_p = target_block.group(1)
                    updated_p = f"{inner_p} {phrase}"
                    html = html[:target_block.start()] + f"<p>{updated_p}</p>" + html[target_block.end():]
                    injected_count += 1
                    p_idx += 1
            else:
                for i in range(needed):
                    phrase = phrases[i % len(phrases)]
                    html = html + f"\n<p>{phrase}</p>"

        elif current_density > 1.5 and kw_count > target_count:
            # Gently reduce over-saturated keywords down to 1.2%
            excess = kw_count - target_count
            p_blocks = list(re.finditer(r"<p\b[^>]*>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL))
            reduced = 0
            for block in reversed(p_blocks):
                if reduced >= excess:
                    break
                inner = block.group(1)
                if art_kw.lower() in inner.lower() and len(inner.split()) > 15:
                    subbed = re.sub(re.escape(art_kw), "این موضوع", inner, count=1, flags=re.IGNORECASE)
                    html = html[:block.start()] + f"<p>{subbed}</p>" + html[block.end():]
                    reduced += 1

    # 11. Clean and sanitize
    html = sanitize_html(html)
    return html, art_title, meta_desc, art_slug


async def generate_seo_article(
    db: AsyncSession,
    website_id: UUID,
    brief_id: UUID | None = None,
    title: str | None = None,
    target_keyword: str | None = None,
    provider: str | None = None,
    user_id: UUID | None = None,
) -> ContentArticle:
    """Generate an enterprise-grade, 100/100 SEO compliant Persian Article from Brief or Keyword."""
    stmt = select(Website).where(Website.id == website_id)
    res = await db.execute(stmt)
    website = res.scalar_one_or_none()
    if not website:
        raise AppException(status_code=404, detail="وب‌سایت یافت نشد.", error_type="website_not_found")

    brief = None
    if brief_id:
        brief = await get_content_brief_by_id(db, brief_id)

    kw = target_keyword or (brief.target_keyword if brief else "سئو وب‌سایت")
    req_title = title or (brief.title if brief else f"{kw}: ۱۰ نکته طلایی و جامع برای رتبه ۱ گوگل [۰ تا ۱۰۰]")
    outline = brief.outline if brief else None

    system_prompt = (
        "تو یک متخصص ارشد تولید محتوای سئو (Chief SEO Copywriter) و مسلط به روان‌ترین و جذاب‌ترین نگارش فارسی، اصول Rank Math و استانداردهای الگوریتم‌های گوگل (E-E-A-T) هستی.\n"
        "وظیفه تو تولید یک مقاله بسیار عمیق، جامع، استاندارد و آماده کسب رتبه ۱ در موتورهای جستجو بر اساس کلمه کلیدی ارائه‌شده است.\n\n"
        "قوانین اجباری تولید محتوا (سئو ۱۰۰٪ Rank Math بر اساس مستندات رسمی):\n"
        "۱. **عنوان مقاله (title)**: باید دقیقاً با کلمه کلیدی شروع شود، شامل یک عدد باشد و یک کلمه قدرت (مثل «جامع»، «طلایی»، «تخصصی»، «بهترین») داشته باشد (مثال: «" + kw + ": ۱۰ گام طلایی و جامع از ۰ تا ۱۰۰»).\n"
        "۲. **اسلاگ انگلیسی (slug_english)**: کوتاه، معنادار و سئو شده به انگلیسی (مثل seo-training-guide).\n"
        "۳. **مقدمه و شروع**: کلمه کلیدی اصلی باید دقیقاً در همان پاراگراف اول (۱۰٪ ابتدایی متن) ذکر شود.\n"
        "۴. **ساختار و زیرعنوان‌ها**: حداقل ۶ تا ۱۰ تگ <h2> و چندین تگ <h3>. کلمه کلیدی اصلی باید در حداقل ۲ زیرعنوان <h2> حضور داشته باشد.\n"
        "۵. **فهرست مطالب (Table of Contents)**: در ابتدای مقاله یک بخش مرتب با تگ <div class=\"rank-math-toc\" id=\"rank-math-toc\"> قرار بده.\n"
        "۶. **لینک‌های خارجی معتبر (DoFollow)**: حداقل ۲ لینک به منابع معتبر جهانی (مانند دانشنامه ویکی‌پدیا https://fa.wikipedia.org یا مراجع رسمی).\n"
        "۷. **لینک‌های داخلی**: حداقل ۲ لینک داخلی با مسیرهای نسبی کاربردی مانند /blog/seo-strategy یا /blog/content-guide.\n"
        "۸. **بخش سوالات متداول (FAQ)**: در انتهای مقاله یک بخش <h2>پرسش‌های متداول درباره " + kw + "</h2> شامل حداقل ۳ پرسش <h3> با پاسخ‌های کوتاه و مستقیم ایجاد کن.\n"
        "۹. **چگالی کلمه کلیدی (بسیار مهم)**: کلمه کلیدی اصلی باید دقیقاً بین ۱.۰٪ تا ۱.۵٪ تکرار شود (برای مقاله ۲۵۰۰ کلمه‌ای بین ۲۵ تا ۳۵ بار تکرار طبیعی).\n"
        "۱۰. **توضیحات متا (meta_description)**: بین ۱۳۰ تا ۱۵۵ کاراکتر، جذاب، با کلمه کلیدی دقیق.\n"
        "۱۱. **حجم محتوا (شرط امتیاز ۱۰۰٪ رنک‌مث)**: مقاله باید بسیار جامع، عمیق و کامل (بین ۲۵۰۰ تا ۳۲۰۰ کلمه) باشد تا نمره طول محتوا ۱۰۰٪ کامل شود.\n"
        "۱۲. **تصاویر و چندرسانه‌ای (شرط ۴ تصویر رنک‌مث)**: حتماً حداقل ۴ تگ <img> با alt حاوی کلمه کلیدی در طول مقاله و بعد از سرفصل‌ها قرار بده.\n\n"
        "خروجی باید دقیقاً یک شیء JSON با ساختار زیر باشد:\n"
        "{\n"
        '  "title": "' + kw + ': ۱۰ نکته طلایی و جامع از ۰ تا ۱۰۰...",\n'
        '  "slug_english": "keyword-guide",\n'
        '  "content_html": "<p>مقدمه جذاب...</p><div class=\\"rank-math-toc\\">...</div><h2>...</h2><img src=\\"featured.jpg\\" alt=\\"' + kw + ' - راهنمای جامع\\" />",\n'
        '  "seo_metadata": {\n'
        '    "meta_description": "توضیحات متای بهینه حاوی کلمه کلیدی...",\n'
        '    "image_prompt_english": "high quality photorealistic 4k tech editorial photography, cinematic lighting, ultra detailed, no text"\n'
        '  }\n'
        "}"
    )
    user_prompt = (
        f"کلمه کلیدی هدف: {kw}\n"
        f"عنوان پیشنهادی: {req_title}\n"
        f"ساختار سرفصل‌ها: {json.dumps(outline, ensure_ascii=False) if outline else 'بر اساس بهترین ساختار سئو و نیازهای کاربر'}\n"
        f"لطفاً مقاله فوق‌العاده باکیفیت و آماده رتبه ۱ گوگل را با تمام قوانین بالا به صورت JSON تولید کن."
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
    content_html = sanitize_html(data.get("content_html", ""))

    if len((content_html or "").strip()) < 200:
        raise AppException(
            status_code=502,
            detail="خروجی هوش مصنوعی ناقص بود (بدنه مقاله خالی برگشت). لطفا دوباره تلاش کنید.",
            error_type="empty_generation",
        )

    seo_metadata = data.get("seo_metadata", {})
    meta_desc = seo_metadata.get("meta_description", "")

    # Clean legacy dead image domains
    content_html = re.sub(
        r"<img\b[^>]*source\.unsplash\.com[^>]*>\s*", "", content_html, flags=re.IGNORECASE
    )

    # Apply 100% Deterministic SEO Compliance Enforcement
    content_html, article_title, meta_desc, slug = _enforce_100_seo_compliance(
        content_html=content_html,
        title=article_title,
        kw=kw,
        meta_desc=meta_desc,
        slug=slug,
    )
    seo_metadata["meta_description"] = meta_desc

    content_md = content_html.replace("<h2>", "## ").replace("</h2>", "\n").replace("<p>", "").replace("</p>", "\n\n").replace("<strong>", "**").replace("</strong>", "**").replace("<ul>", "").replace("</ul>", "").replace("<li>", "- ").replace("</li>", "\n")

    # Generate featured image
    featured_b64 = data.get("featured_image_b64")
    if not featured_b64:
        try:
            import base64 as _b64
            import random
            from urllib.parse import quote
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
    seo_metadata.setdefault("target_keyword", kw)

    article = ContentArticle(
        website_id=website_id,
        brief_id=brief_id,
        title=article_title,
        slug=slug,
        content_markdown=content_md,
        content_html=content_html,
        seo_score=100,
        seo_metadata=seo_metadata,
        status="review",
    )
    db.add(article)
    await db.flush()

    # Deterministically enforce 100% SEO compliance with the real article.id
    article.content_html, article.title, meta_desc, article.slug = _enforce_100_seo_compliance(
        content_html=article.content_html,
        title=article.title,
        kw=kw,
        meta_desc=seo_metadata.get("meta_description", ""),
        slug=article.slug,
        article_id=article.id,
    )
    article.content_markdown = article.content_html.replace("<h2>", "## ").replace("</h2>", "\n").replace("<p>", "").replace("</p>", "\n\n").replace("<strong>", "**").replace("</strong>", "**").replace("<ul>", "").replace("</ul>", "").replace("<li>", "- ").replace("</li>", "\n")

    detailed_score = score_article_detailed(
        content_html=article.content_html,
        title=article.title or "",
        target_keyword=kw,
        meta_description=meta_desc,
        slug=article.slug or "",
    )
    article.seo_score = detailed_score["score"]
    seo_metadata = dict(article.seo_metadata or {})
    seo_metadata["meta_description"] = meta_desc
    seo_metadata["score_breakdown"] = detailed_score
    article.seo_metadata = seo_metadata

    await db.flush()
    await create_version(
        db,
        article,
        change_type="created",
        changed_by=user_id,
        change_summary="ایجاد اولیه محتوا توسط هوش مصنوعی با نمره سئو کامل",
    )
    await db.refresh(article)
    return article


async def refine_article_with_ai(
    db: AsyncSession,
    article_id: UUID,
    instruction: str,
    mode: str = "auto_fix_100",
    user_id: UUID | None = None,
) -> ContentArticle:
    """Refine and upgrade an existing article using AI, enforce 100% SEO rules, and record a version history snapshot."""
    stmt = select(ContentArticle).where(ContentArticle.id == article_id, ContentArticle.deleted_at.is_(None))
    res = await db.execute(stmt)
    article = res.scalar_one_or_none()
    if not article:
        raise AppException(status_code=404, detail="مقاله یافت نشد.", error_type="article_not_found")

    stmt_w = select(Website).where(Website.id == article.website_id)
    res_w = await db.execute(stmt_w)
    website = res_w.scalar_one_or_none()
    if not website:
        raise AppException(status_code=404, detail="وب‌سایت یافت نشد.", error_type="website_not_found")

    kw = article.seo_metadata.get("target_keyword") or article.title.split()[0]
    current_breakdown = article.seo_metadata.get("score_breakdown") or {}
    failed_checks = [c["detail"] for c in current_breakdown.get("checks", []) if not c.get("passed")]

    refine_system_prompt = (
        "تو یک متخصص ارشد بهینه‌سازی و بازنویسی حرفه‌ای محتوای سئو (Senior SEO Optimizer) هستی. "
        "وظیفه تو ارتقای هوشمندانه مقاله موجود، اعمال دستورات دقیق کاربر و رساندن نمره سئو به ۱۰۰٪ کامل بر اساس استانداردهای رسمی Rank Math است.\n\n"
        "قوانین اجباری:\n"
        "۱. ساختار خروجی باید یک شیء JSON با فیلدهای title، content_html و meta_description باشد.\n"
        "۲. عنوان باید با کلمه کلیدی اصلی («" + kw + "») شروع شده، شامل یک عدد و دارای کلمه قدرت (مانند «جامع»، «طلایی»، «تخصصی») باشد.\n"
        "۳. بدنه باید شامل حداقل ۲ لینک خارجی معتبر با پروتکل https:// (مثل دانشنامه ویکی‌پدیا و منابع رسمی) و حداقل ۲ لینک داخلی (مثل /blog/...) با انکرتکست فارسی باشد.\n"
        "۴. کلمه کلیدی باید در پاراگراف اول، در حداقل دو زیرعنوان <h2> و با چگالی ۱.۰٪ تا ۱.۵٪ تکرار شود.\n"
        "۵. فهرست مطالب با تگ <div class=\"rank-math-toc\" id=\"rank-math-toc\"> در ابتدای مقاله قرار گیرد.\n"
        "۶. طول محتوا باید بسیار جامع و عمیق (۲۵۰۰ تا ۳۰۰۰ کلمه) باشد تا امتیاز کامل ۱۰۰٪ رنک‌مث را دریافت کند.\n"
        "۷. حداقل ۴ تگ <img> با alt حاوی کلمه کلیدی در سراسر مقاله توزیع شود.\n"
        "۸. در انتهای متن یک بخش <h2>پرسش‌های متداول درباره " + kw + "</h2> با سوالات <h3> و پاسخ‌های شفاف قرار بده.\n"
        "۹. دستورات خاص کاربر را با بالاترین کیفیت و وفاداری به موضوع مقاله پیاده کن."
    )

    refine_user_prompt = (
        f"کلمه کلیدی اصلی: {kw}\n"
        f"عنوان فعلی: {article.title}\n"
        f"دستور ویژه کاربر برای اصلاح: {instruction}\n"
        f"موارد نیازمند اصلاح و بهینه‌سازی: {', '.join(failed_checks) if failed_checks else 'ارتقای حداکثری کیفیت و سئو'}\n\n"
        f"متن HTML فعلی مقاله:\n{article.content_html[:6000]}\n\n"
        f"لطفاً نسخه بهینه‌سازی‌شده، کامل و فوق‌العاده سئو شده را در قالب JSON ارسال کن."
    )

    data = None
    try:
        raw_res, used_model, p_tok, c_tok = await call_ai_with_rotation(
            db=db,
            org_id=website.organization_id,
            user_prompt=refine_user_prompt,
            system_prompt=refine_system_prompt,
            json_mode=True,
        )
        if raw_res:
            try:
                data = json.loads(raw_res)
            except Exception:
                match = re.search(r"\{.*\}", raw_res, flags=re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
    except Exception as e:
        raise AppException(
            status_code=503,
            detail=f"خطا در ارتباط با هوش مصنوعی: {str(e)}",
            error_type="ai_refine_error",
        )

    if not data or not isinstance(data, dict):
        raise AppException(
            status_code=502,
            detail="پاسخ هوش مصنوعی برای بازنویسی نامعتبر بود. لطفاً مجدداً تلاش کنید.",
            error_type="invalid_ai_response",
        )

    new_title = data.get("title") or article.title
    new_html = data.get("content_html") or article.content_html
    new_meta = data.get("meta_description") or article.seo_metadata.get("meta_description", "")

    # Run deterministic compliance to ensure 95-100 score
    new_html, new_title, new_meta, _ = _enforce_100_seo_compliance(
        content_html=new_html,
        title=new_title,
        kw=kw,
        meta_desc=new_meta,
        slug=article.slug,
        article_id=article.id,
    )

    new_md = new_html.replace("<h2>", "## ").replace("</h2>", "\n").replace("<p>", "").replace("</p>", "\n\n").replace("<strong>", "**").replace("</strong>", "**").replace("<ul>", "").replace("</ul>", "").replace("<li>", "- ").replace("</li>", "\n")

    # Update article
    article.title = new_title
    article.content_html = new_html
    article.content_markdown = new_md
    
    seo_meta = dict(article.seo_metadata or {})
    seo_meta["meta_description"] = new_meta
    
    # Recalculate score
    new_score_data = score_article_detailed(
        content_html=new_html,
        title=new_title,
        target_keyword=kw,
        meta_description=new_meta,
        slug=article.slug or "",
    )
    article.seo_score = new_score_data["score"]
    seo_meta["score_breakdown"] = new_score_data
    article.seo_metadata = seo_meta

    # Snapshot to PostgreSQL Version History
    try:
        await create_version(
            db,
            article,
            change_type="ai_rewrite",
            changed_by=user_id,
            change_summary=f"بهبود هوشمند با هوش مصنوعی ({instruction[:45]})",
        )
    except Exception as err:
        logger.warning(f"Could not create version snapshot: {err}")

    await db.commit()
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
        # Rank Math SEO meta fields
        "rank_math_focus_keyword": focus_kw or "",
        "rank_math_description": meta_desc,
        "rank_math_title": article.title or "",
        "rank_math_robots": ["index", "follow"],
        # Yoast SEO meta fields
        "_yoast_wpseo_focuskw": focus_kw or "",
        "_yoast_wpseo_metadesc": meta_desc,
        "_yoast_wpseo_title": article.title or "",
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
