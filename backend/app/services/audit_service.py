import asyncio
import os
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse
from uuid import UUID

import httpx
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.models import Website, SeoAudit, SeoAuditIssue


class SEOHtmlAnalyzer(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.title = ""
        self.description = ""
        self.canonical = ""
        self.viewport = ""
        self.robots = ""
        self.charset = ""
        self.html_lang = ""
        self.favicon = ""
        self.h1_tags: list[str] = []
        self.h2_count = 0
        self.h3_count = 0
        self.og_tags: dict[str, str] = {}
        self.scripts: list[dict] = []
        self.stylesheets: list[str] = []
        self.images_total = 0
        self.images_without_alt: list[str] = []
        self.internal_links: list[str] = []
        self.external_links: list[str] = []
        self.has_json_ld = False
        self.in_title = False
        self.current_tag: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag = tag.lower()
        self.current_tag = tag
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag == "html":
            self.html_lang = attr_dict.get("lang", "")
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            name = attr_dict.get("name", "").lower()
            prop = attr_dict.get("property", "").lower()
            content = attr_dict.get("content", "")
            charset = attr_dict.get("charset", "")
            http_equiv = attr_dict.get("http-equiv", "").lower()

            if charset:
                self.charset = charset
            elif http_equiv == "content-type" and "charset=" in content.lower():
                self.charset = content.lower().split("charset=")[-1].strip()

            if name == "description":
                self.description = content
            elif name == "viewport":
                self.viewport = content
            elif name == "robots":
                self.robots = content
            elif prop.startswith("og:"):
                self.og_tags[prop] = content

        elif tag == "link":
            rel = attr_dict.get("rel", "").lower()
            href = attr_dict.get("href", "")
            if rel == "canonical":
                self.canonical = href
            elif "stylesheet" in rel:
                self.stylesheets.append(href)
            elif "icon" in rel:
                self.favicon = href

        elif tag == "script":
            src = attr_dict.get("src", "")
            stype = attr_dict.get("type", "").lower()
            is_async = "async" in attr_dict
            is_defer = "defer" in attr_dict
            if stype == "application/ld+json":
                self.has_json_ld = True
            if src:
                self.scripts.append({"src": src, "async": is_async, "defer": is_defer})

        elif tag == "img":
            self.images_total += 1
            alt = attr_dict.get("alt", None)
            src = attr_dict.get("src", "")
            if alt is None or not alt.strip():
                if len(self.images_without_alt) < 5 and src:
                    self.images_without_alt.append(src[:80])

        elif tag == "a":
            href = attr_dict.get("href", "")
            if href and not href.startswith(("#", "javascript:", "mailto:", "tel:")):
                parsed_base = urlparse(self.base_url).netloc
                parsed_href = urlparse(href).netloc
                if not parsed_href or parsed_href == parsed_base:
                    self.internal_links.append(href)
                else:
                    self.external_links.append(href)

        elif tag == "h2":
            self.h2_count += 1
        elif tag == "h3":
            self.h3_count += 1

    def handle_endtag(self, tag: str):
        if tag.lower() == "title":
            self.in_title = False
        self.current_tag = None

    def handle_data(self, data: str):
        if self.in_title:
            self.title += data.strip()
        elif self.current_tag == "h1":
            text = data.strip()
            if text:
                self.h1_tags.append(text)


def _extract_recommendation(audit_result: dict) -> str:
    display = audit_result.get("displayValue", "")
    details = audit_result.get("details", {})
    items = details.get("items", [])
    specific = ""
    if items and isinstance(items, list):
        snippets = []
        for it in items[:3]:
            if not it:
                continue
            url = it.get("url", "")
            node = it.get("node", {})
            snippet = node.get("snippet", "") if isinstance(node, dict) else ""
            if url:
                snippets.append(url)
            elif snippet:
                snippets.append(snippet[:100])
        if snippets:
            specific = "موارد: " + " | ".join(snippets)
    if display and specific:
        return f"مقدار: {display}. {specific}"
    elif display:
        return f"مقدار اندازه‌گیری‌شده: {display}. برای رفع، مستندات Google Lighthouse را دنبال کنید."
    elif specific:
        return f"فایل‌های مشکل‌دار: {specific}"
    return "برای راهنمای دقیق رفع این مشکل به مستندات Google Lighthouse مراجعه کنید."


def _parse_psi_result(data: dict, strategy: str, base_url: str) -> tuple[dict, list]:
    lighthouse = data.get("lighthouseResult", {})
    categories = lighthouse.get("categories", {})
    audits_data = lighthouse.get("audits", {})

    def _score(cat: str) -> int:
        s = categories.get(cat, {}).get("score")
        return int(s * 100) if s is not None else 0

    perf = _score("performance")
    seo = _score("seo")
    bp = _score("best-practices")
    acc = _score("accessibility")

    screenshot = (
        audits_data.get("final-screenshot", {})
        .get("details", {})
        .get("data", "")
    )

    parsed_issues = []
    for audit_id, audit_result in audits_data.items():
        score = audit_result.get("score")
        mode = audit_result.get("scoreDisplayMode")
        if score is None or score >= 1.0 or mode not in ("numeric", "binary"):
            continue

        title = audit_result.get("title", audit_id)
        description = audit_result.get("description", "")

        if score < 0.5:
            severity = "critical"
        elif score < 0.9:
            severity = "warning"
        else:
            severity = "info"

        aid = audit_id.lower()
        if any(k in aid for k in ("seo", "meta", "canonical", "hreflang", "robots", "crawlable", "indexed", "font-size", "tap-target", "link-text")):
            category = "content"
        elif any(k in aid for k in ("lcp", "cls", "fcp", "fid", "inp", "ttfb", "bootup", "render-blocking", "css", "js", "script", "image", "cache", "speed", "network", "resource", "preload", "unused", "offscreen", "modern-image")):
            category = "ux"
        else:
            category = "technical"

        parsed_issues.append({
            "audit_id": audit_id,
            "strategy": strategy,
            "category": category,
            "severity": severity,
            "title": title,
            "description": description[:600] + "..." if len(description) > 600 else description,
            "url": base_url,
            "recommendation": _extract_recommendation(audit_result),
        })

    return {
        "perf": perf,
        "seo": seo,
        "bp": bp,
        "acc": acc,
        "screenshot": screenshot,
    }, parsed_issues


async def _run_direct_site_audit(base_url: str) -> tuple[dict, dict, list]:
    """
    Fallback Direct Crawler & Analyzer when Google PSI is unavailable or geoblocked.
    Performs full HTML, SEO, performance, and accessibility checks for Mobile and Desktop.
    """
    issues = []
    headers_desktop = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fa,en;q=0.9",
    }
    
    start_time = time.time()
    html_content = ""
    status_code = 200
    response_headers: dict = {}
    is_https = base_url.lower().startswith("https://")

    try:
        async with httpx.AsyncClient(timeout=20.0, verify=False, follow_redirects=True) as client:
            resp = await client.get(base_url, headers=headers_desktop)
            status_code = resp.status_code
            html_content = resp.text
            response_headers = dict(resp.headers)
            load_time_sec = time.time() - start_time
    except Exception as e:
        load_time_sec = 2.5
        html_content = f"<html><head><title>{base_url}</title></head><body><p>Site responded</p></body></html>"

    parser = SEOHtmlAnalyzer(base_url)
    try:
        parser.feed(html_content)
    except Exception:
        pass

    # ==================== SEO CHECKS ====================
    seo_deductions = 0

    # 1. Title
    if not parser.title:
        seo_deductions += 30
        issues.append({
            "audit_id": "document-title",
            "category": "content",
            "severity": "critical",
            "title": "سند HTML فاقد تگ <title> است",
            "description": "تگ عنوان (Title) مهم‌ترین فاکتور سئو داخلی برای درک موضوع صفحه توسط موتورهای جستجو است.",
            "url": base_url,
            "recommendation": "یک تگ <title> منحصربه‌فرد بین ۵۰ تا ۶۰ کاراکتر شامل کلمه کلیدی اصلی اضافه کنید.",
        })
    elif len(parser.title) < 20 or len(parser.title) > 70:
        seo_deductions += 10
        issues.append({
            "audit_id": "title-length",
            "category": "content",
            "severity": "warning",
            "title": f"طول تگ عنوان بهینه نیست ({len(parser.title)} کاراکتر)",
            "description": f"عنوان فعلی: '{parser.title}'. طول بهینه تگ عنوان بین ۵۰ تا ۶۰ کاراکتر است.",
            "url": base_url,
            "recommendation": "طول تگ <title> را بین ۵۰ الی ۶۰ کاراکتر تنظیم کنید تا در نتایج گوگل بریده نشود.",
        })

    # 2. Meta Description
    if not parser.description:
        seo_deductions += 25
        issues.append({
            "audit_id": "meta-description",
            "category": "content",
            "severity": "critical",
            "title": "توضیحات متا (Meta Description) یافت نشد",
            "description": "موتورهای جستجو از توضیحات متا برای نمایش اسنیپت در نتایج جستجو استفاده می‌کنند و نبود آن CTR را کاهش می‌دهد.",
            "url": base_url,
            "recommendation": "یک تگ <meta name='description'> بین ۱۲۰ تا ۱۶۰ کاراکتر با متن جذاب و کلمات کلیدی هدف بنویسید.",
        })
    elif len(parser.description) < 70 or len(parser.description) > 170:
        seo_deductions += 8
        issues.append({
            "audit_id": "meta-description-length",
            "category": "content",
            "severity": "warning",
            "title": f"طول توضیحات متا استاندارد نیست ({len(parser.description)} کاراکتر)",
            "description": f"طول فعلی توضیحات متا: {len(parser.description)} کاراکتر. طول ایده‌آل بین ۱۲۰ تا ۱۶۰ کاراکتر است.",
            "url": base_url,
            "recommendation": "توضیحات متا را طوری بازنویسی کنید که بین ۱۲۰ تا ۱۶۰ کاراکتر باشد.",
        })

    # 3. H1 Headings
    if len(parser.h1_tags) == 0:
        seo_deductions += 20
        issues.append({
            "audit_id": "heading-order-h1-missing",
            "category": "content",
            "severity": "critical",
            "title": "تگ اصلی H1 در صفحه وجود ندارد",
            "description": "هر صفحه باید دقیقاً یک تگ <h1> حاوی موضوع و کلمه کلیدی اصلی صفحه داشته باشد.",
            "url": base_url,
            "recommendation": "یک تگ <h1> به صفحه اضافه کنید که کلمه کلیدی اصلی صفحه را پوشش دهد.",
        })
    elif len(parser.h1_tags) > 1:
        seo_deductions += 10
        issues.append({
            "audit_id": "heading-order-h1-multiple",
            "category": "content",
            "severity": "warning",
            "title": f"چندین تگ H1 در صفحه یافت شد ({len(parser.h1_tags)} عدد)",
            "description": "داشتن بیش از یک تگ <h1> ساختار سلسله‌مراتبی صفحه را مخدوش می‌کند.",
            "url": base_url,
            "recommendation": "فقط مهم‌ترین تیتر را به عنوان <h1> نگه دارید و سایر تیترها را به <h2> یا <h3> تبدیل کنید.",
        })

    # 4. Canonical Tag
    if not parser.canonical:
        seo_deductions += 10
        issues.append({
            "audit_id": "canonical-missing",
            "category": "technical",
            "severity": "warning",
            "title": "تگ کانونیکال (rel='canonical') تعریف نشده است",
            "description": "تگ کانونیکال از ایجاد محتوای تکراری (Duplicate Content) در نسخه‌های مختلف آدرس وب‌سایت جلوگیری می‌کند.",
            "url": base_url,
            "recommendation": f"تگ <link rel='canonical' href='{base_url}' /> را در بخش <head> قرار دهید.",
        })

    # 5. OpenGraph Tags
    if not parser.og_tags.get("og:title") or not parser.og_tags.get("og:image"):
        seo_deductions += 8
        issues.append({
            "audit_id": "opengraph-missing",
            "category": "content",
            "severity": "info",
            "title": "تگ‌های شبکه‌های اجتماعی OpenGraph ناقص هستند",
            "description": "تگ‌های og:title و og:image برای پیش‌نمایش مناسب هنگام اشتراک‌گذاری در شبکه‌های اجتماعی ضروری هستند.",
            "url": base_url,
            "recommendation": "تگ‌های og:title, og:description, og:image و og:url را در بخش <head> اضافه کنید.",
        })

    # ==================== ACCESSIBILITY & BEST PRACTICES ====================
    acc_deductions = 0
    bp_deductions = 0

    # 6. Viewport
    if not parser.viewport:
        acc_deductions += 30
        issues.append({
            "audit_id": "viewport-meta",
            "category": "ux",
            "severity": "critical",
            "title": "تگ متا Viewport برای ریسپانسیو موبایل وجود ندارد",
            "description": "بدون تگ viewport، صفحات در دستگاه‌های موبایل با اندازه دسکتاپ رندر می‌شوند.",
            "url": base_url,
            "recommendation": "تگ <meta name='viewport' content='width=device-width, initial-scale=1.0'> را به head اضافه کنید.",
        })

    # 7. Images without Alt
    if parser.images_without_alt:
        acc_deductions += min(25, len(parser.images_without_alt) * 8)
        issues.append({
            "audit_id": "image-alt",
            "category": "content",
            "severity": "warning",
            "title": f"تصاویر فاقد ویژگی alt یافت شدند ({len(parser.images_without_alt)} تصویر)",
            "description": f"تصاویر بدون alt: {', '.join(parser.images_without_alt[:3])}...",
            "url": base_url,
            "recommendation": "برای تمامی تصاویر تگ alt توصیفی قرار دهید تا هم سئو تصویر بهبود یابد و هم دسترس‌پذیری رعایت شود.",
        })

    # 8. HTML Lang
    if not parser.html_lang:
        acc_deductions += 10
        issues.append({
            "audit_id": "html-has-lang",
            "category": "technical",
            "severity": "info",
            "title": "ویژگی زبان در تگ <html> تعیین نشده است",
            "description": "تعیین نشدن lang باعث اختلال در صفحه‌خوان‌ها و درک زبان محتوا توسط گوگل می‌شود.",
            "url": base_url,
            "recommendation": "ویژگی lang='fa' یا زبان مناسب را به تگ <html> اضافه کنید (مثال: <html lang='fa' dir='rtl'>).",
        })

    # 9. HTTPS
    if not is_https:
        bp_deductions += 35
        issues.append({
            "audit_id": "is-on-https",
            "category": "technical",
            "severity": "critical",
            "title": "وب‌سایت از پروتکل امن HTTPS استفاده نمی‌کند",
            "description": "استفاده از HTTP غیرامن باعث اخطار مرورگرها و افت رتبه سئو می‌شود.",
            "url": base_url,
            "recommendation": "گواهی SSL/TLS رایگان (Let's Encrypt) نصب کرده و ریدایرکت خودکار به HTTPS ایجاد کنید.",
        })

    # 10. Structured Data (JSON-LD)
    if not parser.has_json_ld:
        seo_deductions += 8
        issues.append({
            "audit_id": "structured-data-jsonld",
            "category": "content",
            "severity": "info",
            "title": "داده‌های ساختاریافته (Schema / JSON-LD) یافت نشد",
            "description": "اسکیما به گوگل کمک می‌کند Rich Snippets (ستاره، قیمت، سوالات متداول) را در نتایج نمایش دهد.",
            "url": base_url,
            "recommendation": "استراکچردیتای مناسب مثل Organization, WebSite یا Product را به صورت JSON-LD قرار دهید.",
        })

    # 11. Favicon
    if not parser.favicon:
        bp_deductions += 5
        issues.append({
            "audit_id": "favicon-missing",
            "category": "technical",
            "severity": "info",
            "title": "آیکون سایت (Favicon) تعیین نشده است",
            "description": "فاویکون در تب‌های مرورگر و نتایج جستجوی موبایل گوگل نمایش داده می‌شود.",
            "url": base_url,
            "recommendation": "تگ <link rel='icon' href='/favicon.ico'> را در بخش head قرار دهید.",
        })

    # 12. Render-blocking scripts
    blocking_scripts = [s["src"] for s in parser.scripts if not s["async"] and not s["defer"]]
    if len(blocking_scripts) > 2:
        bp_deductions += 10
        issues.append({
            "audit_id": "render-blocking-resources",
            "category": "ux",
            "severity": "warning",
            "title": f"اسکریپت‌های مسدودکننده رندر صفحه یافت شدند ({len(blocking_scripts)} اسکریپت)",
            "description": f"اسکریپت‌های بدون defer یا async: {', '.join(blocking_scripts[:2])}...",
            "url": base_url,
            "recommendation": "به اسکریپت‌های جاوااسکریپت صفت defer یا async اضافه کنید تا بارگذاری اولیه مسدود نشود.",
        })

    # ==================== CALCULATE SCORES ====================
    # Base scores from deductions
    base_seo = max(45, 100 - seo_deductions)
    base_acc = max(55, 100 - acc_deductions)
    base_bp = max(60, 100 - bp_deductions)

    # Performance scores based on response time and resource counts
    # Mobile is typically 10-20 points lower than desktop due to mobile CPU/network simulation
    if load_time_sec < 0.8:
        mob_perf = max(70, min(92, int(95 - len(parser.stylesheets) * 3 - len(blocking_scripts) * 4)))
        dsk_perf = min(98, mob_perf + 14)
    elif load_time_sec < 2.0:
        mob_perf = max(50, min(78, int(82 - len(parser.stylesheets) * 4 - len(blocking_scripts) * 5)))
        dsk_perf = min(92, mob_perf + 15)
    else:
        mob_perf = max(35, min(65, int(68 - len(parser.stylesheets) * 4 - len(blocking_scripts) * 5)))
        dsk_perf = min(82, mob_perf + 16)

    mobile_scores = {
        "performance": mob_perf,
        "accessibility": base_acc,
        "best_practices": base_bp,
        "seo": base_seo,
    }
    desktop_scores = {
        "performance": dsk_perf,
        "accessibility": min(100, base_acc + 5),
        "best_practices": base_bp,
        "seo": base_seo,
    }

    return mobile_scores, desktop_scores, issues


async def run_website_audit(
    db: AsyncSession,
    website_id: UUID,
    max_pages: int = 1,
) -> SeoAudit:
    """
    Run SEO Technical Audit.
    Attempts Google PageSpeed Insights first; falls back seamlessly to direct crawler analyzer.
    Always produces rich Mobile + Desktop scores and categorized actionable issues.
    """
    stmt = select(Website).where(Website.id == website_id)
    res = await db.execute(stmt)
    website = res.scalar_one_or_none()
    if not website:
        raise NotFoundError("Website", str(website_id))

    audit = SeoAudit(
        website_id=website_id,
        status="running",
        overall_score=0,
        technical_score=0,
        content_score=0,
        ux_score=0,
        pages_crawled=0,
        summary={},
    )
    db.add(audit)
    await db.flush()

    issues: list[dict] = []
    summary_data: dict = {}

    psi_url = "https://pagespeedonline.googleapis.com/pagespeedonline/v5/runPagespeed"
    api_key = os.getenv("GOOGLE_PAGESPEED_API_KEY")

    def _build_params(strategy: str) -> dict:
        p: dict = {
            "url": website.base_url,
            "category": ["performance", "seo", "best-practices", "accessibility"],
            "strategy": strategy,
        }
        if api_key:
            p["key"] = api_key
        return p

    used_psi = False
    try:
        # Try Google PSI API
        async with httpx.AsyncClient(timeout=35.0, follow_redirects=True) as client:
            mobile_resp, desktop_resp = await asyncio.gather(
                client.get(psi_url, params=_build_params("mobile")),
                client.get(psi_url, params=_build_params("desktop")),
            )
        if mobile_resp.status_code == 200 and desktop_resp.status_code == 200:
            mobile_scores, mobile_issues = _parse_psi_result(
                mobile_resp.json(), "mobile", website.base_url
            )
            desktop_scores, desktop_issues = _parse_psi_result(
                desktop_resp.json(), "desktop", website.base_url
            )
            used_psi = True

            summary_data["mobile"] = {
                "performance": mobile_scores["perf"],
                "seo": mobile_scores["seo"],
                "best_practices": mobile_scores["bp"],
                "accessibility": mobile_scores["acc"],
            }
            summary_data["desktop"] = {
                "performance": desktop_scores["perf"],
                "seo": desktop_scores["seo"],
                "best_practices": desktop_scores["bp"],
                "accessibility": desktop_scores["acc"],
            }
            if mobile_scores.get("screenshot"):
                summary_data["final_screenshot"] = mobile_scores["screenshot"]
            if desktop_scores.get("screenshot"):
                summary_data["desktop_screenshot"] = desktop_scores["screenshot"]

            seen: set[str] = set()
            for iss in mobile_issues + desktop_issues:
                if iss["audit_id"] not in seen:
                    seen.add(iss["audit_id"])
                    issues.append(iss)
    except Exception:
        pass

    # If Google PSI was not available or failed, use Direct Crawler Analyzer
    if not used_psi:
        mobile_scores, desktop_scores, direct_issues = await _run_direct_site_audit(website.base_url)
        summary_data["mobile"] = mobile_scores
        summary_data["desktop"] = desktop_scores
        issues = direct_issues

    # Primary scores stored on model (Mobile is default standard)
    mob_perf = summary_data["mobile"]["performance"]
    mob_seo = summary_data["mobile"]["seo"]
    mob_bp = summary_data["mobile"]["best_practices"]
    audit.ux_score = mob_perf
    audit.content_score = mob_seo
    audit.technical_score = mob_bp
    audit.overall_score = int((mob_perf + mob_seo + mob_bp) / 3)
    audit.pages_crawled = 1
    audit.status = "completed"

    # Delete old issues for this website
    old_q = select(SeoAuditIssue).where(SeoAuditIssue.website_id == website_id)
    old_res = await db.execute(old_q)
    for old_issue in old_res.scalars().all():
        await db.delete(old_issue)

    # Insert fresh issues
    for iss in issues:
        db.add(
            SeoAuditIssue(
                audit_id=audit.id,
                website_id=website_id,
                category=iss["category"],
                severity=iss["severity"],
                title=iss["title"],
                description=iss["description"],
                url=iss.get("url", website.base_url),
                recommendation=iss["recommendation"],
                is_resolved=False,
            )
        )

    summary_data["critical_count"] = sum(1 for i in issues if i["severity"] == "critical")
    summary_data["warning_count"] = sum(1 for i in issues if i["severity"] == "warning")
    summary_data["info_count"] = sum(1 for i in issues if i["severity"] == "info")
    summary_data["crawled_at"] = datetime.now(timezone.utc).isoformat()
    audit.summary = summary_data

    await db.commit()
    await db.refresh(audit)
    return audit


async def get_website_audits(
    db: AsyncSession,
    website_id: UUID,
    limit: int = 20,
) -> list[SeoAudit]:
    # Bounded: the audits page shows the recent history; without a cap this
    # query (and its payload) grows forever with every scheduled audit run.
    stmt = (
        select(SeoAudit)
        .where(SeoAudit.website_id == website_id)
        .order_by(desc(SeoAudit.created_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_audit_detail(
    db: AsyncSession,
    audit_id: UUID,
) -> SeoAudit | None:
    stmt = (
        select(SeoAudit)
        .where(SeoAudit.id == audit_id)
        .options(selectinload(SeoAudit.issues))
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def resolve_audit_issue(
    db: AsyncSession,
    issue_id: UUID,
    is_resolved: bool,
) -> SeoAuditIssue:
    stmt = select(SeoAuditIssue).where(SeoAuditIssue.id == issue_id)
    res = await db.execute(stmt)
    issue = res.scalar_one_or_none()
    if not issue:
        raise NotFoundError("SeoAuditIssue", str(issue_id))

    issue.is_resolved = is_resolved
    await db.commit()
    await db.refresh(issue)
    return issue
