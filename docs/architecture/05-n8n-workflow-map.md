# n8n Workflow Map — AI SEO OS

## Integration Architecture

### How n8n Connects to the Backend

```
Backend (FastAPI)
    │
    │ HTTP POST to n8n webhook URL
    │ Payload: job_id, website_id, action, data
    │
    ▼
n8n (Webhook Trigger)
    │
    │ Executes workflow steps
    │ Calls external APIs
    │
    ▼
n8n (HTTP Request node)
    │
    │ POST /api/v1/webhooks/n8n/callback
    │ Payload: job_id, status, result, error
    │
    ▼
Backend (FastAPI)
    │
    │ Updates automation_jobs.status
    │ Updates workflow_executions
    │ Triggers next steps if needed
```

### Communication Protocol

**Backend → n8n** (trigger):
```json
{
  "job_id": "uuid",
  "website_id": "uuid",
  "workflow_name": "search-console-daily-sync",
  "action": "sync",
  "data": {
    "property_url": "sc-domain:example.com",
    "date_from": "2026-01-01",
    "date_to": "2026-01-15",
    "access_token": "encrypted_or_fetched_at_runtime"
  },
  "callback_url": "https://api.seoos.app/api/v1/webhooks/n8n/callback",
  "api_key": "webhook_secret"
}
```

**n8n → Backend** (callback):
```json
{
  "job_id": "uuid",
  "status": "completed",
  "result": {
    "records_processed": 1250,
    "summary": "..."
  },
  "error": null
}
```

### n8n Authentication

n8n authenticates to the Backend API using:
1. A dedicated **service account API key** stored as n8n credential
2. The key is validated via `X-Webhook-Secret` header

The Backend authenticates to n8n using:
1. n8n webhook URLs (no auth needed for production webhooks — n8n uses unique webhook paths)

---

## Workflow Catalog

### Category 1: Data Synchronization

---

#### WF-01: Search Console Daily Sync

**Trigger**: Celery Beat (daily at 06:00 UTC per website) or manual

**Purpose**: Fetch the latest Search Console performance data and store it.

```
┌─────────────────┐
│  Webhook Trigger │
│  (from Celery)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Fetch GSC Data  │
│  HTTP Request    │
│  Search Console  │
│  Performance API │
│  ─────────────── │
│  Date range:     │
│  last_sync → now │
└────────┬────────┘
         │
         ├── Error? ──→ Retry (3x) ──→ Error Callback
         │
         ▼
┌─────────────────┐
│  Transform Data  │
│  Function node   │
│  ─────────────── │
│  Normalize dims  │
│  Validate types  │
│  Deduplicate     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Store to DB     │
│  HTTP Request    │
│  POST /api/v1/   │
│  webhooks/n8n/   │
│  callback        │
│  ─────────────── │
│  Batch upsert    │
│  via backend API │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Trigger         │
│  Analysis        │
│  Pipeline        │
└─────────────────┘
```

**Error handling**:
- Retry on 429 (rate limit): wait for `Retry-After`
- Retry on 500/503: exponential backoff (60s, 300s, 900s)
- On max retries exceeded: callback with error status → alert created

**Schedule**: Daily per website. Staggered by 1 minute per website to avoid API quota issues.

---

#### WF-02: WordPress Content Sync

**Trigger**: Celery Beat (daily at 07:00 UTC per website) or manual

**Purpose**: Import/update posts, pages, categories from WordPress.

```
Webhook Trigger
    │
    ▼
Fetch WP Posts (paginated, modified_after=last_sync)
    │
    ▼
Fetch WP Pages (paginated)
    │
    ▼
Fetch WP Categories
    │
    ▼
Fetch WP Tags
    │
    ▼
Transform & Map to internal schema
    │
    ▼
Callback to Backend API (batch upsert)
    │
    ▼
Update sync status
```

**Note**: Only fetches content modified since last sync. Uses `modified_after` parameter to minimize API calls.

---

### Category 2: SEO Analysis

---

#### WF-03: Weekly SEO Analysis

**Trigger**: Celery Beat (Monday 08:00 UTC)

**Purpose**: Run comprehensive weekly analysis across all websites.

```
Webhook Trigger
    │
    ▼
For each website:
    │
    ├── Calculate period-over-period changes
    │
    ├── Detect traffic drops (>15% week-over-week)
    │
    ├── Detect ranking drops (>3 positions)
    │
    ├── Detect CTR anomalies
    │
    ├── Find new opportunities
    │   ├── High impressions + low CTR
    │   ├── Position 4-15 keywords
    │   ├── Growing queries
    │   └── New queries
    │
    ├── Detect content decay
    │   └── Pages declining >20% over 30 days
    │
    └── Generate AI summary
    │
    ▼
Callback with analysis results
    │
    ▼
Create alerts + opportunities in DB
    │
    ▼
Send notification (if critical findings)
```

**Note**: The heavy lifting (data queries, scoring) happens in the Backend/Celery. n8n orchestrates the sequence and handles notifications.

---

#### WF-04: Traffic Drop Alert

**Trigger**: Event (post-analysis pipeline)

**Purpose**: Detect and alert on significant traffic drops.

```
Webhook Trigger (alert data)
    │
    ▼
Evaluate severity
    │
    ├── >50% drop → Critical
    ├── >30% drop → High
    ├── >15% drop → Medium
    └── >5% drop  → Low
    │
    ▼
Generate AI explanation (call AI provider)
    │
    ▼
Create alert in DB via callback
    │
    ▼
Branch by severity:
    │
    ├── Critical/High → Telegram + Email + Dashboard
    ├── Medium → Telegram + Dashboard
    └── Low → Dashboard only
```

---

#### WF-05: Ranking Drop Alert

Same pattern as WF-04 but for position changes.

**Thresholds**:
- Position drops >5 for top-10 keywords → High
- Position drops >10 → Medium
- Position drops out of page 1 (1-10 → 11+) → Critical

---

### Category 3: Content Production

---

#### WF-06: Content Generation Pipeline

**Trigger**: Manual (from approval of content brief) or Agent

**Purpose**: Generate an article from a brief, review it, and create a WordPress draft.

```
Webhook Trigger (content_brief_id)
    │
    ▼
Fetch Brief from Backend API
    │
    ▼
┌─────────────────────┐
│  Generate Article    │
│  AI Provider API     │
│  ─────────────────── │
│  System prompt:      │
│  Writer agent prompt │
│  + brand rules       │
│  + brief outline     │
│  + keyword targets   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Quality Review      │
│  AI Provider API     │
│  ─────────────────── │
│  Reviewer agent      │
│  prompt              │
│  Check: quality,     │
│  SEO, structure,     │
│  readability         │
└──────────┬──────────┘
           │
           ├── Score < threshold? → Rewrite (max 2 attempts)
           │
           ▼
┌─────────────────────┐
│  SEO Optimization    │
│  AI Provider API     │
│  ─────────────────── │
│  Optimize meta title │
│  meta description    │
│  heading structure   │
│  keyword density     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Internal Link       │
│  Suggestions         │
│  Backend API call    │
│  ─────────────────── │
│  Find relevant       │
│  content to link to  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Save Version        │
│  Backend API         │
│  ─────────────────── │
│  Create content      │
│  version with full   │
│  article text        │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Risk Assessment     │
│  ─────────────────── │
│  If autopilot +      │
│  low risk:           │
│    → Create WP draft │
│  Else:               │
│    → Create approval │
│      request         │
└──────────┬──────────┘
           │
           ▼
Callback: content_id, version_id, status
```

---

#### WF-07: WordPress Draft Creation

**Trigger**: Approval (or auto-approve in autopilot)

**Purpose**: Create a draft post in WordPress from a content item.

```
Webhook Trigger (content_id)
    │
    ▼
Fetch content + latest version from Backend
    │
    ▼
Format content for WordPress
    │  - HTML from markdown
    │  - Set category (wp_id)
    │  - Set tags
    │  - Set meta title (Yoast/RankMath)
    │  - Set meta description
    │  - Set slug
    │
    ▼
Create Draft via WordPress REST API
    │  POST /wp-json/wp/v2/posts
    │  status: "draft"
    │
    ├── Error? → Retry → Error callback
    │
    ▼
Callback: wp_id, wp_url, status
    │
    ▼
Backend updates content_item.wp_id
```

---

#### WF-08: WordPress Publish

**Trigger**: Manual approval or scheduled

**Purpose**: Publish a draft that has been reviewed.

```
Webhook Trigger (content_id, wp_id)
    │
    ▼
Update WP Post status to "publish"
    │  POST /wp-json/wp/v2/posts/{wp_id}
    │  status: "publish"
    │
    ├── Scheduled? → Set date field → "future" status
    │
    ▼
Callback: published_url, publish_date
    │
    ▼
Backend updates:
    - content_item.status = "published"
    - content_item.published_at = now
    - audit_log entry
```

---

#### WF-09: Content Refresh

**Trigger**: Agent decision or manual

**Purpose**: Update existing published content to improve performance.

```
Webhook Trigger (content_id, refresh_instructions)
    │
    ▼
Fetch current content from WordPress
    │
    ▼
Fetch current version from Backend
    │
    ▼
Generate updated content via AI
    │  - Keep structure
    │  - Update outdated sections
    │  - Add new information
    │  - Improve keyword targeting
    │
    ▼
Quality review
    │
    ▼
Save new version to Backend
    │
    ▼
Create approval request (always — editing live content is medium+ risk)
    │
    ▼
On approval:
    → Update WordPress post
    → Callback with before/after
```

---

### Category 4: Notifications

---

#### WF-10: Telegram Notification

**Trigger**: Event (from notification service)

**Purpose**: Send alert/notification to Telegram.

```
Webhook Trigger (notification data)
    │
    ▼
Format message (Markdown)
    │
    ▼
Send via Telegram Bot API
    │  POST https://api.telegram.org/bot{token}/sendMessage
    │  chat_id: configured_chat_id
    │  parse_mode: MarkdownV2
    │
    ├── Error? → Retry (5x, 10s backoff)
    │
    ▼
Callback: delivery_status
```

**Message format example**:
```
🔴 *Critical Alert — example.com*

*Traffic Drop Detected*
Page: /best-laptops/
Clicks: 520 → 210 (−59.6%)
Period: Last 7 days vs previous

*AI Analysis:*
Possible ranking algorithm update. Page lost positions for 3 primary keywords.

*Suggested Action:*
Review content freshness and update statistics.

[View in Dashboard](https://seoos.app/alerts/abc123)
```

---

#### WF-11: Email Notification

**Trigger**: Event (from notification service)

**Purpose**: Send email notifications for critical alerts and reports.

```
Webhook Trigger (notification data)
    │
    ▼
Select email template
    │
    ▼
Render HTML email
    │
    ▼
Send via SMTP
    │
    ├── Error? → Retry (3x)
    │
    ▼
Callback: delivery_status
```

---

### Category 5: Reports

---

#### WF-12: Weekly SEO Report

**Trigger**: Celery Beat (Monday 08:00 UTC)

**Purpose**: Generate and distribute weekly SEO summary.

```
Webhook Trigger (org_id)
    │
    ▼
For each website in org:
    │
    ├── Fetch performance summary (Backend API)
    ├── Fetch active alerts (Backend API)
    ├── Fetch completed tasks (Backend API)
    ├── Fetch new opportunities (Backend API)
    └── Generate AI executive summary
    │
    ▼
Compile report JSON
    │
    ▼
Store report in Backend (POST /reports)
    │
    ▼
Send report notification
    ├── Dashboard notification
    ├── Telegram summary
    └── Email full report
```

---

#### WF-13: Monthly SEO Report

Same structure as WF-12 but with:
- 30-day comparison period
- Goal progress tracking
- Content production metrics
- ROI analysis (if available)
- Trend visualization data

---

### Category 6: System Operations

---

#### WF-14: Failed Job Recovery

**Trigger**: Celery Beat (every 6 hours)

**Purpose**: Detect and retry stuck or failed jobs.

```
Webhook Trigger
    │
    ▼
Query Backend API for:
    │  - Jobs with status "running" for >1 hour
    │  - Jobs with status "failed" and retry_count < max_retries
    │
    ▼
For each stuck job:
    │  → Update status to "failed"
    │  → Create alert
    │
    ▼
For each retriable job:
    │  → Increment retry_count
    │  → Re-queue for execution
    │
    ▼
Callback with recovery summary
```

---

#### WF-15: Health Check

**Trigger**: Celery Beat (every 15 minutes)

**Purpose**: Verify all external connections are healthy.

```
Webhook Trigger
    │
    ▼
Check each service:
    │
    ├── Google OAuth token validity
    ├── WordPress connection (GET /wp-json/)
    ├── AI provider reachability
    └── Telegram bot reachability
    │
    ▼
If any failed:
    │  → Create alert
    │  → Notify via working channels
    │
    ▼
Callback with health status
```

---

## Workflow Summary Table

| ID | Name | Trigger | Frequency | Category |
|---|---|---|---|---|
| WF-01 | Search Console Daily Sync | Celery Beat | Daily | Sync |
| WF-02 | WordPress Content Sync | Celery Beat | Daily | Sync |
| WF-03 | Weekly SEO Analysis | Celery Beat | Weekly | Analysis |
| WF-04 | Traffic Drop Alert | Event | On detection | Analysis |
| WF-05 | Ranking Drop Alert | Event | On detection | Analysis |
| WF-06 | Content Generation Pipeline | Manual/Agent | On demand | Content |
| WF-07 | WordPress Draft Creation | Approval/Auto | On demand | Content |
| WF-08 | WordPress Publish | Approval/Schedule | On demand | Content |
| WF-09 | Content Refresh | Agent/Manual | On demand | Content |
| WF-10 | Telegram Notification | Event | On demand | Notification |
| WF-11 | Email Notification | Event | On demand | Notification |
| WF-12 | Weekly SEO Report | Celery Beat | Weekly | Report |
| WF-13 | Monthly SEO Report | Celery Beat | Monthly | Report |
| WF-14 | Failed Job Recovery | Celery Beat | Every 6h | System |
| WF-15 | Health Check | Celery Beat | Every 15m | System |

---

## n8n vs Celery Decision Matrix

Some workflows could run in either Celery or n8n. This matrix documents which runs where and why.

| Task | Runs In | Reason |
|---|---|---|
| GSC data fetch + upsert | **Celery** | Core data pipeline. Needs direct DB access. Must be testable. |
| SEO scoring + analysis | **Celery** | CPU-intensive, needs DB aggregation queries |
| Opportunity detection | **Celery** | Complex business logic, needs full DB context |
| Alert detection | **Celery** | Real-time, needs DB comparison queries |
| AI agent execution | **Celery** | Needs structured agent framework + DB logging |
| Content generation (multi-step) | **n8n** | Multi-step with branching, benefits from visual debugging |
| WordPress publish | **n8n** | External API integration, retry-heavy |
| Telegram notification | **n8n** | Simple integration, fan-out |
| Email notification | **n8n** | Template rendering + SMTP |
| Report compilation | **n8n** | Multi-source aggregation + distribution |
| Failed job recovery | **n8n** | Orchestration with branching logic |
| Health checks | **n8n** | Multi-service checks with notification branching |

**Rule of thumb**: If it needs the database or complex business logic → Celery. If it's external API orchestration or notification distribution → n8n.

---

## n8n File Organization

```
n8n/
└── workflows/
    ├── sync/
    │   ├── wf-01-search-console-daily-sync.json
    │   └── wf-02-wordpress-content-sync.json
    ├── analysis/
    │   ├── wf-03-weekly-seo-analysis.json
    │   ├── wf-04-traffic-drop-alert.json
    │   └── wf-05-ranking-drop-alert.json
    ├── content/
    │   ├── wf-06-content-generation-pipeline.json
    │   ├── wf-07-wordpress-draft-creation.json
    │   ├── wf-08-wordpress-publish.json
    │   └── wf-09-content-refresh.json
    ├── notifications/
    │   ├── wf-10-telegram-notification.json
    │   └── wf-11-email-notification.json
    ├── reports/
    │   ├── wf-12-weekly-seo-report.json
    │   └── wf-13-monthly-seo-report.json
    └── system/
        ├── wf-14-failed-job-recovery.json
        └── wf-15-health-check.json
```

All workflow JSON files are version-controlled. On deployment, workflows are imported to n8n via the n8n CLI or API.

---

## n8n Credentials Required

| Credential Name | Type | Used By |
|---|---|---|
| `backend-api-key` | Header Auth | All workflows (callback to backend) |
| `google-oauth` | OAuth2 | WF-01 (Search Console) |
| `wordpress-{site}` | Basic Auth / App Password | WF-02, WF-07, WF-08, WF-09 |
| `ai-provider` | API Key | WF-06, WF-09 |
| `telegram-bot` | API Key | WF-10 |
| `smtp-email` | SMTP | WF-11 |

**Note**: Google OAuth tokens are managed by the Backend. n8n receives short-lived access tokens per request, not stored credentials.
