from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# --- SEO AUDIT ISSUES ---

class SeoAuditIssueRead(BaseModel):
    id: UUID
    audit_id: UUID
    website_id: UUID
    category: str
    severity: str
    title: str
    description: str
    url: str | None = None
    recommendation: str
    is_resolved: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SeoAuditIssueResolveRequest(BaseModel):
    is_resolved: bool = True


# --- SEO AUDITS ---

class SeoAuditRead(BaseModel):
    id: UUID
    website_id: UUID
    status: str
    overall_score: int
    technical_score: int
    content_score: int
    ux_score: int
    pages_crawled: int
    summary: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SeoAuditDetailRead(SeoAuditRead):
    issues: list[SeoAuditIssueRead] = []


class SeoAuditRunRequest(BaseModel):
    max_pages: int = Field(default=20, ge=1, le=100)


# --- AI SEO STRATEGY ---

class AiSeoStrategyRead(BaseModel):
    id: UUID
    website_id: UUID
    title: str
    executive_summary: str
    target_audience: str | None = None
    keyword_clusters: list = Field(default_factory=list)
    content_gaps: list = Field(default_factory=list)
    action_items: list = Field(default_factory=list)
    provider_used: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiSeoStrategyGenerateRequest(BaseModel):
    provider: str | None = None  # openai, anthropic, google, or default
    focus_area: str | None = None


# --- AI AGENT LOG ---

class AiAgentLogRead(BaseModel):
    id: UUID
    website_id: UUID
    agent_name: str
    provider: str
    prompt_tokens: int
    completion_tokens: int
    action_taken: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
