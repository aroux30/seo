"""Report endpoints.

Route order matters: literal paths (`/summary`, `/templates`, `/public/{token}`)
are declared before `/{report_id}`, otherwise FastAPI tries to parse "summary" or
"templates" as a UUID and 422s.

Role floors: reading the queue/list/detail is `viewer`, generating a report is
`seo_manager` (it does real aggregation work across every source table), sharing
(enable/revoke) is `seo_manager`, and deleting is `admin`.

`GET /public/{share_token}` is the one deliberately unauthenticated route in this
module — no `require_role`, no `db` dependency injected via a member. It is
reachable by anyone holding the token and returns only `PublicReportRead`, which
carries no organization id, website id, user id or report id. See
`report_service.get_report_by_share_token` for the constant-time comparison and
expiry/revocation checks that guard it.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scoping import assert_website_in_org
from app.database import get_db
from app.dependencies import require_role
from app.models import OrganizationMember
from app.schemas.reports import (
    PublicReportRead,
    ReportGenerateRequest,
    ReportListItem,
    ReportRead,
    ReportShareRequest,
    ReportShareResult,
    ReportSummary,
    ReportTemplate,
)
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("", response_model=dict)
async def list_reports_endpoint(
    website_id: UUID | None = Query(None),
    report_type: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """List reports for the org, most recent period first. No `content` payload."""
    if website_id is not None:
        await assert_website_in_org(db, website_id, member.organization_id)

    rows = await report_service.list_reports(
        db,
        organization_id=member.organization_id,
        website_id=website_id,
        report_type=report_type,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"data": [ReportListItem.model_validate(r) for r in rows]}


# Declared before /{report_id}: otherwise "summary" is parsed as a UUID.
@router.get("/summary", response_model=dict)
async def report_summary_endpoint(
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Counts by type/status plus the newest report of each type."""
    summary = await report_service.get_report_summary(db, member.organization_id)
    return {"data": ReportSummary.model_validate(summary)}


@router.get("/templates", response_model=dict)
async def report_templates_endpoint(
    member: OrganizationMember = Depends(require_role("viewer")),
):
    """Predefined report shapes (weekly/monthly/executive/custom) with sections.

    Section keys are guaranteed to match what `generate_report` actually
    produces for that type — see `report_service._SECTIONS_BY_TYPE`.
    """
    templates = report_service.get_report_templates()
    return {"data": [ReportTemplate.model_validate(t) for t in templates]}


@router.post("/generate", response_model=dict, status_code=201)
async def generate_report_endpoint(
    body: ReportGenerateRequest,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Assemble and freeze a new report. `organization_id`/`generated_by` come
    from the session, never from the body."""
    if body.website_id is not None:
        await assert_website_in_org(db, body.website_id, member.organization_id)

    row = await report_service.generate_report(
        db,
        organization_id=member.organization_id,
        report_type=body.report_type,
        period_start=body.period_start,
        period_end=body.period_end,
        website_id=body.website_id,
        generated_by=member.user_id,
        title=body.title,
    )
    await db.commit()
    await db.refresh(row)
    return {"data": ReportRead.model_validate(row)}


# Unauthenticated. Must stay literal-prefixed and above /{report_id}.
@router.get("/public/{share_token}", response_model=dict)
async def get_public_report_endpoint(
    share_token: str,
    db: AsyncSession = Depends(get_db),
):
    """Render a report through its public share link. No auth required.

    Returns only `PublicReportRead` — never an organization id, website id, user
    id or the report's own id. Every failure (revoked, expired, wrong token,
    unknown token) raises the identical 404 so the endpoint cannot be used to
    probe which tokens ever existed.
    """
    row = await report_service.get_report_by_share_token(db, share_token)
    await db.commit()
    return {"data": PublicReportRead.model_validate(row)}


@router.get("/{report_id}", response_model=dict)
async def get_report_endpoint(
    report_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """One report with its full frozen payload, scoped to the org."""
    row = await report_service.get_report(db, report_id, member.organization_id)
    return {"data": ReportRead.model_validate(row)}


@router.get("/{report_id}/export.csv")
async def export_report_csv_endpoint(
    report_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    """Server-rendered CSV of the frozen report, built with the stdlib `csv`
    module. No PDF here — see `report_service.build_print_payload` for the
    print-to-PDF alternative used by the frontend instead of a new dependency."""
    row = await report_service.get_report(db, report_id, member.organization_id)
    csv_text = report_service.build_report_csv(row)
    filename = f"report-{report_id}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{report_id}/share", response_model=dict)
async def enable_report_share_endpoint(
    report_id: UUID,
    body: ReportShareRequest = ReportShareRequest(),
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Mint (or rotate) a public share link. Opt-in, never enabled by default."""
    row = await report_service.enable_share(
        db, report_id, member.organization_id, ttl_days=body.ttl_days
    )
    await db.commit()
    await db.refresh(row)
    return {
        "data": ReportShareResult(
            share_token=row.share_token,
            share_enabled=row.share_enabled,
            share_expires_at=row.share_expires_at,
        )
    }


@router.delete("/{report_id}/share", response_model=dict)
async def revoke_report_share_endpoint(
    report_id: UUID,
    member: OrganizationMember = Depends(require_role("seo_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Kill the public link. The token is cleared, not just disabled."""
    row = await report_service.revoke_share(db, report_id, member.organization_id)
    await db.commit()
    return {
        "data": ReportShareResult(
            share_token="",
            share_enabled=row.share_enabled,
            share_expires_at=row.share_expires_at,
        )
    }


@router.delete("/{report_id}", response_model=dict)
async def delete_report_endpoint(
    report_id: UUID,
    member: OrganizationMember = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """Hard-delete a report."""
    await report_service.delete_report(db, report_id, member.organization_id)
    await db.commit()
    return {"data": {"deleted": True}}
