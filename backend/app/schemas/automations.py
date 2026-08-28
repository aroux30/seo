from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class AutomationWorkflowCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None
    template_key: str | None = None
    trigger_type: str = "cron"
    cron_expression: str | None = None
    n8n_webhook_url: str = Field(..., max_length=500)
    is_active: bool = True
    config_metadata: dict = Field(default_factory=dict)


class AutomationWorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cron_expression: str | None = None
    n8n_webhook_url: str | None = None
    is_active: bool | None = None
    config_metadata: dict | None = None


class AutomationWorkflowToggle(BaseModel):
    is_active: bool


class AutomationWorkflowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    website_id: UUID
    name: str
    description: str | None = None
    template_key: str | None = None
    trigger_type: str
    cron_expression: str | None = None
    n8n_webhook_url: str
    is_active: bool
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    config_metadata: dict
    created_at: datetime
    updated_at: datetime


class AutomationLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    website_id: UUID
    status: str
    execution_time_ms: int | None = None
    payload_json: dict
    result_json: dict
    error_message: str | None = None
    created_at: datetime


class AutomationTemplateRead(BaseModel):
    key: str
    name: str
    description: str
    category: str
    default_trigger: str
    default_cron: str
    sample_webhook_url: str
    parameters_schema: list[dict] = Field(default_factory=list)


class AutomationWebhookCallbackRequest(BaseModel):
    workflow_id: UUID
    website_id: UUID
    status: str
    execution_time_ms: int | None = None
    result_json: dict = Field(default_factory=dict)
    error_message: str | None = None
