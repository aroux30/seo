"""approval queue

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-10 00:00:00.000000

Backs app/models/approvals.py. One table: a human gate before high-risk
content/structural/AI actions execute. See the model docstring for the
lifecycle (pending -> approved/rejected/cancelled -> executed/failed).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'approval_requests',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('website_id', sa.Uuid(), nullable=True),
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('priority', sa.String(length=20), server_default='normal', nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('requester_id', sa.Uuid(), nullable=False),
        sa.Column('reviewer_id', sa.Uuid(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('risk_level', sa.String(length=20), server_default='medium', nullable=False),
        sa.Column('affected_items_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('decided_by', sa.Uuid(), nullable=True),
        sa.Column('decided_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewer_comment', sa.Text(), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_error', sa.Text(), nullable=True),
        sa.Column('execution_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('related_article_id', sa.Uuid(), nullable=True),
        sa.Column('related_brief_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ),
        sa.ForeignKeyConstraint(['requester_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['reviewer_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['decided_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['related_article_id'], ['content_articles.id'], ),
        sa.ForeignKeyConstraint(['related_brief_id'], ['content_briefs.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_approval_org_status', 'approval_requests', ['organization_id', 'status'], unique=False)
    op.create_index('idx_approval_reviewer', 'approval_requests', ['reviewer_id', 'status'], unique=False)
    op.create_index('idx_approval_requester', 'approval_requests', ['requester_id', 'status'], unique=False)
    op.create_index('idx_approval_website_type', 'approval_requests', ['website_id', 'action_type'], unique=False)
    op.create_index(op.f('ix_approval_requests_organization_id'), 'approval_requests', ['organization_id'], unique=False)
    op.create_index(op.f('ix_approval_requests_website_id'), 'approval_requests', ['website_id'], unique=False)
    op.create_index(op.f('ix_approval_requests_status'), 'approval_requests', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_approval_requests_status'), table_name='approval_requests')
    op.drop_index(op.f('ix_approval_requests_website_id'), table_name='approval_requests')
    op.drop_index(op.f('ix_approval_requests_organization_id'), table_name='approval_requests')
    op.drop_index('idx_approval_website_type', table_name='approval_requests')
    op.drop_index('idx_approval_requester', table_name='approval_requests')
    op.drop_index('idx_approval_reviewer', table_name='approval_requests')
    op.drop_index('idx_approval_org_status', table_name='approval_requests')
    op.drop_table('approval_requests')
