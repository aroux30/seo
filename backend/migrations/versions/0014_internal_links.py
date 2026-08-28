"""internal links

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-10 00:00:00.000000

Backs app/models/internal_links.py. Two tables:

* internal_link_suggestions — detector output, deduped by
  (website_id, fingerprint) so a re-run updates in place instead of inserting
  a duplicate row.
* internal_links — links actually applied, deduped by
  (source_article_id, target_article_id, anchor_text).

Both carry organization_id even though it is derivable through website_id:
the scoping guards filter on it directly and a join per guard would be wasted
work on the hot path.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0014'
down_revision: Union[str, None] = '0013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'internal_link_suggestions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('website_id', sa.Uuid(), nullable=False),
        sa.Column('source_article_id', sa.Uuid(), nullable=False),
        sa.Column('target_article_id', sa.Uuid(), nullable=False),
        sa.Column('anchor_text', sa.String(length=500), nullable=False),
        sa.Column('context_snippet', sa.Text(), nullable=True),
        sa.Column('relevance_score', sa.Integer(), server_default='0', nullable=False),
        sa.Column('score_breakdown', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='suggested', nullable=False),
        sa.Column('reason', sa.String(length=30), nullable=False),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decided_by', sa.Uuid(), nullable=True),
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ),
        sa.ForeignKeyConstraint(['source_article_id'], ['content_articles.id'], ),
        sa.ForeignKeyConstraint(['target_article_id'], ['content_articles.id'], ),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_ils_website_status', 'internal_link_suggestions', ['website_id', 'status'], unique=False)
    op.create_index('idx_ils_org_status', 'internal_link_suggestions', ['organization_id', 'status'], unique=False)
    op.create_index('idx_ils_source', 'internal_link_suggestions', ['source_article_id'], unique=False)
    op.create_index('idx_ils_target', 'internal_link_suggestions', ['target_article_id'], unique=False)
    # Dedup guard for the detector upsert.
    op.create_index('idx_ils_fingerprint', 'internal_link_suggestions', ['website_id', 'fingerprint'], unique=True)
    op.create_index(op.f('ix_internal_link_suggestions_organization_id'), 'internal_link_suggestions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_internal_link_suggestions_website_id'), 'internal_link_suggestions', ['website_id'], unique=False)
    op.create_index(op.f('ix_internal_link_suggestions_relevance_score'), 'internal_link_suggestions', ['relevance_score'], unique=False)
    op.create_index(op.f('ix_internal_link_suggestions_detected_at'), 'internal_link_suggestions', ['detected_at'], unique=False)

    op.create_table(
        'internal_links',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('website_id', sa.Uuid(), nullable=False),
        sa.Column('source_article_id', sa.Uuid(), nullable=False),
        sa.Column('target_article_id', sa.Uuid(), nullable=False),
        sa.Column('anchor_text', sa.String(length=500), nullable=False),
        sa.Column('target_url', sa.String(length=1000), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('suggestion_id', sa.Uuid(), nullable=True),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ),
        sa.ForeignKeyConstraint(['source_article_id'], ['content_articles.id'], ),
        sa.ForeignKeyConstraint(['target_article_id'], ['content_articles.id'], ),
        sa.ForeignKeyConstraint(['suggestion_id'], ['internal_link_suggestions.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_il_website', 'internal_links', ['website_id'], unique=False)
    op.create_index('idx_il_org', 'internal_links', ['organization_id'], unique=False)
    op.create_index('idx_il_source', 'internal_links', ['source_article_id'], unique=False)
    op.create_index('idx_il_target', 'internal_links', ['target_article_id'], unique=False)
    # One row per (source, target, anchor): the same link recorded twice is a bug.
    op.create_index(
        'idx_il_source_target_anchor',
        'internal_links',
        ['source_article_id', 'target_article_id', 'anchor_text'],
        unique=True,
    )
    op.create_index(op.f('ix_internal_links_organization_id'), 'internal_links', ['organization_id'], unique=False)
    op.create_index(op.f('ix_internal_links_website_id'), 'internal_links', ['website_id'], unique=False)
    op.create_index(op.f('ix_internal_links_first_seen_at'), 'internal_links', ['first_seen_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_internal_links_first_seen_at'), table_name='internal_links')
    op.drop_index(op.f('ix_internal_links_website_id'), table_name='internal_links')
    op.drop_index(op.f('ix_internal_links_organization_id'), table_name='internal_links')
    op.drop_index('idx_il_source_target_anchor', table_name='internal_links')
    op.drop_index('idx_il_target', table_name='internal_links')
    op.drop_index('idx_il_source', table_name='internal_links')
    op.drop_index('idx_il_org', table_name='internal_links')
    op.drop_index('idx_il_website', table_name='internal_links')
    op.drop_table('internal_links')

    op.drop_index(op.f('ix_internal_link_suggestions_detected_at'), table_name='internal_link_suggestions')
    op.drop_index(op.f('ix_internal_link_suggestions_relevance_score'), table_name='internal_link_suggestions')
    op.drop_index(op.f('ix_internal_link_suggestions_website_id'), table_name='internal_link_suggestions')
    op.drop_index(op.f('ix_internal_link_suggestions_organization_id'), table_name='internal_link_suggestions')
    op.drop_index('idx_ils_fingerprint', table_name='internal_link_suggestions')
    op.drop_index('idx_ils_target', table_name='internal_link_suggestions')
    op.drop_index('idx_ils_source', table_name='internal_link_suggestions')
    op.drop_index('idx_ils_org_status', table_name='internal_link_suggestions')
    op.drop_index('idx_ils_website_status', table_name='internal_link_suggestions')
    op.drop_table('internal_link_suggestions')
