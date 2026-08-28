from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import require_role
from app.models import OrganizationMember
from app.models.ai_providers import AiProviderKey
from app.core.encryption import encrypt_value, decrypt_value
from app.core.exceptions import AppException, NotFoundError
from app.core.ai_router import test_single_ai_key, COOLDOWN_MINUTES
from app.schemas.ai_providers import (
    AiProviderKeyCreate,
    AiProviderKeyUpdate,
    AiProviderKeyRead,
    AiProviderKeyTestRequest,
    AiProviderKeyTestResult,
)

router = APIRouter(prefix="/ai-providers", tags=["AI Provider Key Pool"])


def _mask_api_key(raw_or_enc_key: str, is_encrypted: bool = True) -> str:
    """Mask key so only prefix and suffix are visible."""
    try:
        raw = decrypt_value(raw_or_enc_key) if is_encrypted else raw_or_enc_key
    except Exception:
        return "********"
    if not raw or len(raw) < 8:
        return "********"
    return f"{raw[:6]}...{raw[-4:]}"


def _format_key_read(row: AiProviderKey) -> AiProviderKeyRead:
    now = datetime.now(timezone.utc)
    cooldown_threshold = now - timedelta(minutes=COOLDOWN_MINUTES)
    
    key_status = "active"
    if not row.is_active:
        key_status = "inactive"
    elif row.last_error_at and row.last_error_at > cooldown_threshold and row.error_count >= 2:
        key_status = "rate_limited"
    elif row.error_count > 0:
        key_status = "warning"

    return AiProviderKeyRead(
        id=row.id,
        organization_id=row.organization_id,
        provider_name=row.provider_name,
        label=row.label,
        masked_api_key=_mask_api_key(row.encrypted_api_key, is_encrypted=True),
        model_name=row.model_name,
        priority=row.priority,
        is_active=row.is_active,
        last_error_at=row.last_error_at,
        error_count=row.error_count,
        last_used_at=row.last_used_at,
        usage_count=row.usage_count,
        status=key_status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[AiProviderKeyRead])
async def list_ai_provider_keys(
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """List all AI provider keys in the pool for the organization."""
    stmt = (
        select(AiProviderKey)
        .where(
            (AiProviderKey.organization_id == member.organization_id)
            | (AiProviderKey.organization_id.is_(None))
        )
        .order_by(AiProviderKey.priority.asc(), AiProviderKey.created_at.asc())
    )
    res = await db.execute(stmt)
    rows = res.scalars().all()
    return [_format_key_read(r) for r in rows]


@router.post("", response_model=AiProviderKeyRead, status_code=status.HTTP_201_CREATED)
async def create_ai_provider_key(
    payload: AiProviderKeyCreate,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("admin")),
):
    """Add a new AI provider key to the organization pool."""
    enc_key = encrypt_value(payload.api_key.strip())
    clean_provider = payload.provider_name.lower().strip()
    clean_model = payload.model_name.strip()

    row = AiProviderKey(
        organization_id=member.organization_id,
        provider_name=clean_provider,
        label=payload.label.strip(),
        encrypted_api_key=enc_key,
        model_name=clean_model,
        priority=payload.priority,
        is_active=payload.is_active,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _format_key_read(row)


@router.put("/{key_id}", response_model=AiProviderKeyRead)
async def update_ai_provider_key(
    key_id: UUID,
    payload: AiProviderKeyUpdate,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("admin")),
):
    """Update label, priority, active status, model, or update API key value."""
    stmt = select(AiProviderKey).where(
        AiProviderKey.id == key_id,
        AiProviderKey.organization_id == member.organization_id,
    )
    res = await db.execute(stmt)
    row = res.scalar_one_or_none()
    if not row:
        raise NotFoundError("AiProviderKey", str(key_id))

    if payload.label is not None:
        row.label = payload.label.strip()
    if payload.model_name is not None:
        row.model_name = payload.model_name.strip()
    if payload.priority is not None:
        row.priority = payload.priority
    if payload.is_active is not None:
        row.is_active = payload.is_active
    if payload.api_key is not None and payload.api_key.strip():
        row.encrypted_api_key = encrypt_value(payload.api_key.strip())
        row.error_count = 0
        row.last_error_at = None

    await db.commit()
    await db.refresh(row)
    return _format_key_read(row)


@router.delete("/{key_id}", status_code=status.HTTP_200_OK)
async def delete_ai_provider_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("admin")),
):
    """Delete an AI provider key from the pool."""
    stmt = select(AiProviderKey).where(
        AiProviderKey.id == key_id,
        AiProviderKey.organization_id == member.organization_id,
    )
    res = await db.execute(stmt)
    row = res.scalar_one_or_none()
    if not row:
        raise NotFoundError("AiProviderKey", str(key_id))

    await db.delete(row)
    await db.commit()
    return {"data": {"deleted": True, "id": str(key_id)}}


@router.post("/{key_id}/test", response_model=AiProviderKeyTestResult)
async def test_stored_ai_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Perform a live ping test on an existing key in the pool."""
    stmt = select(AiProviderKey).where(
        AiProviderKey.id == key_id,
        AiProviderKey.organization_id == member.organization_id,
    )
    res = await db.execute(stmt)
    row = res.scalar_one_or_none()
    if not row:
        raise NotFoundError("AiProviderKey", str(key_id))

    raw_key = decrypt_value(row.encrypted_api_key)
    res_dict = await test_single_ai_key(
        provider_name=row.provider_name,
        raw_api_key=raw_key,
        model_name=row.model_name,
    )
    # Clear error state on successful test
    row.error_count = 0
    row.last_error_at = None
    await db.commit()

    return AiProviderKeyTestResult(**res_dict)


@router.post("/test-raw", response_model=AiProviderKeyTestResult)
async def test_raw_ai_key(
    payload: AiProviderKeyTestRequest,
    member: OrganizationMember = Depends(require_role("seo_manager")),
):
    """Perform a live test ping on a raw key before saving it to database."""
    res_dict = await test_single_ai_key(
        provider_name=payload.provider_name,
        raw_api_key=payload.api_key.strip(),
        model_name=payload.model_name.strip(),
    )
    return AiProviderKeyTestResult(**res_dict)
