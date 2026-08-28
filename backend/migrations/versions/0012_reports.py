"""reports

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-10 00:00:00.000000

Backs app/models/reports.py. One table: a frozen, generated SEO report
(weekly/monthly/executive/custom) with an optional public share link. See the
model docstring for why `content` is never recomputed after generation and why
`website_id` is nullable (null = organization-level report).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0012'
down_revision: Union[str, None] = '0011'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'reports',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('website_id', sa.Uuid(), nullable=True),
        sa.Column('report_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('generated_by', sa.Uuid(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('metrics_snapshot', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('share_token', sa.String(length=64), nullable=True),
        sa.Column('share_enabled', sa.Boolean(), server_default=sa.text('false'), nullable=False),
        sa.Column('share_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('view_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ),
        sa.ForeignKeyConstraint(['generated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_report_org_type_period', 'reports', ['organization_id', 'report_type', 'period_start'], unique=False)
    op.create_index('idx_report_org_status', 'reports', ['organization_id', 'status'], unique=False)
    op.create_index('idx_report_website', 'reports', ['website_id'], unique=False)
    op.create_index('idx_report_share_token', 'reports', ['share_token'], unique=True)
    op.create_index(op.f('ix_reports_organization_id'), 'reports', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_reports_organization_id'), table_name='reports')
    op.drop_index('idx_report_share_token', table_name='reports')
    op.drop_index('idx_report_website', table_name='reports')
    op.drop_index('idx_report_org_status', table_name='reports')
    op.drop_index('idx_report_org_type_period', table_name='reports')
    op.drop_table('reports')
