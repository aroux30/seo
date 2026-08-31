import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Organization, OrganizationMember, RefreshToken, AuditLog
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_refresh_token_value, hash_token, ROLE_HIERARCHY,
)
from app.core.exceptions import (
    ConflictError, UnauthorizedError, NotFoundError, ForbiddenError,
    ValidationError,
)
from app.config import get_settings

settings = get_settings()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", slug).strip("-")


async def register_user(db: AsyncSession, email: str, password: str, full_name: str) -> User:
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise ConflictError("Email already registered")

    user = User(email=email, password_hash=hash_password(password), full_name=full_name)
    db.add(user)
    await db.flush()
    return user


async def authenticate_user(db: AsyncSession, email: str, password: str) -> User:
    result = await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        raise UnauthorizedError("Incorrect email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is deactivated")

    user.last_login_at = datetime.now(timezone.utc)
    await db.flush()
    return user


async def create_token_pair(
    db: AsyncSession, user: User, org_id: UUID | None = None,
    device_info: str | None = None, ip: str | None = None,
) -> dict:
    # Find user's first org if not specified
    if not org_id:
        result = await db.execute(
            select(OrganizationMember.organization_id)
            .where(OrganizationMember.user_id == user.id)
            .limit(1)
        )
        row = result.first()
        org_id = row[0] if row else None

    access_token = create_access_token(user.id, org_id)
    raw_refresh = create_refresh_token_value()
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    token = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        device_info=device_info,
        ip_address=ip,
        expires_at=expires_at,
    )
    db.add(token)
    await db.flush()

    return {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }


async def refresh_tokens(db: AsyncSession, raw_refresh: str) -> dict:
    hashed = hash_token(raw_refresh)
    result = await db.execute(
        select(RefreshToken)
        .where(
            RefreshToken.token_hash == hashed,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(timezone.utc),
        )
        .with_for_update()
    )
    token = result.scalar_one_or_none()
    if not token:
        raise UnauthorizedError("Invalid or expired refresh token")

    # Revoke old token (rotation)
    token.revoked_at = datetime.now(timezone.utc)

    # Load user
    user_result = await db.execute(select(User).where(User.id == token.user_id))
    user = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")

    return await create_token_pair(db, user, device_info=token.device_info, ip=token.ip_address)


async def revoke_refresh_token(db: AsyncSession, user_id: UUID, raw_refresh: str) -> None:
    hashed = hash_token(raw_refresh)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == hashed,
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    token = result.scalar_one_or_none()
    if token:
        token.revoked_at = datetime.now(timezone.utc)
        await db.flush()


# --- Organization Service ---

async def create_organization(db: AsyncSession, user: User, name: str, slug: str | None = None, description: str | None = None) -> Organization:
    slug = slug or _slugify(name)
    existing = await db.execute(select(Organization).where(Organization.slug == slug))
    if existing.scalar_one_or_none():
        raise ConflictError(f"سازمانی با نام '{slug}' (یا نامک مشابه) از قبل وجود دارد. لطفاً نام دیگری انتخاب کنید.")

    org = Organization(name=name, slug=slug, description=description)
    db.add(org)
    await db.flush()

    # Creator becomes owner
    member = OrganizationMember(
        organization_id=org.id, user_id=user.id, role="owner",
        joined_at=datetime.now(timezone.utc),
    )
    db.add(member)
    await db.flush()

    await _audit(db, org.id, user.id, "organization.created", "organization", org.id,
                 after_state={"name": name, "slug": slug})
    return org


async def list_user_organizations(db: AsyncSession, user_id: UUID) -> list[Organization]:
    result = await db.execute(
        select(Organization, OrganizationMember.role)
        .join(OrganizationMember)
        .where(
            OrganizationMember.user_id == user_id,
            Organization.deleted_at.is_(None),
        )
    )
    orgs = []
    for org, role in result.all():
        org.my_role = role
        orgs.append(org)
    return orgs


async def get_organization(db: AsyncSession, org_id: UUID) -> Organization:
    result = await db.execute(
        select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
    )
    org = result.scalar_one_or_none()
    if not org:
        raise NotFoundError("Organization", str(org_id))
    return org


async def update_organization(db: AsyncSession, org_id: UUID, user_id: UUID, data: dict) -> Organization:
    org = await get_organization(db, org_id)
    before = {k: getattr(org, k) for k in data.keys() if hasattr(org, k)}
    for key, value in data.items():
        if value is not None and hasattr(org, key):
            setattr(org, key, value)
    await db.flush()
    await _audit(db, org_id, user_id, "organization.updated", "organization", org_id,
                 before_state=before, after_state=data)
    return org


async def delete_organization(db: AsyncSession, org_id: UUID, user_id: UUID) -> None:
    import uuid
    org = await get_organization(db, org_id)
    org.deleted_at = datetime.now(timezone.utc)
    org.slug = f"{org.slug}-deleted-{uuid.uuid4().hex[:8]}"
    await db.flush()
    await _audit(db, org_id, user_id, "organization.deleted", "organization", org_id)


async def list_org_members(db: AsyncSession, org_id: UUID) -> list[dict]:
    result = await db.execute(
        select(OrganizationMember, User.email, User.full_name)
        .join(User, OrganizationMember.user_id == User.id)
        .where(OrganizationMember.organization_id == org_id)
    )
    members = []
    for row in result.all():
        m = row[0]
        members.append({
            "id": m.id, "user_id": m.user_id, "role": m.role,
            "joined_at": m.joined_at, "user_email": row[1], "user_name": row[2],
        })
    return members


def _assert_valid_role(role: str) -> None:
    if role not in ROLE_HIERARCHY:
        raise ValidationError(
            f"Unknown role '{role}'. Valid roles: {', '.join(ROLE_HIERARCHY)}"
        )


def _assert_can_assign_role(actor_role: str, target_role: str) -> None:
    """An actor may never grant a role at or above their own level.

    Without this, an 'admin' could grant 'owner' — to another member or, after
    demoting the real owner, to themselves.
    """
    _assert_valid_role(target_role)
    if ROLE_HIERARCHY.get(target_role, 0) > ROLE_HIERARCHY.get(actor_role, 0):
        raise ForbiddenError(
            f"A '{actor_role}' cannot assign the role '{target_role}'"
        )


def _assert_can_manage_member(actor_role: str, target_role: str) -> None:
    """An actor may never modify or remove a member at or above their own level."""
    if ROLE_HIERARCHY.get(target_role, 0) >= ROLE_HIERARCHY.get(actor_role, 0):
        raise ForbiddenError(
            f"A '{actor_role}' cannot modify a member with the role '{target_role}'"
        )


async def _assert_not_last_owner(db: AsyncSession, org_id: UUID, member: OrganizationMember) -> None:
    """Refuse to demote or remove the only remaining owner (would orphan the org)."""
    if member.role != "owner":
        return
    result = await db.execute(
        select(func.count())
        .select_from(OrganizationMember)
        .where(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.role == "owner",
        )
    )
    if (result.scalar() or 0) <= 1:
        raise ForbiddenError(
            "Cannot demote or remove the last owner of the organization"
        )


async def update_org_member(
    db: AsyncSession,
    org_id: UUID,
    current_user_id: UUID,
    user_id: UUID,
    role: str,
    actor_role: str,
) -> None:
    if user_id == current_user_id:
        raise ForbiddenError("You cannot change your own role")

    result = await db.execute(
        select(OrganizationMember).where(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise NotFoundError("Member", str(user_id))

    _assert_can_manage_member(actor_role, member.role)
    _assert_can_assign_role(actor_role, role)
    await _assert_not_last_owner(db, org_id, member)

    before = {"role": member.role}
    member.role = role
    await db.flush()
    await _audit(db, org_id, current_user_id, "member.role_updated", "member", member.id, before_state=before, after_state={"role": role})


async def remove_org_member(
    db: AsyncSession,
    org_id: UUID,
    current_user_id: UUID,
    user_id: UUID,
    actor_role: str,
) -> None:
    result = await db.execute(
        select(OrganizationMember).where(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user_id)
    )
    member = result.scalar_one_or_none()
    if not member:
        raise NotFoundError("Member", str(user_id))

    # Members may always remove themselves; removing anyone else requires rank.
    if user_id != current_user_id:
        _assert_can_manage_member(actor_role, member.role)
    await _assert_not_last_owner(db, org_id, member)

    await db.delete(member)
    await db.flush()
    await _audit(db, org_id, current_user_id, "member.removed", "member", member.id)


async def add_org_member(db: AsyncSession, org_id: UUID, current_user_id: UUID, email: str, role: str, actor_role: str) -> dict:
    _assert_can_assign_role(actor_role, role)
    # 1. Find user by email
    user_res = await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))
    user = user_res.scalar_one_or_none()
    if not user:
        raise NotFoundError("User", email)
        
    # 2. Check if already member
    mem_res = await db.execute(
        select(OrganizationMember).where(OrganizationMember.organization_id == org_id, OrganizationMember.user_id == user.id)
    )
    if mem_res.scalar_one_or_none():
        raise ConflictError("این کاربر از قبل عضو این سازمان است.")
        
    # 3. Add member
    member = OrganizationMember(
        organization_id=org_id,
        user_id=user.id,
        role=role,
        invited_by=current_user_id,
        joined_at=datetime.now(timezone.utc),
    )
    db.add(member)
    await db.flush()
    await _audit(db, org_id, current_user_id, "member.added", "member", member.id, after_state={"role": role, "email": email})
    
    return {
        "id": member.id, "user_id": member.user_id, "role": member.role,
        "joined_at": member.joined_at, "user_email": user.email, "user_name": user.full_name,
    }


# --- Project Service ---

from app.models import Project


async def create_project(db: AsyncSession, org_id: UUID, user_id: UUID, name: str, slug: str | None = None, description: str | None = None) -> Project:
    slug = slug or _slugify(name)
    existing = await db.execute(
        select(Project).where(Project.organization_id == org_id, Project.slug == slug, Project.deleted_at.is_(None))
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Project slug '{slug}' already exists in this organization")

    project = Project(organization_id=org_id, name=name, slug=slug, description=description)
    db.add(project)
    await db.flush()

    await _audit(db, org_id, user_id, "project.created", "project", project.id,
                 after_state={"name": name, "slug": slug})
    return project


async def list_projects(db: AsyncSession, org_id: UUID) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.organization_id == org_id, Project.deleted_at.is_(None))
    )
    return list(result.scalars().all())


async def get_project(db: AsyncSession, org_id: UUID, project_id: UUID) -> Project:
    result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.organization_id == org_id, Project.deleted_at.is_(None)
        )
    )
    project = result.scalar_one_or_none()
    if not project:
        raise NotFoundError("Project", str(project_id))
    return project


async def update_project(db: AsyncSession, org_id: UUID, user_id: UUID, project_id: UUID, data: dict) -> Project:
    project = await get_project(db, org_id, project_id)
    before = {k: getattr(project, k) for k in data.keys() if hasattr(project, k)}
    for key, value in data.items():
        if value is not None and hasattr(project, key):
            setattr(project, key, value)
    await db.flush()
    await _audit(db, org_id, user_id, "project.updated", "project", project_id,
                 before_state=before, after_state=data)
    return project


async def delete_project(db: AsyncSession, org_id: UUID, user_id: UUID, project_id: UUID) -> None:
    import uuid
    project = await get_project(db, org_id, project_id)
    project.deleted_at = datetime.now(timezone.utc)
    project.slug = f"{project.slug}-deleted-{uuid.uuid4().hex[:8]}"
    await db.flush()
    await _audit(db, org_id, user_id, "project.deleted", "project", project_id)


# --- Website Service ---

from app.models import Website


def _normalize_domain(raw: str) -> str:
    """Strip protocol, trailing slashes and whitespace from a domain input.

    Storing 'http://example.com' and 'example.com' as two separate rows
    breaks every audit-score lookup (audits are linked to the canonical form).
    """
    domain = raw.strip()
    # Remove protocol prefix
    for prefix in ("https://", "http://"):
        if domain.lower().startswith(prefix):
            domain = domain[len(prefix):]
            break
    # Remove trailing slashes and paths — store only the hostname
    domain = domain.rstrip("/").split("/")[0]
    return domain.lower()


async def create_website(
    db: AsyncSession, org_id: UUID, user_id: UUID,
    project_id: UUID, name: str, domain: str, base_url: str,
    website_type: str = "blog", language: str = "fa", country: str = "IR", timezone: str = "Asia/Tehran",
    automation_mode: str = "ai_assist"
) -> Website:
    # Verify project belongs to org
    await get_project(db, org_id, project_id)

    domain = _normalize_domain(domain)

    website = Website(
        project_id=project_id, organization_id=org_id,
        name=name, domain=domain, base_url=base_url,
        website_type=website_type, language=language, country=country, timezone=timezone,
        automation_mode=automation_mode,
    )
    db.add(website)
    await db.flush()

    await _audit(db, org_id, user_id, "website.created", "website", website.id,
                 after_state={"name": name, "domain": domain})
    return website


async def list_websites(db: AsyncSession, org_id: UUID, project_id: UUID | None = None) -> list[Website]:
    q = select(Website).where(Website.organization_id == org_id, Website.deleted_at.is_(None))
    if project_id:
        q = q.where(Website.project_id == project_id)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_website(db: AsyncSession, org_id: UUID, website_id: UUID) -> Website:
    result = await db.execute(
        select(Website).where(
            Website.id == website_id, Website.organization_id == org_id, Website.deleted_at.is_(None)
        )
    )
    website = result.scalar_one_or_none()
    if not website:
        raise NotFoundError("Website", str(website_id))
    return website


async def update_website(db: AsyncSession, org_id: UUID, user_id: UUID, website_id: UUID, data: dict) -> Website:
    website = await get_website(db, org_id, website_id)
    before = {k: getattr(website, k) for k in data.keys() if hasattr(website, k)}
    for key, value in data.items():
        if value is not None and hasattr(website, key):
            setattr(website, key, value)
    await db.flush()
    await _audit(db, org_id, user_id, "website.updated", "website", website_id,
                 before_state=before, after_state=data)
    return website


async def delete_website(db: AsyncSession, org_id: UUID, user_id: UUID, website_id: UUID) -> None:
    website = await get_website(db, org_id, website_id)
    website.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await _audit(db, org_id, user_id, "website.deleted", "website", website_id)


# --- Audit ---

async def _audit(
    db: AsyncSession, org_id: UUID | None, user_id: UUID | None,
    action: str, entity_type: str | None = None, entity_id: UUID | None = None,
    before_state: dict | None = None, after_state: dict | None = None,
    ip_address: str | None = None,
) -> None:
    log = AuditLog(
        organization_id=org_id, user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id,
        before_state=before_state, after_state=after_state,
        ip_address=ip_address,
    )
    db.add(log)
