from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.core.scoping import (
    assert_audit_in_org,
    assert_audit_issue_in_org,
    assert_website_in_org,
)
from app.models import OrganizationMember
from app.schemas import (
    SeoAuditRead, SeoAuditDetailRead, SeoAuditIssueRead,
    SeoAuditIssueResolveRequest, SeoAuditRunRequest,
)
from app.services.audit_service import (
    run_website_audit, get_website_audits, get_audit_detail, resolve_audit_issue,
)
from app.core.exceptions import NotFoundError

router = APIRouter(prefix="/audits", tags=["audits"])


@router.post("/run", response_model=dict, status_code=status.HTTP_201_CREATED)
async def run_audit_endpoint(
    website_id: UUID = Query(...),
    body: SeoAuditRunRequest = SeoAuditRunRequest(),
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Run Technical SEO Audit for a website and generate issues & scores."""
    await assert_website_in_org(db, website_id, member.organization_id)
    audit = await run_website_audit(db, website_id=website_id, max_pages=body.max_pages)
    # Return flat so frontend can check res.id directly
    validated = SeoAuditRead.model_validate(audit)
    return validated.model_dump()


@router.get("", response_model=dict)
async def list_audits_endpoint(
    website_id: UUID = Query(...),
    limit: int = Query(20, le=100),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """List historical SEO audits for a website (most recent first)."""
    await assert_website_in_org(db, website_id, member.organization_id)
    audits = await get_website_audits(db, website_id=website_id, limit=limit)
    data = [SeoAuditRead.model_validate(a) for a in audits]
    return {"data": data}


@router.get("/{audit_id}", response_model=dict)
async def get_audit_detail_endpoint(
    audit_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed audit report including all detected issues."""
    await assert_audit_in_org(db, audit_id, member.organization_id)
    audit = await get_audit_detail(db, audit_id=audit_id)
    if not audit:
        raise NotFoundError("SeoAudit", str(audit_id))
    return {"data": SeoAuditDetailRead.model_validate(audit)}


@router.patch("/issues/{issue_id}/resolve", response_model=dict)
async def resolve_issue_endpoint(
    issue_id: UUID,
    body: SeoAuditIssueResolveRequest,
    member: OrganizationMember = Depends(require_role("editor")),
    db: AsyncSession = Depends(get_db),
):
    """Mark an SEO audit issue as resolved or unresolved."""
    await assert_audit_issue_in_org(db, issue_id, member.organization_id)
    issue = await resolve_audit_issue(db, issue_id=issue_id, is_resolved=body.is_resolved)
    return {"data": SeoAuditIssueRead.model_validate(issue)}
