"""phase4 content engine

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-05 03:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. content_briefs
    op.create_table(
        'content_briefs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('keyword_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('target_keyword', sa.String(length=255), nullable=False),
        sa.Column('secondary_keywords', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('search_intent', sa.String(length=50), nullable=False, server_default='informational'),
        sa.Column('outline', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('target_word_count', sa.Integer(), nullable=False, server_default='1500'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['keyword_id'], ['keywords.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_content_brief_website', 'content_briefs', ['website_id', 'status'], unique=False)
    op.create_index(op.f('ix_content_briefs_keyword_id'), 'content_briefs', ['keyword_id'], unique=False)
    op.create_index(op.f('ix_content_briefs_website_id'), 'content_briefs', ['website_id'], unique=False)

    # 2. content_articles
    op.create_table(
        'content_articles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('brief_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('content_markdown', sa.Text(), nullable=False),
        sa.Column('content_html', sa.Text(), nullable=False),
        sa.Column('seo_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('seo_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('wp_post_id', sa.Integer(), nullable=True),
        sa.Column('published_url', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['brief_id'], ['content_briefs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_content_article_website', 'content_articles', ['website_id', 'status'], unique=False)
    op.create_index(op.f('ix_content_articles_brief_id'), 'content_articles', ['brief_id'], unique=False)
    op.create_index(op.f('ix_content_articles_website_id'), 'content_articles', ['website_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_content_articles_website_id'), table_name='content_articles')
    op.drop_index(op.f('ix_content_articles_brief_id'), table_name='content_articles')
    op.drop_index('idx_content_article_website', table_name='content_articles')
    op.drop_table('content_articles')

    op.drop_index(op.f('ix_content_briefs_website_id'), table_name='content_briefs')
    op.drop_index(op.f('ix_content_briefs_keyword_id'), table_name='content_briefs')
    op.drop_index('idx_content_brief_website', table_name='content_briefs')
    op.drop_table('content_briefs')
