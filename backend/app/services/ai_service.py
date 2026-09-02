import json
import re
import time
from datetime import datetime, timezone, timedelta
from uuid import UUID
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError, AppException
from app.models import (
    Website, AiSeoStrategy, AiAgentLog, Keyword, KeywordRanking, SeoAudit, SeoAuditIssue,
    ContentArticle, ContentBrief, ContentCalendarEntry, ContentCategory,
    GscQuery, GscPage, Opportunity, WordPressIntegration,
)
from app.services import agent_activity_service
from app.core.ai_router import call_ai_with_rotation

settings = get_settings()

# Map website_type codes to Persian labels for prompt context
_WEBSITE_TYPE_LABELS = {
    "blog": "وبلاگ / مجله تخصصی آنلاین",
    "ecommerce": "فروشگاه اینترنتی و فروش آنلاین محصولات",
    "corporate": "وب‌سایت شرکتی / خدمات سازمانی",
    "portfolio": "نمونه‌کار / معرفی خدمات و پورتفولیو",
    "news": "خبرگزاری / پایگاه خبری و اطلاع‌رسانی",
    "saas": "سرویس ابری و نرم‌افزار آنلاین (SaaS)",
    "landing": "لندینگ پیج اختصاصی / صفحه فرود تبلیغاتی",
    "forum": "تالار گفتگو / انجمن تخصصی کاربران",
    "directory": "دایرکتوری / بانک اطلاعاتی و فهرست مشاغل",
    "educational": "آکادمی آموزشی و دوره‌های تخصصی آنلاین",
}

_FOCUS_AREA_PROMPTS = {
    "quick_wins": "تمرکز ویژه روی دستاوردهای سریع (Quick Wins): بهینه‌سازی کلمات صفحه ۲ (رتبه‌های ۴ تا ۱۵) و کوئری‌های پرنمایش با کلیک کم برای رساندن سریع ترافیک.",
    "topical_authority": "تمرکز ویژه روی مرجعیت موضوعی (Topical Authority): ایجاد ساختار پیلار-کلاستر عمیق، پوشش ۱۰۰٪ تمام شاخه‌های دانشی و پاسخ به تمامی نیات سرچ کاربران.",
    "revenue_ecommerce": "تمرکز ویژه روی افزایش فروش و تبدیل (Transactional & Commercial): تمرکز روی صفحات محصول، صفحات فرود خرید، مقایسه‌ها و کلمات با نیت تراکنشی بالا.",
    "technical_recovery": "تمرکز ویژه روی رفع نقایص فنی و بازگشت رتبه: برطرف کردن بحرانی‌ترین خطاهای تکنیکال، هم‌نوع‌خواری کلمات و لینک‌سازی ساخت‌یافته.",
    "content_gap_expansion": "تمرکز ویژه روی کشف و پوشش شکاف‌های محتوایی عمیق بازار: کشف موضوعاتی که رقبا روی آن ترافیک می‌گیرند ولی سایت فعلاً پوشش نداده.",
}


async def generate_seo_strategy(
    db: AsyncSession,
    website_id: UUID,
    provider: str | None = None,
    focus_area: str | None = None,
) -> AiSeoStrategy:
    """
    Generate a cutting-edge, dynamic AI SEO Strategy for a website.
    Gathers multi-source intelligence:
    - Real GSC query/page metrics (impressions, clicks, CTR, position)
    - Active growth opportunities (striking distance, low CTR, cannibalization)
    - Existing published articles and planned briefs (zero duplication guarantee)
    - Content categories / silo taxonomy
    - Technical audit scores & critical issues
    - Business description & niche context
    """
    start_time = time.time()
    stmt = select(Website).where(Website.id == website_id, Website.deleted_at.is_(None))
    res = await db.execute(stmt)
    website = res.scalar_one_or_none()
    if not website:
        raise NotFoundError("Website", str(website_id))
    
    org_id = website.organization_id
    used_provider = provider or settings.DEFAULT_AI_PROVIDER or "openai"

    # ── 1. Website Profile ─────────────────────────────────────────────
    domain = website.domain
    site_name = website.name or domain
    site_description = (website.description or "").strip()
    site_type = _WEBSITE_TYPE_LABELS.get(website.website_type, website.website_type or "وبسایت")
    site_language = website.language or "fa"
    site_country = website.country or "IR"

    # SEO goals (JSONB)
    seo_goals = website.seo_goals or {}
    goals_parts = [f"{k}: {v}" for k, v in seo_goals.items() if v]
    goals_text = "، ".join(goals_parts) if goals_parts else ""

    # Check WordPress integration status
    wp_stmt = select(WordPressIntegration).where(
        WordPressIntegration.website_id == website_id,
        WordPressIntegration.status == "active",
    ).limit(1)
    wp_res = await db.execute(wp_stmt)
    wp_integration = wp_res.scalar_one_or_none()
    has_wp = wp_integration is not None

    # ── 2. Content Categories / Silo Taxonomy ──────────────────────────
    cat_stmt = select(ContentCategory).where(
        ContentCategory.website_id == website_id,
        ContentCategory.deleted_at.is_(None),
    ).order_by(ContentCategory.depth.asc(), ContentCategory.sort_order.asc()).limit(20)
    cat_res = await db.execute(cat_stmt)
    categories = list(cat_res.scalars().all())
    categories_text = ""
    if categories:
        cat_lines = [f"- شاخه: {c.name} (مسیر: {c.path})" for c in categories]
        categories_text = "\n".join(cat_lines)

    # ── 3. Real Search Console Data (GSC Queries & Pages) ─────────────
    gsc_stmt = (
        select(GscQuery)
        .where(GscQuery.website_id == website_id)
        .order_by(desc(GscQuery.impressions))
        .limit(25)
    )
    gsc_res = await db.execute(gsc_stmt)
    gsc_queries = list(gsc_res.scalars().all())

    gsc_insights_lines = []
    for gq in gsc_queries:
        pos_str = f"رتبه {gq.position:.1f}" if gq.position else "بدون رتبه"
        ctr_str = f"نرخ کلیک {gq.ctr*100:.1f}%" if gq.ctr else "0%"
        gsc_insights_lines.append(f"- کوئری «{gq.query}»: {gq.impressions:,} نمایش | {gq.clicks:,} کلیک | {ctr_str} | {pos_str}")

    # ── 4. Pre-computed Growth Opportunities ───────────────────────────
    opp_stmt = select(Opportunity).where(
        Opportunity.website_id == website_id,
        Opportunity.status.in_(["open", "in_progress"]),
    ).order_by(desc(Opportunity.priority_score)).limit(10)
    opp_res = await db.execute(opp_stmt)
    opportunities = list(opp_res.scalars().all())

    opp_lines = []
    for opp in opportunities:
        opp_lines.append(f"- [{opp.opportunity_type}] {opp.title}: {opp.recommended_action or opp.description}")

    # ── 5. Tracked Target Keywords & Ranking History ───────────────────
    kw_stmt = select(Keyword).where(Keyword.website_id == website_id).limit(30)
    kw_res = await db.execute(kw_stmt)
    tracked_keywords = list(kw_res.scalars().all())

    has_real_keywords = bool(tracked_keywords)
    kw_names = [k.keyword for k in tracked_keywords] if tracked_keywords else []

    kw_details_lines = []
    for k in tracked_keywords:
        parts = [f"«{k.keyword}»"]
        if k.search_volume is not None:
            parts.append(f"حجم: {k.search_volume:,}/ماه")
        if k.difficulty is not None:
            parts.append(f"سختی: {k.difficulty}/100")
        if k.intent:
            parts.append(f"نیت: {k.intent}")
        if k.last_position is not None:
            parts.append(f"رتبه فعلی: {k.last_position:.1f}")
        if k.best_position is not None:
            parts.append(f"بهترین رتبه: {k.best_position:.1f}")
        kw_details_lines.append(" | ".join(parts))

    # ── 6. Latest Technical SEO Audit & Issues ─────────────────────────
    audit_stmt = select(SeoAudit).where(SeoAudit.website_id == website_id).order_by(desc(SeoAudit.created_at)).limit(1)
    audit_res = await db.execute(audit_stmt)
    latest_audit = audit_res.scalar_one_or_none()
    
    issues_text = ""
    audit_scores_text = ""
    issues = []
    if latest_audit:
        issue_stmt = select(SeoAuditIssue).where(
            SeoAuditIssue.audit_id == latest_audit.id,
            SeoAuditIssue.is_resolved == False,
        ).order_by(desc(SeoAuditIssue.severity)).limit(15)
        issue_res = await db.execute(issue_stmt)
        issues = list(issue_res.scalars().all())
        issues_text = "\n".join([f"- [{i.severity.upper()}] {i.title}: {i.description[:100]}" for i in issues])
        audit_scores_text = (
            f"امتیاز کلی: {latest_audit.overall_score}/100 | "
            f"فنی: {latest_audit.technical_score}/100 | "
            f"محتوا: {latest_audit.content_score}/100 | "
            f"تجربه کاربری: {latest_audit.ux_score}/100 | "
            f"صفحات خزش‌شده: {latest_audit.pages_crawled}"
        )

    # ── 7. Existing Content Corpus (Deduplication Safety Net) ──────────
    art_stmt = (
        select(ContentArticle.title, ContentArticle.seo_metadata, ContentArticle.status)
        .where(ContentArticle.website_id == website_id, ContentArticle.deleted_at.is_(None))
        .order_by(desc(ContentArticle.created_at))
        .limit(60)
    )
    art_res = await db.execute(art_stmt)
    existing_articles = list(art_res.all())

    existing_article_titles = []
    existing_article_keywords = set()
    for art_title, art_meta, art_status in existing_articles:
        existing_article_titles.append(art_title)
        if isinstance(art_meta, dict):
            kw = art_meta.get("target_keyword", "")
            if kw:
                existing_article_keywords.add(kw)

    brief_stmt = (
        select(ContentBrief.title, ContentBrief.target_keyword, ContentBrief.status)
        .where(ContentBrief.website_id == website_id, ContentBrief.deleted_at.is_(None))
        .order_by(desc(ContentBrief.created_at))
        .limit(60)
    )
    brief_res = await db.execute(brief_stmt)
    existing_briefs = list(brief_res.all())

    for br_title, br_kw, br_status in existing_briefs:
        if br_kw:
            existing_article_keywords.add(br_kw)

    cal_stmt = (
        select(ContentCalendarEntry.title, ContentCalendarEntry.target_keyword)
        .where(
            ContentCalendarEntry.website_id == website_id,
            ContentCalendarEntry.deleted_at.is_(None),
            ContentCalendarEntry.status.notin_(["cancelled"]),
        )
        .limit(40)
    )
    cal_res = await db.execute(cal_stmt)
    calendar_entries = list(cal_res.all())

    for cal_title, cal_kw in calendar_entries:
        if cal_kw:
            existing_article_keywords.add(cal_kw)

    existing_content_text = ""
    if existing_article_titles or existing_article_keywords:
        parts = []
        if existing_article_titles:
            parts.append("عناوین مقالات موجود و منتشرشده:")
            for i, t in enumerate(existing_article_titles[:35], 1):
                parts.append(f"  {i}. {t}")
        if existing_article_keywords:
            parts.append(f"\nکلمات کلیدی‌ای که قبلاً مقاله اختصاصی دارند: {' | '.join(sorted(existing_article_keywords))}")
        existing_content_text = "\n".join(parts)
    
    content_stats = {
        "articles_count": len(existing_articles),
        "briefs_count": len(existing_briefs),
        "calendar_count": len(calendar_entries),
        "covered_keywords": len(existing_article_keywords),
    }

    # ── 8. Previous Strategies (Anti-repetition) ───────────────────────
    prev_stmt = (
        select(AiSeoStrategy.executive_summary, AiSeoStrategy.title)
        .where(AiSeoStrategy.website_id == website_id)
        .order_by(desc(AiSeoStrategy.created_at))
        .limit(3)
    )
    prev_res = await db.execute(prev_stmt)
    prev_strategies = list(prev_res.all())
    prev_summaries_text = ""
    if prev_strategies:
        prev_parts = [f"استراتژی قبلی {idx}: {s[:180]}..." for idx, (s, t) in enumerate(prev_strategies, 1)]
        prev_summaries_text = "\n".join(prev_parts)

    prompt_tokens = 0
    completion_tokens = 0

    # ── 9. Construct Super-Intelligent Prompts ─────────────────────────
    focus_guideline = _FOCUS_AREA_PROMPTS.get(focus_area, "") if focus_area else ""

    system_prompt = (
        "تو یک استراتژیست ارشد سئو و معمار داده‌های ارگانیک (Principal SEO Strategist & Topical Architect) در سطح برترین آژانس‌های سئوی جهان هستی.\n"
        "وظیفه تو: طراحی یک استراتژی سئوی کاملاً اختصاصی، بسیار عمیق، علمی و مبتنی بر داده‌های واقعی برای این وب‌سایت است.\n\n"
        "قوانین طلایی و تخلف‌ناپذیر:\n"
        "۱. هرگز از روی نام دامنه حدس نزن که سایت درباره چیست! نام دامنه ممکن است مخفف یا گمراه‌کننده باشد.\n"
        "۲. فقط و فقط بر اساس «توضیحات کسب‌وکار»، «کلمات کلیدی ثبت‌شده»، «داده‌های سرچ‌کنسول» و «دسته‌بندی‌های سایت» موضوع سایت را درک کن.\n"
        "۳. موضوعات موجود را تحلیل کن: هرگز کلمه‌ای که قبلاً مقاله دارد را به عنوان شکاف محتوایی (content_gap) معرفی نکن.\n"
        "۴. ساختار خوشه‌ای (Topic Clusters) باید ساختار دقیق پیلار و کلاستر داشته باشد (یک Pillar Page اصلی و حداقل ۴ Cluster Article مرتبط برای هر خوشه).\n"
        "۵. حداقل ۶ خوشه موضوعی کامل و غنی، حداقل ۶ شکاف محتوایی بکر و پرتقاضا، و حداقل ۸ اقدام عملیاتی زمان‌بندی‌شده با تفکیک تیم مسئول ارائه بده.\n"
        "۶. نوع نیت کاربر (intent) حتماً یکی از: \"اطلاعاتی\"، \"تجاری\"، \"تراکنشی\"، یا \"ناوبری\" باشد.\n"
        "۷. سطح اولویت (priority) و اثرگذاری (impact) حتماً یکی از: \"بالا\"، \"متوسط\"، یا \"پایین\" باشد.\n"
        "۸. اقدامات عملیاتی (action_items) باید دقیق و فنی باشند (شامل اصلاح متا، ساخت پیلار، بهینه‌سازی سرعت، لینک‌سازی داخلی، تولید بریف محتوا).\n\n"
        "خروجی را الزاماً و صرفاً به صورت یک JSON معتبر و بدون هیچ متن مقدمه یا موخره تولید کن:\n"
        "{\n"
        '  "strategy_title": "عنوان اختصاصی و جذاب برای این برنامه استراتژیک",\n'
        '  "executive_summary": "خلاصه مدیریتی ۴-۶ جمله‌ای: ارزیابی وضعیت فعلی، سهم بازار ارگانیک، اولویت‌های فوری و دستاوردهای ۳ ماهه آینده",\n'
        '  "target_audience": "تحلیل پرسونای مخاطب: انگیزه‌ها، دغدغه‌ها، مرحله سفر مشتری (Buyer Journey) و رفتار جستجوی کاربران این بازار",\n'
        '  "keyword_clusters": [\n'
        '    {\n'
        '      "cluster_title": "نام خوشه بر اساس شاخه‌های تخصصی سایت",\n'
        '      "main_keyword": "کلمه کلیدی پیلار (صفحه ستون)",\n'
        '      "secondary_keywords": ["کلمه کلاستر ۱", "کلمه کلاستر ۲", "کلمه کلاستر ۳", "کلمه کلاستر ۴"],\n'
        '      "intent": "تجاری",\n'
        '      "priority": "بالا"\n'
        '    }\n'
        '  ],\n'
        '  "content_gaps": [\n'
        '    {\n'
        '      "topic": "موضوع دقیق شکاف که سایت هنوز پوشش نداده",\n'
        '      "target_keyword": "کلمه کلیدی هدف",\n'
        '      "suggested_title": "عنوان جذاب سئوشده برای مقاله",\n'
        '      "search_volume_estimate": 1500,\n'
        '      "difficulty": 35\n'
        '    }\n'
        '  ],\n'
        '  "action_items": [\n'
        '    {\n'
        '      "step": "عنوان اقدام فنی/محتوایی",\n'
        '      "task": "دستورالعمل اجرایی دقیق با شرح مراحل و ابزارها",\n'
        '      "department": "تیم محتوا",\n'
        '      "timeline": "هفته ۱ الی ۲",\n'
        '      "impact": "بالا"\n'
        '    }\n'
        '  ]\n'
        "}"
    )

    user_prompt_sections = [
        "══════════════════════════════════════════════════",
        "  مشخصات پایه و شناسنامه وب‌سایت",
        "══════════════════════════════════════════════════",
        f"نام وب‌سایت: {site_name}",
        f"دامنه: {domain} (توجه: از نام دامنه حدس نزن!)",
        f"مدل و نوع پلتفرم: {site_type}",
        f"زبان: {site_language} | بازار هدف: {site_country}",
        f"اتصال به وردپرس: {'بله (همگام‌سازی مستقیم فعال است)' if has_wp else 'خیر / مستقل'}",
    ]

    if site_description:
        user_prompt_sections.append(f"\n⚡ توضیحات تخصصی کسب‌وکار و حوزه فعالیت (مبنای اصلی تحلیل):\n{site_description}")
    else:
        user_prompt_sections.append("\n⚠️ توضیحات مستقیم کسب‌وکار توسط مدیر ثبت نشده است. موضوع سایت را منحصراً از روی کلمات کلیدی، دسته‌بندی‌ها و سرچ‌کنسول زیر استخراج کن.")

    if focus_guideline:
        user_prompt_sections.append(f"\n🎯 اولویت و جهت‌گیری ویژه کاربر (Focus Area):\n{focus_guideline}")
    elif focus_area:
        user_prompt_sections.append(f"\n🎯 اولویت و جهت‌گیری ویژه کاربر: {focus_area}")

    if goals_text:
        user_prompt_sections.append(f"\n🏆 اهداف کلیدی سئو تعریف‌شده: {goals_text}")

    if categories_text:
        user_prompt_sections.append(f"\n📂 ساختار دسته‌بندی‌ها و سیلوی فعلی سایت:\n{categories_text}")

    if gsc_insights_lines:
        user_prompt_sections.append(
            f"\n📊 داده‌های واقعی گوگل سرچ کنسول (کوئری‌های واقعی کاربران با بالاترین نمایش):\n"
            + "\n".join(gsc_insights_lines)
        )

    if opp_lines:
        user_prompt_sections.append(
            f"\n💡 فرصت‌های رشد و هشدارهای شناسایی‌شده توسط سیستم:\n"
            + "\n".join(opp_lines)
        )

    if has_real_keywords:
        user_prompt_sections.append(f"\n🔑 کلمات کلیدی هدف ثبت‌شده توسط کارشناس سئو ({len(tracked_keywords)} کلمه):\n" + "\n".join(kw_details_lines))
    else:
        user_prompt_sections.append(
            f"\n🔑 کلمات کلیدی ثبت‌شده:\n"
            f"هنوز کلمه کلیدی به صورت دستی اضافه نشده است. "
            f"بر مبنای توضیحات کسب‌وکار فوق، خوشه‌ها و کلمات کلیدی استاندارد و سودآور این بازار را استخراج کن."
        )

    if audit_scores_text:
        user_prompt_sections.append(f"\n🛠️ آخرین وضعیت آدیت تکنیکال سایت: {audit_scores_text}")
    if issues_text:
        user_prompt_sections.append(f"\n🚨 خطاهای فنی باز و حل‌نشده:\n{issues_text}")

    if existing_content_text:
        user_prompt_sections.append(
            f"\n📚 پایگاه مقالات و محتوای موجود ({content_stats['articles_count']} مقاله و {content_stats['briefs_count']} بریف فعال):\n"
            f"⛔ موضوعات و کلمات زیر قبلاً تولید شده‌اند. هرگز این موضوعات را در شکاف‌های محتوایی تکرار نکن:\n"
            f"{existing_content_text}"
        )

    if prev_summaries_text:
        user_prompt_sections.append(
            f"\n🔄 استراتژی‌های قبلی (برای حفظ تنوع و پوشش زوایای جدید):\n{prev_summaries_text}"
        )

    user_prompt_sections.append(
        "\nلطفاً با تلفیق تمام داده‌های زنده و ساخت‌یافته بالا، استراتژی جامع و نقشه راه پیشرفته سئو را در فرمت JSON خواسته شده تولید کن."
    )

    user_prompt = "\n".join(user_prompt_sections)

    result = {}
    try:
        raw_res, used_provider, prompt_tokens, completion_tokens = await call_ai_with_rotation(
            db=db,
            org_id=org_id,
            user_prompt=user_prompt,
            system_prompt=system_prompt,
            provider_preference=provider,
            json_mode=True,
        )
        if raw_res:
            try:
                result = json.loads(raw_res)
            except Exception:
                match = re.search(r"\{.*\}", raw_res, flags=re.DOTALL)
                if match:
                    result = json.loads(match.group(0))

        def _as_str(v) -> str:
            if v is None:
                return ""
            if isinstance(v, str):
                return v
            if isinstance(v, (dict, list)):
                return json.dumps(v, ensure_ascii=False)
            return str(v)

        def _as_list(v) -> list:
            if v is None:
                return []
            if isinstance(v, list):
                return v
            return [v]

        ai_title = _as_str(result.get("strategy_title", ""))
        title = ai_title if ai_title.strip() else f"استراتژی جامع سئو برای {domain}"

        executive_summary = _as_str(result.get("executive_summary", ""))
        target_audience = _as_str(result.get("target_audience", ""))
        keyword_clusters = _as_list(result.get("keyword_clusters", []))
        content_gaps = _as_list(result.get("content_gaps", []))
        action_items = _as_list(result.get("action_items", []))

    except AppException:
        raise
    except Exception as e:
        raise AppException(
            status_code=503,
            detail=f"خطا در تولید استراتژی با هوش مصنوعی: {str(e)}",
            error_type="strategy_generation_error",
        )

    def _clamp_int(v, lo, hi, default):
        try:
            return max(lo, min(hi, int(v)))
        except (TypeError, ValueError):
            return default

    # Normalize keyword clusters
    keyword_clusters = [
        c for c in keyword_clusters
        if isinstance(c, dict) and str(c.get("cluster_title") or "").strip()
        and str(c.get("main_keyword") or "").strip()
    ]
    for c in keyword_clusters:
        if not isinstance(c.get("secondary_keywords"), list):
            c["secondary_keywords"] = []
        c.setdefault("priority", "بالا")
        c.setdefault("intent", "اطلاعاتی")

    # Normalize & deduplicate content gaps against existing articles
    content_gaps = [
        g for g in content_gaps
        if isinstance(g, dict) and str(g.get("topic") or "").strip()
    ]
    if existing_article_keywords:
        existing_kw_lower = {kw.lower().strip() for kw in existing_article_keywords}
        content_gaps = [
            g for g in content_gaps
            if str(g.get("target_keyword", "")).lower().strip() not in existing_kw_lower
        ]
    for g in content_gaps:
        g["search_volume_estimate"] = _clamp_int(
            g.get("search_volume_estimate"), 0, 1_000_000, 500
        )
        g["difficulty"] = _clamp_int(g.get("difficulty"), 0, 100, 50)
        g.setdefault("target_keyword", g.get("topic", ""))
        g.setdefault("suggested_title", g.get("topic", ""))

    # Normalize action items
    action_items = [
        a for a in action_items
        if isinstance(a, dict) and str(a.get("step") or a.get("task") or "").strip()
    ]
    for a in action_items:
        a.setdefault("department", "تیم محتوا")
        a.setdefault("timeline", "هفته ۱ الی ۲")
        a.setdefault("impact", "بالا")
        if not a.get("step"):
            a["step"] = a.get("task", "")

    if not keyword_clusters:
        raise AppException(
            status_code=502,
            detail="خروجی هوش مصنوعی نامعتبر بود (خوشه کلمات کلیدی خالی). لطفاً دوباره تلاش کنید.",
            error_type="invalid_ai_response",
        )

    strategy = AiSeoStrategy(
        website_id=website_id,
        title=title,
        executive_summary=executive_summary,
        target_audience=target_audience,
        keyword_clusters=keyword_clusters,
        content_gaps=content_gaps,
        action_items=action_items,
        provider_used=used_provider,
    )
    db.add(strategy)
    await db.flush()

    duration_ms = int((time.time() - start_time) * 1000)

    # Log AI agent execution with rich context metrics
    input_context = {
        "domain": domain,
        "site_name": site_name,
        "site_type": website.website_type,
        "description_provided": bool(site_description),
        "focus_area": focus_area,
        "keywords_count": len(tracked_keywords),
        "gsc_queries_count": len(gsc_queries),
        "opportunities_count": len(opportunities),
        "issues_count": len(issues),
        "previous_strategies_count": len(prev_strategies),
        "existing_content": content_stats,
    }
    output_result = {
        "strategy_title": title,
        "keyword_clusters_count": len(keyword_clusters),
        "content_gaps_count": len(content_gaps),
        "action_items_count": len(action_items),
    }
    decision_summary = (
        f"تدوین استراتژی پیشرفته «{title}» با {len(keyword_clusters)} خوشه موضوعی، "
        f"{len(content_gaps)} شکاف محتوایی بکر و {len(action_items)} اقدام عملیاتی مبتنی بر داده‌های GSC و سرچ کاربران."
    )

    await agent_activity_service.log_agent_activity(
        db,
        website_id=website_id,
        organization_id=org_id,
        agent_name="SEO Strategy Architect Agent",
        agent_type="strategy",
        provider=used_provider,
        action_taken="تولید استراتژی جامع سئو (موتور چندمنبعی هوشمند)",
        status="success",
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        confidence_score=96.5,
        decision_summary=decision_summary,
        input_context=input_context,
        output_result=output_result,
        duration_ms=duration_ms,
        related_entity_type="ai_seo_strategy",
        related_entity_id=strategy.id,
    )

    await db.commit()
    await db.refresh(strategy)
    return strategy


async def get_website_strategies(
    db: AsyncSession,
    website_id: UUID,
) -> list[AiSeoStrategy]:
    stmt = (
        select(AiSeoStrategy)
        .where(AiSeoStrategy.website_id == website_id)
        .order_by(desc(AiSeoStrategy.created_at))
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def get_strategy_detail(
    db: AsyncSession,
    strategy_id: UUID,
) -> AiSeoStrategy | None:
    stmt = select(AiSeoStrategy).where(AiSeoStrategy.id == strategy_id)
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def get_website_ai_logs(
    db: AsyncSession,
    website_id: UUID,
    limit: int = 20,
) -> list[AiAgentLog]:
    stmt = (
        select(AiAgentLog)
        .where(AiAgentLog.website_id == website_id)
        .order_by(desc(AiAgentLog.created_at))
        .limit(limit)
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())
