# System Architecture — AI SEO OS

## 1. Product Vision

An AI-powered SEO Operating System that centralizes all SEO operations for multiple websites into a single dashboard. The user operates as an SEO executive — monitoring, approving, and directing — while AI Agents and automation handle the 70–90% of routine work.

The platform is not an article generator. It is an SEO control center that combines data collection, analysis, planning, content operations, automation, and monitoring.

---

## 2. Architecture Principles

1. **PostgreSQL is the source of truth.** Every business entity, metric, decision, and log lives in the database. n8n, Redis, and external APIs are transient.
2. **Organization isolation is mandatory.** Every query is scoped to `organization_id`. Cross-org data access is architecturally impossible.
3. **AI decisions are structured and auditable.** Agents produce validated JSON schemas, not free-text chat. Every decision is logged with explanation, confidence, risk, and the data that informed it.
4. **Risk gates before destructive actions.** High-risk actions always require human approval regardless of automation mode. Low-risk actions can auto-execute in Autopilot mode.
5. **Idempotent external operations.** Every sync job, API call, and workflow execution uses idempotency keys or upsert logic. Re-running is always safe.
6. **Modular monolith, not microservices.** One backend, one database, clean module boundaries. Modules can be extracted later if needed.

---

## 3. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER (Browser)                          │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTPS
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND — Next.js 15                         │
│                                                                  │
│  Dashboard · Search Performance · Content · Intelligence         │
│  Automation · Reports · Settings                                 │
│  ─────────────────────────────────────────────────────────────── │
│  shadcn/ui · TanStack Table · Recharts · TanStack Query          │
└──────────────────────────────┬──────────────────────────────────┘
                               │ REST API (/api/v1/*)
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BACKEND — FastAPI                              │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐   │
│  │   Auth    │  │ Services │  │   API    │  │    Agent      │   │
│  │  Module   │  │  Layer   │  │ Handlers │  │ Orchestrator  │   │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘   │
│  ─────────────────────────────────────────────────────────────── │
│  Pydantic Schemas · SQLAlchemy Models · Alembic Migrations       │
└────────┬───────────────────┬───────────────────┬────────────────┘
         │                   │                   │
         ▼                   ▼                   ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────────────┐
│  PostgreSQL  │   │    Redis     │   │    Celery Workers        │
│              │   │              │   │                          │
│  30 tables   │   │  Message     │   │  Sync tasks              │
│  Historical  │   │  Broker      │   │  Analysis tasks          │
│  data        │   │  Cache       │   │  Agent tasks             │
│  Audit logs  │   │  Rate limits │   │  Notification tasks      │
│              │   │              │   │  ────────────────────    │
│              │   │              │   │  Celery Beat (Scheduler) │
└──────────────┘   └──────────────┘   └───────────┬──────────────┘
                                                   │
                              ┌─────────────────────┼──────────────────┐
                              ▼                     ▼                  ▼
                   ┌──────────────────┐  ┌──────────────┐  ┌──────────────────┐
                   │ Google Search    │  │  WordPress   │  │   AI Providers   │
                   │ Console API     │  │  REST API    │  │                  │
                   │                  │  │              │  │  Content gen     │
                   │ OAuth 2.0       │  │  Import      │  │  Analysis        │
                   │ Performance     │  │  Publish     │  │  Scoring         │
                   │ data            │  │  Update      │  │                  │
                   └──────────────────┘  └──────────────┘  └──────────────────┘
                              │                     │                  │
                              └─────────────────────┼──────────────────┘
                                                    ▼
                                         ┌──────────────────┐
                                         │      n8n         │
                                         │                  │
                                         │  Complex multi-  │
                                         │  step workflows  │
                                         │  Notifications   │
                                         │  Retry chains    │
                                         └────────┬─────────┘
                                                  │
                                    ┌─────────────┼─────────────┐
                                    ▼             ▼             ▼
                              Telegram        Email        Webhooks
```

---

## 4. Component Descriptions

### 4.1 Frontend (Next.js 15)

The dashboard application. Uses App Router with server components for initial page loads and client components for interactive features (charts, tables, filters).

Responsibilities:
- Render all dashboard pages
- Handle user authentication (JWT storage, refresh)
- Make API calls to backend
- Display real-time data (polling via TanStack Query)
- Provide responsive layout (desktop-first, mobile-responsive)

Does NOT contain:
- Business logic
- Direct database access
- Direct external API calls

### 4.2 Backend (FastAPI)

The central API server. All business logic lives here.

Layers:
- **API layer** (`api/v1/`): Route handlers, request validation, response formatting
- **Service layer** (`services/`): Business logic, database operations, orchestration
- **Model layer** (`models/`): SQLAlchemy ORM models
- **Schema layer** (`schemas/`): Pydantic request/response schemas
- **Integration layer** (`integrations/`): External service clients (Google, WordPress, n8n, AI)
- **Agent layer** (`agents/`): AI agent definitions and orchestrator
- **Worker layer** (`workers/`): Celery task definitions
- **Core layer** (`core/`): Security, permissions, exceptions, utilities

### 4.3 Celery Workers

Background task execution. Runs the same codebase as the backend but in worker mode.

Task categories:
- **Sync tasks**: Search Console data fetch, WordPress content import
- **Analysis tasks**: SEO scoring, opportunity detection, alert generation
- **Agent tasks**: AI agent execution, content generation, review
- **Notification tasks**: Telegram, email, dashboard notifications
- **Maintenance tasks**: Data aggregation, cleanup, health checks

**Celery Beat** runs as a separate container and schedules recurring tasks (daily sync, weekly analysis, monthly reports).

### 4.4 PostgreSQL

Primary data store. All business data, historical metrics, agent decisions, and audit logs.

Key design decisions:
- UUID primary keys for all tables
- `created_at` / `updated_at` timestamps on every table
- `deleted_at` for soft-delete on business entities
- JSONB columns for flexible metadata
- Composite unique constraints for idempotent syncs
- Proper indexes on all foreign keys and filter columns
- Organization-scoped queries enforced at the service layer

### 4.5 Redis

Three roles:
1. **Celery message broker**: Task queue for workers
2. **Cache**: Dashboard aggregates, API response caching (TTL-based)
3. **Rate limiting**: Per-user API rate limits, per-website sync rate limits

Redis is ephemeral. No business data lives only in Redis. If Redis restarts, the system recovers — cached data is recalculated, pending tasks are re-queued.

### 4.6 n8n

Visual workflow engine for complex multi-step integrations. NOT the primary task runner.

n8n is used for:
- Multi-step publishing pipelines (generate → review → format → publish to WordPress)
- Notification dispatch (fan-out to Telegram + email)
- Complex retry chains with branching logic
- Integration workflows that benefit from visual debugging

n8n is NOT used for:
- Data storage
- Business logic
- Authentication
- Direct database access

Communication pattern:
```
Backend → (webhook) → n8n → (executes) → (callback) → Backend API
```

### 4.7 External Services

| Service | Protocol | Purpose |
|---|---|---|
| Google Search Console API | REST + OAuth 2.0 | Performance data |
| Google OAuth | OAuth 2.0 | Account authentication |
| WordPress REST API | REST + App Passwords | Content import/export |
| AI Providers | REST | Content generation, analysis |
| Telegram Bot API | REST | Alert notifications |
| SMTP | SMTP | Email notifications |

---

## 5. Technology Stack

### Backend

| Component | Technology | Version |
|---|---|---|
| Language | Python | 3.12 |
| Framework | FastAPI | 0.115+ |
| ORM | SQLAlchemy | 2.0 |
| Migrations | Alembic | 1.13+ |
| Validation | Pydantic | 2.0 |
| Task Queue | Celery | 5.4+ |
| Scheduler | Celery Beat | (built-in) |
| HTTP Client | httpx | 0.27+ |
| Password Hashing | passlib + bcrypt | — |
| JWT | python-jose | — |
| Encryption | cryptography (Fernet) | — |
| Testing | pytest + pytest-asyncio | — |

### Frontend

| Component | Technology | Version |
|---|---|---|
| Framework | Next.js | 15 |
| Language | TypeScript | 5.5+ |
| Routing | App Router | (built-in) |
| CSS | Tailwind CSS | 4 |
| Components | shadcn/ui | latest |
| Server State | TanStack Query | 5 |
| Charts | Recharts | 2.12+ |
| Data Tables | TanStack Table | 8 |
| Forms | React Hook Form + Zod | — |
| Icons | Lucide React | — |
| Date Handling | date-fns | — |

### Infrastructure

| Component | Technology | Version |
|---|---|---|
| Containers | Docker + Docker Compose | — |
| Database | PostgreSQL | 16 |
| Cache/Broker | Redis | 7 |
| Automation | n8n | latest |
| Worker Monitor | Flower | (dev only) |
| Reverse Proxy | Nginx | (production) |

---

## 6. Multi-Tenancy Design

### Hierarchy

```
Organization (tenant boundary)
└── Project (logical grouping)
    └── Website (operational unit)
        ├── Search Console Connection (1:1)
        ├── WordPress Connection (1:1)
        ├── Categories (tree)
        ├── Content Items (list)
        ├── Search Performance Data (time series)
        ├── SEO Alerts (list)
        ├── SEO Opportunities (list)
        ├── SEO Scores (computed)
        ├── Agent Runs (log)
        ├── Automation Jobs (queue)
        └── Automation Rules (config)
```

### Isolation Enforcement

Every service method receives `organization_id` from the authenticated user's JWT. The dependency injection chain guarantees:

```python
# dependencies.py — simplified
async def get_current_org(token: JWT) -> Organization:
    member = db.query(OrgMember).filter_by(user_id=token.sub).first()
    return member.organization

# Every service method
class WebsiteService:
    def list_websites(self, org_id: UUID, project_id: UUID) -> list[Website]:
        return db.query(Website).filter(
            Website.organization_id == org_id,
            Website.project_id == project_id
        ).all()
```

There is no endpoint that returns data without org scoping. Even admin endpoints are org-scoped.

---

## 7. Data Flow Diagrams

### 7.1 Search Console Data Flow

```
Google Search Console API
        │
        │ OAuth 2.0 + Performance API
        ▼
┌──────────────────────────┐
│  Celery Sync Task        │
│                          │
│  1. Check last sync date │
│  2. Fetch date range     │
│  3. Validate response    │
│  4. Normalize dimensions │
│  5. Upsert to DB         │
│  6. Update sync status   │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  PostgreSQL              │
│                          │
│  search_performance_     │
│  daily                   │
│  (historical fact table) │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Analysis Pipeline       │
│                          │
│  1. Aggregate metrics    │
│  2. Calculate changes    │
│  3. Detect drops         │
│  4. Detect opportunities │
│  5. Update SEO scores    │
│  6. Generate alerts      │
│  7. AI executive summary │
└──────────┬───────────────┘
           │
           ▼
    Dashboard displays
    real-time insights
```

### 7.2 Content Production Flow

```
SEO Opportunity / User Request
        │
        ▼
┌──────────────────────────┐
│  Content Strategy Agent  │
│                          │
│  1. Analyze opportunity  │
│  2. Check existing       │
│     content              │
│  3. Determine intent     │
│  4. Plan content piece   │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Keyword Research Agent  │
│                          │
│  1. Cluster keywords     │
│  2. Analyze competition  │
│  3. Set target keyword   │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Content Brief Agent     │
│                          │
│  1. Generate outline     │
│  2. Set word count       │
│  3. Define tone          │
│  4. List internal links  │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Content Writer Agent    │
│                          │
│  1. Generate article     │
│  2. Follow brief         │
│  3. Insert links         │
│  4. Add metadata         │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Content Reviewer Agent  │
│                          │
│  1. Quality check        │
│  2. SEO check            │
│  3. Duplicate check      │
│  4. Fact check           │
│  5. Score content        │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Approval Gate           │
│                          │
│  If risk > threshold:    │
│    → approval_requests   │
│    → Wait for human      │
│                          │
│  If risk ≤ threshold:    │
│    → Auto-approve        │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  WordPress Publishing    │
│  (via n8n workflow)      │
│                          │
│  1. Create draft         │
│  2. Set metadata         │
│  3. Schedule/publish     │
│  4. Confirm via callback │
└──────────┬───────────────┘
           │
           ▼
    Performance monitoring
    (ongoing via daily sync)
```

### 7.3 Alert and Response Flow

```
Analysis Pipeline detects anomaly
        │
        ▼
┌──────────────────────────┐
│  Create SEO Alert        │
│                          │
│  Type: traffic_drop      │
│  Severity: high          │
│  Data: before/after      │
│  AI explanation          │
│  Suggested action        │
└──────────┬───────────────┘
           │
           ├──────────────────────┐
           ▼                      ▼
┌──────────────────┐   ┌──────────────────┐
│  Dashboard       │   │  Notification    │
│  Alert Center    │   │  (Telegram/Email)│
└──────────────────┘   └──────────────────┘
           │
           ▼ (if automation_mode != manual)
┌──────────────────────────┐
│  Alert Agent             │
│                          │
│  1. Analyze root cause   │
│  2. Propose action       │
│  3. Assess risk          │
│  4. Create task or       │
│     delegate to agent    │
└──────────┬───────────────┘
           │
           ▼
   Risk-based approval gate
```

---

## 8. Security Architecture

### Authentication Flow

```
User Login
    │
    ▼
Backend validates credentials
    │
    ├── Returns: access_token (JWT, 15 min TTL)
    ├── Returns: refresh_token (opaque, 7 day TTL)
    └── Stores: refresh_token hash in DB
    
API Request
    │
    ▼
Authorization header: Bearer {access_token}
    │
    ▼
Backend decodes JWT, extracts user_id
    │
    ▼
Loads org membership + role
    │
    ▼
RBAC middleware checks permission
    │
    ▼
Handler executes with org-scoped context

Token Refresh
    │
    ▼
POST /api/v1/auth/refresh with refresh_token
    │
    ▼
Backend validates refresh_token against DB hash
    │
    ▼
Issues new access_token + rotates refresh_token
```

### Credential Encryption

OAuth tokens and WordPress credentials are encrypted at rest using Fernet symmetric encryption. The encryption key is stored as an environment variable, never in code or database.

```
Plaintext token → Fernet.encrypt() → Stored in DB as ciphertext
DB ciphertext → Fernet.decrypt() → Used in API call → Discarded
```

### Rate Limiting

| Endpoint Group | Limit |
|---|---|
| Auth (login, register) | 10 req/min per IP |
| Auth (refresh) | 30 req/min per user |
| API (general) | 100 req/min per user |
| Sync triggers | 5 req/hour per website |

Enforced via Redis-backed sliding window counters.

---

## 9. Infrastructure Architecture

### Docker Compose (Development)

```yaml
# docker-compose.yml — service overview
services:
  frontend:     # Next.js dev server, port 3000
  backend:      # FastAPI + uvicorn, port 8000
  worker:       # Celery worker (same image as backend)
  beat:         # Celery beat scheduler (same image as backend)
  postgres:     # PostgreSQL 16, port 5432
  redis:        # Redis 7, port 6379
  n8n:          # n8n automation, port 5678
  flower:       # Celery monitoring (dev only), port 5555
```

### Docker Compose (Production)

Adds:
- Nginx reverse proxy (port 80/443)
- SSL termination
- Backend runs with gunicorn + uvicorn workers
- Frontend runs as static build
- Health checks on all services
- Restart policies
- Volume mounts for persistent data (postgres, n8n, redis)
- Log drivers

### Volume Strategy

| Service | Volume | Purpose |
|---|---|---|
| PostgreSQL | `pgdata` | Database files |
| Redis | `redisdata` | Persistence (RDB snapshots) |
| n8n | `n8ndata` | Workflow definitions, credentials |

### Network

All services communicate on an internal Docker network. Only `nginx` (production) or `frontend` + `backend` (development) expose ports to the host.

---

## 10. Deployment Architecture

### Single Server (MVP)

```
VPS (4 CPU, 8 GB RAM, 100 GB SSD)
├── Docker Compose
│   ├── nginx (reverse proxy)
│   ├── frontend (Next.js)
│   ├── backend (FastAPI)
│   ├── worker (Celery × 2 concurrency)
│   ├── beat (Celery scheduler)
│   ├── postgres (PostgreSQL)
│   ├── redis (Redis)
│   └── n8n
├── Automated backups (pg_dump daily)
└── Monitoring (health check endpoints)
```

### Future Scaling Path

```
Load Balancer
├── Frontend (static, CDN)
├── Backend (2+ instances)
├── Workers (scale horizontally)
├── Managed PostgreSQL
├── Managed Redis
└── n8n (separate instance)
```

The modular monolith architecture allows vertical scaling first, then selective extraction of heavy modules (workers, n8n) to separate servers.

---

## 11. Error Handling Strategy

### API Errors

All errors follow RFC 7807 Problem Details format:

```json
{
  "type": "https://seoos.app/errors/not-found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "Website with ID abc-123 not found",
  "instance": "/api/v1/websites/abc-123"
}
```

### Worker Errors

Celery tasks use built-in retry with exponential backoff:

| Task Type | Max Retries | Backoff |
|---|---|---|
| Search Console sync | 3 | 60s, 300s, 900s |
| WordPress sync | 3 | 30s, 120s, 600s |
| AI generation | 2 | 30s, 120s |
| Notifications | 5 | 10s, 30s, 60s, 300s, 900s |

Failed tasks after max retries create an `seo_alert` with severity `high` and type `automation_failure`.

### External Service Errors

All external API clients use:
- Connection timeouts (10s)
- Read timeouts (30s for most, 120s for AI generation)
- Retry on 429 (rate limit) with `Retry-After` header
- Retry on 500/502/503 with exponential backoff
- Circuit breaker pattern for repeated failures

---

## 12. Observability

### Structured Logging

All services emit JSON-structured logs with:
- Timestamp
- Level (DEBUG, INFO, WARNING, ERROR)
- Service name
- Request ID (correlation)
- Organization ID (when available)
- User ID (when available)
- Message
- Extra data

### Health Checks

| Service | Endpoint | Checks |
|---|---|---|
| Backend | `GET /health` | DB connection, Redis connection |
| Frontend | `GET /api/health` | Backend reachability |
| Workers | Celery inspect ping | Worker responsiveness |

### Metrics (Future)

Prometheus-compatible metrics for:
- API request latency (p50, p95, p99)
- Background task duration
- Queue depth
- Sync success/failure rates
- Active agent runs

---

## 13. File Structure

```
SEO/
├── docker-compose.yml              # Development services
├── docker-compose.prod.yml         # Production overrides
├── .env.example                    # Environment variable template
├── .gitignore
├── README.md
│
├── docs/
│   └── architecture/               # This document set
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml               # Dependencies (uv/pip)
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/               # Migration files
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI app creation
│   │   ├── config.py                # Settings from env
│   │   ├── database.py              # Engine + session factory
│   │   ├── dependencies.py          # DI: auth, db session, org scope
│   │   │
│   │   ├── models/                  # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # Base model with id, timestamps
│   │   │   ├── user.py
│   │   │   ├── organization.py
│   │   │   ├── project.py
│   │   │   ├── website.py
│   │   │   ├── google_account.py
│   │   │   ├── search_console.py
│   │   │   ├── search_performance.py
│   │   │   ├── wordpress.py
│   │   │   ├── category.py
│   │   │   ├── content.py
│   │   │   ├── seo.py
│   │   │   ├── agent.py
│   │   │   ├── automation.py
│   │   │   ├── notification.py
│   │   │   └── audit.py
│   │   │
│   │   ├── schemas/                 # Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── user.py
│   │   │   ├── organization.py
│   │   │   ├── project.py
│   │   │   ├── website.py
│   │   │   ├── search_console.py
│   │   │   ├── performance.py
│   │   │   ├── content.py
│   │   │   ├── seo.py
│   │   │   ├── agent.py
│   │   │   ├── automation.py
│   │   │   └── common.py            # Pagination, filters, errors
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py        # Main v1 router
│   │   │       ├── auth.py
│   │   │       ├── users.py
│   │   │       ├── organizations.py
│   │   │       ├── projects.py
│   │   │       ├── websites.py
│   │   │       ├── google.py
│   │   │       ├── search_console.py
│   │   │       ├── performance.py
│   │   │       ├── queries.py
│   │   │       ├── pages.py
│   │   │       ├── wordpress.py
│   │   │       ├── categories.py
│   │   │       ├── content.py
│   │   │       ├── content_calendar.py
│   │   │       ├── content_briefs.py
│   │   │       ├── opportunities.py
│   │   │       ├── alerts.py
│   │   │       ├── seo_scores.py
│   │   │       ├── agents.py
│   │   │       ├── automation.py
│   │   │       ├── approvals.py
│   │   │       ├── notifications.py
│   │   │       ├── reports.py
│   │   │       ├── audit_logs.py
│   │   │       └── settings.py
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── auth_service.py
│   │   │   ├── user_service.py
│   │   │   ├── organization_service.py
│   │   │   ├── project_service.py
│   │   │   ├── website_service.py
│   │   │   ├── google_service.py
│   │   │   ├── search_console_service.py
│   │   │   ├── performance_service.py
│   │   │   ├── wordpress_service.py
│   │   │   ├── category_service.py
│   │   │   ├── content_service.py
│   │   │   ├── calendar_service.py
│   │   │   ├── brief_service.py
│   │   │   ├── seo_scoring_service.py
│   │   │   ├── opportunity_service.py
│   │   │   ├── alert_service.py
│   │   │   ├── agent_orchestrator.py
│   │   │   ├── automation_service.py
│   │   │   ├── approval_service.py
│   │   │   ├── notification_service.py
│   │   │   ├── report_service.py
│   │   │   └── audit_service.py
│   │   │
│   │   ├── workers/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py        # Celery instance config
│   │   │   └── tasks/
│   │   │       ├── __init__.py
│   │   │       ├── search_console_tasks.py
│   │   │       ├── wordpress_tasks.py
│   │   │       ├── analysis_tasks.py
│   │   │       ├── agent_tasks.py
│   │   │       ├── content_tasks.py
│   │   │       ├── notification_tasks.py
│   │   │       └── maintenance_tasks.py
│   │   │
│   │   ├── integrations/
│   │   │   ├── __init__.py
│   │   │   ├── google/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── oauth.py          # OAuth flow
│   │   │   │   └── search_console.py  # GSC API client
│   │   │   ├── wordpress/
│   │   │   │   ├── __init__.py
│   │   │   │   └── client.py          # WP REST API client
│   │   │   ├── n8n/
│   │   │   │   ├── __init__.py
│   │   │   │   └── client.py          # n8n webhook client
│   │   │   └── ai/
│   │   │       ├── __init__.py
│   │   │       ├── base.py            # Abstract provider
│   │   │       ├── openai_provider.py
│   │   │       └── provider_factory.py
│   │   │
│   │   ├── agents/
│   │   │   ├── __init__.py
│   │   │   ├── base_agent.py          # Abstract base agent
│   │   │   ├── seo_manager.py
│   │   │   ├── search_analyst.py
│   │   │   ├── keyword_agent.py
│   │   │   ├── content_strategist.py
│   │   │   ├── content_writer.py
│   │   │   ├── content_reviewer.py
│   │   │   ├── internal_linker.py
│   │   │   ├── content_refresher.py
│   │   │   ├── alert_agent.py
│   │   │   └── report_agent.py
│   │   │
│   │   └── core/
│   │       ├── __init__.py
│   │       ├── security.py            # JWT, password hashing
│   │       ├── encryption.py          # Fernet for credentials
│   │       ├── permissions.py         # RBAC decorator/middleware
│   │       ├── exceptions.py          # App exception classes
│   │       └── utils.py
│   │
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py                # Fixtures, test DB
│       ├── test_auth.py
│       ├── test_organizations.py
│       ├── test_websites.py
│       ├── test_search_console.py
│       └── ...
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── components.json              # shadcn/ui config
│   │
│   └── src/
│       ├── app/
│       │   ├── layout.tsx            # Root layout
│       │   ├── page.tsx              # Landing / redirect
│       │   ├── globals.css
│       │   │
│       │   ├── (auth)/
│       │   │   ├── layout.tsx        # Auth layout (centered)
│       │   │   ├── login/page.tsx
│       │   │   ├── register/page.tsx
│       │   │   └── forgot-password/page.tsx
│       │   │
│       │   └── (dashboard)/
│       │       ├── layout.tsx        # Dashboard layout (sidebar)
│       │       ├── page.tsx          # Main dashboard
│       │       │
│       │       ├── search-performance/
│       │       │   ├── page.tsx      # Overview
│       │       │   ├── queries/page.tsx
│       │       │   ├── pages/page.tsx
│       │       │   ├── countries/page.tsx
│       │       │   ├── devices/page.tsx
│       │       │   └── trends/page.tsx
│       │       │
│       │       ├── website-structure/
│       │       │   ├── page.tsx      # Site map
│       │       │   ├── categories/page.tsx
│       │       │   └── internal-links/page.tsx
│       │       │
│       │       ├── content/
│       │       │   ├── page.tsx      # Content table
│       │       │   ├── calendar/page.tsx
│       │       │   ├── kanban/page.tsx
│       │       │   ├── ideas/page.tsx
│       │       │   ├── briefs/page.tsx
│       │       │   └── [id]/page.tsx  # Content detail
│       │       │
│       │       ├── seo-intelligence/
│       │       │   ├── page.tsx      # Overview
│       │       │   ├── opportunities/page.tsx
│       │       │   ├── alerts/page.tsx
│       │       │   ├── scores/page.tsx
│       │       │   └── gaps/page.tsx
│       │       │
│       │       ├── automation/
│       │       │   ├── page.tsx      # AI SEO Manager
│       │       │   ├── agents/page.tsx
│       │       │   ├── jobs/page.tsx
│       │       │   ├── approvals/page.tsx
│       │       │   └── activity/page.tsx
│       │       │
│       │       ├── reports/
│       │       │   ├── page.tsx
│       │       │   └── [id]/page.tsx
│       │       │
│       │       └── settings/
│       │           ├── page.tsx      # Organization
│       │           ├── users/page.tsx
│       │           ├── websites/page.tsx
│       │           ├── google/page.tsx
│       │           ├── wordpress/page.tsx
│       │           ├── ai/page.tsx
│       │           ├── automation/page.tsx
│       │           ├── notifications/page.tsx
│       │           └── security/page.tsx
│       │
│       ├── components/
│       │   ├── ui/                   # shadcn/ui components
│       │   ├── layout/
│       │   │   ├── sidebar.tsx
│       │   │   ├── header.tsx
│       │   │   ├── org-switcher.tsx
│       │   │   └── website-selector.tsx
│       │   ├── dashboard/
│       │   │   ├── metric-card.tsx
│       │   │   ├── seo-health-score.tsx
│       │   │   ├── ai-summary.tsx
│       │   │   └── quick-actions.tsx
│       │   ├── charts/
│       │   │   ├── performance-chart.tsx
│       │   │   ├── trend-chart.tsx
│       │   │   └── comparison-chart.tsx
│       │   └── data-table/
│       │       ├── data-table.tsx
│       │       ├── column-header.tsx
│       │       ├── pagination.tsx
│       │       ├── filters.tsx
│       │       └── view-options.tsx
│       │
│       ├── lib/
│       │   ├── api-client.ts         # Fetch wrapper with auth
│       │   ├── auth.ts               # Token management
│       │   ├── utils.ts              # cn(), formatters
│       │   └── constants.ts
│       │
│       ├── hooks/
│       │   ├── use-auth.ts
│       │   ├── use-website.ts
│       │   ├── use-performance.ts
│       │   └── use-debounce.ts
│       │
│       └── types/
│           ├── api.ts                # API response types
│           ├── auth.ts
│           ├── website.ts
│           ├── performance.ts
│           ├── content.ts
│           └── seo.ts
│
├── n8n/
│   ├── Dockerfile                    # Custom n8n image if needed
│   └── workflows/
│       ├── search-console-daily-sync.json
│       ├── wordpress-publish.json
│       ├── content-generation-pipeline.json
│       ├── telegram-notification.json
│       ├── email-notification.json
│       ├── weekly-report.json
│       └── failed-job-recovery.json
│
└── docker/
    ├── nginx/
    │   └── nginx.conf                # Production reverse proxy
    ├── postgres/
    │   └── init.sql                  # Initial DB creation
    └── redis/
        └── redis.conf                # Custom Redis config
```
