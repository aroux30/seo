from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


# --- CONTENT BRIEFS ---

class ContentBriefCreate(BaseModel):
    target_keyword: str = Field(..., min_length=2, max_length=255)
    title: str | None = None
    secondary_keywords: list[str] = Field(default_factory=list)
    search_intent: str = Field(default="informational")
    target_word_count: int = Field(default=1500, ge=300, le=5000)
    keyword_id: UUID | None = None


class ContentBriefRead(BaseModel):
    id: UUID
    website_id: UUID
    keyword_id: UUID | None = None
    title: str
    target_keyword: str
    secondary_keywords: list
    search_intent: str
    outline: dict = Field(default_factory=dict)
    target_word_count: int
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --- CONTENT ARTICLES ---

class ContentArticleCreate(BaseModel):
    brief_id: UUID | None = None
    title: str | None = None
    target_keyword: str | None = None
    provider: str | None = None


class ContentArticleUpdate(BaseModel):
    title: str | None = None
    content_markdown: str | None = None
    # Closed vocabulary: the list page badges and the WordPress publish flow both
    # branch on these exact strings, so an arbitrary client-supplied value would
    # either render a meaningless badge or silently corrupt lifecycle logic.
    status: Literal["draft", "review", "published"] | None = None


class ContentArticlePublishRequest(BaseModel):
    # Validated here rather than at the WordPress API: an invalid value used to
    # travel all the way to the WP REST endpoint and come back as a 500 with the
    # internal WP URL leaked in the message. Pydantic rejects it with a clean 422.
    post_status: Literal["draft", "publish"] = "draft"


class ContentArticleRead(BaseModel):
    id: UUID
    website_id: UUID
    brief_id: UUID | None = None
    title: str
    slug: str
    content_markdown: str
    content_html: str
    seo_score: int
    seo_metadata: dict = Field(default_factory=dict)
    status: str
    wp_post_id: int | None = None
    published_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
