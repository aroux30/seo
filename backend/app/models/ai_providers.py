from datetime import datetime
from uuid import UUID
from sqlalchemy import (
    String, Text, Boolean, Integer, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB

from app.models.base import BaseModel


class AiProviderKey(BaseModel):
    """Stores multiple AI provider API keys per organization for automatic rotation and failover."""
    __tablename__ = "ai_provider_keys"

    organization_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    provider_name: Mapped[str] = mapped_column(String(50), default="gemini", nullable=False)  # gemini, openai, claude, deepseek, openrouter
    label: Mapped[str] = mapped_column(String(100), nullable=False)  # Display label, e.g. "Gemini Pro #1"
    encrypted_api_key: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), default="gemini-2.0-flash", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)  # Lower value = higher priority (used first)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta_info: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)

    __table_args__ = (
        Index("idx_ai_provider_org_prio", "organization_id", "is_active", "priority"),
    )
