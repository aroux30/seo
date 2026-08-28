import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET, ARRAY

from app.models.base import Base, BaseModel, SoftDeleteMixin
from sqlalchemy import func


class User(BaseModel, SoftDeleteMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    preferences: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    # Relationships
    memberships: Mapped[list["OrganizationMember"]] = relationship(
        back_populates="user", foreign_keys="OrganizationMember.user_id"
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user")


class Organization(BaseModel, SoftDeleteMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    # Relationships
    members: Mapped[list["OrganizationMember"]] = relationship(back_populates="organization")
    projects: Mapped[list["Project"]] = relationship(back_populates="organization")


class OrganizationMember(BaseModel):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_members_org_user"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)  # owner, admin, seo_manager, editor, reviewer, viewer
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="memberships", foreign_keys=[user_id])


class Project(BaseModel, SoftDeleteMixin):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_projects_org_slug"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(back_populates="projects")
    websites: Mapped[list["Website"]] = relationship(back_populates="project")


class Website(BaseModel, SoftDeleteMixin):
    __tablename__ = "websites"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    website_type: Mapped[str] = mapped_column(String(50), default="blog", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="fa", nullable=False)
    country: Mapped[str] = mapped_column(String(5), default="IR", nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Tehran", nullable=False)
    automation_mode: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    seo_goals: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    content_production_limit: Mapped[int] = mapped_column(default=10, nullable=False)
    notification_preferences: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="websites")


class RefreshToken(BaseModel):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    device_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("idx_audit_entity", "entity_type", "entity_id"),
        Index("idx_audit_action", "action"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # No updated_at — audit logs are immutable


from app.models.integrations import (
    OAuthIntegration,
    WordPressIntegration,
    GscQuery,
    GscPage, GscCountry, GscDevice, GscDate,
    Keyword,
    KeywordRanking,
)
from app.models.audits import (
    SeoAudit,
    SeoAuditIssue,
    AiSeoStrategy,
    AiAgentLog,
    AGENT_TYPES,
    AGENT_STATUSES,
    AGENT_RELATED_ENTITY_TYPES,
)
from app.models.content import (
    ContentBrief,
    ContentArticle,
)
from app.models.automations import (
    AutomationWorkflow,
    AutomationLog,
)
from app.models.approvals import (
    ApprovalRequest,
    APPROVAL_ACTION_TYPES,
    APPROVAL_STATUSES,
    APPROVAL_PRIORITIES,
    APPROVAL_RISK_LEVELS,
)
from app.models.categories import (
    ContentCategory,
    MAX_CATEGORY_DEPTH,
    CATEGORY_PATH_SEPARATOR,
    CATEGORY_SOURCES,
)
from app.models.calendar import (
    ContentCalendarEntry,
    CALENDAR_ENTRY_STATUSES,
    CALENDAR_ENTRY_PRIORITIES,
    CALENDAR_ENTRY_SOURCES,
    CALENDAR_OPEN_STATUSES,
)
from app.models.reports import (
    Report,
    REPORT_TYPES,
    REPORT_STATUSES,
    REPORT_TERMINAL_STATUSES,
    DEFAULT_SHARE_TTL_DAYS,
)
from app.models.versions import (
    ContentVersion,
    CONTENT_CHANGE_TYPES,
    CONTENT_SYSTEM_CHANGE_TYPES,
)
from app.models.internal_links import (
    InternalLinkSuggestion,
    InternalLink,
    SUGGESTION_STATUSES,
    SUGGESTION_REASONS,
    SUGGESTION_DECIDED_STATUSES,
)
from app.models.insights import (
    Opportunity,
    Alert,
    Notification,
    OPPORTUNITY_TYPES,
    OPPORTUNITY_STATUSES,
    ALERT_TYPES,
    ALERT_SEVERITIES,
    ALERT_STATUSES,
    NOTIFICATION_CHANNELS,
    NOTIFICATION_STATUSES,
)

__all__ = [
    "Base",
    "User",
    "Organization",
    "OrganizationMember",
    "Project",
    "Website",
    "RefreshToken",
    "AuditLog",
    "OAuthIntegration",
    "WordPressIntegration",
    "GscQuery",
    "GscPage",
    "Keyword",
    "GscCountry",
    "GscDevice",
    "GscDate",
    "SeoAudit",
    "SeoAuditIssue",
    "AiSeoStrategy",
    "AiAgentLog",
    "ContentBrief",
    "ContentArticle",
    "AutomationWorkflow",
    "AutomationLog",
    "Opportunity",
    "Alert",
    "Notification",
    "OPPORTUNITY_TYPES",
    "OPPORTUNITY_STATUSES",
    "ALERT_TYPES",
    "ALERT_SEVERITIES",
    "ALERT_STATUSES",
    "NOTIFICATION_CHANNELS",
    "NOTIFICATION_STATUSES",
    "ApprovalRequest",
    "APPROVAL_ACTION_TYPES",
    "APPROVAL_STATUSES",
    "APPROVAL_PRIORITIES",
    "APPROVAL_RISK_LEVELS",
    "ContentCategory",
    "MAX_CATEGORY_DEPTH",
    "CATEGORY_PATH_SEPARATOR",
    "CATEGORY_SOURCES",
    "ContentCalendarEntry",
    "CALENDAR_ENTRY_STATUSES",
    "CALENDAR_ENTRY_PRIORITIES",
    "CALENDAR_ENTRY_SOURCES",
    "CALENDAR_OPEN_STATUSES",
    "Report",
    "REPORT_TYPES",
    "REPORT_STATUSES",
    "REPORT_TERMINAL_STATUSES",
    "DEFAULT_SHARE_TTL_DAYS",
    "ContentVersion",
    "CONTENT_CHANGE_TYPES",
    "CONTENT_SYSTEM_CHANGE_TYPES",
    "InternalLinkSuggestion",
    "InternalLink",
    "SUGGESTION_STATUSES",
    "SUGGESTION_REASONS",
    "SUGGESTION_DECIDED_STATUSES",
    "AGENT_TYPES",
    "AGENT_STATUSES",
    "AGENT_RELATED_ENTITY_TYPES",
]
