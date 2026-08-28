"""phase2 connectors and keywords

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-05 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. oauth_integrations
    op.create_table(
        'oauth_integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='google_search_console'),
        sa.Column('client_id', sa.String(length=255), nullable=True),
        sa.Column('encrypted_access_token', sa.Text(), nullable=False),
        sa.Column('encrypted_refresh_token', sa.Text(), nullable=True),
        sa.Column('scopes', sa.Text(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('website_id', 'provider', name='uq_oauth_integrations_site_provider')
    )
    op.create_index(op.f('ix_oauth_integrations_website_id'), 'oauth_integrations', ['website_id'], unique=False)

    # 2. wordpress_integrations
    op.create_table(
        'wordpress_integrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('wp_url', sa.String(length=500), nullable=False),
        sa.Column('username', sa.String(length=255), nullable=False),
        sa.Column('encrypted_app_password', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('settings', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_wordpress_integrations_website_id'), 'wordpress_integrations', ['website_id'], unique=True)

    # 3. gsc_queries
    op.create_table(
        'gsc_queries',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('query', sa.String(length=500), nullable=False),
        sa.Column('page_url', sa.String(length=1000), nullable=True),
        sa.Column('clicks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('impressions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ctr', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('position', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('date_metric', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gsc_queries_date_metric'), 'gsc_queries', ['date_metric'], unique=False)
    op.create_index(op.f('ix_gsc_queries_website_id'), 'gsc_queries', ['website_id'], unique=False)
    op.create_index('idx_gsc_query_site_date', 'gsc_queries', ['website_id', 'date_metric'], unique=False)
    op.create_index('idx_gsc_query_text', 'gsc_queries', ['query'], unique=False)

    # 4. gsc_pages
    op.create_table(
        'gsc_pages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('page_url', sa.String(length=1000), nullable=False),
        sa.Column('clicks', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('impressions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ctr', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('position', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('date_metric', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gsc_pages_date_metric'), 'gsc_pages', ['date_metric'], unique=False)
    op.create_index(op.f('ix_gsc_pages_website_id'), 'gsc_pages', ['website_id'], unique=False)
    op.create_index('idx_gsc_page_site_date', 'gsc_pages', ['website_id', 'date_metric'], unique=False)
    op.create_index('idx_gsc_page_url', 'gsc_pages', ['page_url'], unique=False)

    # 5. keywords
    op.create_table(
        'keywords',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('keyword', sa.String(length=255), nullable=False),
        sa.Column('search_volume', sa.Integer(), nullable=True),
        sa.Column('difficulty', sa.Integer(), nullable=True),
        sa.Column('target_page_url', sa.String(length=500), nullable=True),
        sa.Column('intent', sa.String(length=50), nullable=False, server_default='informational'),
        sa.Column('tags', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
        sa.Column('last_position', sa.Float(), nullable=True),
        sa.Column('best_position', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('website_id', 'keyword', name='uq_keywords_site_keyword')
    )
    op.create_index(op.f('ix_keywords_website_id'), 'keywords', ['website_id'], unique=False)

    # 6. keyword_rankings
    op.create_table(
        'keyword_rankings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('keyword_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('position', sa.Float(), nullable=False),
        sa.Column('url_found', sa.String(length=500), nullable=True),
        sa.Column('check_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['keyword_id'], ['keywords.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('keyword_id', 'check_date', name='uq_keyword_rankings_keyword_date')
    )
    op.create_index(op.f('ix_keyword_rankings_check_date'), 'keyword_rankings', ['check_date'], unique=False)
    op.create_index(op.f('ix_keyword_rankings_keyword_id'), 'keyword_rankings', ['keyword_id'], unique=False)


def downgrade() -> None:
    op.drop_table('keyword_rankings')
    op.drop_table('keywords')
    op.drop_table('gsc_pages')
    op.drop_table('gsc_queries')
    op.drop_table('wordpress_integrations')
    op.drop_table('oauth_integrations')
