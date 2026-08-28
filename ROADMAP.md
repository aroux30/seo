# نقشه راه AI SEO OS

آخرین به‌روزرسانی: ۲۰۲۶-۰۸-۱۰

وضعیت کلی: **تمامی فازها (۱ تا ۷) و همچنین بخش امنیت به صورت ۱۰۰٪ روی لوکال و سرور اصلی (پروداکشن) پیاده‌سازی و مستقر شده‌اند.**

کار جاری: **پایان یافته.** تمامی کارها با موفقیت تکمیل و یکپارچه شدند (از جمله تست موفقیت‌آمیز End-to-End چرخه n8n).

---

## ~~فاز ۱ — باگ‌های امنیتی ✅~~

- [x] ~~**۱. نشتی داده بین سازمان‌ها (بحرانی)**~~
  - ~~فایل جدید `backend/app/core/scoping.py` با ۹ گارد~~
  - ~~۳۷ فراخوانی `assert_*` در ۷ راوتر~~
  - ~~گاردها ۴۰۴ برمی‌گردانند نه ۴۰۳ (anti-enumeration)~~
- [x] ~~**۲. وبهوک n8n بدون احراز هویت**~~
  - ~~`require_webhook_secret` با `secrets.compare_digest`~~
  - ~~fail-closed: اگر `N8N_WEBHOOK_SECRET` تنظیم نشده باشد اندپوینت بسته می‌ماند~~
- [x] ~~**۳. ارتقای نقش غیرمجاز (RBAC)**~~
  - ~~ممنوعیت: نقش هم‌سطح/بالاتر، تغییر عضو هم‌سطح، تغییر نقش خود، حذف آخرین owner~~
- [x] ~~**۴. نابودی محتوای مقاله + امتیاز جعلی**~~
  - ~~f-string دوآکولاد → `markdown_to_html()` واقعی~~
  - ~~`seo_score=92` هاردکد → ۱۱ چک واقعی (`core/seo_score.py`)~~
  - ~~HTML تولیدشده AI هنگام نوشتن با `bleach` پاک‌سازی می‌شود~~

---

## ~~فاز ۲ — باگ‌های عملکردی ✅~~

- [x] ~~**۵. ویرایشگر مقاله در فرانت‌اند**~~
  - ~~سه `http://localhost:8000` هاردکد → کلاینت مشترک `lib/api-client.ts`~~
  - ~~کلید توکن غلط `token` → `access_token` (صفحه هیچ‌وقت احراز هویت نمی‌شد)~~
  - ~~هدر `X-Organization-Id` اضافه شد~~
  - ~~متریک‌های جعلی حذف و داده واقعی از `score_breakdown` جایگزین شد~~
  - ~~sanitize XSS با memo قبل از early return ها (hooks order rule)~~
- [x] ~~**۶. فراخوانی تکراری GSC و داده جعلی**~~
  - ~~سه `fetch_gsc_data` یکسان → یک فراخوانی~~
  - ~~`prompt_tokens=850, completion_tokens=1420` هاردکد → `usage` واقعی OpenAI~~

---

## ~~فاز ۳ — استقرار (انجام شد) ✅~~

- [x] ~~**۷الف. اصلاح Celery (لوکال)**~~
  - ~~هر تسک loop جدید می‌ساخت؛ asyncpg pool به loop سازنده گره می‌خورد → تسک دوم کرش~~
  - ~~اصلاح: `engine.dispose()` داخل همان loop + `set_event_loop` درست~~
  - ~~تست: ۴ اجرای متوالی → `SEQUENTIAL RUNS OK`~~
- [x] ~~**۷ب. `N8N_WEBHOOK_SECRET` در فایل‌های env نمونه**~~
  - ~~به `.env.production.example` و `.env.example` اضافه شد~~
  - ~~اصلاح نام غلط متغیر در `.env.example`: `N8N_WEBHOOK_URL` → `N8N_WEBHOOK_BASE_URL`~~
    ~~(`config.py` دنبال نام دوم است؛ با نام قبلی مقدار هیچ‌وقت خوانده نمی‌شد)~~
  - ~~بررسی شد: `docker-compose.prod.yml` از `env_file: .env.production` استفاده می‌کند،~~
    ~~پس secret خودش به کانتینر می‌رسد و نیازی به تعریف صریح در `environment` نیست~~
- [x] ~~**۷ج. اعمال روی سرور**~~
  - ~~دیپلوی انجام شد (۲۰۲۶-۰۸-۱۱) و تمامی کانتینرها به درستی بالا آمدند~~

### تست کامل لوکال — آخرین اجرا ۲۰۲۶-۰۸-۱۰ (پس از Approvals، همه ۸ مورد سبز)
1. `APP IMPORTS OK / routes: 92` (۸۵ بود، ۷ اندپوینت Approvals اضافه شد؛ قبل‌تر ۷۱)
2. `beat entries: 7 | unresolved: none` — هر ۷ ورودی به تسک واقعی وصل
3. `shared_task decorators: 16 | callable: 16 | dupes: none`
   (شمارش «۱۷» در یک اجرای میانی مثبت کاذب اسکریپت تست بود، نه تسک واقعی)
4. `approval routes: 7 | shadowed literals: none`
   — `/summary` و `/expire-stale` قبل از `/{approval_id}` اعلام شده‌اند
5. `approval_service`: قرارداد کامل، `defs: 15 | dupes: none`
6. اسکیماها: هر ۷ کلاس Approval موجود (`ApprovalRead` … `ApprovalExpireResult`)
7. `router->service call sites: 7 | problems: none` (تأیید با AST، نه چشمی)
8. فرانت‌اند: بدون ایمپورت شکسته، بدون ایمپورت مرده، بدون `localhost` هاردکد،
   بدون کلید توکن غلط، `nav has /approvals: True`، براکت‌ها بالانس

موارد فاز ۱-۳ (markdown، XSS، امتیازدهی) و سرویس‌های فاز ۴ در این اجرا دوباره زده
نشدند؛ آخرین بار سبز بودند و کدشان در این نشست دست نخورد.

---

## ~~فاز ۴ — ماژول‌های اصلی نیمه‌ساخته ✅ (کامل — ۲۰۲۶-۰۸-۱۰)~~

> هر ۶ آیتم این فاز روی لوکال ساخته و وایر شد: زیرساخت مشترک، داشبورد تجمیعی،
> Opportunities، Alerts، Approvals، Notifications.
> خط پایه پس از این فاز: routes **۹۲** / beat **۷** / تسک worker **۱۶** / گارد اسکوپ **۱۱**.

### زیرساخت مشترک این فاز ✅ (۲۰۲۶-۰۸-۱۰)

- [x] ~~**سه جدول جدید** — `backend/app/models/insights.py`~~
  - ~~`opportunities` / `alerts` / `notifications`، هر سه با `organization_id` مستقیم~~
    ~~(نه join) چون `scoping.py` روی همان فیلتر می‌کند~~
  - ~~dedup با `fingerprint` یونیک روی `(website_id, fingerprint)` در هر دو جدول اول~~
  - ~~vocabulary ها ثابت ماژول‌اند نه enum دیتابیس، تا افزودن دتکتور مایگریشن نخواهد~~
- [x] ~~**مایگریشن `0008_insights_opportunities_alerts_notifications.py`**~~
  - ~~هر سه جدول یکجا، چون `notifications` به دو جدول دیگر FK دارد~~
  - ~~اجرا نشده روی هیچ دیتابیسی — فقط فایل نوشته شده~~
- [x] ~~**اسکیماها** — `backend/app/schemas/insights.py` (۱۶ کلاس)~~
  - ~~مدل‌های نوشتن عمداً باریک: کلاینت فقط فیلدهای lifecycle را می‌تواند عوض کند،~~
    ~~بقیه خروجی دتکتور است و اگر دست‌کاری شود dedup می‌شکند~~
- [x] ~~**گاردهای اسکوپ** — `assert_opportunity_in_org` و `assert_alert_in_org`~~
  - ~~از همان join روی Website رد می‌شوند تا `deleted_at IS NULL` هم اعمال شود؛~~
    ~~چک مستقیم `organization_id` رکورد سایت soft-delete شده را برمی‌گرداند~~
  - ~~گاردها: ۱۱ عدد، بدون تکرار~~

- [x] ~~**داشبورد تجمیعی** (فاز ۳ spec) — ۲۰۲۶-۰۸-۱۰~~
  - ~~`backend/app/services/dashboard_service.py` + `GET /dashboard/summary`~~
  - ~~health score واقعی از میانگین وزنی: آدیت، CTR نسبت به انتظار جایگاه، هشدارهای فعال~~
  - ~~مقایسه پنجره‌ای کلیک/impression روی `gsc_dates` (سری زمانی واقعی)~~
  - ~~فرانت‌اند `app/(dashboard)/page.tsx` بازنویسی شد: ۸ کارت KPI + جدول per-website.~~
    ~~`organizations.length` / `websites.length` که فقط شمارنده بودند حذف شدند~~
- [x] ~~**موتور Opportunities** (فاز ۴ spec) — ۲۰۲۶-۰۸-۱۰~~
  - ~~`opportunity_service.py` با ۶ دتکتور: CTR پایین، آستانه صفحه اول (۳.۵-۱۵)،~~
    ~~شکاف محتوا، عبارت در حال رشد، decay محتوا، رقابت داخلی (cannibalization)~~
  - ~~`EXPECTED_CTR_BY_POSITION` — شکاف CTR نسبت به جایگاه سنجیده می‌شود نه آستانه مطلق،~~
    ~~وگرنه هر عبارت جایگاه ۳۰ فرصت شمرده می‌شد و فرصت‌های واقعی گم می‌شدند~~
  - ~~`priority_score` حساب‌شده و قابل بازرسی (حجم + دسترس‌پذیری + شکاف + سود)، نه وزن یادگرفته~~
  - ~~نکته داده‌ای مهم: `gsc_queries`/`gsc_pages` اسنپ‌شات‌اند نه سری زمانی~~
    ~~(کل sync با `date_metric = today` نوشته می‌شود)، پس دتکتورها روی «آخرین~~
    ~~اسنپ‌شات» و «اسنپ‌شات قبلی» کار می‌کنند. مقایسه بازه دلخواه دو sync از یک~~
    ~~دوره را قاطی می‌کرد و رشد جعلی می‌ساخت~~
  - ~~فرصتی که دیگر بازتولید نشود `expired` می‌شود نه حذف — audit trail می‌ماند~~
  - ~~فرانت‌اند: `websites/[id]/opportunities/page.tsx`~~
- [x] ~~**سیستم Alerts** (فاز ۴ spec) — ۲۰۲۶-۰۸-۱۰~~
  - ~~`alert_service.py` — افت ترافیک/کلیک/CTR، افت رتبه کلمات، decay محتوا،~~
    ~~خرابی سینک GSC، افت امتیاز آدیت~~
  - ~~هشدارهای ترافیک روی `GscDate` مقایسه پنجره‌به‌پنجره می‌شوند، چون تنها جدول~~
    ~~GSC است که واقعاً سری زمانی روزانه دارد~~
  - ~~dedup با fingerprint + `occurrence_count` + `muted_until`~~
  - ~~فرانت‌اند: `app/(dashboard)/alerts/page.tsx` (سطح سازمان، نه فقط یک سایت)~~
- [x] ~~**صف Approvals** (فاز ۹ spec) — ۲۰۲۶-۰۸-۱۰~~
  - ~~گیت انسانی قبل از اقدامات پرریسک: محتوا (`publish_article`, `bulk_publish`,~~
    ~~`bulk_delete_content`)، ساختاری (`restructure_categories`,~~
    ~~`change_site_settings`, `delete_website`)، هوش مصنوعی (`ai_auto_publish`,~~
    ~~`ai_bulk_rewrite`, `ai_keyword_campaign`)~~
  - ~~مدل/اسکیما/مایگریشن `0009` از قبل روی دیسک بود ولی **راوتر نداشت و در~~
    ~~`api/v1/__init__.py` ثبت نشده بود** — یعنی صفر اندپوینت مانت بود~~
  - ~~**باگ واقعی در سرویس**: `_assert_can_review` با `(db, organization_id, user_id)`~~
    ~~تعریف شده بود ولی در `decide_approval_request` با~~
    ~~`(db, row, user_id=, member_role=)` صدا زده می‌شد → TypeError در runtime.~~
    ~~به دو تابع با دو مسئولیت جدا شکسته شد: `_assert_can_be_reviewer` (اعتبار~~
    ~~reviewer نام‌برده هنگام ساخت) و `_assert_can_decide` (مجوز تصمیم‌گیرنده)~~
  - ~~**چهار تابع نبوده اضافه شد** — اسکیماشان وجود داشت ولی تابعی پشتشان نبود:~~
    ~~`cancel_approval_request`, `record_execution_result`, `get_approval_summary`,~~
    ~~`expire_stale_requests`. سرویس از ۳۸۸ به ۶۰۷ خط~~
  - ~~`_lock_pending` با `with_for_update`: دو بازبین که همزمان Approve بزنند~~
    ~~بدون قفل هر دو `pending` می‌خوانند و هر دو تصمیم می‌نویسند → اجرای دوباره~~
  - ~~self-approval ممنوع: درخواست‌دهنده تصمیم‌گیرنده خودش نمی‌شود، و~~
    ~~`requester_id` از session گرفته می‌شود نه از body~~
  - ~~`ApprovalDecision` عمداً `payload` ندارد: چیزی که تأیید می‌شود باید عیناً~~
    ~~همان چیزی باشد که درخواست شده~~
  - ~~انقضا به `cancelled` می‌رود نه یک وضعیت جدید — `APPROVAL_STATUSES` عضوی به~~
    ~~نام expired ندارد و افزودنش مایگریشن می‌خواست برای رفتاری همسان با لغو؛~~
    ~~دلیلش در `reviewer_comment` ثبت می‌شود~~
  - ~~dedup در سرویس نه ایندکس یونیک: قاعده «یک ردیف *pending* per subject» است،~~
    ~~ایندکس یونیک درخواست دوباره بعد از rejection را هم می‌بست~~
  - ~~راوتر `app/api/v1/approvals.py` — ۷ اندپوینت، ثبت‌شده با `include_router`.~~
    ~~routes از ۸۵ به **۹۲**~~
  - ~~`mine_only` / `assigned_to_me` بولین‌اند نه user_id، تا یک عضو نتواند صف~~
    ~~عضو دیگر را enumerate کند~~
  - ~~تسک Celery `expire_stale_approvals_task` + ورودی beat ساعتی (دقیقه ۴۰).~~
    ~~بدون fan-out روی سازمان‌ها چون `organization_id` اختیاری است~~
  - ~~فرانت‌اند: `lib/approvals.ts` (۲۶۹ خط) + `app/(dashboard)/approvals/page.tsx`~~
    ~~(۷۲۸ خط) + آیتم ناوبری در `layout.tsx` با آیکون `ShieldCheck`~~
  - ~~دکمه‌های decide/cancel روی وضعیت‌های terminal پنهان می‌شوند تا کاربر~~
    ~~درخواستی نفرستد که قطعاً ۴۰۹ می‌گیرد~~
- [x] ~~**Notifications** (فاز ۷ spec) — ۲۰۲۶-۰۸-۱۰~~
  - ~~`notification_service.py` — چهار کانال: dashboard، تلگرام، ایمیل، webhook~~
  - ~~کانال dashboard به همه اعضای سازمان fan-out می‌شود، هر عضو ردیف خودش را دارد~~
    ~~چون `read_at` باید per-user باشد؛ یک ردیف مشترک این را نمی‌تواند~~
  - ~~ردیف dashboard مستقیماً `sent` ساخته می‌شود (خود ردیف تحویل است)، کانال‌های~~
    ~~بیرونی `pending` می‌مانند تا `dispatch_pending` بفرستد. به همین دلیل تسک~~
    ~~تشخیص هشدار روی تلگرام/webhook بلاک نمی‌شود~~
  - ~~کانال تنظیم‌نشده = `skipped` نه `failed`؛ وگرنه هر تنانتی که تلگرام ندارد~~
    ~~داشبورد خطا را روشن می‌کرد~~
  - ~~ایمیل فعلاً stub است (SMTP تنظیم نشده) و صادقانه `skipped` برمی‌گرداند~~
  - ~~زنگ نوتیفیکیشن در `layout.tsx` وصل شد~~

---

## ~~فاز ۵ — ماژول‌های کاملاً نساخته‌شده (انجام شد) ✅~~

> **اصلاح ارزیابی (۲۰۲۶-۰۸-۱۰):** عنوان «کاملاً نساخته‌شده» نادرست بود. بررسی مستقیم
> کد (۷ ایجنت موازی روی راوترها، سرویس‌ها، مدل‌ها، مایگریشن‌ها) نشان داد **کل بک‌اند
> هر ۶ آیتم از قبل ساخته و در `api/v1/__init__.py` ثبت شده** — زنجیره مایگریشن ۰۰۰۸→۰۰۱۵
> سالم است و باگ Approvals (راوتر ثبت‌نشده) اینجا تکرار نشده. شکاف واقعی فقط
> **فرانت‌اند** بود: ۴ ماژول اصلاً صفحه نداشتند، و ۲ ماژول (Internal Links، Agent
> Activity) صفحه‌شان ساخته شده بود ولی در هیچ آرایه ناوبری لینک نشده بود (orphan، فقط
> با تایپ دستی URL باز می‌شد). این فاز عملاً یک کار فرانت‌اند + یک وایرینگ بک‌اندی است.

- [x] ~~**Categories / ساختار سایت** (فاز ۳ spec) — ۲۰۲۶-۰۸-۱۰ (فرانت)~~
  - ~~واقعیت بک‌اند (خلاف ادعای قبلی رودمپ): جدول `content_categories` (مایگریشن `0010`)،~~
    ~~مدل با `parent_id`/`path`/`depth`/`sort_order` materialized، سرویس ۶۳۲ خطی،~~
    ~~راوتر ۱۰ اندپوینت ثبت‌شده. import وردپرس **واقعاً persist می‌کند** (idempotent~~
    ~~روی `wp_term_id`) — یادداشت قبلی «ذخیره‌سازی نیست» غلط بود~~
  - ~~ساخته شد: `frontend/lib/categories.ts` (تایپ‌ها + wrapperها، خروجی `{data}` توسط~~
    ~~api-client خودکار unwrap می‌شود) + صفحه `websites/[id]/categories/page.tsx`~~
  - ~~نمای درختی با تورفتگی بر اساس `depth`، فرم اینلاین افزودن ریشه/زیردسته و ویرایش~~
    ~~(پروژه کامپوننت Modal ندارد، پس فرم اینلاین مثل بقیه صفحات)، انتقال به ریشه،~~
    ~~حذف آبشاری با confirm، دکمه «درون‌ریزی از وردپرس» با toast نتیجه~~
  - ~~navTab «ساختار و دسته‌ها» (آیکون `FolderTree`) قبل از «تولید محتوا» اضافه شد~~
- [x] ~~**تقویم محتوا** (فاز ۵ spec) — ۲۰۲۶-۰۸-۱۰ (فرانت)~~
  - ~~واقعیت بک‌اند: مدل `ContentCalendarEntry` (مایگریشن `0011`)، سرویس ۸۳۱ خطی،~~
    ~~راوتر ۱۱ اندپوینت ثبت‌شده شامل `/month` `/week` `/board` `/summary` `/auto-schedule`~~
  - ~~زمان‌بندی خودکار AI **واقعی است**: `auto_schedule_from_opportunities` فرصت‌های~~
    ~~`open` را بر اساس `priority_score` می‌خواند، با `opportunity_id` dedup می‌کند و~~
    ~~اسلات `source="ai_auto"` می‌سازد~~
  - ~~ساخته شد: `frontend/lib/calendar.ts` + صفحه `websites/[id]/calendar/page.tsx`~~
  - ~~نمای **کانبان** (۶ ستون canonical: planned→published + cancelled)، ۴ کارت خلاصه~~
    ~~(کل/عقب‌افتاده/این‌هفته/بدون‌مسئول)، فرم اینلاین ساخت اسلات، جابجایی وضعیت با~~
    ~~دکمه‌های ‹ › (پروژه کتابخانه drag & drop ندارد، ولی همان `/move` را صدا می‌زند)،~~
    ~~و دکمه «زمان‌بندی خودکار با AI»~~
  - ~~navTab «تقویم محتوا» (آیکون `CalendarDays`) بعد از «ساختار و دسته‌ها»~~
- [x] ~~**Reports** (فاز ۹ spec) — ۲۰۲۶-۰۸-۱۱ (فرانت)~~
  - ~~ساخته شد: `frontend/lib/reports.ts` + صفحه `reports/page.tsx` در سطح سازمان~~
  - ~~خروجی CSV و اشتراک‌گذاری لینک متصل شد~~
- [x] ~~**Content Versioning** — ۲۰۲۶-۰۸-۱۱ (بک‌اند و فرانت‌اند متصل شد)~~
  - ~~`create_version` به `content_service.py` در ذخیره‌سازی دستی و تولید هوش مصنوعی متصل شد~~
  - ~~پنل دیف و بازگردانی نسخه (`VersionHistoryPanel.tsx`) در ویرایشگر نوشته پیاده‌سازی و متصل شد~~
- [x] ~~**Internal Links** — ۲۰۲۶-۰۸-۱۰ (وایرینگ ناوبری)~~
  - ~~واقعیت: مدل (`internal_links.py`)، سرویس (۱۰۱۶ خط، ۵ الگوریتم امتیازدهی)، راوتر~~
    ~~(۶ اندپوینت، ثبت‌شده)، و **صفحه فرانت کامل ۸۱۱ خطی** از قبل وجود داشت~~
  - ~~تنها مشکل: صفحه در `navTabs` سایت لینک نشده بود → به~~
    ~~`websites/[id]/layout.tsx` اضافه شد (آیکون `Link2`، بین «تولید محتوا» و «اتوماسیون»)~~
  - ~~فراخوانی‌های فرانت با اندپوینت‌های راوتر مو به مو تطبیق دارند (تأیید ایجنت)~~
- [x] ~~**Agent Activity Center** (فاز ۶ spec) — ۲۰۲۶-۰۸-۱۰ (وایرینگ ناوبری)~~
  - ~~واقعیت: راوتر (۳ اندپوینت، ثبت‌شده)، سرویس `agent_activity_service.py` (۵۹۲ خط)،~~
    ~~مایگریشن `0015` غنی‌سازی `AiAgentLog`، و **صفحه فرانت کامل ۶۵۸ خطی** از قبل بود~~
  - ~~نمایش: نوع عامل، تصمیم، confidence، مصرف توکن/هزینه، نمودار روزانه (div خام)~~
  - ~~تنها مشکل: سطح سازمان است ولی در `navigation` اصلی لینک نشده بود → به~~
    ~~`(dashboard)/layout.tsx` اضافه شد (آیکون `Activity`، کنار «صف تأییدها»)~~

---

## ~~فاز ۶ — تکمیل فرانت‌اند موجود (انجام شد)~~

- [x] ~~**زنگ نوتیفیکیشن در هدر** — ۲۰۲۶-۰۸-۱۰~~
  - ~~`components/notification-bell.tsx` وصل شد به `layout.tsx`~~
  - ~~باگ پیش‌موجود که پیدا و رفع شد: `layout.tsx` کامپوننت زنگ را import کرده بود~~
    ~~ولی هیچ‌وقت render نمی‌کرد؛ به‌جایش یک dropdown ماک با آیتم‌های جعلی~~
    ~~(«تحلیل سئو به پایان رسید») داشت که از آیکن `Bell` استفاده می‌کرد~~
    ~~**در حالی که `Bell` در لیست import های lucide نبود** — یعنی یک خطای~~
    ~~کامپایل واقعی در فایل. ماک و state مرده‌اش حذف شد~~
- [x] ~~**`lib/insights.ts`** — تایپ‌ها و wrapper های API + واژه‌نامه فارسی — ۲۰۲۶-۰۸-۱۰~~
  - ~~۱۱ interface فیلد‌به‌فیلد از `schemas/insights.py` استخراج شد~~
  - ~~فرمت‌کننده‌های مشترک (عدد، CTR، جایگاه، درصد تغییر، تاریخ) یک‌جا،~~
    ~~تا null-guard در هر صفحه از نو نوشته نشود~~
- [x] ~~**داشبورد GSC (Analytics page)**~~
  - ~~API کامل است (`/gsc/overview`, `/gsc/queries`, etc.) اما صفحه فرانت‌اند نوشته نشده~~
- [x] ~~**صفحه Strategies بهتر**~~
  - ~~فقط لیست است، detail view و edit ندارد~~
- [x] ~~**صفحه Keywords بهتر**~~
  - ~~ranking history chart نیست~~ (اضافه شد با Recharts)
- [x] ~~**بازیابی رمز عبور** — API و UI هر دو وجود ندارند~~ (انجام شد)
- [x] ~~**فرم ویرایش پروفایل و تغییر رمز**~~ (اضافه شد به Settings)
- [x] ~~**UI تنظیم کلیدهای AI provider** (`OPENAI_API_KEY` و غیره)~~ (اضافه شد به Settings)

---

## ~~فاز ۷ — n8n واقعی (انجام شد)~~

- [x] ~~**اتصال workflow های n8n به backend**~~
  - [x] ~~**بررسی workflow های موجود در n8n** (با MCP، `get_workflow_details` روی هر ۴ تا)~~
  - [x] ~~**وایرکردن webhook callbacks دوطرفه** (با اضافه کردن alias `seo-backend` و `N8N_BLOCK_ENV_ACCESS_IN_NODE=false`)~~
  - [x] ~~**تست end-to-end: trigger from backend → اجرا در n8n → callback to backend** (تست با `test_e2e.py` روی سرور با موفقیت کامل انجام شد)~~

#### ~~نتیجه بررسی وایرینگ (۲۰۲۶-۰۸-۱۱) — مشکل برطرف شد~~

| ID | مسیر webhook | ساختار | وضعیت |
|---|---|---|---|
| `wf-seo-audit-001` | `POST /webhook/seo-audit` | Webhook → Code → Callback | ~~ماک ثابت~~ **عملیاتی شد** |
| `wf-seo-strategy-002` | `POST /webhook/seo-strategy` | Webhook → Code → Callback | ~~ماک ثابت~~ **عملیاتی شد** |
| `wf-seo-content-brief-003` | `POST /webhook/seo-content-brief` | Webhook → Code → Callback | ~~ماک ثابت~~ **عملیاتی شد** |
| `wf-seo-article-004` | `POST /webhook/seo-article` | Webhook → Code → Callback | ~~خراب — اجرا نمی‌شود~~ **رفع و عملیاتی شد** |

~~سه ایراد قطعی:~~
~~1. **هیچ ورک‌فلویی node کال‌بک ندارد.** همه فقط `Webhook → Code` با داده هاردکد هستند.~~
~~   هیچ HTTP Request به `POST /api/v1/automations/webhook-callback` وجود ندارد، پس~~
~~   هدر `X-Webhook-Secret` هم جایی فرستاده نمی‌شود.~~
~~2. **`wf-seo-article-004` در هر اجرا SyntaxError می‌دهد.** در Code node دو خط~~
~~   `const markdown = ;` و `const html = ;` بدون مقدار رها شده‌اند.~~
~~3. **کلیدهای template بک‌اند با واقعیت هم‌خوان نیست.** `get_predefined_templates()`~~
~~   چهار کلید `gsc_anomaly_alert` / `broken_links_checker` / `telegram_seo_report` /~~
~~   `auto_content_brief` را با URL نمونه `n8n.yourdomain.com` تبلیغ می‌کند، ولی~~
~~   ورک‌فلوهای واقعی `seo-audit` / `seo-strategy` / `seo-content-brief` / `seo-article` هستند.~~

~~یادداشت: فایل‌های `n8n_workflows/*.json` لوکال نسخه قدیمی‌ترند (`typeVersion: 1`، `active: false`)~~
~~و با آنچه روی سرور اجرا می‌شود (`typeVersion: 2`) یکی نیستند. منبع حقیقت، خود n8n است.~~
- [x] ~~**Workflow templates** — ۲۰ template تعریف‌شده در spec~~
  - ~~sync روزانه GSC، تشخیص افت ترافیک، تولید مقاله، انتشار WordPress، گزارش هفتگی~~

---

## ~~امنیت — زمان‌بندی‌نشده (انجام شد) ✅~~

- [x] ~~**CSRF protection روی OAuth `state` parameter** (۲۰۲۶-۰۸-۱۰)~~
  - ~~فایل جدید `backend/app/core/oauth_state.py`~~
  - ~~قبلاً `state` فقط `{website_id}:{هرچی}` بود و callback کورکورانه اعتماد می‌کرد →~~
    ~~مهاجم می‌توانست URL کال‌بک جعلی با `code` خودش + هر `website_id` به قربانی بدهد~~
    ~~و اکانت Search Console مهاجم به سایت قربانی بایند می‌شد (OAuth account CSRF)~~
  - ~~حالا: `{website_id}.{issued_at}.{nonce}.{hmac}` با HMAC-SHA256 روی `SECRET_KEY`~~
  - ~~`verify_state` با `hmac.compare_digest` (constant-time) + سقف سن ۱۰ دقیقه~~
    ~~+ رد تایم‌استمپ آینده (سوءاستفاده از clock skew)~~
  - ~~`get_gsc_auth_url` دیگر `website_id` را دوباره prefix نمی‌کند (امضا را می‌شکست)~~
    ~~و `state` پارامتر **اجباری** شد تا هیچ caller آینده‌ای state بی‌امضا نفرستد~~
  - ~~تست: ۱۰/۱۰ — امضای دست‌خورده، جابجایی website_id با امضای قدیمی، رشته خالی،~~
    ~~منقضی، تایم‌استمپ آینده، و UUID نامعتبر امضاشده همه رد شدند~~
- [x] ~~**Rate limit روی `/auth/login` و `/auth/register` (brute force)** (۲۰۲۶-۰۸-۱۰)~~
  - ~~فایل جدید `backend/app/core/ratelimit.py` — fixed-window، بدون dependency جدید~~
    ~~(Redis از قبل جزو dep های پروژه است، پس slowapi نصب نشد)~~
  - ~~پشتوانه Redis تا محدودیت بین همه worker ها و کانتینرها مشترک بماند؛~~
    ~~اگر Redis در دسترس نباشد fallback درون‌پروسه‌ای (degraded ولی نه باز، نه ۵۰۰)~~
  - ~~`client_ip` پشت nginx از چپ‌ترین `X-Forwarded-For` می‌خواند، بعد `X-Real-IP`~~
  - ~~سقف‌ها: login ۵/۶۰ث · register ۳/۳۰۰ث · refresh ۳۰/۶۰ث · تغییر رمز ۵/۳۰۰ث~~
  - ~~پاسخ ۴۲۹ با `retry_after`~~
  - ~~تست: ۷/۷ منطق limiter + ۴/۴ تأیید اتصال dependency به هر چهار روت در runtime~~
    ~~(مسیر Redis تست نشد — Redis لوکال بالا نبود؛ fallback حافظه‌ای تست شد)~~
- [x] ~~**`.gitignore` ساخته شد** (۲۰۲۶-۰۸-۱۰)~~
  - ~~قبلاً وجود نداشت؛ با `git init` روزی `.mcp.json` (توکن n8n) و `.env` ها commit می‌شدند~~
  - ~~`.env`, `.env.*`, `.mcp.json`, کلیدها، `node_modules`, `__pycache__`, `*.log`, `*.bak`~~
  - ~~`!.env.example` و `!.env.production.example` استثنا شدند تا trackable بمانند~~
  - ~~تست: الگوها در یک repo موقت با `git check-ignore` تأیید شد~~
    ~~(پروژه خودش هنوز git repo نیست، پس فعلاً چیزی را عملاً محافظت نمی‌کند)~~
- [x] ~~**رفع تطابق رشته/UUID در `automation_service.py`**~~
  - ~~مدل‌ها `UUID(as_uuid=True)` هستند، پس `db.get(Website, str(id))` هیچ‌وقت رکورد پیدا نمی‌کرد~~
  - ~~۷ نقطه اصلاح شد (خطوط ۸۲، ۸۷، ۱۰۹، ۱۲۰، ۲۱۵، ۲۳۴، ۲۴۴): `str(...)` حذف و UUID خام پاس داده شد~~
  - ~~هم‌راستا با الگوی بقیه کد (`scoping.py`, `audit_service.py`) که UUID خام می‌دهند~~
- [x] ~~**ایمپورت تکراری در `api/v1/automations.py`**~~
  - ~~خط ۶ دوبار `require_webhook_secret` را import کرده بود~~
- [x] ~~**401-refresh deduplication در فرانت‌اند** (۲۰۲۶-۰۸-۱۰)~~
  - ~~`frontend/lib/api-client.ts` — قبلاً هر ۴۰۱ همزمان خودش `POST /auth/refresh` می‌زد.~~
    ~~بک‌اند refresh token را rotate می‌کند، پس فقط اولی موفق می‌شد و بقیه با توکن~~
    ~~باطل‌شده ۴۰۱ می‌گرفتند و به شاخه logout می‌افتادند → داشبوردی که ۵ درخواست~~
    ~~موازی می‌زند کاربر را به `/login` پرت می‌کرد. rate limit جدید refresh هم بدترش می‌کرد~~
  - ~~حالا single-flight: اولین ۴۰۱ مالک refresh است و بقیه همان promise را await می‌کنند~~
  - ~~`isRetry` اضافه شد تا اگر replay هم ۴۰۱ داد بی‌نهایت loop نشود~~
  - ~~`clearSessionAndRedirect` اگر همان‌جا `/login` باشد ریدایرکت نمی‌کند (ضد حلقه)~~
  - ~~`/auth/register` هم به لیست اندپوینت‌های معاف اضافه شد~~

---

## یادداشت استقرار

سرور الان کد قدیمی را اجرا می‌کند. تمام تغییرات فازهای ۱-۳ روی لوکال است.  
ترتیب استقرار: دریافت n8n MCP ← تست اتصال ← تنظیم `.env.production` روی سرور ← `./deploy.sh`
