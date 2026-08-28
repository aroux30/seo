from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.core.scoping import assert_website_in_org
from app.models import OrganizationMember
from app.schemas import GscOverviewRead, GscQueryRead, GscPageRead, GscCountryRead, GscDeviceRead, GscDateRead
from app.services.gsc_service import (
    get_gsc_overview, list_gsc_queries, list_gsc_pages, list_gsc_countries, list_gsc_devices, list_gsc_dates
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/gsc/overview/{website_id}", response_model=dict)
async def get_overview(
    website_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await assert_website_in_org(db, website_id, member.organization_id)
    overview = await get_gsc_overview(db, website_id)
    return {"data": overview}


@router.get("/gsc/queries/{website_id}", response_model=dict)
async def get_queries(
    website_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    sort_by: str = Query("clicks"),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await assert_website_in_org(db, website_id, member.organization_id)
    queries = await list_gsc_queries(db, website_id, limit=limit, sort_by=sort_by)
    return {"data": [GscQueryRead.model_validate(q) for q in queries]}


@router.get("/gsc/pages/{website_id}", response_model=dict)
async def get_pages(
    website_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    sort_by: str = Query("clicks"),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await assert_website_in_org(db, website_id, member.organization_id)
    pages = await list_gsc_pages(db, website_id, limit=limit, sort_by=sort_by)
    return {"data": [GscPageRead.model_validate(p) for p in pages]}


@router.get("/gsc/countries/{website_id}", response_model=dict)
async def get_countries(
    website_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    sort_by: str = Query("clicks"),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await assert_website_in_org(db, website_id, member.organization_id)
    countries = await list_gsc_countries(db, website_id, limit=limit, sort_by=sort_by)
    return {"data": [GscCountryRead.model_validate(c) for c in countries]}


@router.get("/gsc/devices/{website_id}", response_model=dict)
async def get_devices(
    website_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    sort_by: str = Query("clicks"),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await assert_website_in_org(db, website_id, member.organization_id)
    devices = await list_gsc_devices(db, website_id, limit=limit, sort_by=sort_by)
    return {"data": [GscDeviceRead.model_validate(d) for d in devices]}


@router.get("/gsc/dates/{website_id}", response_model=dict)
async def get_dates(
    website_id: UUID,
    limit: int = Query(365, ge=1, le=500),
    sort_by: str = Query("date"),
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    await assert_website_in_org(db, website_id, member.organization_id)
    dates = await list_gsc_dates(db, website_id, limit=limit, sort_by=sort_by)
    return {"data": [GscDateRead.model_validate(d) for d in dates]}
