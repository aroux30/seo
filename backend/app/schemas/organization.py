from pydantic import BaseModel, Field, EmailStr
from uuid import UUID
from datetime import datetime
from app.schemas.common import OrmBase


# --- Organization ---
class OrganizationCreate(BaseModel):
    name: str
    slug: str | None = None  # Auto-generated if not provided
    description: str | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    logo_url: str | None = None
    settings: dict | None = None


class OrganizationRead(OrmBase):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    logo_url: str | None = None
    plan: str
    created_at: datetime
    my_role: str | None = None


class MemberRead(OrmBase):
    id: UUID
    user_id: UUID
    role: str
    joined_at: datetime | None = None
    user_email: str | None = None
    user_name: str | None = None


class MemberRoleUpdate(BaseModel):
    role: str = Field(..., description="Role to assign to the member")


class MemberInvite(BaseModel):
    email: str = Field(..., description="Email of the user to invite")
    role: str = Field("viewer", description="Role to assign")


# --- Project ---
class ProjectCreate(BaseModel):
    name: str
    slug: str | None = None
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectRead(OrmBase):
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    description: str | None = None
    created_at: datetime


# --- Website ---
class WebsiteCreate(BaseModel):
    project_id: UUID
    name: str
    domain: str
    base_url: str
    description: str | None = None
    website_type: str = "blog"
    language: str = "fa"
    country: str = "IR"
    timezone: str = "Asia/Tehran"
    automation_mode: str = "ai_assist"


class WebsiteUpdate(BaseModel):
    name: str | None = None
    domain: str | None = None
    base_url: str | None = None
    description: str | None = None
    website_type: str | None = None
    language: str | None = None
    country: str | None = None
    timezone: str | None = None
    automation_mode: str | None = None
    content_production_limit: int | None = None
    seo_goals: dict | None = None
    notification_preferences: dict | None = None


class WebsiteRead(OrmBase):
    id: UUID
    project_id: UUID
    organization_id: UUID
    name: str
    domain: str
    base_url: str
    description: str | None = None
    website_type: str
    language: str
    country: str
    timezone: str
    automation_mode: str
    status: str
    content_production_limit: int
    created_at: datetime
