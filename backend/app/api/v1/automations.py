from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role, require_webhook_secret
from app.core.scoping import assert_website_in_org, assert_workflow_in_org
from app.core.ratelimit import webhook_rate_limit
from app.models import OrganizationMember
from app.schemas.automations import (
    AutomationWorkflowCreate,
    AutomationWorkflowToggle,
    AutomationWorkflowRead,
    AutomationLogRead,
    AutomationTemplateRead,
    AutomationWebhookCallbackRequest,
)
from app.services.automation_service import (
    get_predefined_templates,
    create_automation_workflow,
    get_automation_workflows,
    get_automation_workflow_by_id,
    toggle_automation_workflow,
    delete_automation_workflow,
    trigger_automation_workflow,
    get_automation_logs,
    handle_webhook_callback,
)
from app.core.exceptions import AppException

router = APIRouter(prefix="/automations", tags=["n8n Automations & SEO Workflows"])


@router.get("/templates", response_model=list[AutomationTemplateRead])
async def list_templates_endpoint(
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Get Built-in SEO OS n8n automation templates."""
    return get_predefined_templates()


@router.post("/workflows/{website_id}", response_model=AutomationWorkflowRead, status_code=status.HTTP_201_CREATED)
async def create_workflow_endpoint(
    website_id: UUID,
    payload: AutomationWorkflowCreate,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Create a new n8n automation workflow for a website."""
    await assert_website_in_org(db, website_id, member.organization_id)
    workflow = await create_automation_workflow(
        db=db,
        website_id=website_id,
        name=payload.name,
        n8n_webhook_url=payload.n8n_webhook_url,
        description=payload.description,
        template_key=payload.template_key,
        trigger_type=payload.trigger_type,
        cron_expression=payload.cron_expression,
        is_active=payload.is_active,
        config_metadata=payload.config_metadata,
    )
    return workflow


@router.get("/workflows/{website_id}", response_model=list[AutomationWorkflowRead])
async def list_workflows_endpoint(
    website_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """List all automation workflows for a website."""
    await assert_website_in_org(db, website_id, member.organization_id)
    return await get_automation_workflows(db, website_id)


@router.get("/workflows/detail/{workflow_id}", response_model=AutomationWorkflowRead)
async def get_workflow_endpoint(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Get specific workflow detail by ID."""
    await assert_workflow_in_org(db, workflow_id, member.organization_id)
    workflow = await get_automation_workflow_by_id(db, workflow_id)
    if not workflow:
        raise AppException(status_code=404, detail="اتوماسیون یافت نشد.", error_type="workflow_not_found")
    return workflow


@router.patch("/workflows/detail/{workflow_id}/toggle", response_model=AutomationWorkflowRead)
async def toggle_workflow_endpoint(
    workflow_id: UUID,
    payload: AutomationWorkflowToggle,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Enable or disable an automation workflow."""
    await assert_workflow_in_org(db, workflow_id, member.organization_id)
    return await toggle_automation_workflow(db, workflow_id, is_active=payload.is_active)


@router.delete("/workflows/detail/{workflow_id}", status_code=status.HTTP_200_OK)
async def delete_workflow_endpoint(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Delete an automation workflow (its execution logs are removed with it)."""
    await assert_workflow_in_org(db, workflow_id, member.organization_id)
    result = await delete_automation_workflow(db, workflow_id)
    await db.commit()
    return {"data": result}


@router.post("/workflows/detail/{workflow_id}/run", response_model=AutomationLogRead)
async def run_workflow_endpoint(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Manually trigger an automation workflow to call its n8n webhook URL."""
    await assert_workflow_in_org(db, workflow_id, member.organization_id)
    return await trigger_automation_workflow(db, workflow_id)


@router.get("/logs/{website_id}", response_model=list[AutomationLogRead])
async def list_logs_endpoint(
    website_id: UUID,
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Get recent execution logs for a website's automations."""
    await assert_website_in_org(db, website_id, member.organization_id)
    return await get_automation_logs(db, website_id, limit=limit)


@router.post(
    "/webhook-callback",
    response_model=AutomationLogRead,
    dependencies=[Depends(webhook_rate_limit)],
)
async def webhook_callback_endpoint(
    payload: AutomationWebhookCallbackRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_webhook_secret),
):
    """External callback endpoint for n8n to post back async execution results.

    Authenticated by the shared `X-Webhook-Secret` header, not a user session.
    """
    return await handle_webhook_callback(
        db=db,
        workflow_id=payload.workflow_id,
        website_id=payload.website_id,
        status=payload.status,
        result_json=payload.result_json,
        execution_time_ms=payload.execution_time_ms,
        error_message=payload.error_message,
    )
