# API Design — AI SEO OS

## Conventions

### Base URL

```
http://localhost:8000/api/v1
```

### Authentication

All endpoints except `/auth/login`, `/auth/register`, and `/auth/refresh` require a Bearer token:

```
Authorization: Bearer <access_token>
```

### Request Format

- Content-Type: `application/json`
- Query parameters for GET filters
- Request body for POST/PUT/PATCH

### Response Format

#### Success (single item)

```json
{
  "data": { ... }
}
```

#### Success (list)

```json
{
  "data": [ ... ],
  "meta": {
    "total": 1250,
    "page": 1,
    "page_size": 25,
    "total_pages": 50
  }
}
```

#### Error (RFC 7807)

```json
{
  "type": "validation_error",
  "title": "Validation Error",
  "status": 422,
  "detail": "Field 'email' is required",
  "errors": [
    {
      "field": "email",
      "message": "This field is required",
      "code": "required"
    }
  ]
}
```

### Common Query Parameters (List endpoints)

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `page_size` | int | 25 | Items per page (max 100) |
| `sort_by` | string | `created_at` | Sort column |
| `sort_dir` | string | `desc` | `asc` or `desc` |
| `search` | string | | Full-text search |
| `date_from` | date | | Start date filter |
| `date_to` | date | | End date filter |

---

## Endpoints

### Auth (`/api/v1/auth`)

| Method | Path | Description | Auth | Role |
|---|---|---|---|---|
| POST | `/auth/register` | Create account | No | — |
| POST | `/auth/login` | Login, get tokens | No | — |
| POST | `/auth/refresh` | Refresh access token | No (refresh token in body) | — |
| POST | `/auth/logout` | Revoke refresh token | Yes | Any |
| POST | `/auth/forgot-password` | Send reset email | No | — |
| POST | `/auth/reset-password` | Reset password with token | No | — |
| GET | `/auth/me` | Get current user profile | Yes | Any |
| PATCH | `/auth/me` | Update profile | Yes | Any |
| PUT | `/auth/me/password` | Change password | Yes | Any |

#### POST `/auth/register`

```json
// Request
{
  "email": "user@example.com",
  "password": "securePassword123",
  "full_name": "Ali Rezaei"
}

// Response 201
{
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "full_name": "Ali Rezaei",
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

#### POST `/auth/login`

```json
// Request
{
  "email": "user@example.com",
  "password": "securePassword123"
}

// Response 200
{
  "data": {
    "access_token": "eyJ...",
    "refresh_token": "abc123...",
    "token_type": "bearer",
    "expires_in": 900
  }
}
```

---

### Organizations (`/api/v1/organizations`)

| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/organizations` | Create organization | Any |
| GET | `/organizations` | List user's organizations | Any |
| GET | `/organizations/:id` | Get organization details | Viewer+ |
| PATCH | `/organizations/:id` | Update organization | Admin+ |
| DELETE | `/organizations/:id` | Soft-delete organization | Owner |
| GET | `/organizations/:id/members` | List members | Viewer+ |
| POST | `/organizations/:id/members` | Invite member | Admin+ |
| PATCH | `/organizations/:id/members/:memberId` | Update member role | Admin+ |
| DELETE | `/organizations/:id/members/:memberId` | Remove member | Admin+ |

---

### Projects (`/api/v1/projects`)

All endpoints scoped to current organization.

| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/projects` | Create project | Admin+ |
| GET | `/projects` | List projects | Viewer+ |
| GET | `/projects/:id` | Get project details | Viewer+ |
| PATCH | `/projects/:id` | Update project | SEO Manager+ |
| DELETE | `/projects/:id` | Soft-delete project | Admin+ |

---

### Websites (`/api/v1/websites`)

| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/websites` | Create website | SEO Manager+ |
| GET | `/websites` | List websites (filter by project) | Viewer+ |
| GET | `/websites/:id` | Get website details | Viewer+ |
| PATCH | `/websites/:id` | Update website | SEO Manager+ |
| DELETE | `/websites/:id` | Soft-delete website | Admin+ |
| GET | `/websites/:id/stats` | Get website summary stats | Viewer+ |
| PATCH | `/websites/:id/settings` | Update website settings | SEO Manager+ |
| PATCH | `/websites/:id/automation-mode` | Change automation mode | Admin+ |

#### Query parameters for GET `/websites`

| Parameter | Type | Description |
|---|---|---|
| `project_id` | UUID | Filter by project |
| `website_type` | string | Filter by type |
| `status` | string | Filter by status |
| `automation_mode` | string | Filter by mode |

---

### Google (`/api/v1/google`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/google/auth-url` | Get Google OAuth redirect URL | SEO Manager+ |
| GET | `/integrations/gsc/callback` | OAuth callback handler | — |
| GET | `/google/accounts` | List connected Google accounts | SEO Manager+ |
| DELETE | `/google/accounts/:id` | Disconnect Google account | Admin+ |
| POST | `/google/accounts/:id/refresh` | Force token refresh | SEO Manager+ |

---

### Search Console (`/api/v1/search-console`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/search-console/properties` | List available SC properties | SEO Manager+ |
| POST | `/search-console/connections` | Connect website to SC property | SEO Manager+ |
| GET | `/search-console/connections/:websiteId` | Get connection status | Viewer+ |
| DELETE | `/search-console/connections/:websiteId` | Disconnect | Admin+ |
| POST | `/search-console/connections/:websiteId/sync` | Trigger manual sync | SEO Manager+ |
| GET | `/search-console/connections/:websiteId/sync-history` | Sync job history | Viewer+ |

#### POST `/search-console/connections`

```json
// Request
{
  "website_id": "uuid",
  "property_id": "uuid",
  "sync_interval_hours": 24
}
```

---

### Performance (`/api/v1/performance`)

All endpoints require `website_id` query parameter.

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/performance/overview` | Aggregated metrics + charts | Viewer+ |
| GET | `/performance/comparison` | Period-over-period comparison | Viewer+ |
| GET | `/performance/trends` | Trend analysis (growing/declining) | Viewer+ |

#### GET `/performance/overview`

Query parameters:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `website_id` | UUID | Yes | |
| `date_from` | date | Yes | |
| `date_to` | date | Yes | |
| `compare_date_from` | date | No | Comparison period start |
| `compare_date_to` | date | No | Comparison period end |
| `search_type` | string | No | web, image, video |
| `country` | string | No | ISO country code |
| `device` | string | No | DESKTOP, MOBILE, TABLET |

Response:

```json
{
  "data": {
    "current": {
      "clicks": 15420,
      "impressions": 892100,
      "ctr": 0.0173,
      "position": 18.4
    },
    "previous": {
      "clicks": 13800,
      "impressions": 810000,
      "ctr": 0.0170,
      "position": 19.1
    },
    "change": {
      "clicks": { "value": 1620, "pct": 11.74 },
      "impressions": { "value": 82100, "pct": 10.14 },
      "ctr": { "value": 0.0003, "pct": 1.76 },
      "position": { "value": -0.7, "pct": -3.66 }
    },
    "daily_series": [
      { "date": "2026-01-01", "clicks": 520, "impressions": 30100, "ctr": 0.0173, "position": 18.2 },
      ...
    ]
  }
}
```

---

### Queries (`/api/v1/queries`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/queries` | Query explorer with filters | Viewer+ |
| GET | `/queries/:query/details` | Detailed query analysis | Viewer+ |
| GET | `/queries/:query/pages` | Pages ranking for this query | Viewer+ |
| GET | `/queries/:query/history` | Historical performance | Viewer+ |

#### GET `/queries`

Query parameters:

| Parameter | Type | Description |
|---|---|---|
| `website_id` | UUID | Required |
| `date_from` | date | Required |
| `date_to` | date | Required |
| `compare_date_from` | date | Comparison period |
| `compare_date_to` | date | Comparison period |
| `search` | string | Query text search |
| `min_clicks` | int | Minimum clicks filter |
| `max_position` | float | Maximum position filter |
| `min_impressions` | int | Minimum impressions |
| `country` | string | Country filter |
| `device` | string | Device filter |
| `search_type` | string | Search type filter |
| `intent` | string | Search intent filter |
| `status` | string | growing, declining, stable, new, lost |

Response row:

```json
{
  "query": "بهترین لپتاپ ۲۰۲۶",
  "clicks": 340,
  "impressions": 8200,
  "ctr": 0.0415,
  "position": 7.3,
  "previous_clicks": 280,
  "click_change": 21.4,
  "previous_position": 9.1,
  "position_change": -1.8,
  "opportunity_score": 82,
  "intent": "commercial",
  "related_page": "/laptop-guide/",
  "status": "growing"
}
```

---

### Pages (`/api/v1/pages`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/pages` | Page explorer with filters | Viewer+ |
| GET | `/pages/:id` | Page detail (by content_item ID) | Viewer+ |
| GET | `/pages/:id/queries` | Queries for this page | Viewer+ |
| GET | `/pages/:id/history` | Performance history | Viewer+ |
| GET | `/pages/:id/links` | Internal links from/to page | Viewer+ |

---

### WordPress (`/api/v1/wordpress`)

| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/wordpress/connections` | Create WordPress connection | SEO Manager+ |
| GET | `/wordpress/connections/:websiteId` | Get connection status | Viewer+ |
| PATCH | `/wordpress/connections/:websiteId` | Update credentials | SEO Manager+ |
| DELETE | `/wordpress/connections/:websiteId` | Disconnect | Admin+ |
| POST | `/wordpress/connections/:websiteId/test` | Test connection | SEO Manager+ |
| POST | `/wordpress/connections/:websiteId/sync` | Trigger manual sync | SEO Manager+ |
| POST | `/wordpress/draft` | Create WP draft from content item | Editor+ |
| POST | `/wordpress/publish` | Publish content to WordPress | SEO Manager+ (requires approval) |
| PATCH | `/wordpress/update/:wpId` | Update existing WP post | SEO Manager+ (requires approval) |

---

### Categories (`/api/v1/categories`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/categories` | List categories (flat or tree) | Viewer+ |
| POST | `/categories` | Create category | SEO Manager+ |
| GET | `/categories/:id` | Get category with stats | Viewer+ |
| PATCH | `/categories/:id` | Update category | SEO Manager+ |
| DELETE | `/categories/:id` | Delete category | Admin+ |
| PATCH | `/categories/:id/move` | Move in tree (change parent) | SEO Manager+ |
| GET | `/categories/:id/content` | Content items in category | Viewer+ |

#### GET `/categories` — Tree mode

```json
{
  "data": [
    {
      "id": "uuid",
      "name": "لپتاپ",
      "slug": "laptop",
      "depth": 0,
      "content_count": 45,
      "clicks": 12400,
      "impressions": 340000,
      "seo_score": 72,
      "children": [
        {
          "id": "uuid",
          "name": "لپتاپ گیمینگ",
          "slug": "gaming-laptop",
          "depth": 1,
          "content_count": 12,
          "clicks": 4200,
          "impressions": 98000,
          "seo_score": 68,
          "children": []
        }
      ]
    }
  ]
}
```

---

### Content (`/api/v1/content`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/content` | Content inventory table | Viewer+ |
| POST | `/content` | Create content item | Editor+ |
| GET | `/content/:id` | Get content detail | Viewer+ |
| PATCH | `/content/:id` | Update content | Editor+ |
| DELETE | `/content/:id` | Soft-delete content | Admin+ |
| PATCH | `/content/:id/status` | Change status | Editor+ |
| GET | `/content/:id/versions` | Version history | Viewer+ |
| GET | `/content/:id/versions/:version` | Specific version | Viewer+ |
| POST | `/content/:id/versions` | Create new version | Editor+ |
| GET | `/content/:id/performance` | Performance from SC data | Viewer+ |
| POST | `/content/bulk-action` | Bulk status change, tag, assign | SEO Manager+ |

#### GET `/content` — Filter parameters

| Parameter | Type | Description |
|---|---|---|
| `website_id` | UUID | Required |
| `category_id` | UUID | |
| `content_type` | string | article, product, etc. |
| `status` | string | Published, draft, etc. |
| `author_id` | UUID | |
| `search_intent` | string | |
| `min_seo_score` | float | |
| `max_seo_score` | float | |
| `tags` | string[] | |
| `has_brief` | boolean | |

---

### Content Calendar (`/api/v1/content-calendar`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/content-calendar` | Calendar view (month/week/day) | Viewer+ |
| PATCH | `/content-calendar/:contentId/schedule` | Set/change planned date | Editor+ |
| GET | `/content-calendar/queue` | Content production queue | Viewer+ |
| PATCH | `/content-calendar/queue/reorder` | Reorder queue | SEO Manager+ |

---

### Content Briefs (`/api/v1/content-briefs`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/content-briefs` | List briefs | Viewer+ |
| POST | `/content-briefs` | Create brief (manual) | Editor+ |
| POST | `/content-briefs/generate` | Generate brief via AI | SEO Manager+ |
| GET | `/content-briefs/:id` | Get brief detail | Viewer+ |
| PATCH | `/content-briefs/:id` | Update brief | Editor+ |
| POST | `/content-briefs/:id/approve` | Approve brief | SEO Manager+ |

---

### Opportunities (`/api/v1/opportunities`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/opportunities` | List opportunities | Viewer+ |
| GET | `/opportunities/:id` | Opportunity detail | Viewer+ |
| PATCH | `/opportunities/:id/status` | Change status (assign, dismiss) | SEO Manager+ |
| POST | `/opportunities/:id/execute` | Execute via agent | SEO Manager+ |
| GET | `/opportunities/summary` | Summary by type | Viewer+ |

#### GET `/opportunities` — Filter parameters

| Parameter | Type | Description |
|---|---|---|
| `website_id` | UUID | Required |
| `opportunity_type` | string | |
| `status` | string | open, assigned, in_progress, completed, dismissed |
| `min_priority` | float | |
| `risk` | string | low, medium, high |
| `effort_estimate` | string | low, medium, high |

---

### Alerts (`/api/v1/alerts`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/alerts` | List alerts | Viewer+ |
| GET | `/alerts/:id` | Alert detail | Viewer+ |
| PATCH | `/alerts/:id/status` | Change status | SEO Manager+ |
| POST | `/alerts/:id/assign` | Assign to agent | SEO Manager+ |
| POST | `/alerts/:id/resolve` | Mark as resolved | SEO Manager+ |
| POST | `/alerts/:id/ignore` | Dismiss alert | SEO Manager+ |
| GET | `/alerts/summary` | Alert counts by severity | Viewer+ |

---

### SEO Scores (`/api/v1/seo-scores`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/seo-scores/website/:websiteId` | Website-level scores | Viewer+ |
| GET | `/seo-scores/pages` | Page-level scores | Viewer+ |
| GET | `/seo-scores/categories` | Category-level scores | Viewer+ |
| POST | `/seo-scores/recalculate` | Trigger score recalculation | SEO Manager+ |

---

### Agents (`/api/v1/agents`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/agents` | List available agents | Viewer+ |
| GET | `/agents/:id` | Agent configuration | SEO Manager+ |
| PATCH | `/agents/:id` | Update agent config | Admin+ |
| GET | `/agents/runs` | Agent run history | Viewer+ |
| GET | `/agents/runs/:id` | Run detail with decisions | Viewer+ |
| POST | `/agents/runs` | Trigger manual agent run | SEO Manager+ |
| GET | `/agents/runs/:id/decisions` | Decisions for a run | Viewer+ |
| GET | `/agents/activity` | Activity feed (all agents) | Viewer+ |

---

### Automation (`/api/v1/automation`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/automation/rules` | List automation rules | Viewer+ |
| POST | `/automation/rules` | Create rule | Admin+ |
| GET | `/automation/rules/:id` | Rule detail | Viewer+ |
| PATCH | `/automation/rules/:id` | Update rule | Admin+ |
| DELETE | `/automation/rules/:id` | Delete rule | Admin+ |
| PATCH | `/automation/rules/:id/toggle` | Enable/disable rule | SEO Manager+ |
| GET | `/automation/jobs` | Job history | Viewer+ |
| GET | `/automation/jobs/:id` | Job detail | Viewer+ |
| POST | `/automation/jobs/:id/retry` | Retry failed job | SEO Manager+ |
| POST | `/automation/jobs/:id/cancel` | Cancel pending job | SEO Manager+ |
| POST | `/automation/emergency-stop` | Stop all running automation | Admin+ |
| GET | `/automation/workflows` | Workflow execution history | Viewer+ |

---

### Approvals (`/api/v1/approvals`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/approvals` | List pending approvals | Reviewer+ |
| GET | `/approvals/:id` | Approval detail with context | Reviewer+ |
| POST | `/approvals/:id/approve` | Approve request | SEO Manager+ |
| POST | `/approvals/:id/reject` | Reject with reason | SEO Manager+ |
| GET | `/approvals/count` | Count of pending approvals | Reviewer+ |

---

### Notifications (`/api/v1/notifications`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/notifications` | List user notifications | Any |
| GET | `/notifications/unread-count` | Unread count | Any |
| PATCH | `/notifications/:id/read` | Mark as read | Any |
| POST | `/notifications/mark-all-read` | Mark all as read | Any |

---

### Reports (`/api/v1/reports`)

| Method | Path | Description | Role |
|---|---|---|---|
| POST | `/reports/generate` | Generate on-demand report | SEO Manager+ |
| GET | `/reports` | List generated reports | Viewer+ |
| GET | `/reports/:id` | Get report content | Viewer+ |
| GET | `/reports/schedule` | List scheduled reports | Viewer+ |
| POST | `/reports/schedule` | Schedule recurring report | SEO Manager+ |

---

### Dashboard (`/api/v1/dashboard`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/dashboard/summary` | Executive dashboard data | Viewer+ |
| GET | `/dashboard/ai-summary` | AI SEO Manager summary | Viewer+ |
| GET | `/dashboard/portfolio` | Multi-site portfolio overview | Viewer+ |

#### GET `/dashboard/summary`

```json
{
  "data": {
    "seo_health_score": 74,
    "metrics": {
      "clicks": { "current": 15420, "previous": 13800, "change_pct": 11.74 },
      "impressions": { "current": 892100, "previous": 810000, "change_pct": 10.14 },
      "ctr": { "current": 0.0173, "previous": 0.0170, "change_pct": 1.76 },
      "position": { "current": 18.4, "previous": 19.1, "change_pct": -3.66 }
    },
    "top_growing_pages": [...],
    "top_declining_pages": [...],
    "top_growing_queries": [...],
    "top_declining_queries": [...],
    "active_alerts": { "critical": 1, "high": 3, "medium": 7 },
    "active_opportunities": 15,
    "pending_approvals": 2,
    "content_status": {
      "published_this_week": 3,
      "in_progress": 5,
      "refresh_needed": 8
    },
    "recent_agent_activity": [...]
  }
}
```

---

### Audit Logs (`/api/v1/audit-logs`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/audit-logs` | Query audit log | Admin+ |

#### Filter parameters

| Parameter | Type | Description |
|---|---|---|
| `user_id` | UUID | Filter by actor |
| `agent_id` | UUID | Filter by agent |
| `action` | string | Filter by action type |
| `entity_type` | string | Filter by entity type |
| `entity_id` | UUID | Filter by specific entity |

---

### Settings (`/api/v1/settings`)

| Method | Path | Description | Role |
|---|---|---|---|
| GET | `/settings/organization` | Get org settings | Admin+ |
| PATCH | `/settings/organization` | Update org settings | Admin+ |
| GET | `/settings/ai-provider` | Get AI provider config | Admin+ |
| PATCH | `/settings/ai-provider` | Update AI provider | Admin+ |
| GET | `/settings/notifications` | Get notification settings | SEO Manager+ |
| PATCH | `/settings/notifications` | Update notification settings | SEO Manager+ |
| GET | `/settings/telegram` | Get Telegram bot config | SEO Manager+ |
| PATCH | `/settings/telegram` | Update Telegram config | SEO Manager+ |

---

### Health (`/health`)

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/health` | System health check | No |

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "checks": {
    "database": "ok",
    "redis": "ok",
    "n8n": "ok"
  }
}
```

---

### Webhook Callbacks (`/api/v1/webhooks`)

These are called by n8n, not by the frontend.

| Method | Path | Description | Auth |
|---|---|---|---|
| POST | `/webhooks/n8n/callback` | n8n workflow completion callback | API key |
| POST | `/webhooks/integrations/gsc/callback` | Google OAuth callback | — |

Webhook auth: n8n callbacks use a shared API key in the `X-Webhook-Secret` header.
