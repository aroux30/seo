from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_membership, require_role
from app.models import OrganizationMember
from app.schemas import (
    ProjectCreate, ProjectUpdate, ProjectRead,
    WebsiteCreate, WebsiteUpdate, WebsiteRead,
)
from app.services import (
    create_project, list_projects, get_project, update_project, delete_project,
    create_website, list_websites, get_website, update_website, delete_website,
)

projects_router = APIRouter(prefix="/projects", tags=["projects"])
websites_router = APIRouter(prefix="/websites", tags=["websites"])


# --- Projects ---

@projects_router.post("", response_model=dict, status_code=201)
async def create_proj(
    body: ProjectCreate,
    member: OrganizationMember = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    project = await create_project(
        db, member.organization_id, member.user_id,
        body.name, body.slug, body.description,
    )
    await db.commit()
    return {"data": ProjectRead.model_validate(project)}


@projects_router.get("", response_model=dict)
async def list_projs(
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    projects = await list_projects(db, member.organization_id)
    return {"data": [ProjectRead.model_validate(p) for p in projects]}


@projects_router.get("/{project_id}", response_model=dict)
async def get_proj(
    project_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    project = await get_project(db, member.organization_id, project_id)
    return {"data": ProjectRead.model_validate(project)}


@projects_router.put("/{project_id}", response_model=dict)
async def update_proj(
    project_id: UUID,
    body: ProjectUpdate,
    member: OrganizationMember = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    data = body.model_dump(exclude_unset=True)
    project = await update_project(db, member.organization_id, member.user_id, project_id, data)
    await db.commit()
    return {"data": ProjectRead.model_validate(project)}


@projects_router.delete("/{project_id}", status_code=204)
async def delete_proj(
    project_id: UUID,
    member: OrganizationMember = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    await delete_project(db, member.organization_id, member.user_id, project_id)
    await db.commit()
    return None


# --- Websites ---

@websites_router.post("", response_model=dict, status_code=201)
async def create_site(
    body: WebsiteCreate,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    website = await create_website(
        db, member.organization_id, member.user_id,
        body.project_id, body.name, body.domain, body.base_url,
        body.website_type, body.language, body.country, body.timezone,
        body.automation_mode,
    )
    await db.commit()
    
    # Trigger initial audit in background so the dashboard isn't empty
    from app.workers.tasks import run_website_audit_task
    run_website_audit_task.delay(str(website.id))
    
    return {"data": WebsiteRead.model_validate(website)}


@websites_router.get("", response_model=dict)
async def list_sites(
    project_id: UUID | None = Query(None),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    websites = await list_websites(db, member.organization_id, project_id)
    return {"data": [WebsiteRead.model_validate(w) for w in websites]}


@websites_router.get("/{website_id}", response_model=dict)
async def get_site(
    website_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    website = await get_website(db, member.organization_id, website_id)
    return {"data": WebsiteRead.model_validate(website)}


@websites_router.patch("/{website_id}", response_model=dict)
async def update_site(
    website_id: UUID,
    body: WebsiteUpdate,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    data = body.model_dump(exclude_none=True)
    website = await update_website(db, member.organization_id, member.user_id, website_id, data)
    await db.commit()
    return {"data": WebsiteRead.model_validate(website)}


@websites_router.delete("/{website_id}", status_code=204)
async def delete_site(
    website_id: UUID,
    member: OrganizationMember = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    await delete_website(db, member.organization_id, member.user_id, website_id)
    await db.commit()
    return None
