from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user, get_current_membership, require_role
from app.core.scoping import assert_org_matches
from app.models import User, OrganizationMember
from app.schemas import (
    OrganizationCreate, OrganizationUpdate, OrganizationRead,
    MemberRead, MemberRoleUpdate, MemberInvite,
)
from app.services import (
    create_organization, list_user_organizations, get_organization,
    list_org_members, update_organization, delete_organization,
    update_org_member, remove_org_member, add_org_member
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("", response_model=dict, status_code=201)
async def create_org(
    body: OrganizationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    org = await create_organization(db, user, body.name, body.slug, body.description)
    await db.commit()
    org.my_role = "owner"
    return {"data": OrganizationRead.model_validate(org)}


@router.get("", response_model=dict)
async def list_orgs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    orgs = await list_user_organizations(db, user.id)
    return {"data": [OrganizationRead.model_validate(o) for o in orgs]}


@router.get("/{org_id}", response_model=dict)
async def get_org(
    org_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    assert_org_matches(member, org_id)
    org = await get_organization(db, org_id)
    org.my_role = member.role
    return {"data": OrganizationRead.model_validate(org)}


@router.put("/{org_id}", response_model=dict)
async def update_org(
    org_id: UUID,
    body: OrganizationUpdate,
    member: OrganizationMember = Depends(require_role("owner")),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assert_org_matches(member, org_id)
    org = await update_organization(db, org_id, user.id, body.model_dump(exclude_unset=True))
    await db.commit()
    org.my_role = member.role
    return {"data": OrganizationRead.model_validate(org)}


@router.delete("/{org_id}", status_code=204)
async def delete_org(
    org_id: UUID,
    member: OrganizationMember = Depends(require_role("owner")),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assert_org_matches(member, org_id)
    await delete_organization(db, org_id, user.id)
    await db.commit()
    return None


@router.get("/{org_id}/members", response_model=dict)
async def get_members(
    org_id: UUID,
    member: OrganizationMember = Depends(require_role("viewer")),
    db: AsyncSession = Depends(get_db),
):
    assert_org_matches(member, org_id)
    members = await list_org_members(db, org_id)
    return {"data": [MemberRead(**m) for m in members]}


@router.put("/{org_id}/members/{user_id}", status_code=200)
async def update_member(
    org_id: UUID,
    user_id: UUID,
    body: MemberRoleUpdate,
    member: OrganizationMember = Depends(require_role("admin")),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assert_org_matches(member, org_id)
    await update_org_member(db, org_id, user.id, user_id, body.role, actor_role=member.role)
    await db.commit()
    return {"message": "Member role updated"}


@router.post("/{org_id}/members", status_code=201, response_model=dict)
async def add_member(
    org_id: UUID,
    body: MemberInvite,
    member: OrganizationMember = Depends(require_role("admin")),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assert_org_matches(member, org_id)
    member_data = await add_org_member(db, org_id, user.id, body.email, body.role, actor_role=member.role)
    await db.commit()
    return {"data": member_data}


@router.delete("/{org_id}/members/{user_id}", status_code=204)
async def remove_member(
    org_id: UUID,
    user_id: UUID,
    member: OrganizationMember = Depends(require_role("admin")),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    assert_org_matches(member, org_id)
    await remove_org_member(db, org_id, user.id, user_id, actor_role=member.role)
    await db.commit()
    return None
