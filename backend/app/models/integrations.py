from datetime import datetime, date
from uuid import UUID
from sqlalchemy import (
    String, Text, Boolean, Integer, Float, Date, DateTime, ForeignKey,
    UniqueConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import BaseModel


class OAuthIntegration(BaseModel):
    """Google Search Console OAuth connection tokens per website."""
    __tablename__ = "oauth_integrations"

    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), default="google_search_console", nullable=False)
    client_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("website_id", "provider", name="uq_oauth_integrations_site_provider"),
    )


class WordPressIntegration(BaseModel):
    """WordPress REST API Application Password credentials per website."""
    __tablename__ = "wordpress_integrations"

    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    wp_url: Mapped[str] = mapped_column(String(500), nullable=False)
    username: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_app_password: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, error, disconnected
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class GscQuery(BaseModel):
    """Search Console query-level performance metrics."""
    __tablename__ = "gsc_queries"

    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    query: Mapped[str] = mapped_column(String(500), nullable=False)
    page_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    position: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    date_metric: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    __table_args__ = (
        Index("idx_gsc_query_site_date", "website_id", "date_metric"),
        Index("idx_gsc_query_text", "query"),
    )


class GscPage(BaseModel):
    """Search Console page-level performance metrics."""
    __tablename__ = "gsc_pages"

    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    page_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    position: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    date_metric: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    __table_args__ = (
        Index("idx_gsc_page_site_date", "website_id", "date_metric"),
        Index("idx_gsc_page_url", "page_url"),
    )


class Keyword(BaseModel):
    """Target SEO keyword tracked for a website."""
    __tablename__ = "keywords"

    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    search_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    difficulty: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0 to 100
    target_page_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    intent: Mapped[str] = mapped_column(String(50), default="informational", nullable=False)
    tags: Mapped[dict] = mapped_column(JSONB, default=list, nullable=False)
    last_position: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_position: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("website_id", "keyword", name="uq_keywords_site_keyword"),
    )


class KeywordRanking(BaseModel):
    """Historical daily rankings for target keywords."""
    __tablename__ = "keyword_rankings"

    keyword_id: Mapped[UUID] = mapped_column(
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[float] = mapped_column(Float, nullable=False)
    url_found: Mapped[str | None] = mapped_column(String(500), nullable=True)
    check_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("keyword_id", "check_date", name="uq_keyword_rankings_keyword_date"),
    )


class GscCountry(BaseModel):
    """Search Console country-level performance metrics."""
    __tablename__ = "gsc_countries"

    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    country: Mapped[str] = mapped_column(String(100), nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    position: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    date_metric: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    __table_args__ = (
        Index("idx_gsc_country_site_date", "website_id", "date_metric"),
        Index("idx_gsc_country_name", "country"),
    )


class GscDevice(BaseModel):
    """Search Console device-level performance metrics."""
    __tablename__ = "gsc_devices"

    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device: Mapped[str] = mapped_column(String(100), nullable=False)
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    position: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    date_metric: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    __table_args__ = (
        Index("idx_gsc_device_site_date", "website_id", "date_metric"),
        Index("idx_gsc_device_name", "device"),
    )


class GscDate(BaseModel):
    """Search Console date-level performance metrics."""
    __tablename__ = "gsc_dates"

    website_id: Mapped[UUID] = mapped_column(
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clicks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    impressions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ctr: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    position: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    date_metric: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    __table_args__ = (
        Index("idx_gsc_date_site_date", "website_id", "date_metric"),
        UniqueConstraint("website_id", "date_metric", name="uq_gsc_dates_site_date"),
    )
