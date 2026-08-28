الان اینم فایلم هست 
"C:\Users\Administrator\Desktop\SEO"

root@91.107.144.136
Pass: 13831381Mj
/root/SEO

این موارد بالا ادرس و پسورد سرور ابونتو و دایرکتوری همین پروژه روی سرور هست

 ROADMAP.md  ← لیست کارها با تیک
"C:\Users\Administrator\Desktop\SEO\ROADMAP.md"

بعد بدون پرسیدن سؤال، قسمت های باقی مانده رودمپ ادامه بده
- بعد از هر کار واقعی ROADMAP.md را تیک بزن، من از همان می‌فهمم کجاییم
- استقرار روی سرور فعلاً ممنوع، تا خودم بگویم

---------------------------------------
اول کد رو سریع نگاه میکنی و رودمپ بعد میگی میخوای کدوم فاز رو استارت بزنی اگه من اوکیه بودم میری روی اون فاز ادامه میدی حله؟
Show less
Read C:\Users\Administrator\Desktop\SEO\ROADMAP.md
Globpattern: "PHASE5_INPROGRESS.md"
Globpattern: "*"
Found 101 files
Globpattern: "**/*.md"
Found 11 files
Grep "category|Category|content_version|internal_link|ai_agent_logs|agent_activity" (in C:\Users\Administrator\Desktop\SEO\backend)
32 lines of output
Agent:Audit Phase 5 module status vs roadmap
IN
This is a FastAPI + Next.js SEO SaaS project at C:\Users\Administrator\Desktop\SEO. The file ROADMAP.md (root of project) claims Phase 5 items are "کاملاً نساخته‌شده" (completely not built): Categories/site structure, Content Calendar, Reports, Content Versioning, Internal Links, Agent Activity Center.

However a grep just found these files already exist on disk, which contradicts the roadmap:
- backend/app/api/v1/calendar.py
- backend/app/api/v1/categories.py, backend/app/services/category_service.py, backend/app/models/categories.py, backend/app/schemas/categories.py, backend/migrations/versions/0010_content_categories.py
- backend/app/services/agent_activity_service.py, backend/app/api/v1/agent_activity.py, backend/app/schemas/agent_activity.py, backend/migrations/versions/0015_agent_log_enrichment.py
- backend/app/services/internal_link_service.py, backend/migrations/versions/0014_internal_links.py, backend/app/schemas/internal_links.py, backend/app/api/v1/internal_links.py, backend/app/models/internal_links.py
- backend/app/api/v1/versions.py, backend/app/services/version_service.py, backend/migrations/versions/0013_content_versions.py, backend/app/models/versions.py

There's also a mentioned file PHASE5_INPROGRESS.md that should track in-progress state of this phase but a glob search found it does NOT exist anywhere in the project.

I need a precise, factual status report on EACH of these 6 Phase 5 items (Categories, Content Calendar, Reports, Content Versioning, Internal Links, Agent Activity Center). For each item, determine:
1. Does a DB model exist? Does a migration exist and is it plausible it was applied (check migration file references, alembic version chain — read backend/migrations/versions/ files near 0008-0016 to see the down_revision chain and find the HEAD)?
2. Does a service layer exist, and how complete is it (rough line count / does it look like real logic or stubs)?
3. Is there an API router file, and CRITICALLY: is it registered in backend/app/api/v1/__init__.py (include_router)? Roadmap emphasizes that unregistered routers = zero mounted endpoints, this bit the project before (Approvals).
4. Does a corresponding frontend page exist under frontend/app/(dashboard)/ or frontend/app/(dashboard)/websites/[id]/ for it? Is there a nav link in frontend/app/layout.tsx?
5. Is there a "Reports" feature anywhere (weekly/monthly/executive reports, PDF export) — search broadly since it wasn't in the grep results, it may genuinely not exist at all.

Also check backend/app/models/__init__.py and backend/app/schemas/__init__.py to see if these new models/schemas are actually imported/exported (unregistered exports could mean broken imports elsewhere).

Report back a clear per-item status table: e.g. "Categories: model✓ migration✓(head) service✓(~180 lines, real logic) router file✓ but NOT registered in __init__.py → 0 endpoints mounted; frontend: no page found, no nav link". Be precise about what you actually read vs assumed. Keep the final report well organized but under 600 words.
Agent:Audit Phase 6 frontend gaps status
IN
This is a FastAPI + Next.js SEO SaaS project at C:\Users\Administrator\Desktop\SEO. Its ROADMAP.md lists Phase 6 ("تکمیل فرانت‌اند موجود" — complete existing frontend) remaining unchecked items:
- داشبورد GSC (Analytics page) — claims backend API is complete (/gsc/overview, /gsc/queries etc.) but frontend page not written
- صفحه Strategies بهتر — only a list view exists, no detail/edit view
- صفحه Keywords بهتر — no ranking history chart
- بازیابی رمز عبور (password reset) — neither API nor UI exist
- فرم ویرایش پروفایل و تغییر رمز (profile edit + change password form)
- UI تنظیم کلیدهای AI provider (OPENAI_API_KEY etc. settings UI)

I need you to verify each claim against actual code, since the roadmap could be stale (a parallel check just found Phase 5 items in the roadmap marked "not built" that actually have substantial code already, so I don't trust this roadmap file's checkboxes blindly).

For each of the 6 items above, check:
1. Analytics/GSC: does backend/app/api/v1/analytics.py (or similar) expose gsc endpoints, and does frontend/app/(dashboard)/websites/[id]/analytics/page.tsx exist and what does it currently render (placeholder vs real charts)?
2. Strategies: read frontend/app/(dashboard)/websites/[id]/strategies/page.tsx — is there any detail/edit route or modal, or just a list?
3. Keywords: read frontend/app/(dashboard)/websites/[id]/keywords/page.tsx — any chart library usage (recharts, chart.js) or ranking history?
4. Password reset: search backend for any "reset_password", "forgot_password", "password_reset" endpoints/tokens, and frontend for any forgot-password page/route.
5. Profile edit / change password: search backend/app/api for a "me" or "profile" or "users" router with PATCH/PUT, and frontend for a profile/account settings page (note frontend/app/(dashboard)/settings/page.tsx exists — check what it actually contains, is it org settings only or also user profile?).
6. AI provider key UI: search frontend and backend for where OPENAI_API_KEY or similar AI provider credentials are configured — is it only via .env, or is there a per-org/per-website settings field and UI for it?

Report a concise per-item status (confirmed accurate / stale-roadmap correction) with the specific file paths and line evidence. Under 500 words.
دو تا Explore agent فرستادم که وضعیت واقعی فاز ۵ و فاز ۶ رو با کد چک کنن (چون رودمپ در مورد فاز ۵ داره اشتباه میگه "کاملاً نساخته‌شده" در حالی که فایل‌های واقعی service/model/router برای Categories، Calendar، Versions، Internal Links، Agent Activity روی دیسک پیدا شد). منتظر نتیجه‌شون می‌مونم تا فاز درست رو برای شروع پیشنهاد بدم.

TaskOutput task: "ad2a8c630cce12455"
OUT
<retrieval_status>timeout</retrieval_status>

<task_id>ad2a8c630cce12455</task_id>

<task_type>local_agent</task_type>

<status>running</status>
TaskOutput task: "ad2a8c630cce12455"
OUT
<retrieval_status>success</retrieval_status>

<task_id>ad2a8c630cce12455</task_id>

<task_type>local_agent</task_type>

<status>completed</status>

<output>
Verified against actual code:

**1. Analytics/GSC — STALE, already built.** `backend/app/api/v1/analytics.py:17-80` exposes `/gsc/overview`, `/queries`, `/pages`, `/countries`, `/devices`, `/dates` (registered in `api/v1/__init__.py`). Frontend `websites/[id]/analytics/page.tsx` is a full 559-line page: 4 stat cards, 5 tabs, filters, manual sync, empty states — real tables wired to those endpoints, not a placeholder (though it uses plain HTML tables, no chart library). Roadmap's "frontend page not written" is wrong — remove from remaining list.

**2. Strategies — PARTIALLY STALE.** `websites/[id]/strategies/page.tsx` calls `GET /strategies/{id}` (line 55) and renders a rich inline detail view (clusters/gaps/roadmap tabs, lines 245-393) for the selected strategy. So a detail view exists. But there's no dedicated detail/edit route, no way to browse/select among multiple past strategies, and no edit form. "Only a list view" is inaccurate; "no edit view" is accurate.

**3. Keywords — CONFIRMED accurate.** No `recharts`/`chart.js`/`Chart` import anywhere in `keywords/page.tsx` (369 lines). No ranking history chart.

**4. Password reset — CONFIRMED accurate.** No `reset_password`/`forgot_password`/`PasswordReset` anywhere in `backend/app`. No forgot-password page in `frontend/app`.

**5. Profile edit / change password — STALE on backend, correct on frontend.** `backend/app/api/v1/auth.py:79-105` already has `PATCH /auth/me` (update full_name/avatar_url) and `PUT /auth/me/password` (verifies current password, sets new hash) — fully implemented with rate limiting. But frontend has zero calls to these (`change_password`/`update_me` grep empty), and `(dashboard)/settings/page.tsx` lines 38-58 only show read-only name/email/status — no form, no password field. So: backend done, UI missing. Roadmap should say "UI missing" not "neither exists."

**6. AI provider key UI — CONFIRMED accurate.** `OPENAI_API_KEY` only appears in `backend/app/config.py`, `services/ai_service.py`, `services/content_service.py` — env-var only, no org/website DB column found. Settings page lines 61-111 show three static "آماده اتصال" badges for OpenAI/Claude/Gemini with no input fields or save action — purely decorative.

**Bottom line:** items 3, 4, 6 are accurate. Item 1 is done — drop it. Items 2 and 5 are overstated: strategy detail view and password-change backend already exist; what's actually missing is a strategies edit UI/history browser and a profile+password form on the frontend.
</output>
TaskOutput task: "a719d9b6c23d46939"
OUT
<retrieval_status>success</retrieval_status>

<task_id>a719d9b6c23d46939</task_id>

<task_type>local_agent</task_type>

<status>completed</status>

<output>

Based on what I read directly (migrations, `__init__.py` files, service/router line counts, frontend directory listings, and `layout.tsx`):

**Migration chain**: 0008→0009→...→0015 is a clean, unbroken `down_revision` chain confirmed by reading each file's `revision`/`down_revision`. 0015 (agent_log_enrichment) is HEAD. All 6 features' migrations exist and chain correctly — plausible they were applied in order, though I did not check the DB itself (no `alembic_version` table query run).

**Router registration**: I read `backend/app/api/v1/__init__.py` in full — all 6 routers (`categories`, `calendar`, `reports`, `versions`, `internal_links`, `agent_activity`) are imported AND passed to `api_router.include_router(...)`. This contradicts the roadmap's core claim and the "Approvals bug" pattern — none of these are orphaned like Approvals was.

**Models/schemas**: `models/__init__.py` and `schemas/__init__.py` both import and `__all__`-export everything for all 6 features. No dangling/unused model files.

| Item | Model | Migration | Service | Router | Registered? | Frontend page | Nav link |
|---|---|---|---|---|---|---|---|
| Categories | ✓ `categories.py` (135 ln) | ✓ 0010 (head-chained) | ✓ `category_service.py` 632 ln, real logic | ✓ `categories.py` 236 ln | ✓ yes | ✗ none found | ✗ none |
| Content Calendar | ✓ `calendar.py` (126 ln) | ✓ 0011 | ✓ `calendar_service.py` 831 ln | ✓ `calendar.py` 323 ln | ✓ yes | ✗ none found | ✗ none |
| Reports | ✓ `reports.py` (145 ln) | ✓ 0012 | ✓ `report_service.py` 1581 ln (largest of all) | ✓ `reports.py` 216 ln | ✓ yes | ✗ none found | ✗ none |
| Content Versioning | ✓ `versions.py` (131 ln) | ✓ 0013 | ✓ `version_service.py` 393 ln | ✓ `versions.py` 159 ln | ✓ yes | ✗ none found | ✗ none |
| Internal Links | ✓ `internal_links.py` (159 ln) | ✓ 0014 | ✓ `internal_link_service.py` 1016 ln | ✓ `internal_links.py` 213 ln | ✓ yes | ✓ `websites/[id]/internal-links/page.tsx` exists | ✗ not in nav array |
| Agent Activity Center | uses existing `AiAgentLog` model (in `audits.py`), enriched by migration 0015, no separate model file | ✓ 0015 | ✓ `agent_activity_service.py` 592 ln | ✓ `agent_activity.py` 213 ln | ✓ yes | ✓ `(dashboard)/agent-activity/page.tsx` exists | ✗ not in nav array |

**Nav check**: I read `frontend/app/(dashboard)/layout.tsx` fully — the `navigation` array has 9 hardcoded items (dashboard, websites, analytics, keywords, opportunities, integrations, alerts, approvals, organizations, projects, settings). None of the 6 Phase 5 items appear, confirming zero nav links for any of them, including the two that do have pages.

**Reports feature**: Contrary to the roadmap and to it being absent from the original grep, a full Reports feature exists on disk — model, migration, a 1581-line service, and a registered 216-line router. However **no frontend page was found anywhere** under `frontend/app` matching report-related routes, so it's backend-only with no UI.

**PHASE5_INPROGRESS.md**: confirmed absent (searched full project tree excluding `node_modules`).

**Bottom line**: The roadmap's claim that these are "completely not built" is false for the backend — all 6 have real, sizeable service logic and are correctly registered (no repeat of the Approvals bug). The actual gap is the **frontend**: 4 of 6 features (Categories, Calendar, Reports, Versioning) have no page at all, and even the 2 that do (Internal Links, Agent Activity) are unreachable via navigation since `layout.tsx` never links them — they're orphan pages only reachable by typing the URL directly.
</output>
دقت خوبی بود. جمع‌بندی چک کد: ROADMAP.md در مورد فاز ۵ کاملاً nادرست است — بک‌اند هر ۶ آیتم (Categories، Calendar، Reports، Versioning، Internal Links، Agent Activity) از قبل مدل+migration+service (سنگین، صدها تا ۱۵۸۱ خط)+router دارد و همه در api/v1/__init__.py رجیستر شده‌اند (باگ Approvals تکرار نشده). خلاصه:

آیتم	بک‌اند	صفحه فرانت	نکس‌بار
Categories	کامل	ندارد	-
Content Calendar	کامل	ندارد	-
Reports	کامل (۱۵۸۱ خط سرویس)	ندارد	-
Content Versioning	کامل	ندارد	-
Internal Links	کامل	هست ولی در nav نیست (orphan)	-
Agent Activity Center	کامل	هست ولی در nav نیست (orphan)	-
پس فاز ۵ عملاً یک کار فرانت‌اند است، نه ساخت از صفر. طبق درخواستت الان چند Explore agent موازی می‌فرستم تا جزئیات دقیق هر آیتم (اسکیمای API واقعی، فیلدهای مورد نیاز فرم/جدول، الگوهای صفحات مشابه موجود) رو دربیارن تا پلن دقیق بنویسم.

Agent:Categories API + frontend pattern detail
IN
Project at C:\Users\Administrator\Desktop\SEO (FastAPI backend + Next.js frontend, App Router, TS). Read-only research, no edits.

I'm planning a frontend page for the Categories feature (tree of category -> subcategory -> content per website). Backend is already built: backend/app/api/v1/categories.py (router), backend/app/services/category_service.py (632 lines), backend/app/models/categories.py, backend/app/schemas/categories.py, migration backend/migrations/versions/0010_content_categories.py.

Please read these files fully and report:
1. Every endpoint in categories.py: method, path, request/response schema names, what it does (list tree, create, update, move/reorder, delete, WordPress import?).
2. The Category model fields (parent_id for tree? position/order? website_id scoping?).
3. Whether WordPress category import is wired here (roadmap claims /wordpress/categories/{id} endpoint exists but doesn't persist — check backend/app/services/wordpress_service.py and backend/app/api/v1/... wordpress-related router for any category import call, and whether category_service has an import_from_wordpress-style function).
4. Look at an existing similar frontend page for pattern to reuse — read frontend/app/(dashboard)/websites/[id]/keywords/page.tsx or strategies/page.tsx fully (whichever is more tree/list-like) to note: how they fetch website id from route params, how they call the api client (frontend/lib/api-client.ts usage pattern), loading/error/empty state conventions, and UI component library in use (shadcn? plain divs? which components imported).
5. Check frontend/lib/ for an existing categories.ts or similar wrapper file — does one exist already (like lib/approvals.ts or lib/insights.ts pattern)?

Report concise, in English, under 400 words, with exact file:line references for the endpoint list and model fields.
Agent:Content Calendar API + AI scheduling detail
IN
Project at C:\Users\Administrator\Desktop\SEO (FastAPI backend + Next.js frontend). Read-only research, no edits.

I'm planning a frontend page for the Content Calendar feature (monthly/weekly/kanban view of scheduled content, with AI auto-scheduling based on opportunities). Backend already built: backend/app/api/v1/calendar.py (router, 323 lines), backend/app/services/calendar_service.py (831 lines), model backend/app/models likely in models/content.py or a dedicated file, migration backend/migrations/versions/0011_*.py.

Please read these files fully and report:
1. Every endpoint in calendar.py: method, path, request/response schema names, purpose (list by month/week, create scheduled item, reschedule/drag-move, delete, AI auto-schedule endpoint?).
2. The underlying calendar item model: fields (scheduled_date, status, content_id link, website_id, category_id?, created_by_ai flag?).
3. Does calendar_service.py have real logic linking to the Opportunities engine (backend/app/services/opportunity_service.py) for AI-based auto-scheduling? Quote the relevant function name and a couple lines showing how it picks opportunities and turns them into calendar entries.
4. Check backend/app/schemas/ for the calendar schema file — list the Pydantic model field names exactly (needed to build a frontend form/type).
5. Check frontend/lib/ for any existing calendar.ts wrapper — does it exist?
6. Skim one existing frontend page with a similar "list with date/status and modal create form" pattern (e.g. frontend/app/(dashboard)/alerts/page.tsx or approvals/page.tsx) just enough to identify: API client import pattern, toast/notification pattern used on success/error, and whether there's a reusable Modal/Dialog component already in the project (search for "Dialog" or "Modal" component imports).

Report concise, in English, under 400 words, with exact file:line references for endpoints and model/schema fields.
Agent:Reports API + export detail
IN
Project at C:\Users\Administrator\Desktop\SEO (FastAPI backend + Next.js frontend). Read-only research, no edits.

I'm planning a frontend page for the Reports feature (weekly/monthly/executive reports, PDF export or shareable link). Backend already built: backend/app/api/v1/reports.py (216 lines), backend/app/services/report_service.py (1581 lines, the largest service in the project), migration backend/migrations/versions/0012_*.py.

Please read these files fully (report_service.py can be skimmed for function signatures/docstrings rather than every line, but read reports.py router completely) and report:
1. Every endpoint in reports.py: method, path, request/response schema names, purpose (generate report, list reports, get by id, PDF export, shareable public link, delete/schedule).
2. Does report_service.py actually generate a PDF (check for weasyprint/reportlab/wkhtmltopdf/playwright imports) or does it return structured JSON/HTML only? Quote the relevant import lines or function.
3. Is there a public/shareable link mechanism (a token-based unauthenticated GET route)? Quote it if found.
4. What report types/periods exist (weekly/monthly/executive) — list the enum or literal values from the schema file (backend/app/schemas/ — find the reports schema file).
5. Check frontend/lib/ for an existing reports.ts wrapper — does it exist? (It shouldn't, since there's no frontend page at all currently — confirm this by checking frontend/app for any "report" path.)
6. Note any auth/scoping pattern the router uses (assert_website_in_org style guard) so the frontend knows what params are required (website_id vs organization-level).

Report concise, in English, under 400 words, with exact file:line references.
Agent:Content Versioning API detail
IN
Project at C:\Users\Administrator\Desktop\SEO (FastAPI backend + Next.js frontend). Read-only research, no edits.

I'm planning a frontend page/panel for Content Versioning (track before/after history of article edits, likely a diff view). Backend already built: backend/app/api/v1/versions.py (159 lines), backend/app/services/version_service.py (393 lines), backend/app/models/versions.py, migration backend/migrations/versions/0013_content_versions.py.

Please read these files fully and report:
1. Every endpoint in versions.py: method, path, request/response schema, purpose (list versions for a content item, get one version, restore/rollback to a version, diff between two versions?).
2. The ContentVersion model fields exactly (content_id FK, version_number, snapshot of what fields — title/body/seo_score?, created_by, created_at, change_reason?).
3. Does version_service.py compute a diff (check for difflib or similar) or just store snapshots for the frontend to diff itself?
4. Is version creation automatic (hooked into content_service.py on every edit) or does it require an explicit API call? Search backend/app/services/content_service.py for any call into version_service to confirm whether existing article edits already produce versions, or whether this is dead code nothing calls yet.
5. Check the content detail/edit page frontend/app/(dashboard)/websites/[id]/content/page.tsx (and any content/[id] subpage if it exists) — is there already a place where a "version history" button/tab would naturally slot in, or is content editing done via a modal only?

Report concise, in English, under 400 words, with exact file:line references.
Agent:Internal Links + Agent Activity nav wiring detail
IN
Project at C:\Users\Administrator\Desktop\SEO (FastAPI backend + Next.js frontend, Next App Router). Read-only research, no edits.

Two features already have backend AND a frontend page, but are NOT linked in navigation (confirmed: frontend/app/(dashboard)/layout.tsx nav array doesn't include them):
1. Internal Links — page at frontend/app/(dashboard)/websites/[id]/internal-links/page.tsx, backend backend/app/api/v1/internal_links.py + backend/app/services/internal_link_service.py (1016 lines) + backend/app/models/internal_links.py + backend/app/schemas/internal_links.py.
2. Agent Activity Center — page at frontend/app/(dashboard)/agent-activity/page.tsx, backend backend/app/api/v1/agent_activity.py + backend/app/services/agent_activity_service.py (592 lines), uses AiAgentLog model in backend/app/models/audits.py.

Please:
1. Read frontend/app/(dashboard)/layout.tsx fully. Quote the exact `navigation` array (or whatever it's called) including each item's icon import and href, so I know the exact pattern to add two more entries (or one, since internal-links is per-website nested under websites/[id]/ so it might belong in a per-website sub-nav rather than the main sidebar — check if there's a per-website sub-nav/tabs component separate from the main sidebar, e.g. for keywords/audits/strategies/content/settings under websites/[id]/).
2. Read both page.tsx files fully (internal-links and agent-activity) — report: do they actually work correctly against the real API (check the fetch calls match real endpoint paths from the routers), any obvious bugs, and their current line count.
3. Read backend/app/api/v1/internal_links.py and agent_activity.py to list their exact endpoints (method+path) so I can confirm the frontend calls match.
4. Is agent-activity page organization-level (matches its nav-array sibling items like /alerts, /approvals) or per-website? Confirm from its file path and any params it reads.

Report concise, in English, under 450 words, with exact file:line references, especially the full nav array quote.
۵ ایجنت دیگه فرستادم برای جزئیات دقیق هر آیتم فاز ۵ (Internal Links/Agent Activity nav، Calendar، Categories، Versioning، Reports). منتظر نتایج می‌مونم.

TaskOutput task: "a7147fdbf300f2838"
TaskOutput task: "ab48b438f205adda2"
TaskOutput task: "ac4be55ba94852ea7"
TaskOutput task: "a6fe0dab4e72736bb"
OUT
<retrieval_status>success</retrieval_status>

<task_id>a6fe0dab4e72736bb</task_id>

<task_type>local_agent</task_type>

<status>completed</status>

<output>
**1. Endpoints (`backend/app/api/v1/versions.py`)**
- `GET /versions` (L49-67): query `article_id`, `limit`, `offset` (viewer). Lists history newest-first, no body content → `ContentVersionListItem[]`.
- `GET /versions/summary` (L71-80): query `article_id` (viewer). Header counters → `ContentVersionSummary` (total, current version #, last changed, contributors).
- `GET /versions/diff` (L84-103): query `article_id`, `from_version`, `to_version` (viewer). Line-level diff → `ContentVersionDiff`.
- `GET /versions/{version_id}` (L106-118): full snapshot incl. bodies → `ContentVersionRead` (viewer).
- `POST /versions/{version_id}/rollback` (L121-159): body `ContentVersionRollbackRequest` (optional `change_summary`), role `editor`. Restores old snapshot onto live article, appends a new version (never edits/deletes history) → `ContentVersionRollbackResult`.

No `POST /versions` create endpoint exists — versions are never created directly by a client (L4-6 module docstring).

**2. `ContentVersion` model** (`backend/app/models/versions.py` L61-131): `organization_id`, `website_id`, `article_id` (FK, CASCADE), `version_number` (int, per-article unique w/ `article_id`), snapshot fields `title`, `content_markdown`, `content_html`, `seo_score`, `seo_metadata` (JSONB) — deliberately *no* `slug`/`status`; provenance: `change_type` (enum-like: created/edited/ai_rewrite/rollback/published/imported), `change_summary`, `changed_by` (nullable), `diff_stats` (JSONB: added/removed chars/words vs previous), `is_current` (bool flag, exactly one true row per article).

**3. Diff computation** — `version_service.py` uses stdlib `difflib` (imported L22): `_compute_diff_stats` (L46-70, `SequenceMatcher` opcodes) stored on every version at write time, and `diff_versions` (L263-313) computes a live `difflib.unified_diff` between two version numbers, classified into added/removed/context/hunk lines, capped at `MAX_DIFF_LINES=2000`. Backend fully computes the diff — frontend doesn't need to.

**4. Version creation is NOT hooked into edits.** `create_version` is only called from `rollback_to_version` (L352, versions.py L145) and directly if something calls it — but `grep -rn create_version` across `backend/` returns only `version_service.py` itself. `content_service.py` has zero references to `version_service` (confirmed via grep, no matches). So saving an article via the editor (`PATCH /content/articles/detail/{id}`, used in `handleSave`) creates **no** version row. Only rollback produces new versions. This is effectively dead/unwired functionality for normal edits.

**5. Frontend** — `frontend/app/(dashboard)/websites/[id]/content/[articleId]/page.tsx` is a full page (not a modal), single-column layout: header bar (L228-266) with back button, title input, Save/Publish buttons; 4-col grid with editor (3 cols) + sidebar (1 col: score, metrics, checklist, WordPress status, L318-429). No tabs/version UI exists yet. A "Version History" button would slot naturally into the header bar (next to Save, ~L247-265) or as a new tab alongside the existing preview/markdown toggle (L272-300), opening a side panel or separate route/modal — no version_service calls appear anywhere in this file.
</output>
Agent:Content Calendar API detail retry
IN
Project at C:\Users\Administrator\Desktop\SEO (FastAPI backend + Next.js frontend). This is a read-only research task — do not edit any files, do not use the dataviz skill or any other skill, just use Read/Grep/Glob tools directly to inspect files and report back in plain text.

Read these files fully with the Read tool:
1. backend/app/api/v1/calendar.py
2. backend/app/services/calendar_service.py (at least the function signatures/docstrings and any function referencing "opportunity")
3. backend/app/schemas/calendar.py (or wherever the calendar Pydantic schemas live — grep for it if unsure)
4. The calendar model (grep backend/app/models for "class.*Calendar" to find the file)
5. Check if frontend/lib/calendar.ts exists (glob it)
6. Read frontend/app/(dashboard)/alerts/page.tsx briefly to see: what API client import it uses, what toast/notification library, and whether it uses any Dialog/Modal component (grep the file for "Dialog" or "Modal")

Then report, in plain English text (no skill invocations needed, this is pure code reading):
1. Every endpoint in calendar.py: HTTP method, path, request/response schema type names, one-line purpose each.
2. The calendar item DB model's field names.
3. Whether calendar_service.py has real logic connecting to opportunity_service.py for AI auto-scheduling — quote the function name if found.
4. The Pydantic schema field names for creating/reading a calendar entry.
5. Whether frontend/lib/calendar.ts already exists.
6. The alerts page's API client import pattern and whether it uses a Dialog/Modal component.

Keep the report under 400 words with file:line citations.
<think>
</think>بررسی فاز ۵ تمام شد. نتیجه مهم و غافلگیرکننده است: خلاف چیزی که رودمپ می‌گوید، کل بک‌اند فاز ۵ ساخته شده و ثبت هم شده — تکرار باگ Approvals رخ نداده. شکاف واقعی فقط فرانت‌اند است.

اجازه بده جمع‌بندی چهار (+ چند) ایجنت را بگویم، بعد پلن را می‌نویسم. یک ایجنت آخر (جزئیات تقویم محتوا) هنوز در حال اجراست، منتظرش می‌مانم.

خلاصه وضعیت واقعی فاز ۵:

ماژول	بک‌اند	Migration	فرانت‌اند	ناوبری
Categories	✅ سرویس ۶۳۲ خط + راوتر ۱۰ اندپوینت	✅ 0010	❌ صفحه ندارد	❌
Content Calendar	✅ سرویس ۸۳۱ خط + راوتر	✅ 0011	❌ صفحه ندارد	❌
Reports	✅ سرویس ۱۵۸۱ خط + راوتر ۱۰ اندپوینت	✅ 0012	❌ صفحه ندارد	❌
Content Versioning	✅ سرویس ۳۹۳ خط + راوتر	✅ 0013	❌ UI تاریخچه ندارد	❌
Internal Links	✅ سرویس ۱۰۱۶ خط + راوتر	✅ 0014	✅ صفحه هست (۸۱۱ خط)	❌ در navTabs نیست
Agent Activity	✅ سرویس ۵۹۲ خط + راوتر	✅ 0015	✅ صفحه هست (۶۵۸ خط)	❌ در nav نیست
نکات مهمی که ایجنت‌ها پیدا کردند:

Content Versioning عملاً مرده است: create_version هیچ‌جا از content_service صدا زده نمی‌شود، یعنی ذخیره یا ویرایش مقاله هیچ نسخه‌ای نمی‌سازد. فقط rollback نسخه تولید می‌کند. این یک باگ وایرینگ واقعی است.
Internal Links و Agent Activity صفحه کامل و درست دارند ولی چون در آرایه ناوبری نیستند، فقط با تایپ دستی URL باز می‌شوند (orphan pages).
Reports خروجی PDF سمت‌سرور ندارد (عمدی)، ولی CSV export و لینک عمومی اشتراک‌گذاری دارد.
Categories: import وردپرس واقعاً persist می‌کند (خلاف یادداشت رودمپ).
منتظر ایجنت آخر (تقویم) می‌مانم، بعد پلن نهایی را در فایل می‌نویسم و برای تأیید می‌فرستم.

<task-notification>
<task-id>a4a1f42cbebc50cf2</task-id>
<tool-use-id>toolu_01P3I67dJy86ygg5iHQyQ6WC</tool-use-id>
<output-file>C:\Users\ADMINI~1\AppData\Local\Temp\claude\c--Users-Administrator-Desktop-SEO\7b938aa2-0279-4584-b516-cc22bfb7f73d\tasks\a4a1f42cbebc50cf2.output</output-file>
<status>completed</status>
<summary>Agent "Content Calendar API detail retry" finished</summary>
<note>A task-notification fires each time this agent stops with no live background children of its own. The user can send it another message and resume it, so the same task-id may notify more than once.</note>
<result>Report — Content Calendar (read-only)

**1. Endpoints (backend/app/api/v1/calendar.py)**
- `POST /calendar` (calendar.py:58) — body `CalendarEntryCreate` → `dict{data: CalendarEntryRead}`. Create a new slot; forces `source="manual"`.
- `GET /calendar` (calendar.py:95) — query filters → `dict{data: list[CalendarEntryRead], meta}`. Filtered/paginated slot list (org-wide or per website).
- `GET /calendar/month` (calendar.py:139) — `website_id, year, month` → `dict{data: CalendarMonthView}`. One Tehran-local month, bucketed by day.
- `GET /calendar/week` (calendar.py:159) — `website_id, start_date` → `dict{data: CalendarWeekView}`. 7-day local strip.
- `GET /calendar/board` (calendar.py:179) — `website_id?, limit_per_column` → `dict{data: CalendarBoardView}`. Kanban columns by status.
- `GET /calendar/summary` (calendar.py:198) — `website_id?` → `dict{data: CalendarSummary}`. Dashboard counters (by_status, overdue, due_this_week, unassigned).
- `POST /calendar/auto-schedule` (calendar.py:215) — `website_id`, body `CalendarAutoScheduleRequest` → `dict{data: CalendarAutoScheduleResult}`. Turns open opportunities into planned slots (seo_manager role).
- `GET /calendar/{entry_id}` (calendar.py:252) — → `dict{data: CalendarEntryRead}`. Fetch one slot (404 not 403 cross-tenant).
- `PATCH /calendar/{entry_id}` (calendar.py:263) — body `CalendarEntryUpdate` → `dict{data: CalendarEntryRead}`. Partial edit.
- `POST /calendar/{entry_id}/move` (calendar.py:286) — body `CalendarEntryMove` → `dict{data: CalendarEntryRead}`. Drag-and-drop reschedule/status change only.
- `DELETE /calendar/{entry_id}` (calendar.py:310) — → `dict{data:{deleted, id}}`. Soft-delete.

**2. DB model fields** (backend/app/models/calendar.py:77-117, `ContentCalendarEntry`): `organization_id`, `website_id`, `title`, `brief_id`, `article_id`, `opportunity_id`, `status`, `priority`, `source`, `scheduled_for`, `deadline`, `published_at`, `assigned_to`, `target_keyword`, `notes`, `details` (JSONB). Plus inherited `id`, `created_at`, `updated_at`, `deleted_at` (SoftDeleteMixin). `opportunity_id` FKs to `opportunities.id`.

**3. Opportunity integration — yes, real logic.** `auto_schedule_from_opportunities` (calendar_service.py:659-768) queries `app.models.insights.Opportunity` for `status == "open"` ordered by `priority_score`, filters out ones already claimed via `opportunity_id` dedup (line 687-698), maps score→priority via `_priority_from_score` (line 771), and creates `ContentCalendarEntry` rows with `source="ai_auto"`, `target_keyword=opp.query`, `notes=opp.recommended_action`, and `details` carrying `opportunity_type`, `priority_score`, `estimated_traffic_gain`, `page_url` (lines 738-759). No direct import of a file named `opportunity_service.py` — it queries the `Opportunity` model directly, not through a service module.

**4. Pydantic create/read schema fields** (backend/app/schemas/calendar.py):
- `CalendarEntryCreate` (line 52): `website_id`, `title`, `brief_id`, `article_id`, `opportunity_id`, `status`, `priority`, `scheduled_for`, `deadline`, `assigned_to`, `target_keyword`, `notes`, `details`.
- `CalendarEntryRead` (line 26): same fields plus `id`, `organization_id`, `source`, `published_at`, `created_at`, `updated_at`.

**5. frontend/lib/calendar.ts** — does not exist (glob returned no matches).

**6. Alerts page** (frontend/app/(dashboard)/alerts/page.tsx):
- API client: imports `ApiError` from `@/lib/api-client` (line 5) but the actual data calls (`listAlerts`, `getAlertSummary`, `updateAlertStatus`) come from `@/lib/insights` (lines 6-18), not a generic api-client wrapper.
- Toast: `react-hot-toast` (line 31), used via `toast.success` / `toast.error` (lines 169, 176).
- No `Dialog` or `Modal` component usage found in this file — grep for those terms returned no matches.</result>
<usage><subagent_tokens>48418</subagent_tokens><tool_uses>9</tool_uses><duration_ms>238634</duration_ms></usage>
</task-notification>
No response requested.

چیشد الان ایجنت اخر ؟
ایجنت آخر (تقویم محتوا) هم تموم شد. خلاصه‌ش:

Content Calendar — بک‌اند کامل و واقعی:

۱۱ اندپوینت: CRUD + /month, /week, /board (کانبان)، /summary، و مهم‌تر از همه /auto-schedule
auto_schedule_from_opportunities (calendar_service.py:659-768) واقعاً به جدول Opportunities وصل است: فرصت‌های باز رو بر اساس priority_score می‌گیره، دوباره‌کاری رو با opportunity_id فیلتر می‌کنه، و خودش entry تقویم با source="ai_auto" می‌سازه — دقیقاً همون چیزی که رودمپ به عنوان "زمان‌بندی خودکار AI" خواسته
مدل ContentCalendarEntry: scheduled_for, deadline, status, priority, source, target_keyword, opportunity_id, article_id, brief_id
فرانت‌اند: هیچی نیست — نه صفحه، نه lib/calendar.ts
با این، تمام تحقیق فاز ۵ کامل شد. جمع‌بندی نهایی:

ماژول	بک‌اند	چیزی که کم است
Categories	✅ کامل (۱۰ اندپوینت، درخت، import وردپرس واقعی)	صفحه فرانت
Content Calendar	✅ کامل (کانبان + AI auto-schedule واقعی)	صفحه فرانت + lib wrapper
Reports	✅ کامل (۱۰ اندپوینت، CSV export، لینک عمومی)	صفحه فرانت
Content Versioning	✅ راوتر/سرویس هست ولی مرده: هیچ ذخیره مقاله‌ای نسخه نمی‌سازه	وایر کردن به content_service + UI تاریخچه/diff
Internal Links	✅ کامل + صفحه فرانت هم هست	فقط باید به navTabs سایت اضافه شه
Agent Activity	✅ کامل + صفحه فرانت هم هست	فقط باید به nav اصلی اضافه شه
الان می‌رم پلن نهایی رو می‌نویسم و برات میارم که تأیید کنی.

Read C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\layout.tsx
Read C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\websites\[id]\layout.tsx
Read C:\Users\Administrator\Desktop\SEO\frontend\lib\internal-links.ts
Good, this confirms the exact pattern to follow. I have everything I need. Let me write the plan file.

Write C:\Users\Administrator\.claude\plans\steady-hopping-acorn.md
69 lines
# پلن فاز ۵ — تکمیل ماژول‌های "نساخته‌شده"

## Context

رودمپ (`ROADMAP.md`) فاز ۵ را کاملاً "نساخته‌شده" علامت زده بود. بررسی مستقیم کد با ۷ ایجنت موازی (Explore) نشان داد این ادعا **غلط** است: بک‌اند هر ۶ آیتم از قبل کامل روی دیسک است — مدل، migration (زنجیره ۰۰۰۸ تا ۰۰۱۵ سالم و بدون شکست)، سرویس (بین ۳۹۳ تا ۱۵۸۱ خط منطق واقعی)، و راوتر — و همه در `backend/app/api/v1/__init__.py` واقعاً `include_router` شده‌اند. باگ Approvals (راوتر نوشته‌شده ولی مانت‌نشده) اینجا تکرار **نشده**.

شکاف واقعی صرفاً **فرانت‌اند** است، و یک مورد هم **وایرینگ بین دو سرویس بک‌اندی**. رودمپ باید پس از این فاز اصلاح شود تا واقعیت را نشان دهد.

وضعیت دقیق هر آیتم (طبق کد، نه رودمپ):

| آیتم | بک‌اند | فرانت‌اند | کار باقی‌مانده |
|---|---|---|---|
| Categories | کامل (۱۰ اندپوینت، درخت، import وردپرس *واقعاً persist می‌کند*) | هیچ صفحه‌ای نیست | صفحه جدید + `lib/categories.ts` |
| Content Calendar | کامل (۱۱ اندپوینت شامل `/month` `/week` `/board` `/auto-schedule` واقعی متصل به Opportunities) | هیچ صفحه‌ای نیست | صفحه جدید + `lib/calendar.ts` |
| Reports | کامل (۱۰ اندپوینت، CSV export، لینک عمومی امن) | هیچ صفحه‌ای نیست | صفحه جدید + `lib/reports.ts` |
| Content Versioning | راوتر/سرویس هست ولی **مرده**: `create_version` هیچ‌جا از `content_service.py` صدا زده نمی‌شود؛ فقط rollback نسخه می‌سازد | UI تاریخچه/diff نیست | وایر کردن نویسندگی نسخه در `content_service.py` + پنل تاریخچه در صفحه ادیتور |
| Internal Links | کامل، صفحه فرانت هم کامل و درست است | صفحه هست ولی در `navTabs` سایت نیست (orphan) | فقط افزودن یک آیتم به `navTabs` |
| Agent Activity Center | کامل، صفحه فرانت هم کامل و درست است | صفحه هست ولی در `navigation` اصلی نیست (orphan) | فقط افزودن یک آیتم به `navigation` |

## الگوی موجود برای پیروی

هر صفحه/lib جدید باید دقیقاً الگوی `internal-links` را کپی کند (تازه‌ترین و کامل‌ترین نمونه در پروژه):
- **الگوی صفحه**: `frontend/app/(dashboard)/websites/[id]/internal-links/page.tsx` — `useParams()` برای `websiteId`، `useState`+`useCallback`+`useEffect` برای لود، skeleton پالس برای loading، حالت خالی با border-dashed، `react-hot-toast` برای فیدبک، همه hookها قبل از هر return زودهنگام (کامنت بالای فایل).
- **الگوی lib**: `frontend/lib/internal-links.ts` — تایپ‌های TS دقیقاً از اسکیمای پایتون، دیکشنری‌های `_LABELS_FA` برای ترجمه enum ها، توابع `api.get/post/patch/delete<T>()` از `@/lib/api-client`.
- بدون shadcn/Dialog — فقط Tailwind خام + آیکون‌های `lucide-react` (تأیید شده در alerts.tsx هم هیچ Dialog/Modal نیست).
- ناوبری: آیتم‌های per-website در `frontend/app/(dashboard)/websites/[id]/layout.tsx` (آرایه `navTabs`، خط ۴۰-۸۶)؛ آیتم‌های سطح سازمان در `frontend/app/(dashboard)/layout.tsx` (آرایه `navigation`، خط ۶۷-۹۹).

## ترتیب اجرا (از کوچک/کم‌ریسک به بزرگ)

### گام ۱ — رفع دو صفحه orphan (سریع، بدون کد جدید)
- `frontend/app/(dashboard)/websites/[id]/layout.tsx`: افزودن آیتم `internal-links` به `navTabs` (آیکون مثلاً `Link2` از lucide) بین «تولید محتوا» و «اتوماسیون‌ها».
- `frontend/app/(dashboard)/layout.tsx`: افزودن آیتم `/agent-activity` به `navigation` (آیکون `Activity`)، کنار `/approvals` و `/alerts`.

### گام ۲ — Internal Links tie-in تکمیل است، رد شو. برو روی Categories
فایل‌های جدید:
- `frontend/lib/categories.ts` — تایپ `CategoryNode`/`CategoryRead`/`CategorySummary` مطابق `backend/app/schemas/categories.py`، توابع `listCategoryTree`, `createCategory`, `updateCategory`, `moveCategory`, `reorderCategories`, `deleteCategory`, `importFromWordPress`.
- `frontend/app/(dashboard)/websites/[id]/categories/page.tsx` — نمایش درختی (indent بر اساس `depth`)، دکمه‌های افزودن زیردسته/ویرایش/حذف/جابجایی، دکمه «Import از وردپرس» که `POST /categories/import/wordpress` را صدا می‌زند و نتیجه (`CategoryImportResult`) را toast می‌کند.
- افزودن به `navTabs`.

### گام ۳ — Content Calendar
- `frontend/lib/calendar.ts` — تایپ‌ها از `backend/app/schemas/calendar.py`، توابع برای `getMonthView`, `getWeekView`, `getBoardView`, `getSummary`, `createEntry`, `updateEntry`, `moveEntry`, `deleteEntry`, `autoScheduleFromOpportunities`.
- `frontend/app/(dashboard)/websites/[id]/calendar/page.tsx` — نمای کانبان (ساده‌تر برای فاز اول از ماهانه/هفتگی؛ ستون‌ها بر اساس `status`)، دکمه «زمان‌بندی خودکار با AI» که `/calendar/auto-schedule` را صدا می‌زند، مودال ساده (بدون کتابخانه Dialog، همان الگوی overlay دستی که باید بسازیم چون در پروژه سابقه‌ای ندارد — یا ساده‌تر: فرم اینلاین باز/بسته‌شونده مثل الگوهای دیگر پروژه).
- افزودن به `navTabs`.

### گام ۴ — Reports
- `frontend/lib/reports.ts` — تایپ‌ها از `backend/app/schemas/reports.py`، توابع `listReports`, `getSummary`, `getTemplates`, `generateReport`, `getReport`, `exportCsv` (لینک مستقیم دانلود)، `shareReport`, `revokeShare`, `deleteReport`.
- `frontend/app/(dashboard)/websites/[id]/reports/page.tsx` (یا سطح سازمان چون هم می‌تواند org-level باشد — بر اساس همان الگوی alerts که سطح سازمان است ولی فیلتر website دارد؛ صفحه را در مسیر سطح سازمان `frontend/app/(dashboard)/reports/page.tsx` می‌گذاریم تا با قابلیت "بدون website_id" سازگار باشد) — لیست گزارش‌ها با وضعیت (pending/generating/ready/failed)، دکمه Generate با انتخاب نوع (weekly/monthly/executive) و website اختیاری، دکمه Export CSV، toggle اشتراک‌گذاری عمومی (نمایش لینک `/reports/public/{token}` قابل کپی).
- افزودن به `navigation` سطح اصلی (کنار Approvals/Alerts/Agent Activity).

### گام ۵ — Content Versioning (نیازمند تغییر بک‌اند + فرانت)
این تنها موردی است که واقعاً باگ وایرینگ بک‌اند دارد، نه فقط فرانت خالی:
- در `backend/app/services/content_service.py`: هر جا مقاله ذخیره/ویرایش می‌شود (تابع ذخیره‌سازی مقاله، احتمالاً `update_article` یا مشابه، هنگام `PATCH /content/articles/detail/{id}`)، یک فراخوانی به `version_service.create_version(...)` اضافه شود تا هر ذخیره واقعی یک نسخه بسازد (نه فقط rollback). باید بررسی شود امضای `create_version` چه پارامترهایی می‌خواهد (از `version_service.py` خواندیم: article_id، سازمان/سایت، snapshot فیلدها، change_type، تشخیص خودکار diff_stats).
- فرانت: در `frontend/app/(dashboard)/websites/[id]/content/[articleId]/page.tsx` یک دکمه «تاریخچه نسخه‌ها» کنار Save (نزدیک خط ۲۴۷-۲۶۵) که یک پنل/صفحه کمکی باز می‌کند: `frontend/lib/versions.ts` جدید + یک کامپوننت یا صفحه که لیست نسخه‌ها، دیف بین دو نسخه انتخابی (خروجی خود بک‌اند `/versions/diff`)، و دکمه Rollback را نشان می‌دهد.

## تیک‌گذاری ROADMAP.md

بعد از هر گام واقعی و تست‌شده:
- تیک بزن آیتم مربوطه در فاز ۵.
- یک خط توضیح کوتاه اضافه کن (مثل سبک بقیه فایل) که واقعیت پیاده‌سازی را ثبت کند — مثلاً برای Categories: «صفحه درختی جدید + `lib/categories.ts`؛ بک‌اند از قبل کامل بود».
- برای دو مورد orphan (Internal Links، Agent Activity) در فاز ۴ که رفع می‌شوند، یک یادداشت اصلاحی کوتاه در همان بخش فاز ۴ اضافه کن نه فاز ۵ (چون آن دو در فاز ۴ ساخته شده بودند).
- در انتها یک پاراگراف اصلاحی بالای فاز ۵ اضافه کن که توضیح دهد ارزیابی اولیه رودمپ در مورد "کاملاً نساخته‌شده" نادرست بود و علت واقعی چه بود (فقط فرانت‌اند map نشده بود).

## Verification

- بعد از هر صفحه/فایل جدید: `cd frontend && npx tsc --noEmit` (یا build) برای اطمینان از نبود خطای تایپ.
- برای گام ۵ (Versioning): تست دستی/اسکریپتی که یک مقاله را دوبار ذخیره می‌کند و بررسی می‌کند دو ردیف در `content_versions` ساخته شده (مثل الگوی تست‌های قبلی پروژه که با اسکریپت پایتون مستقیم چک می‌کردند، طبق سابقه در ROADMAP فاز ۳).
- استقرار روی سرور ممنوع است — همه تست‌ها فقط لوکال.
- بعد از هر گام گزارش کوتاه بده و طبق قانون "بعد از هر کار واقعی تیک بزن" پیش برو.
<think>
</think>ایجنت آخر (تقویم محتوا / Content Calendar) موفق تمام شد. نتیجه‌اش:

Content Calendar — بک‌اند کامل است. راوتر backend/app/api/v1/calendar.py یازده اندپوینت دارد:

POST /calendar ساخت اسلات دستی، GET /calendar لیست فیلتردار
GET /calendar/month نمای ماهانه (به وقت تهران)، GET /calendar/week نمای هفتگی، GET /calendar/board نمای کانبان بر اساس وضعیت
GET /calendar/summary شمارنده‌ها (overdue، این هفته، بدون‌مسئول)
POST /calendar/auto-schedule ← زمان‌بندی خودکار AI واقعاً کار می‌کند: از جدول Opportunity فرصت‌های open را بر اساس priority_score می‌خواند، آن‌هایی که قبلاً اسلات دارند را dedup می‌کند، و ردیف تقویم با source="ai_auto" می‌سازد
PATCH، /move (drag & drop)، DELETE (soft-delete)
شکاف فقط فرانت‌اند است: frontend/lib/calendar.ts وجود ندارد و هیچ صفحه‌ای برای تقویم نیست.

پس جمع‌بندی نهایی هر ۶ ایجنت یکسان است: بک‌اند کل فاز ۵ ساخته و ثبت شده — باگ Approvals (راوتر ثبت‌نشده) تکرار نشده. کار باقی‌مانده واقعی:

Categories — صفحه + lib/categories.ts (نمای درختی)
Content Calendar — صفحه (ماه/هفته/کانبان) + lib/calendar.ts
Reports — صفحه + lib/reports.ts (لیست، تولید، CSV، لینک اشتراک)
Content Versioning — UI تاریخچه/diff + رفع باگ وایرینگ: create_version هیچ‌جا از content_service صدا زده نمی‌شود، پس ویرایش مقاله نسخه نمی‌سازد
Internal Links — فقط اضافه‌کردن به navTabs
Agent Activity — فقط اضافه‌کردن به navigation اصلی
پلن را در فایل نوشتم. الان از plan mode خارج شده‌ام. می‌خواهی از کدام ماژول شروع کنم؟ پیشنهادم به‌ترتیب: اول دو وایرینگ سریع (۵ و ۶) که کم‌هزینه‌اند، بعد رفع باگ Versioning (۴)، بعد سه صفحه بزرگ (۱، ۲، ۳).

/fast
/agents
/model
/model opus
/model
/model
/model default
/model
پلن را در فایل نوشتم. الان از plan mode خارج شده‌ام. می‌خواهی از کدام ماژول شروع کنم؟ پیشنهادم به‌ترتیب: اول دو وایرینگ سریع (۵ و ۶) که کم‌هزینه‌اند، بعد رفع باگ Versioning (۴)، بعد سه صفحه بزرگ (۱، ۲، ۳).


به ترتیب شروع کن هرجوری خودت اوکیه ای
باشه، به‌ترتیب پیش می‌رم. اول یک لیست کار می‌سازم و بعد شروع می‌کنم.

Update Todos

گام ۱: رفع دو صفحه orphan — افزودن Internal Links به navTabs سایت و Agent Activity به navigation اصلی

گام ۲: Categories — ساخت lib/categories.ts + صفحه درختی + navTab

گام ۳: Content Calendar — ساخت lib/calendar.ts + صفحه کانبان/ماهانه + navTab

گام ۴: Reports — ساخت lib/reports.ts + صفحه گزارش‌ها + navigation

گام ۵: Content Versioning — وایر کردن create_version در content_service.py + UI تاریخچه/diff

به‌روزرسانی ROADMAP.md با واقعیت پیاده‌سازی و تیک‌ها
گام ۱: دو صفحه orphan. آیکون‌های لازم را چک می‌کنم و لینک‌ها را اضافه می‌کنم.

قبل از ویرایش، مطمئن می‌شوم آیکون‌های Link2 و Activity در lucide موجودند و صفحه‌های مقصد واقعاً وجود دارند.

Bash Verify orphan page directories exist
IN
ls "C:/Users/Administrator/Desktop/SEO/frontend/app/(dashboard)/agent-activity/" "C:/Users/Administrator/Desktop/SEO/frontend/app/(dashboard)/websites/[id]/internal-links/" 2>&1

OUT
C:/Users/Administrator/Desktop/SEO/frontend/app/(dashboard)/agent-activity/:
page.tsx

C:/Users/Administrator/Desktop/SEO/frontend/app/(dashboard)/websites/[id]/internal-links/:
page.tsx
هر دو صفحه هستند. حالا لینک‌ها را اضافه می‌کنم. اول per-website navTabs (Internal Links):

Edit C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\websites\[id]\layout.tsx
Added 1 line
باشه، به ترتیب می‌رم. اول دو وایرینگ سریع، بعد باگ Versioning، بعد سه صفحه. اول فایل ناوبری و صفحات موجود را می‌خوانم تا دقیقاً بفهمم کجا باید اضافه کنم.

قطع شده اتصالت فکر کنم ادامه بده
اتصال درست است، ادامه می‌دهم. Internal Links را به navTabs اضافه می‌کنم:

Edit C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\websites\[id]\layout.tsx
Added 5 lines
حالا Agent Activity را به navigation اصلی اضافه می‌کنم:

Edit C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\layout.tsx
Added 1 line
Edit C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\layout.tsx
Added 1 line
گام ۱ تمام شد. حالا ROADMAP را برای این دو مورد تیک می‌زنم (چون در فاز ۴ ساخته شده بودند، یادداشت اصلاحی همان‌جا اضافه می‌کنم) و بعد سراغ گام ۲ می‌روم. اول بذار TypeScript را چک کنم که چیزی نشکسته باشد.

Bash Check frontend package scripts and tsconfig
IN
cd "C:/Users/Administrator/Desktop/SEO/frontend" && cat package.json | grep -A 10 '"scripts"'

OUT
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^15.1.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "lucide-react": "^1.16.0",
Bash Verify Link2 and Activity icons exist in installed lucide-react
IN
cd "C:/Users/Administrator/Desktop/SEO/frontend" && node -e "const l=require('lucide-react'); console.log('Link2:', !!l.Link2, '| Activity:', !!l.Activity, '| Version:', require('lucide-react/package.json').version)" 2>&1

OUT
Exit code 1
node:internal/modules/cjs/loader:1505
  throw err;
  ^

Error: Cannot find module 'lucide-react'
Require stack:
- C:\Users\Administrator\Desktop\SEO\frontend\[eval]
    at Module._resolveFilename (node:internal/modules/cjs/loader:1502:15)
    at wrapResolveFilename (node:internal/modules/cjs/loader:1073:27)
    at defaultResolveImplForCJSLoading (node:internal/modules/cjs/loader:1097:10)
    at resolveForCJSWithHooks (node:internal/modules/cjs/loader:1118:12)
    at Module._load (node:internal/modules/cjs/loader:1287:25)
    at wrapModuleLoad (node:internal/modules/cjs/loader:255:19)
    at Module.require (node:internal/modules/cjs/loader:1602:12)
    at require (node:internal/modules/helpers:191:16)
    at [eval]:1:9
    at runScriptInThisContext (node:internal/vm:219:10) {
  code: 'MODULE_NOT_FOUND',
  requireStack: [ 'C:\\Users\\Administrator\\Desktop\\SEO\\frontend\\[eval]' ]
}

Node.js v26.1.0
ک می‌کنم:

Bash Check if node_modules exists
IN
cd "C:/Users/Administrator/Desktop/SEO/frontend" && ls node_modules 2>&1 | head -3; echo "---exit: $?---"

OUT
ls: cannot access 'node_modules': No such file or directory
---exit: 0---
node_modules نصب نیست، پس نمی‌توانم build/tsc را لوکال اجرا کنم. این یعنی verify از طریق کامپایل ممکن نیست مگر npm install کنم. آیکون‌های Link2 و Activity هر دو در lucide-react استاندارد وجود دارند (نام‌های شناخته‌شده)، و در خود صفحه agent-activity هم Activity استفاده شده بود طبق گزارش ایجنت. پس امن است.

تصمیم: npm install را در پس‌زمینه اجرا می‌کنم تا بتوانم بعداً tsc بزنم، ولی منتظرش نمی‌مانم و کار را ادامه می‌دهم.

Bash Install frontend deps in background for later type-check
IN
cd "C:/Users/Administrator/Desktop/SEO/frontend" && npm install 2>&1 | tail -5

OUT
Command running in background with ID: bn23p3pkf. Output is being written to: C:\Users\ADMINI~1\AppData\Local\Temp\claude\c--Users-Administrator-Desktop-SEO\7b938aa2-0279-4584-b516-cc22bfb7f73d\tasks\bn23p3pkf.output. You will be notified when it completes. To check interim output, use Read on that file path.
Session cwd remains C:\Users\Administrator\Desktop\SEO\frontend; directory changes made by the backgrounded command do not apply to subsequent commands.
حالا ROADMAP را برای گام ۱ به‌روز می‌کنم. این دو مورد در فاز ۴ ساخته شده بودند ولی orphan بودند، پس یادداشت اصلاحی در همان بخش فاز ۴ اضافه می‌کنم و آیتم‌های فاز ۵ Internal Links / Agent Activity را هم تیک می‌زنم.

قبل از ادامه، صفحه‌های orphan را می‌خوانم تا مطمئن شوم واقعاً کار می‌کنند (چون قرار است در ناوبری معرفی‌شان کنم، نباید کاربر روی صفحه خراب برود). Agent activity را چک می‌کنم:

Read C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\agent-activity\page.tsx
صفحه سالم است و lib/agent-activity.ts را import می‌کند. این دو صفحه از قبل کامل بودند، فقط لینک نداشتند. حالا ROADMAP را به‌روز می‌کنم.

اول بخش فاز ۴ — یادداشت اصلاحی برای دو orphan که رفع شد. و بخش فاز ۵ — تیک Internal Links و Agent Activity.

Let me update the roadmap. First the header note atop Phase 5, then the two checkboxes.

Edit C:\Users\Administrator\Desktop\SEO\ROADMAP.md
Added 8 lines
Edit C:\Users\Administrator\Desktop\SEO\ROADMAP.md
Added 7 lines
گام ۱ کامل شد. حالا گام ۲: Categories. اول اسکیمای بک‌اند و یک صفحه الگو را دقیق می‌خوانم.

Update Todos

گام ۱: رفع دو صفحه orphan — افزودن Internal Links به navTabs سایت و Agent Activity به navigation اصلی

گام ۲: Categories — ساخت lib/categories.ts + صفحه درختی + navTab

گام ۳: Content Calendar — ساخت lib/calendar.ts + صفحه کانبان/ماهانه + navTab

گام ۴: Reports — ساخت lib/reports.ts + صفحه گزارش‌ها + navigation

گام ۵: Content Versioning — وایر کردن create_version در content_service.py + UI تاریخچه/diff

به‌روزرسانی ROADMAP.md با واقعیت پیاده‌سازی و تیک‌ها
Read C:\Users\Administrator\Desktop\SEO\backend\app\schemas\categories.py
Now let me read the categories router to confirm exact paths and response envelope, and check the api-client wrapper shape.

Read C:\Users\Administrator\Desktop\SEO\backend\app\api\v1\categories.py
همه پاسخ‌ها در {"data": ...} پیچیده شده‌اند. حالا api-client و بقیه lib/internal-links را می‌خوانم تا الگوی دقیق unwrap را بفهمم.

Read C:\Users\Administrator\Desktop\SEO\frontend\lib\api-client.ts
مهم: request خودش json.data را unwrap می‌کند (خط ۱۷۰)، پس در lib فقط api.get<CategoryNode[]>(...) می‌زنم و مستقیم آرایه می‌گیرم. حالا انتهای lib/internal-links.ts را می‌خوانم تا الگوی توابع API را ببینم.

Read C:\Users\Administrator\Desktop\SEO\frontend\lib\internal-links.ts (from line 231)
الگو کاملاً روشن است. حالا lib/categories.ts را می‌سازم:

Write C:\Users\Administrator\Desktop\SEO\frontend\lib\categories.ts
128 lines
import { api } from "@/lib/api-client";

// ---------------------------------------------------------------- vocabularies

/** Mirrors CATEGORY_SOURCES in backend/app/models/categories.py. */
export type CategorySource = "manual" | "wordpress";

export const CATEGORY_SOURCE_LABELS_FA: Record<string, string> = {
  manual: "دستی",
  wordpress: "وردپرس",
};

// -------------------------------------------------------------------- entities

/** Flat row, mirrors CategoryRead in backend/app/schemas/categories.py. */
export interface CategoryRow {
  id: string;
  organization_id: string;
  website_id: string;
  parent_id: string | null;
  name: string;
  slug: string;
  description: string | null;
  path: string;
  depth: number;
  sort_order: number;
  wp_term_id: number | null;
  source: CategorySource | string;
  content_count: number;
}

/** Recursive shape, mirrors CategoryNode (CategoryRead + children). */
export interface CategoryNode extends CategoryRow {
  children: CategoryNode[];
}

export interface CategorySummary {
  total: number;
  roots: number;
  max_depth: number;
  by_source: Record<string, number>;
}

export interface CategoryDeleteResult {
  deleted: number;
}

export interface CategoryImportResult {
  created: number;
  updated: number;
  skipped: number;
}

// ----------------------------------------------------------------- write bodies

export interface CategoryCreateBody {
  website_id: string;
  parent_id?: string | null;
  name: string;
  slug?: string | null;
  description?: string | null;
  sort_order?: number;
}

export interface CategoryUpdateBody {
  name?: string | null;
  slug?: string | null;
  description?: string | null;
  sort_order?: number | null;
}

// ---------------------------------------------------------------------- helpers

/**
 * Flatten a tree into rows carrying their depth, in display order (parent
 * before children, siblings by their existing order). The backend already
 * sorts children by sort_order then name, so we preserve array order and only
 * annotate depth for indentation.
 */
export function flattenTree(nodes: CategoryNode[]): CategoryNode[] {
  const out: CategoryNode[] = [];
  const walk = (list: CategoryNode[]) => {
    for (const node of list) {
      out.push(node);
      if (node.children && node.children.length > 0) {
        walk(node.children);
      }
    }
  };
  walk(nodes);
  return out;
}

// ----------------------------------------------------------------------- calls

export function getCategoryTree(websiteId: string) {
  return api.get<CategoryNode[]>(`/categories/tree?website_id=${websiteId}`);
}

export function getCategorySummary(websiteId: string) {
  return api.get<CategorySummary>(`/categories/summary?website_id=${websiteId}`);
}

export function createCategory(body: CategoryCreateBody) {
  return api.post<CategoryRow>(`/categories`, body);
}

export function updateCategory(categoryId: string, body: CategoryUpdateBody) {
  return api.patch<CategoryRow>(`/categories/${categoryId}`, body);
}

export function moveCategory(categoryId: string, newParentId: string | null) {
  return api.post<CategoryRow>(`/categories/${categoryId}/move`, {
    new_parent_id: newParentId,
  });
}

export function deleteCategory(categoryId: string) {
  return api.delete<CategoryDeleteResult>(`/categories/${categoryId}`);
}

export function importWordpressCategories(websiteId: string) {
  return api.post<CategoryImportResult>(
    `/categories/import/wordpress?website_id=${websiteId}`,
    {}
  );
}
Now let me read the full internal-links page to copy the exact structure (loading skeleton, empty state, toast patterns, header) for the categories page.

Read C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\websites\[id]\internal-links\page.tsx
Let me see the rest — the render section with loading/empty/error states and formatNumberFa helper.

Read C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\websites\[id]\internal-links\page.tsx (lines 131-250)
I have the pattern. Let me check the formatNumberFa and labelFa helpers in insights.ts quickly, then build the categories page.

Grep "export function (formatNumberFa|labelFa|formatDateFa)" (in C:\Users\Administrator\Desktop\SEO\frontend\lib\insights.ts)
23 lines of output
Now I'll build the categories page. It's a tree view with inline add/edit/delete/move and a WordPress import button. I'll write it in chunks.

Write C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\websites\[id]\categories\page.tsx
231 lines
"use client";

/**
 * Site-structure (categories) workspace.
 *
 * One website, one materialised tree. The backend returns children already
 * nested and sorted (sort_order, then name); we flatten to rows carrying depth
 * and indent by depth. Add / rename / delete / move are inline — no modal
 * component exists in this project, so an "add child" row expands under its
 * parent and the edit form replaces a row in place, matching how the rest of
 * the app handles forms.
 *
 * Every hook runs before any conditional return. A hook placed after an early
 * return reorders the hook list between renders and React rejects it — that has
 * broken a page in this codebase, so the "no website" guard lives inside JSX.
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import {
  getCategoryTree,
  getCategorySummary,
  createCategory,
  updateCategory,
  moveCategory,
  deleteCategory,
  importWordpressCategories,
  flattenTree,
  CATEGORY_SOURCE_LABELS_FA,
  type CategoryNode,
  type CategorySummary,
} from "@/lib/categories";
import { formatNumberFa, labelFa } from "@/lib/insights";
import {
  AlertCircle,
  ChevronLeft,
  CornerDownLeft,
  Download,
  FolderTree,
  Layers,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  X,
} from "lucide-react";
import toast from "react-hot-toast";

export default function WebsiteCategoriesPage() {
  const params = useParams();
  const websiteId = params.id as string;

  const [tree, setTree] = useState<CategoryNode[]>([]);
  const [summary, setSummary] = useState<CategorySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Inline form state. `addUnder` is a parent id ("" = new root); `editingId`
  // is the row being renamed. Only one of the two is active at a time.
  const [addUnder, setAddUnder] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [nameDraft, setNameDraft] = useState("");
  const [descDraft, setDescDraft] = useState("");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!websiteId) return;
    setLoading(true);
    setError(null);
    try {
      const [t, s] = await Promise.all([
        getCategoryTree(websiteId),
        getCategorySummary(websiteId),
      ]);
      setTree(Array.isArray(t) ? t : []);
      setSummary(s);
    } catch (err: any) {
      setError(
        err instanceof ApiError ? err.message : "خطا در دریافت ساختار دسته‌ها"
      );
      setTree([]);
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    load();
  }, [load]);

  const rows = useMemo(() => flattenTree(tree), [tree]);

  const resetForm = () => {
    setAddUnder(null);
    setEditingId(null);
    setNameDraft("");
    setDescDraft("");
  };

  const openAdd = (parentId: string | null) => {
    resetForm();
    setAddUnder(parentId ?? "");
  };

  const openEdit = (node: CategoryNode) => {
    resetForm();
    setEditingId(node.id);
    setNameDraft(node.name);
    setDescDraft(node.description ?? "");
  };

  const submitCreate = async () => {
    const name = nameDraft.trim();
    if (!name) {
      toast.error("نام دسته را وارد کنید");
      return;
    }
    setSaving(true);
    try {
      await createCategory({
        website_id: websiteId,
        parent_id: addUnder ? addUnder : null,
        name,
        description: descDraft.trim() || null,
      });
      toast.success("دسته جدید ساخته شد");
      resetForm();
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در ساخت دسته"
      );
    } finally {
      setSaving(false);
    }
  };

  const submitEdit = async () => {
    const name = nameDraft.trim();
    if (!name || !editingId) {
      toast.error("نام دسته را وارد کنید");
      return;
    }
    setSaving(true);
    try {
      await updateCategory(editingId, {
        name,
        description: descDraft.trim() || null,
      });
      toast.success("دسته ویرایش شد");
      resetForm();
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در ویرایش دسته"
      );
    } finally {
      setSaving(false);
    }
  };

  const handleMoveToRoot = async (node: CategoryNode) => {
    if (node.parent_id === null) return;
    setBusyId(node.id);
    try {
      await moveCategory(node.id, null);
      toast.success("دسته به ریشه منتقل شد");
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در انتقال دسته"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (node: CategoryNode) => {
    const childCount = node.children?.length ?? 0;
    const msg =
      childCount > 0
        ? `«${node.name}» و همه زیردسته‌هایش حذف شوند؟`
        : `«${node.name}» حذف شود؟`;
    if (!window.confirm(msg)) return;
    setBusyId(node.id);
    try {
      const res = await deleteCategory(node.id);
      toast.success(`${formatNumberFa(res.deleted)} دسته حذف شد`);
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در حذف دسته"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleImport = async () => {
    setImporting(true);
    setError(null);
    try {
      const res = await importWordpressCategories(websiteId);
      toast.success(
        `درون‌ریزی وردپرس: ${formatNumberFa(res.created)} جدید، ${formatNumberFa(
          res.updated
        )} بروزرسانی، ${formatNumberFa(res.skipped)} رد‌شده`
      );
      await load();
    } catch (err: any) {
      const message =
        err instanceof ApiError
          ? err.message
          : "خطا در درون‌ریزی دسته‌های وردپرس";
      setError(message);
      toast.error(message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* PLACEHOLDER_BODY */}
    </div>
  );
}
Now the render body. I'll replace the placeholder with the header, summary cards, and tree.

Edit C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\websites\[id]\categories\page.tsx
Added 302 lines
Now add the categories nav tab. I'll place it after "content" and before "internal-links" so structure/content/links flow together.

Edit C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\websites\[id]\layout.tsx
Added 5 lines
c:\Users\Administrator\Desktop\SEO\ROADMAP.md
چیشد اتصال قطع شد
اتصال برقرار است، مشکلی نیست. Categories کامل شد و ROADMAP تیک خورد. الان وسط گام ۳ (Content Calendar) هستم. ادامه می‌دهم.

اول اسکیمای کامل تقویم و راوترش را می‌خوانم تا فیلدها را دقیق دربیارم.

Read C:\Users\Administrator\Desktop\SEO\backend\app\schemas\calendar.py
Let me check the exact status/priority/source vocabularies and the router response envelope.

Bash Read calendar model vocab constants
IN
cd "C:/Users/Administrator/Desktop/SEO/backend" && grep -n "CALENDAR_ENTRY_STATUSES\|CALENDAR_ENTRY_PRIORITIES\|CALENDAR_ENTRY_SOURCES" app/models/calendar.py | head -20

OUT
37:CALENDAR_ENTRY_STATUSES = (
46:CALENDAR_ENTRY_PRIORITIES = ("low", "normal", "high", "urgent")
51:CALENDAR_ENTRY_SOURCES = ("manual", "ai_auto")
122:    "CALENDAR_ENTRY_STATUSES",
123:    "CALENDAR_ENTRY_PRIORITIES",
124:    "CALENDAR_ENTRY_SOURCES",
Read C:\Users\Administrator\Desktop\SEO\backend\app\models\calendar.py (lines 38-49)
Now let me check the router response envelope quickly (list endpoint returns {data, meta}).

Read C:\Users\Administrator\Desktop\SEO\backend\app\api\v1\calendar.py (lines 96-145)
The list returns {data, meta} but api-client unwraps only .data — fine, I'll use the board view for kanban. Let me confirm the board/auto-schedule/move endpoint shapes.

Read C:\Users\Administrator\Desktop\SEO\backend\app\api\v1\calendar.py (lines 180-239)
I have everything. Now I'll build lib/calendar.ts:

Write C:\Users\Administrator\Desktop\SEO\frontend\lib\calendar.ts
166 lines
import { api } from "@/lib/api-client";

// ---------------------------------------------------------------- vocabularies

/** Mirrors CALENDAR_ENTRY_STATUSES in backend/app/models/calendar.py (order matters). */
export const CALENDAR_STATUSES = [
  "planned",
  "in_progress",
  "ready",
  "scheduled",
  "published",
  "cancelled",
] as const;
export type CalendarStatus = (typeof CALENDAR_STATUSES)[number];

export const CALENDAR_STATUS_LABELS_FA: Record<string, string> = {
  planned: "برنامه‌ریزی‌شده",
  in_progress: "در حال تولید",
  ready: "آماده بازبینی",
  scheduled: "زمان‌بندی‌شده",
  published: "منتشر شده",
  cancelled: "لغو شده",
};

/** Tailwind classes per status, for column headers and chips. */
export const CALENDAR_STATUS_STYLE: Record<string, string> = {
  planned: "bg-slate-500/15 text-slate-300 border-slate-500/30",
  in_progress: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  ready: "bg-sky-500/15 text-sky-300 border-sky-500/30",
  scheduled: "bg-indigo-500/15 text-indigo-300 border-indigo-500/30",
  published: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  cancelled: "bg-red-500/15 text-red-300 border-red-500/30",
};

export const CALENDAR_PRIORITIES = ["low", "normal", "high", "urgent"] as const;
export type CalendarPriority = (typeof CALENDAR_PRIORITIES)[number];

export const CALENDAR_PRIORITY_LABELS_FA: Record<string, string> = {
  low: "کم",
  normal: "معمولی",
  high: "زیاد",
  urgent: "فوری",
};

export const CALENDAR_PRIORITY_STYLE: Record<string, string> = {
  low: "bg-white/5 text-muted-foreground",
  normal: "bg-sky-500/15 text-sky-300",
  high: "bg-amber-500/15 text-amber-300",
  urgent: "bg-red-500/15 text-red-300",
};

export const CALENDAR_SOURCE_LABELS_FA: Record<string, string> = {
  manual: "دستی",
  ai_auto: "زمان‌بندی AI",
};

// -------------------------------------------------------------------- entities

/** Mirrors CalendarEntryRead in backend/app/schemas/calendar.py. */
export interface CalendarEntry {
  id: string;
  organization_id: string;
  website_id: string;
  title: string;
  brief_id: string | null;
  article_id: string | null;
  opportunity_id: string | null;
  status: CalendarStatus | string;
  priority: CalendarPriority | string;
  source: string;
  scheduled_for: string | null;
  deadline: string | null;
  published_at: string | null;
  assigned_to: string | null;
  target_keyword: string | null;
  notes: string | null;
  details: Record<string, any>;
  created_at: string;
  updated_at: string;
}

/** Mirrors CalendarBoardView: columns keyed by status. */
export interface CalendarBoardView {
  columns: Record<string, CalendarEntry[]>;
}

export interface CalendarSummary {
  by_status: Record<string, number>;
  overdue: number;
  due_this_week: number;
  unassigned: number;
}

export interface CalendarAutoScheduleResult {
  website_id: string;
  created: number;
  skipped: number;
  scheduled_through: string | null;
}

// ----------------------------------------------------------------- write bodies

export interface CalendarEntryCreateBody {
  website_id: string;
  title: string;
  status?: CalendarStatus;
  priority?: CalendarPriority;
  scheduled_for?: string | null;
  deadline?: string | null;
  target_keyword?: string | null;
  notes?: string | null;
}

export interface CalendarEntryUpdateBody {
  title?: string;
  status?: CalendarStatus;
  priority?: CalendarPriority;
  scheduled_for?: string | null;
  deadline?: string | null;
  target_keyword?: string | null;
  notes?: string | null;
}

// ----------------------------------------------------------------------- calls

export function getCalendarBoard(websiteId: string) {
  return api.get<CalendarBoardView>(`/calendar/board?website_id=${websiteId}`);
}

export function getCalendarSummary(websiteId: string) {
  return api.get<CalendarSummary>(`/calendar/summary?website_id=${websiteId}`);
}

export function createCalendarEntry(body: CalendarEntryCreateBody) {
  return api.post<CalendarEntry>(`/calendar`, body);
}

export function updateCalendarEntry(
  entryId: string,
  body: CalendarEntryUpdateBody
) {
  return api.patch<CalendarEntry>(`/calendar/${entryId}`, body);
}

/** Board drag: change status and/or scheduled date only. */
export function moveCalendarEntry(
  entryId: string,
  body: { status?: CalendarStatus; scheduled_for?: string | null }
) {
  return api.post<CalendarEntry>(`/calendar/${entryId}/move`, body);
}

export function deleteCalendarEntry(entryId: string) {
  return api.delete<{ deleted: boolean; id: string }>(`/calendar/${entryId}`);
}

export function autoScheduleFromOpportunities(
  websiteId: string,
  maxEntries = 10
) {
  return api.post<CalendarAutoScheduleResult>(
    `/calendar/auto-schedule?website_id=${websiteId}`,
    { max_entries: maxEntries }
  );
}
Now the calendar page — a kanban board with columns by status, an auto-schedule button, an inline create form, and per-card status move + delete. Let me write it.

Write C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\websites\[id]\calendar\page.tsx
501 lines
"use client";

/**
 * Content calendar workspace — kanban board over one website.
 *
 * Columns are the canonical statuses (planned → published, plus cancelled). The
 * backend returns them already keyed by status and in order, empty columns
 * included, so the board never has to invent a column list client-side.
 *
 * There is no drag-and-drop library in this project; moving a card between
 * statuses is done with the ‹ › buttons on each card, which call the same
 * /move endpoint a drag would. "Auto-schedule" turns the highest-impact open
 * opportunities into planned slots via the AI scheduler.
 *
 * Every hook runs before any conditional return — a hook after an early return
 * reorders the hook list and React rejects it (has broken a page here before).
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { ApiError } from "@/lib/api-client";
import {
  getCalendarBoard,
  getCalendarSummary,
  createCalendarEntry,
  moveCalendarEntry,
  deleteCalendarEntry,
  CALENDAR_STATUSES,
  CALENDAR_STATUS_LABELS_FA,
  CALENDAR_STATUS_STYLE,
  CALENDAR_PRIORITY_LABELS_FA,
  CALENDAR_PRIORITY_STYLE,
  CALENDAR_SOURCE_LABELS_FA,
  autoScheduleFromOpportunities,
  type CalendarBoardView,
  type CalendarEntry,
  type CalendarSummary,
  type CalendarStatus,
} from "@/lib/calendar";
import { formatNumberFa, formatDateFa, labelFa } from "@/lib/insights";
import {
  AlertCircle,
  AlertTriangle,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Clock,
  Plus,
  RefreshCw,
  Sparkles,
  Target,
  Trash2,
  UserX,
  X,
} from "lucide-react";
import toast from "react-hot-toast";

export default function WebsiteCalendarPage() {
  const params = useParams();
  const websiteId = params.id as string;

  const [board, setBoard] = useState<CalendarBoardView | null>(null);
  const [summary, setSummary] = useState<CalendarSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  // Inline create form
  const [adding, setAdding] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [keywordDraft, setKeywordDraft] = useState("");
  const [dateDraft, setDateDraft] = useState("");
  const [priorityDraft, setPriorityDraft] = useState<string>("normal");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    if (!websiteId) return;
    setLoading(true);
    setError(null);
    try {
      const [b, s] = await Promise.all([
        getCalendarBoard(websiteId),
        getCalendarSummary(websiteId),
      ]);
      setBoard(b);
      setSummary(s);
    } catch (err: any) {
      setError(
        err instanceof ApiError ? err.message : "خطا در دریافت تقویم محتوا"
      );
      setBoard(null);
    } finally {
      setLoading(false);
    }
  }, [websiteId]);

  useEffect(() => {
    load();
  }, [load]);

  const totalEntries = useMemo(() => {
    if (!board) return 0;
    return Object.values(board.columns).reduce(
      (acc, col) => acc + (col?.length ?? 0),
      0
    );
  }, [board]);

  const isEmpty = !loading && !error && totalEntries === 0;

  const resetForm = () => {
    setAdding(false);
    setTitleDraft("");
    setKeywordDraft("");
    setDateDraft("");
    setPriorityDraft("normal");
  };

  const submitCreate = async () => {
    const title = titleDraft.trim();
    if (title.length < 3) {
      toast.error("عنوان باید حداقل ۳ نویسه باشد");
      return;
    }
    setSaving(true);
    try {
      await createCalendarEntry({
        website_id: websiteId,
        title,
        priority: priorityDraft as any,
        target_keyword: keywordDraft.trim() || null,
        // datetime-local yields "YYYY-MM-DDTHH:mm"; send as-is, backend parses ISO.
        scheduled_for: dateDraft ? new Date(dateDraft).toISOString() : null,
      });
      toast.success("اسلات محتوا ساخته شد");
      resetForm();
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در ساخت اسلات محتوا"
      );
    } finally {
      setSaving(false);
    }
  };

  const moveStatus = async (entry: CalendarEntry, direction: -1 | 1) => {
    const idx = CALENDAR_STATUSES.indexOf(entry.status as CalendarStatus);
    if (idx === -1) return;
    const nextIdx = idx + direction;
    if (nextIdx < 0 || nextIdx >= CALENDAR_STATUSES.length) return;
    const nextStatus = CALENDAR_STATUSES[nextIdx];
    setBusyId(entry.id);
    try {
      await moveCalendarEntry(entry.id, { status: nextStatus });
      toast.success(
        `به «${labelFa(CALENDAR_STATUS_LABELS_FA, nextStatus)}» منتقل شد`
      );
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در جابجایی وضعیت"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (entry: CalendarEntry) => {
    if (!window.confirm(`اسلات «${entry.title}» حذف شود؟`)) return;
    setBusyId(entry.id);
    try {
      await deleteCalendarEntry(entry.id);
      toast.success("اسلات حذف شد");
      await load();
    } catch (err: any) {
      toast.error(err instanceof ApiError ? err.message : "خطا در حذف اسلات");
    } finally {
      setBusyId(null);
    }
  };

  const handleAutoSchedule = async () => {
    setScheduling(true);
    setError(null);
    try {
      const res = await autoScheduleFromOpportunities(websiteId, 10);
      toast.success(
        `زمان‌بندی هوشمند: ${formatNumberFa(res.created)} اسلات جدید از فرصت‌ها${
          res.skipped ? `، ${formatNumberFa(res.skipped)} رد‌شده` : ""
        }`
      );
      await load();
    } catch (err: any) {
      const message =
        err instanceof ApiError
          ? err.message
          : "خطا در زمان‌بندی خودکار از فرصت‌ها";
      setError(message);
      toast.error(message);
    } finally {
      setScheduling(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">تقویم محتوا</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            برنامه‌ریزی و پیگیری تولید محتوا به‌صورت کانبان؛ زمان‌بندی خودکار بر
            اساس فرصت‌های رشد
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setAdding((v) => !v)}
            disabled={!websiteId}
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-sky-500 to-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-sky-500/20 transition hover:from-sky-600 hover:to-indigo-700 disabled:opacity-50"
          >
            <Plus className="h-4 w-4" />
            اسلات جدید
          </button>
          <button
            onClick={handleAutoSchedule}
            disabled={scheduling || !websiteId}
            className="inline-flex items-center gap-2 rounded-xl border border-purple-500/30 bg-purple-500/10 px-4 py-2.5 text-xs font-semibold text-purple-200 transition hover:bg-purple-500/20 disabled:opacity-50"
          >
            {scheduling ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {scheduling ? "در حال زمان‌بندی..." : "زمان‌بندی خودکار با AI"}
          </button>
        </div>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          {
            label: "کل اسلات‌ها",
            value: totalEntries,
            icon: CalendarDays,
            tone: "text-sky-400",
          },
          {
            label: "عقب‌افتاده",
            value: summary?.overdue,
            icon: AlertTriangle,
            tone: "text-red-400",
          },
          {
            label: "این هفته",
            value: summary?.due_this_week,
            icon: Clock,
            tone: "text-amber-400",
          },
          {
            label: "بدون مسئول",
            value: summary?.unassigned,
            icon: UserX,
            tone: "text-muted-foreground",
          },
        ].map((card) => {
          const Icon = card.icon;
          return (
            <div
              key={card.label}
              className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs font-medium text-muted-foreground">
                  {card.label}
                </span>
                <Icon className={`h-4 w-4 ${card.tone}`} />
              </div>
              <p className="mt-2 text-2xl font-bold text-white">
                {formatNumberFa(card.value)}
              </p>
            </div>
          );
        })}
      </div>

      {/* Inline create form */}
      {adding && (
        <div className="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold text-sky-300">
              افزودن اسلات محتوا
            </span>
            <button
              onClick={resetForm}
              className="rounded-lg p-1 text-muted-foreground transition hover:bg-white/10 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <input
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              autoFocus
              placeholder="عنوان محتوا"
              className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none placeholder:text-muted-foreground/60 focus:border-sky-500/50 sm:col-span-2"
            />
            <input
              value={keywordDraft}
              onChange={(e) => setKeywordDraft(e.target.value)}
              placeholder="کلمه کلیدی هدف (اختیاری)"
              className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none placeholder:text-muted-foreground/60 focus:border-sky-500/50"
            />
            <input
              type="datetime-local"
              value={dateDraft}
              onChange={(e) => setDateDraft(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-sky-500/50"
            />
            <select
              value={priorityDraft}
              onChange={(e) => setPriorityDraft(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-sky-500/50"
            >
              {Object.entries(CALENDAR_PRIORITY_LABELS_FA).map(([k, v]) => (
                <option key={k} value={k} className="bg-card">
                  اولویت: {v}
                </option>
              ))}
            </select>
            <div className="flex items-center justify-end gap-2 sm:col-span-2">
              <button
                onClick={resetForm}
                className="rounded-lg px-3 py-1.5 text-xs text-muted-foreground transition hover:text-white"
              >
                انصراف
              </button>
              <button
                onClick={submitCreate}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-lg bg-sky-500 px-4 py-1.5 text-xs font-semibold text-white transition hover:bg-sky-600 disabled:opacity-50"
              >
                {saving && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                ذخیره
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-300">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Board */}
      {loading ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {CALENDAR_STATUSES.map((s) => (
            <div key={s} className="space-y-3">
              <div className="h-8 animate-pulse rounded-lg bg-white/5" />
              <div className="h-24 animate-pulse rounded-xl bg-white/5" />
              <div className="h-24 animate-pulse rounded-xl bg-white/5" />
            </div>
          ))}
        </div>
      ) : isEmpty ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-white/15 p-12 text-center">
          <CalendarDays className="h-10 w-10 text-muted-foreground/50" />
          <p className="text-sm font-medium text-white">
            تقویم محتوا خالی است
          </p>
          <p className="max-w-md text-xs text-muted-foreground">
            یک اسلات دستی بسازید یا با «زمان‌بندی خودکار با AI» فرصت‌های رشد را به
            برنامه محتوا تبدیل کنید.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {CALENDAR_STATUSES.map((status) => {
            const cards = board?.columns?.[status] ?? [];
            return (
              <div key={status} className="flex flex-col gap-3">
                <div
                  className={`flex items-center justify-between rounded-lg border px-3 py-2 text-xs font-semibold ${
                    CALENDAR_STATUS_STYLE[status] ??
                    "border-white/10 bg-white/5 text-white"
                  }`}
                >
                  <span>{labelFa(CALENDAR_STATUS_LABELS_FA, status)}</span>
                  <span className="rounded-md bg-black/20 px-1.5 py-0.5">
                    {formatNumberFa(cards.length)}
                  </span>
                </div>
                <div className="flex flex-col gap-2">
                  {cards.map((entry) => {
                    const statusIdx = CALENDAR_STATUSES.indexOf(
                      entry.status as CalendarStatus
                    );
                    return (
                      <div
                        key={entry.id}
                        className="rounded-xl border border-white/10 bg-card/80 p-3 backdrop-blur-md transition hover:border-white/20"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-xs font-semibold leading-5 text-white">
                            {entry.title}
                          </p>
                          <button
                            onClick={() => handleDelete(entry)}
                            disabled={busyId === entry.id}
                            title="حذف"
                            className="shrink-0 rounded-md p-1 text-muted-foreground transition hover:bg-red-500/15 hover:text-red-400 disabled:opacity-50"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>

                        {entry.target_keyword && (
                          <div className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
                            <Target className="h-3 w-3 shrink-0" />
                            <span className="truncate">
                              {entry.target_keyword}
                            </span>
                          </div>
                        )}

                        <div className="mt-2 flex flex-wrap items-center gap-1.5">
                          <span
                            className={`rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
                              CALENDAR_PRIORITY_STYLE[entry.priority] ??
                              "bg-white/5 text-muted-foreground"
                            }`}
                          >
                            {labelFa(CALENDAR_PRIORITY_LABELS_FA, entry.priority)}
                          </span>
                          {entry.source === "ai_auto" && (
                            <span className="inline-flex items-center gap-1 rounded-md bg-purple-500/15 px-1.5 py-0.5 text-[10px] text-purple-300">
                              <Sparkles className="h-2.5 w-2.5" />
                              {labelFa(CALENDAR_SOURCE_LABELS_FA, entry.source)}
                            </span>
                          )}
                        </div>

                        {entry.scheduled_for && (
                          <div className="mt-2 flex items-center gap-1 text-[10px] text-muted-foreground">
                            <CalendarDays className="h-3 w-3 shrink-0" />
                            <span>{formatDateFa(entry.scheduled_for)}</span>
                          </div>
                        )}

                        {/* Status move controls (no DnD lib in project) */}
                        <div className="mt-2 flex items-center justify-between border-t border-white/5 pt-2">
                          <button
                            onClick={() => moveStatus(entry, -1)}
                            disabled={busyId === entry.id || statusIdx <= 0}
                            title="مرحله قبل"
                            className="rounded-md p-1 text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-30"
                          >
                            <ChevronRight className="h-4 w-4" />
                          </button>
                          <span className="text-[10px] text-muted-foreground">
                            جابجایی وضعیت
                          </span>
                          <button
                            onClick={() => moveStatus(entry, 1)}
                            disabled={
                              busyId === entry.id ||
                              statusIdx >= CALENDAR_STATUSES.length - 1
                            }
                            title="مرحله بعد"
                            className="rounded-md p-1 text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-30"
                          >
                            <ChevronLeft className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                  {cards.length === 0 && (
                    <div className="rounded-xl border border-dashed border-white/10 p-4 text-center text-[10px] text-muted-foreground/60">
                      خالی
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
Now add the calendar navTab. I'll place it right after "categories" (structure → calendar → content flows naturally).

Edit C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\websites\[id]\layout.tsx
Added 5 lines
Edit C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\websites\[id]\layout.tsx
Added 1 line
Calendar done. Update ROADMAP and move to Reports.

Edit C:\Users\Administrator\Desktop\SEO\ROADMAP.md
Added 9 lines
Update Todos

گام ۱: رفع دو صفحه orphan

گام ۲: Categories

گام ۳: Content Calendar

گام ۴: Reports — ساخت lib/reports.ts + صفحه گزارش‌ها + navigation

گام ۵: Content Versioning

به‌روزرسانی نهایی ROADMAP.md
گام ۴: Reports. اسکیمای reports و راوتر را می‌خوانم. این یکی سطح سازمان است (website_id اختیاری)، پس صفحه‌اش را در (dashboard)/reports/ می‌گذارم و به navigation اصلی اضافه می‌کنم.

قبل از نوشتن، مطمئن می‌شومگام ۳ (تقویم) کامل شد. حالا گام ۴: Reports. اسکیمای Reports و راوترش را می‌خوانم.

Read C:\Users\Administrator\Desktop\SEO\backend\app\schemas\reports.py
Now the router — let me confirm exact paths, share result shape, CSV export path, and the share_token→public URL. I already have the endpoint list from the earlier agent, but let me verify the share endpoint response and how the public token is exposed.

Read C:\Users\Administrator\Desktop\SEO\backend\app\api\v1\reports.py (lines 149-198)
Let me check the list/generate/templates endpoint shapes and the report_type templates values.

Read C:\Users\Administrator\Desktop\SEO\backend\app\api\v1\reports.py (lines 41-110)
ادامه می‌دم. الان Reports را می‌سازم (گام ۴). فایل‌های لازم را می‌خونم و بعد lib/reports.ts و صفحه را می‌سازم.

قبلش بذار وضعیت کارهای قبلی را جمع‌بندی کنم تا بدونم دقیقاً کجاییم:

تمام‌شده تا الان:

گام ۱ (وایرینگ Internal Links + Agent Activity به ناوبری) ✅
گام ۲ (Categories: lib/categories.ts + صفحه + navTab) ✅
گام ۳ (Content Calendar: lib/calendar.ts + صفحه + navTab) ✅
الان روی گام ۴ (Reports) هستم. راوتر و اسکیمای Reports را خوندم. بذار باقی جزئیات راوتر (اندپوینت get تکی و generate تا آخر) و الگوی یک صفحه سطح‌سازمانی موجود مثل approvals را ببینم تا صفحه Reports را درست بسازم.

Read C:\Users\Administrator\Desktop\SEO\backend\app\api\v1\reports.py (lines 110-149)
I have all endpoint shapes. The CSV export is a direct download (not JSON), so I need a helper that builds an authenticated blob download since api-client sends the auth header. Let me check the report templates default types and check how a similar org-level page (approvals) is structured for consistency.

Read C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\approvals\page.tsx (lines 2-71)
No response requested.

c:\Users\Administrator\Desktop\SEO\ROADMAP.md
داری اتم غنی میکنی کجای کاری و چقدر مونده فکر کنم گیر کردی ؟
گیر نکردم، فقط داشتم اسکیمای Reports رو دقیق می‌خوندم تا فرم درست بسازم. الان می‌سازم. وضعیت واقعی:

گام ۱ (وایرینگ ناوبری) ✅
گام ۲ (Categories) ✅
گام ۳ (Content Calendar) ✅
گام ۴ (Reports) ← الان روی این‌ام
گام ۵ (Content Versioning) باقی مونده
به‌روزرسانی نهایی ROADMAP باقی مونده
الان lib و صفحه Reports رو می‌سازم.

Write C:\Users\Administrator\Desktop\SEO\frontend\lib\reports.ts
190 lines
import { api, ApiError } from "@/lib/api-client";

// ---------------------------------------------------------------- vocabularies

/** Mirrors REPORT_TYPES in backend/app/models/reports.py. */
export const REPORT_TYPES = ["weekly", "monthly", "executive", "custom"] as const;
export type ReportType = (typeof REPORT_TYPES)[number];

export const REPORT_TYPE_LABELS_FA: Record<string, string> = {
  weekly: "هفتگی",
  monthly: "ماهانه",
  executive: "اجرایی (خلاصه مدیریتی)",
  custom: "دلخواه",
};

/** Mirrors REPORT_STATUSES in backend/app/models/reports.py. Terminal: ready/failed. */
export const REPORT_STATUS_LABELS_FA: Record<string, string> = {
  pending: "در انتظار",
  generating: "در حال تولید",
  ready: "آماده",
  failed: "ناموفق",
};

export const REPORT_STATUS_STYLE: Record<string, string> = {
  pending: "bg-slate-500/15 text-slate-300",
  generating: "bg-amber-500/15 text-amber-300",
  ready: "bg-emerald-500/15 text-emerald-300",
  failed: "bg-red-500/15 text-red-300",
};

export function isReportTerminal(status: string): boolean {
  return status === "ready" || status === "failed";
}

// -------------------------------------------------------------------- entities

export interface ReportListItem {
  id: string;
  website_id: string | null;
  report_type: ReportType | string;
  status: string;
  title: string;
  period_start: string;
  period_end: string;
  generated_at: string | null;
  metrics_snapshot: Record<string, any>;
  share_enabled: boolean;
  view_count: number;
  created_at: string;
}

export interface ReportRead extends ReportListItem {
  organization_id: string;
  generated_by: string | null;
  content: Record<string, any>;
  share_expires_at: string | null;
  error_message: string | null;
  updated_at: string;
}

export interface ReportSummaryTypeCount {
  report_type: string;
  count: number;
  latest_report_id: string | null;
  latest_generated_at: string | null;
}

export interface ReportSummary {
  total: number;
  by_type: ReportSummaryTypeCount[];
  ready: number;
  generating: number;
  failed: number;
}

export interface ReportTemplateSection {
  key: string;
  title_fa: string;
}

export interface ReportTemplate {
  report_type: string;
  title_fa: string;
  description_fa: string;
  default_period_days: number;
  sections: ReportTemplateSection[];
}

export interface ReportShareResult {
  share_token: string;
  share_enabled: boolean;
  share_expires_at: string | null;
}

// ----------------------------------------------------------------- write bodies

export interface ReportGenerateBody {
  report_type: ReportType;
  title?: string | null;
  period_start: string; // ISO date, "YYYY-MM-DD"
  period_end: string;
  website_id?: string | null;
}

// ----------------------------------------------------------------------- calls

export function listReports(params: {
  website_id?: string;
  report_type?: string;
  status?: string;
  limit?: number;
  offset?: number;
}) {
  const qs = new URLSearchParams();
  if (params.website_id) qs.set("website_id", params.website_id);
  if (params.report_type) qs.set("report_type", params.report_type);
  if (params.status) qs.set("status", params.status);
  if (params.limit !== undefined) qs.set("limit", String(params.limit));
  if (params.offset !== undefined) qs.set("offset", String(params.offset));
  return api.get<ReportListItem[]>(`/reports?${qs.toString()}`);
}

export function getReportSummary() {
  return api.get<ReportSummary>(`/reports/summary`);
}

export function getReportTemplates() {
  return api.get<ReportTemplate[]>(`/reports/templates`);
}

export function generateReport(body: ReportGenerateBody) {
  return api.post<ReportRead>(`/reports/generate`, body);
}

export function getReport(reportId: string) {
  return api.get<ReportRead>(`/reports/${reportId}`);
}

export function shareReport(reportId: string, ttlDays?: number) {
  return api.post<ReportShareResult>(`/reports/${reportId}/share`, {
    ttl_days: ttlDays ?? null,
  });
}

export function revokeReportShare(reportId: string) {
  return api.delete<ReportShareResult>(`/reports/${reportId}/share`);
}

export function deleteReport(reportId: string) {
  return api.delete<{ deleted: boolean }>(`/reports/${reportId}`);
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

/**
 * CSV export is a raw file download, not a JSON envelope, so it bypasses the
 * shared `request()` helper and does its own auth header + blob handling.
 */
export async function downloadReportCsv(reportId: string, filename?: string) {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  const orgId =
    typeof window !== "undefined" ? localStorage.getItem("current_org_id") : null;

  const res = await fetch(`${API_URL}/reports/${reportId}/export.csv`, {
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(orgId ? { "X-Organization-Id": orgId } : {}),
    },
  });
  if (!res.ok) {
    throw new ApiError(res.status, "خطا در دریافت خروجی CSV گزارش");
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || `report-${reportId}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

export function publicReportUrl(shareToken: string): string {
  // Points at the frontend's own public viewer route, not the API host.
  if (typeof window === "undefined") return `/reports/public/${shareToken}`;
  return `${window.location.origin}/reports/public/${shareToken}`;
}
Let me check the report content shape briefly so the public page renders something meaningful, not just raw JSON.

Grep "content\[.sections.\]|"sections"|_SECTIONS_BY_TYPE|def generate_report|def build_print_payload" (in C:\Users\Administrator\Desktop\SEO\backend\app\services\report_service.py)
58 lines of output
Read C:\Users\Administrator\Desktop\SEO\backend\app\services\report_service.py (lines 1156-1200)
Grep "def _build_overview_section|"has_data"|"rows":|"summary":|"key": ?"|SECTION_TITLES_FA" (in C:\Users\Administrator\Desktop\SEO\backend\app\services\report_service.py)
41 lines of output
Read C:\Users\Administrator\Desktop\SEO\backend\app\services\report_service.py (lines 201-245)
برای صفحه public لازم است بیرون از گروه (dashboard) باشد چون آن گروه اگر user نباشد ریدایرکت به لاگین می‌کند. باید مسیر جدید در app/reports/public/[token]/page.tsx بسازم (خارج از گروه‌های auth/dashboard).

Bash Check top-level app directory structure for route groups
IN
ls "C:/Users/Administrator/Desktop/SEO/frontend/app"

OUT
(auth)
(dashboard)
globals.css
layout.tsx
Good, confirms only two route groups plus a root layout — no top-level pages that would need auth. I'll create frontend/app/reports/public/[token]/page.tsx as a standalone public page.

Read C:\Users\Administrator\Desktop\SEO\frontend\app\layout.tsx
خوب، بدون AuthProvider مشکلی ایجاد نمی‌کند چون این کامپوننت فقط context فراهم می‌کند، ریدایرکت در (dashboard)/layout.tsx است که این صفحه جدید داخلش نیست. حالا صفحه اصلی Reports (سازمانی) را می‌سازم.

Write C:\Users\Administrator\Desktop\SEO\frontend\app\(dashboard)\reports\page.tsx
457 lines
"use client";

/**
 * Reports — organization level (a report can span every website or one).
 *
 * There is no server-side PDF renderer in this project (see report_service's
 * own docstring) — export is CSV, or the browser's print-to-PDF over the
 * on-screen view. Sharing mints a token-based public link that needs no auth;
 * the public viewer lives outside the (dashboard) route group at
 * /reports/public/[token] so it never hits the login redirect.
 *
 * Every hook runs before any conditional return — a hook after an early
 * return reorders the hook list and React rejects it (has broken a page here
 * before).
 */

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useAuth } from "@/context/auth-context";
import { ApiError } from "@/lib/api-client";
import {
  listReports,
  getReportSummary,
  getReportTemplates,
  generateReport,
  shareReport,
  revokeReportShare,
  deleteReport,
  downloadReportCsv,
  publicReportUrl,
  isReportTerminal,
  REPORT_TYPE_LABELS_FA,
  REPORT_STATUS_LABELS_FA,
  REPORT_STATUS_STYLE,
  type ReportListItem,
  type ReportSummary,
  type ReportTemplate,
} from "@/lib/reports";
import { formatNumberFa, formatDateFa, labelFa } from "@/lib/insights";
import {
  AlertCircle,
  Copy,
  Download,
  FileBarChart2,
  Globe,
  Link2,
  Plus,
  RefreshCw,
  ShieldOff,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import toast from "react-hot-toast";

const STATUS_TABS: { id: string; label: string }[] = [
  { id: "all", label: "همه" },
  { id: "ready", label: "آماده" },
  { id: "generating", label: "در حال تولید" },
  { id: "pending", label: "در انتظار" },
  { id: "failed", label: "ناموفق" },
];

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function daysAgoIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const { websites } = useAuth();

  const [reports, setReports] = useState<ReportListItem[]>([]);
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [busyId, setBusyId] = useState<string | null>(null);

  // Generate form
  const [generating, setGenerating] = useState(false);
  const [typeDraft, setTypeDraft] = useState("weekly");
  const [websiteDraft, setWebsiteDraft] = useState<string>("");
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [list, sum, tpl] = await Promise.all([
        listReports({
          status: statusFilter === "all" ? undefined : statusFilter,
          limit: 100,
        }),
        getReportSummary(),
        getReportTemplates(),
      ]);
      setReports(Array.isArray(list) ? list : []);
      setSummary(sum);
      setTemplates(Array.isArray(tpl) ? tpl : []);
    } catch (err: any) {
      setError(err instanceof ApiError ? err.message : "خطا در دریافت گزارش‌ها");
      setReports([]);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const isEmpty = !loading && !error && reports.length === 0;

  const activeTemplate = useMemo(
    () => templates.find((t) => t.report_type === typeDraft) || null,
    [templates, typeDraft]
  );

  const submitGenerate = async () => {
    const days = activeTemplate?.default_period_days ?? 7;
    setCreating(true);
    try {
      await generateReport({
        report_type: typeDraft as any,
        period_start: daysAgoIso(days - 1),
        period_end: todayIso(),
        website_id: websiteDraft || null,
      });
      toast.success("تولید گزارش شروع شد");
      setGenerating(false);
      setWebsiteDraft("");
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در تولید گزارش"
      );
    } finally {
      setCreating(false);
    }
  };

  const handleShare = async (report: ReportListItem) => {
    setBusyId(report.id);
    try {
      const res = await shareReport(report.id);
      const url = publicReportUrl(res.share_token);
      await navigator.clipboard.writeText(url).catch(() => {});
      toast.success("لینک عمومی ساخته و در کلیپ‌بورد کپی شد");
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در ساخت لینک اشتراک‌گذاری"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleRevoke = async (report: ReportListItem) => {
    setBusyId(report.id);
    try {
      await revokeReportShare(report.id);
      toast.success("لینک عمومی غیرفعال شد");
      await load();
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در لغو لینک اشتراک‌گذاری"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleDownload = async (report: ReportListItem) => {
    setBusyId(report.id);
    try {
      await downloadReportCsv(report.id, `${report.title}.csv`);
    } catch (err: any) {
      toast.error(
        err instanceof ApiError ? err.message : "خطا در دریافت خروجی CSV"
      );
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (report: ReportListItem) => {
    if (!window.confirm(`گزارش «${report.title}» حذف شود؟`)) return;
    setBusyId(report.id);
    try {
      await deleteReport(report.id);
      toast.success("گزارش حذف شد");
      await load();
    } catch (err: any) {
      toast.error(err instanceof ApiError ? err.message : "خطا در حذف گزارش");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-bold text-white">گزارش‌ها</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            گزارش‌های هفتگی، ماهانه و اجرایی؛ خروجی CSV یا لینک اشتراک‌گذاری عمومی
          </p>
        </div>
        <button
          onClick={() => setGenerating((v) => !v)}
          className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-500 to-fuchsia-600 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-violet-500/20 transition hover:from-violet-600 hover:to-fuchsia-700"
        >
          <Plus className="h-4 w-4" />
          گزارش جدید
        </button>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[
          { label: "کل گزارش‌ها", value: summary?.total, tone: "text-violet-400" },
          { label: "آماده", value: summary?.ready, tone: "text-emerald-400" },
          { label: "در حال تولید", value: summary?.generating, tone: "text-amber-400" },
          { label: "ناموفق", value: summary?.failed, tone: "text-red-400" },
        ].map((card) => (
          <div
            key={card.label}
            className="rounded-2xl border border-white/10 bg-card/80 p-5 backdrop-blur-md"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {card.label}
              </span>
              <FileBarChart2 className={`h-4 w-4 ${card.tone}`} />
            </div>
            <p className="mt-2 text-2xl font-bold text-white">
              {formatNumberFa(card.value)}
            </p>
          </div>
        ))}
      </div>

      {/* Generate form */}
      {generating && (
        <div className="rounded-2xl border border-violet-500/20 bg-violet-500/5 p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold text-violet-300">
              تولید گزارش جدید
            </span>
            <button
              onClick={() => setGenerating(false)}
              className="rounded-lg p-1 text-muted-foreground transition hover:bg-white/10 hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <select
              value={typeDraft}
              onChange={(e) => setTypeDraft(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-violet-500/50"
            >
              {Object.entries(REPORT_TYPE_LABELS_FA).map(([k, v]) => (
                <option key={k} value={k} className="bg-card">
                  {v}
                </option>
              ))}
            </select>
            <select
              value={websiteDraft}
              onChange={(e) => setWebsiteDraft(e.target.value)}
              className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-violet-500/50"
            >
              <option value="" className="bg-card">
                همه وب‌سایت‌های سازمان
              </option>
              {websites.map((w) => (
                <option key={w.id} value={w.id} className="bg-card">
                  {w.domain}
                </option>
              ))}
            </select>
            <button
              onClick={submitGenerate}
              disabled={creating}
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-violet-500 px-4 py-2 text-xs font-semibold text-white transition hover:bg-violet-600 disabled:opacity-50"
            >
              {creating ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              تولید کن
            </button>
          </div>
          {activeTemplate && (
            <p className="mt-3 text-[11px] text-muted-foreground">
              {activeTemplate.description_fa} — بازه پیش‌فرض{" "}
              {formatNumberFa(activeTemplate.default_period_days)} روز، شامل بخش‌های{" "}
              {activeTemplate.sections.map((s) => s.title_fa).join("، ")}
            </p>
          )}
        </div>
      )}

      {/* Status tabs */}
      <div className="flex flex-wrap gap-2">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setStatusFilter(tab.id)}
            className={`rounded-xl px-3.5 py-2 text-xs font-semibold transition ${
              statusFilter === tab.id
                ? "bg-primary text-primary-foreground shadow-md shadow-primary/20"
                : "border border-white/10 bg-white/5 text-muted-foreground hover:text-white"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-300">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* List */}
      {loading ? (
        <div className="space-y-2">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-20 animate-pulse rounded-xl bg-white/5" />
          ))}
        </div>
      ) : isEmpty ? (
        <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-white/15 p-12 text-center">
          <FileBarChart2 className="h-10 w-10 text-muted-foreground/50" />
          <p className="text-sm font-medium text-white">هنوز گزارشی تولید نشده</p>
          <p className="max-w-md text-xs text-muted-foreground">
            یک گزارش هفتگی، ماهانه یا اجرایی بسازید تا خلاصه عملکرد سئو در یک سند
            یک‌جا جمع شود.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {reports.map((report) => {
            const website = report.website_id
              ? websites.find((w) => w.id === report.website_id)
              : null;
            return (
              <div
                key={report.id}
                className="flex flex-col gap-3 rounded-2xl border border-white/10 bg-card/80 p-4 backdrop-blur-md sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold text-white">
                      {report.title}
                    </span>
                    <span
                      className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-medium ${
                        REPORT_STATUS_STYLE[report.status] ??
                        "bg-white/5 text-muted-foreground"
                      }`}
                    >
                      {labelFa(REPORT_STATUS_LABELS_FA, report.status)}
                    </span>
                    {report.share_enabled && (
                      <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-sky-500/15 px-1.5 py-0.5 text-[10px] text-sky-300">
                        <Link2 className="h-2.5 w-2.5" />
                        عمومی
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                    <span>
                      {labelFa(REPORT_TYPE_LABELS_FA, report.report_type)}
                    </span>
                    <span>·</span>
                    <span>
                      {formatDateFa(report.period_start)} تا{" "}
                      {formatDateFa(report.period_end)}
                    </span>
                    <span>·</span>
                    <span className="inline-flex items-center gap-1">
                      <Globe className="h-3 w-3" />
                      {website ? website.domain : "کل سازمان"}
                    </span>
                    {report.view_count > 0 && (
                      <>
                        <span>·</span>
                        <span>{formatNumberFa(report.view_count)} بازدید</span>
                      </>
                    )}
                  </div>
                </div>

                <div className="flex shrink-0 items-center gap-1.5">
                  {report.status === "ready" && (
                    <>
                      <button
                        onClick={() => handleDownload(report)}
                        disabled={busyId === report.id}
                        title="دریافت CSV"
                        className="rounded-lg p-2 text-muted-foreground transition hover:bg-white/10 hover:text-white disabled:opacity-50"
                      >
                        <Download className="h-4 w-4" />
                      </button>
                      {report.share_enabled ? (
                        <button
                          onClick={() => handleRevoke(report)}
                          disabled={busyId === report.id}
                          title="لغو لینک عمومی"
                          className="rounded-lg p-2 text-muted-foreground transition hover:bg-amber-500/15 hover:text-amber-400 disabled:opacity-50"
                        >
                          <ShieldOff className="h-4 w-4" />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleShare(report)}
                          disabled={busyId === report.id}
                          title="ساخت لینک عمومی"
                          className="rounded-lg p-2 text-muted-foreground transition hover:bg-sky-500/15 hover:text-sky-400 disabled:opacity-50"
                        >
                          <Copy className="h-4 w-4" />
                        </button>
                      )}
                    </>
                  )}
                  <button
                    onClick={() => handleDelete(report)}
                    disabled={busyId === report.id}
                    title="حذف"
                    className="rounded-lg p-2 text-muted-foreground transition hover:bg-red-500/15 hover:text-red-400 disabled:opacity-50"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
Now the public viewer page. It renders PublicReportRead content with the sections array.

Bash Create directory for public report viewer route
IN
mkdir -p "C:/Users/Administrator/Desktop/SEO/frontend/app/reports/public/[token]"

OUT
(Bash completed with no output)
Write C:\Users\Administrator\Desktop\SEO\frontend\app\reports\public\[token]\page.tsx
196 lines
"use client";

/**
 * Public report viewer — no auth, reached only via a share token.
 *
 * Lives outside the (auth)/(dashboard) route groups on purpose: the dashboard
 * layout redirects to /login whenever there is no session, which would make a
 * "public" link unusable for the client it was shared with.
 *
 * Section bodies are backend-defined and vary by type (weekly/monthly/
 * executive), so rendering stays generic: a table when `rows` is a non-empty
 * array of objects, otherwise the Persian `note` the backend already writes
 * for `has_data: false` sections instead of guessing at a chart.
 */

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, ApiError } from "@/lib/api-client";
import { AlertCircle, CalendarDays, Globe, Sparkles } from "lucide-react";

interface PublicReportSection {
  key: string;
  title_fa: string;
  has_data: boolean;
  note?: string;
  rows?: Record<string, any>[];
  [key: string]: any;
}

interface PublicReport {
  report_type: string;
  title: string;
  period_start: string;
  period_end: string;
  generated_at: string | null;
  content: {
    sections?: PublicReportSection[];
    scope?: { level: string; websites: { name: string; domain: string }[] };
    [key: string]: any;
  };
  metrics_snapshot: Record<string, any>;
}

function formatFa(v: any): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return v.toLocaleString("fa-IR");
  return String(v);
}

export default function PublicReportPage() {
  const params = useParams();
  const token = params.token as string;

  const [report, setReport] = useState<PublicReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await api.get<PublicReport>(`/reports/public/${token}`);
        setReport(data);
      } catch (err: any) {
        setError(
          err instanceof ApiError
            ? "این لینک منقضی شده یا نامعتبر است"
            : "خطا در بارگذاری گزارش"
        );
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  return (
    <div dir="rtl" className="min-h-screen bg-background px-4 py-10 text-foreground">
      <div className="mx-auto max-w-3xl space-y-6">
        {loading && (
          <div className="space-y-3">
            <div className="h-8 w-2/3 animate-pulse rounded-lg bg-white/5" />
            <div className="h-32 animate-pulse rounded-2xl bg-white/5" />
          </div>
        )}

        {!loading && error && (
          <div className="flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            <AlertCircle className="h-5 w-5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {!loading && report && (
          <>
            <div className="rounded-2xl border border-white/10 bg-card/80 p-6 backdrop-blur-md">
              <div className="flex items-center gap-2 text-xs text-primary">
                <Sparkles className="h-3.5 w-3.5" />
                <span>گزارش عمومی — فقط خواندنی</span>
              </div>
              <h1 className="mt-2 text-2xl font-bold text-white">
                {report.title}
              </h1>
              <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                <span className="inline-flex items-center gap-1">
                  <CalendarDays className="h-3.5 w-3.5" />
                  {report.period_start} تا {report.period_end}
                </span>
                {report.content?.scope && (
                  <span className="inline-flex items-center gap-1">
                    <Globe className="h-3.5 w-3.5" />
                    {report.content.scope.level === "organization"
                      ? "کل سازمان"
                      : report.content.scope.websites?.[0]?.domain ?? "یک وب‌سایت"}
                  </span>
                )}
              </div>
            </div>

            {/* Key metrics */}
            {report.metrics_snapshot && (
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {Object.entries(report.metrics_snapshot)
                  .filter(([, v]) => typeof v === "number")
                  .slice(0, 8)
                  .map(([key, value]) => (
                    <div
                      key={key}
                      className="rounded-xl border border-white/10 bg-card/60 p-4"
                    >
                      <p className="text-[10px] text-muted-foreground" dir="ltr">
                        {key}
                      </p>
                      <p className="mt-1 text-lg font-bold text-white">
                        {formatFa(value)}
                      </p>
                    </div>
                  ))}
              </div>
            )}

            {/* Sections */}
            <div className="space-y-4">
              {(report.content?.sections ?? []).map((section) => (
                <div
                  key={section.key}
                  className="rounded-2xl border border-white/10 bg-card/60 p-5"
                >
                  <h2 className="text-sm font-semibold text-white">
                    {section.title_fa}
                  </h2>
                  {!section.has_data ? (
                    <p className="mt-2 text-xs text-muted-foreground">
                      {section.note}
                    </p>
                  ) : Array.isArray(section.rows) && section.rows.length > 0 ? (
                    <div className="mt-3 overflow-x-auto">
                      <table className="w-full text-right text-xs">
                        <thead>
                          <tr className="border-b border-white/10 text-muted-foreground">
                            {Object.keys(section.rows[0]).map((col) => (
                              <th key={col} className="px-2 py-1.5 font-medium">
                                {col}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {section.rows.slice(0, 50).map((row, i) => (
                            <tr key={i} className="border-b border-white/5">
                              {Object.keys(section.rows![0]).map((col) => (
                                <td key={col} className="px-2 py-1.5 text-white">
                                  {formatFa(row[col])}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-muted-foreground">
                      داده‌ای برای نمایش جدولی در این بخش وجود ندارد.
                    </p>
                  )}
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
