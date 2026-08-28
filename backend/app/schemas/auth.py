from pydantic import BaseModel, ConfigDict, EmailStr
from uuid import UUID
from datetime import datetime
from app.schemas.common import OrmBase


# --- Auth ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


# --- User ---
class MembershipInfo(BaseModel):
    """Minimal org membership info embedded in /auth/me to avoid a second round-trip."""
    model_config = ConfigDict(from_attributes=True)
    organization_id: UUID
    role: str


class UserRead(OrmBase):
    id: UUID
    email: str
    full_name: str
    avatar_url: str | None = None
    is_active: bool
    created_at: datetime


class UserMeRead(UserRead):
    memberships: list[MembershipInfo] = []



class UserUpdate(BaseModel):
    full_name: str | None = None
    avatar_url: str | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

