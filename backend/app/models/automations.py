from datetime import datetime
from sqlalchemy import String, Integer, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import BaseModel


class AutomationWorkflow(BaseModel):
    __tablename__ = "automation_workflows"

    website_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    trigger_type: Mapped[str] = mapped_column(String(50), default="cron", nullable=False)
    cron_expression: Mapped[str | None] = mapped_column(String(100), nullable=True)
    n8n_webhook_url: Mapped[str] = mapped_column(String(500), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    config_metadata: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    website = relationship("Website", backref="automation_workflows")
    logs = relationship("AutomationLog", back_populates="workflow", cascade="all, delete-orphan")


class AutomationLog(BaseModel):
    __tablename__ = "automation_logs"

    workflow_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("automation_workflows.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    website_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    result_json: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    workflow = relationship("AutomationWorkflow", back_populates="logs")
