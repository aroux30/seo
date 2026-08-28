"""content versions

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-10 00:00:00.000000

Backs app/models/versions.py. One table: the append-only revision history of
content_articles. Full snapshots, not deltas — see the model docstring.

Two things to note about the schema:

* No `deleted_at`. The history is immutable by design; there is no soft-delete
  path and no update path for these rows.
* The FK to content_articles is ON DELETE CASCADE. Deleting an article must take
  its history with it, otherwise the FK blocks the delete outright.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0013'
down_revision: Union[str, None] = '0012'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'content_versions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('website_id', sa.Uuid(), nullable=False),
        sa.Column('article_id', sa.Uuid(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('content_markdown', sa.Text(), nullable=False),
        sa.Column('content_html', sa.Text(), nullable=False),
        sa.Column('seo_score', sa.Integer(), server_default='0', nullable=False),
        sa.Column('seo_metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('change_type', sa.String(length=30), nullable=False),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('changed_by', sa.Uuid(), nullable=True),
        sa.Column('diff_stats', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('is_current', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ),
        sa.ForeignKeyConstraint(['article_id'], ['content_articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    # Unique: version_number is the user-visible identity of a revision, and this
    # is the backstop for the numbering race version_service locks against.
    op.create_index(
        'uq_content_version_article_number',
        'content_versions', ['article_id', 'version_number'], unique=True,
    )
    op.create_index(
        'idx_content_version_article_current',
        'content_versions', ['article_id', 'is_current'], unique=False,
    )
    op.create_index(
        'idx_content_version_article_created',
        'content_versions', ['article_id', 'created_at'], unique=False,
    )
    op.create_index('idx_content_version_org', 'content_versions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_content_versions_organization_id'), 'content_versions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_content_versions_website_id'), 'content_versions', ['website_id'], unique=False)
    op.create_index(op.f('ix_content_versions_article_id'), 'content_versions', ['article_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_content_versions_article_id'), table_name='content_versions')
    op.drop_index(op.f('ix_content_versions_website_id'), table_name='content_versions')
    op.drop_index(op.f('ix_content_versions_organization_id'), table_name='content_versions')
    op.drop_index('idx_content_version_org', table_name='content_versions')
    op.drop_index('idx_content_version_article_created', table_name='content_versions')
    op.drop_index('idx_content_version_article_current', table_name='content_versions')
    op.drop_index('uq_content_version_article_number', table_name='content_versions')
    op.drop_table('content_versions')
