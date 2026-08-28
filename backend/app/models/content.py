from sqlalchemy import String, Integer, Text, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import BaseModel, SoftDeleteMixin


class ContentBrief(BaseModel, SoftDeleteMixin):
    __tablename__ = "content_briefs"

    website_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    keyword_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("keywords.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    target_keyword: Mapped[str] = mapped_column(String(255), nullable=False)
    secondary_keywords: Mapped[list] = mapped_column(JSONB, server_default="[]", nullable=False)
    search_intent: Mapped[str] = mapped_column(String(50), default="informational", nullable=False)
    outline: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    target_word_count: Mapped[int] = mapped_column(Integer, default=1500, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)

    # Relationships
    articles: Mapped[list["ContentArticle"]] = relationship(
        back_populates="brief", cascade="all, delete-orphan"
    )


class ContentArticle(BaseModel, SoftDeleteMixin):
    __tablename__ = "content_articles"

    website_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("websites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brief_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("content_briefs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    seo_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    seo_metadata: Mapped[dict] = mapped_column(JSONB, server_default="{}", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    wp_post_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Relationships
    brief: Mapped["ContentBrief | None"] = relationship(back_populates="articles")
