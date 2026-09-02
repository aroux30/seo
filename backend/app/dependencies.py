import secrets
from uuid import UUID
from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import get_settings
from app.database import get_db
from app.models import User, OrganizationMember
from app.core.security import decode_access_token, role_has_permission
from app.core.exceptions import UnauthorizedError, ForbiddenError, BadRequestError

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = decode_access_token(credentials.credentials)
    except Exception:
        raise UnauthorizedError("Invalid or expired token")

    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")

    result = await db.execute(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


async def get_current_membership(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_organization_id: str | None = Header(None),
) -> OrganizationMember:
    """Get the user's membership for the specified organization.
    
    Requires explicit X-Organization-Id header to prevent accidental tenant leaks.
    """
    if not x_organization_id:
        raise BadRequestError("X-Organization-Id header is required")

    try:
        org_uuid = UUID(x_organization_id)
    except (ValueError, TypeError):
        raise BadRequestError("Invalid X-Organization-Id format")

    result = await db.execute(
        select(OrganizationMember).where(
            OrganizationMember.user_id == user.id,
            OrganizationMember.organization_id == org_uuid,
        )
    )
    member = result.scalar_one_or_none()
    if not member:
        raise ForbiddenError("Not a member of this organization")
    return member


def require_role(required_role: str):
    """Dependency factory: checks that the user's org role is >= required_role."""
    async def checker(member: OrganizationMember = Depends(get_current_membership)):
        if not role_has_permission(member.role, required_role):
            raise ForbiddenError(f"Role '{required_role}' or above required")
        return member
    return checker


async def require_webhook_secret(
    x_webhook_secret: str | None = Header(None),
) -> None:
    """Authenticate a machine-to-machine callback (e.g. n8n posting back results).

    These endpoints have no user session, so they are guarded by a shared secret
    instead. Fails closed: if N8N_WEBHOOK_SECRET is unset, the endpoint is
    disabled rather than left open to the internet.
    """
    expected = get_settings().N8N_WEBHOOK_SECRET
    if not expected:
        raise ForbiddenError(
            "Webhook endpoint is disabled: N8N_WEBHOOK_SECRET is not configured"
        )
    if not x_webhook_secret or not secrets.compare_digest(
        x_webhook_secret, expected
    ):
        raise UnauthorizedError("Invalid or missing webhook secret")
