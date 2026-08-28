"""content categories (site structure tree)

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-10 00:00:00.000000

Backs app/models/categories.py. One table: a website's category tree, stored as
a self-referencing parent_id edge plus a materialised `path` / `depth` pair so
the whole structure can be rendered from one flat SELECT.

Note what is deliberately NOT here: a unique index on (website_id, slug). The
real rule is "unique among non-deleted rows", which a plain unique index cannot
express — a soft-deleted "/news" would block reusing that slug forever.
`category_service._assert_slug_free` enforces it instead.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'content_categories',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('website_id', sa.Uuid(), nullable=False),
        sa.Column('parent_id', sa.Uuid(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('path', sa.String(length=2000), nullable=False),
        # server_default mirrors the model's python-side default so a raw INSERT
        # (a data migration, a psql session) cannot leave these NULL.
        sa.Column('depth', sa.Integer(), server_default='0', nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('wp_term_id', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=20), server_default='manual', nullable=False),
        sa.Column('content_count', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ),
        # Self-FK, no ondelete: rows are soft-deleted, so the database never
        # removes a parent out from under its children.
        sa.ForeignKeyConstraint(['parent_id'], ['content_categories.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_category_website_parent', 'content_categories', ['website_id', 'parent_id'], unique=False)
    op.create_index('idx_category_org', 'content_categories', ['organization_id'], unique=False)
    op.create_index('idx_category_sort', 'content_categories', ['website_id', 'parent_id', 'sort_order'], unique=False)
    # Leading column of this btree is what makes `path LIKE '<prefix>/%'` usable.
    op.create_index('idx_category_path', 'content_categories', ['website_id', 'path'], unique=False)
    # Not unique: wp_term_id is null for every hand-made row and Postgres would
    # allow only one such row per website under a plain unique index.
    op.create_index('idx_category_wp_term', 'content_categories', ['website_id', 'wp_term_id'], unique=False)
    op.create_index(op.f('ix_content_categories_organization_id'), 'content_categories', ['organization_id'], unique=False)
    op.create_index(op.f('ix_content_categories_website_id'), 'content_categories', ['website_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_content_categories_website_id'), table_name='content_categories')
    op.drop_index(op.f('ix_content_categories_organization_id'), table_name='content_categories')
    op.drop_index('idx_category_wp_term', table_name='content_categories')
    op.drop_index('idx_category_path', table_name='content_categories')
    op.drop_index('idx_category_sort', table_name='content_categories')
    op.drop_index('idx_category_org', table_name='content_categories')
    op.drop_index('idx_category_website_parent', table_name='content_categories')
    op.drop_table('content_categories')
