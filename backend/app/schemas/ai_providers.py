from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


class AiProviderKeyCreate(BaseModel):
    provider_name: str = Field(default="gemini", description="gemini, openai, claude, deepseek, openrouter")
    label: str = Field(min_length=1, max_length=100, description="Display name for this key")
    api_key: str = Field(min_length=5, description="Plaintext API key to be encrypted and stored")
    model_name: str = Field(default="gemini-3.6-flash", max_length=100)
    priority: int = Field(default=1, ge=1, le=100, description="Lower number = used first")
    is_active: bool = True


class AiProviderKeyUpdate(BaseModel):
    label: str | None = None
    api_key: str | None = None
    model_name: str | None = None
    priority: int | None = Field(default=None, ge=1, le=100)
    is_active: bool | None = None


class AiProviderKeyRead(BaseModel):
    id: UUID
    organization_id: UUID | None
    provider_name: str
    label: str
    masked_api_key: str
    model_name: str
    priority: int
    is_active: bool
    last_error_at: datetime | None = None
    error_count: int = 0
    last_used_at: datetime | None = None
    usage_count: int = 0
    status: str = "active"  # active, rate_limited, error
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiProviderKeyTestRequest(BaseModel):
    provider_name: str = "gemini"
    api_key: str
    model_name: str = "gemini-3.6-flash"


class AiProviderKeyTestResult(BaseModel):
    status: str
    provider: str
    model: str
    latency_ms: int
    response_sample: str
