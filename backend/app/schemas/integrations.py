from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class OAuthIntegrationRead(BaseModel):
    id: UUID
    website_id: UUID
    provider: str
    client_id: str | None = None
    scopes: str | None = None
    expires_at: datetime | None = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WordPressConnectRequest(BaseModel):
    wp_url: str = Field(..., max_length=500, description="URL to WordPress root e.g. https://example.com")
    username: str = Field(..., max_length=255)
    app_password: str = Field(..., max_length=255, description="WordPress REST API Application Password")


class WordPressIntegrationRead(BaseModel):
    id: UUID
    website_id: UUID
    wp_url: str
    username: str
    status: str
    last_synced_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GscQueryRead(BaseModel):
    id: UUID
    website_id: UUID
    query: str
    page_url: str | None = None
    clicks: int
    impressions: int
    ctr: float
    position: float
    date_metric: date

    model_config = ConfigDict(from_attributes=True)


class GscPageRead(BaseModel):
    id: UUID
    website_id: UUID
    page_url: str
    clicks: int
    impressions: int
    ctr: float
    position: float
    date_metric: date

    model_config = ConfigDict(from_attributes=True)


class GscOverviewRead(BaseModel):
    total_clicks: int
    total_impressions: int
    avg_ctr: float
    avg_position: float
    start_date: date | None = None
    end_date: date | None = None


class KeywordCreate(BaseModel):
    keyword: str = Field(..., max_length=255)
    search_volume: int | None = None
    difficulty: int | None = Field(None, ge=0, le=100)
    target_page_url: str | None = Field(None, max_length=500)
    intent: str = Field("informational", max_length=50)
    tags: list[str] = Field(default_factory=list)


class KeywordRankingRead(BaseModel):
    id: UUID
    keyword_id: UUID
    position: float
    url_found: str | None = None
    check_date: date

    model_config = ConfigDict(from_attributes=True)


class KeywordRead(BaseModel):
    id: UUID
    website_id: UUID
    keyword: str
    search_volume: int | None = None
    difficulty: int | None = None
    target_page_url: str | None = None
    intent: str
    tags: list[str]
    last_position: float | None = None
    best_position: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GscCountryRead(BaseModel):
    id: UUID
    country: str
    clicks: int
    impressions: int
    ctr: float
    position: float
    date_metric: date
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class GscDeviceRead(BaseModel):
    id: UUID
    device: str
    clicks: int
    impressions: int
    ctr: float
    position: float
    date_metric: date
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class GscDateRead(BaseModel):
    id: UUID
    clicks: int
    impressions: int
    ctr: float
    position: float
    date_metric: date
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

