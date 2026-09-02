from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import (
    LoginRequest, RegisterRequest, TokenResponse, RefreshRequest,
    UserRead, UserUpdate, PasswordChange, ForgotPasswordRequest, ResetPasswordRequest
)
from app.services import (
    register_user, authenticate_user, create_token_pair,
    refresh_tokens, revoke_refresh_token,
)
from app.core.security import verify_password, hash_password, verify_password_async, hash_password_async
from app.core.exceptions import UnauthorizedError
from app.core.ratelimit import (
    login_rate_limit, register_rate_limit,
    password_change_rate_limit, refresh_rate_limit, forgot_password_rate_limit,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=dict,
    status_code=201,
    dependencies=[Depends(register_rate_limit)],
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    user = await register_user(db, body.email, body.password, body.full_name)
    await db.commit()
    return {"data": UserRead.model_validate(user)}


@router.post(
    "/login",
    response_model=dict,
    dependencies=[Depends(login_rate_limit)],
)
async def login(body: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, body.email, body.password)
    tokens = await create_token_pair(
        db, user,
        device_info=request.headers.get("user-agent"),
        ip=request.client.host if request.client else None,
    )
    await db.commit()
    return {"data": tokens}


@router.post(
    "/refresh",
    response_model=dict,
    dependencies=[Depends(refresh_rate_limit)],
)
async def refresh(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    tokens = await refresh_tokens(db, body.refresh_token)
    await db.commit()
    return {"data": tokens}


@router.post("/logout", status_code=204)
async def logout(
    body: RefreshRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await revoke_refresh_token(db, user.id, body.refresh_token)
    await db.commit()


@router.get("/me", response_model=dict)
async def get_me(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models import OrganizationMember
    result = await db.execute(
        select(OrganizationMember).where(OrganizationMember.user_id == user.id)
    )
    memberships = result.scalars().all()
    user_data = UserRead.model_validate(user).model_dump()
    user_data["memberships"] = [
        {"organization_id": str(m.organization_id), "role": m.role}
        for m in memberships
    ]
    return {"data": user_data}


@router.patch("/me", response_model=dict)
async def update_me(
    body: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.avatar_url is not None:
        user.avatar_url = body.avatar_url
    await db.commit()
    return {"data": UserRead.model_validate(user)}


from app.core.security import (
    verify_password,
    verify_password_async,
    hash_password,
    hash_password_async,
    create_access_token,
    create_refresh_token_value,
    hash_token,
    create_reset_token,
    decode_reset_token,
)
from jose import JWTError
import secrets
import logging

logger = logging.getLogger(__name__)


@router.put(
    "/me/password",
    status_code=204,
    dependencies=[Depends(password_change_rate_limit)],
)
async def change_password(
    body: PasswordChange,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not await verify_password_async(body.current_password, user.password_hash):
        raise UnauthorizedError("Current password is incorrect")
    user.password_hash = await hash_password_async(body.new_password)
    # Revoke all active refresh tokens on password change
    from app.models import RefreshToken
    from datetime import datetime, timezone
    from sqlalchemy import update
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()


@router.post(
    "/forgot-password",
    status_code=204,
    dependencies=[Depends(forgot_password_rate_limit)],
)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == body.email, User.deleted_at.is_(None)))
    user = result.scalars().first()
    if user:
        nonce = secrets.token_urlsafe(32)
        user.password_reset_nonce = nonce
        await db.commit()
        token = create_reset_token(body.email, nonce=nonce)
        logger.info(f"Password reset token issued for user {user.id}")
        # In a real production setup, dispatch background email worker here:
        # await send_password_reset_email(to=user.email, token=token)
    return None


@router.post("/reset-password", status_code=204)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        payload = decode_reset_token(body.token)
        email = payload.get("sub")
        token_nonce = payload.get("nonce")
    except JWTError:
        raise UnauthorizedError("لینک بازیابی نامعتبر یا منقضی شده است")
        
    result = await db.execute(select(User).where(User.email == email, User.deleted_at.is_(None)))
    user = result.scalars().first()
    if not user:
        raise UnauthorizedError("کاربر یافت نشد")

    if not token_nonce or token_nonce != user.password_reset_nonce:
        raise UnauthorizedError("لینک بازیابی قبلاً استفاده شده یا منقضی شده است")

    user.password_hash = await hash_password_async(body.new_password)
    # Invalidate the nonce so token is strictly one-time-use
    user.password_reset_nonce = None

    # Invalidate all active sessions/tokens for user
    from app.models import RefreshToken
    from datetime import datetime, timezone
    from sqlalchemy import update
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return None
