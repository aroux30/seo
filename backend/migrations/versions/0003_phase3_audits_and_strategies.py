"""phase3 audits and strategies

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-05 03:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. seo_audits
    op.create_table(
        'seo_audits',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('overall_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('technical_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('content_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ux_score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('pages_crawled', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('summary', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_seo_audit_website_status', 'seo_audits', ['website_id', 'status'], unique=False)
    op.create_index(op.f('ix_seo_audits_website_id'), 'seo_audits', ['website_id'], unique=False)

    # 2. seo_audit_issues
    op.create_table(
        'seo_audit_issues',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('audit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('url', sa.String(length=1000), nullable=True),
        sa.Column('recommendation', sa.Text(), nullable=False),
        sa.Column('is_resolved', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['audit_id'], ['seo_audits.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_issue_severity', 'seo_audit_issues', ['website_id', 'severity', 'is_resolved'], unique=False)
    op.create_index(op.f('ix_seo_audit_issues_audit_id'), 'seo_audit_issues', ['audit_id'], unique=False)
    op.create_index(op.f('ix_seo_audit_issues_website_id'), 'seo_audit_issues', ['website_id'], unique=False)

    # 3. ai_seo_strategies
    op.create_table(
        'ai_seo_strategies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('executive_summary', sa.Text(), nullable=False),
        sa.Column('target_audience', sa.String(length=500), nullable=True),
        sa.Column('keyword_clusters', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('content_gaps', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('action_items', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('provider_used', sa.String(length=50), nullable=False, server_default='openai'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ai_strategy_website', 'ai_seo_strategies', ['website_id'], unique=False)
    op.create_index(op.f('ix_ai_seo_strategies_website_id'), 'ai_seo_strategies', ['website_id'], unique=False)

    # 4. ai_agent_logs
    op.create_table(
        'ai_agent_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('agent_name', sa.String(length=100), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('action_taken', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='success'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_ai_agent_log_website', 'ai_agent_logs', ['website_id'], unique=False)
    op.create_index(op.f('ix_ai_agent_logs_website_id'), 'ai_agent_logs', ['website_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_agent_logs_website_id'), table_name='ai_agent_logs')
    op.drop_index('idx_ai_agent_log_website', table_name='ai_agent_logs')
    op.drop_table('ai_agent_logs')

    op.drop_index(op.f('ix_ai_seo_strategies_website_id'), table_name='ai_seo_strategies')
    op.drop_index('idx_ai_strategy_website', table_name='ai_seo_strategies')
    op.drop_table('ai_seo_strategies')

    op.drop_index(op.f('ix_seo_audit_issues_website_id'), table_name='seo_audit_issues')
    op.drop_index(op.f('ix_seo_audit_issues_audit_id'), table_name='seo_audit_issues')
    op.drop_index('idx_audit_issue_severity', table_name='seo_audit_issues')
    op.drop_table('seo_audit_issues')

    op.drop_index(op.f('ix_seo_audits_website_id'), table_name='seo_audits')
    op.drop_index('idx_seo_audit_website_status', table_name='seo_audits')
    op.drop_table('seo_audits')
