from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://seoos:seoos@localhost:5432/seoos"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "change-me"
    ENCRYPTION_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # CORS
    BACKEND_CORS_ORIGINS: str = "http://localhost:3000"

    # API
    API_V1_PREFIX: str = "/api/v1"


    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # AI provider — used as fallback when the caller does not specify one.
    # Valid values: openai, anthropic, google, algorithmic_fallback
    DEFAULT_AI_PROVIDER: str = "algorithmic_fallback"

    # n8n Webhooks (used by automations module only, NOT for content generation)
    N8N_WEBHOOK_BASE_URL: str = "http://n8n:5678"
    # Shared secret n8n must present on POST /automations/webhook-callback.
    # Empty means the callback endpoint is disabled (fail closed) rather than open.
    N8N_WEBHOOK_SECRET: str = ""

    # Public frontend domain, used to build OAuth return redirects.
    DOMAIN: str = "seo.arouxpingg.com"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",")]

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
