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
from app.core.security import verify_password, hash_password
from app.core.exceptions import UnauthorizedError
from app.core.ratelimit import (
    login_rate_limit, register_rate_limit,
    password_change_rate_limit, refresh_rate_limit,
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
    if not verify_password(body.current_password, user.password_hash):
        raise UnauthorizedError("Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    # Revoke all active refresh tokens on password change
    from app.models import RefreshToken
    from datetime import datetime, timezone
    from sqlalchemy import update, select
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()


from app.core.security import create_reset_token, decode_reset_token
from jose import JWTError
import logging

logger = logging.getLogger(__name__)

@router.post("/forgot-password", status_code=204)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalars().first()
    if user:
        token = create_reset_token(body.email)
        logger.info(f"Password reset requested for {body.email}")
        # In a real system, send this token via email
    return None


@router.post("/reset-password", status_code=204)
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        email = decode_reset_token(body.token)
    except JWTError:
        raise UnauthorizedError("لینک بازیابی نامعتبر یا منقضی شده است")
        
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if not user:
        raise UnauthorizedError("کاربر یافت نشد")
        
    user.password_hash = hash_password(body.new_password)
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
