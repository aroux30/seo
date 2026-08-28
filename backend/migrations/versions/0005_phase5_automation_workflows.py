"""phase5 automation workflows

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-05 04:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. automation_workflows
    op.create_table(
        'automation_workflows',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('template_key', sa.String(length=100), nullable=True),
        sa.Column('trigger_type', sa.String(length=50), nullable=False, server_default='cron'),
        sa.Column('cron_expression', sa.String(length=100), nullable=True),
        sa.Column('n8n_webhook_url', sa.String(length=500), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_run_status', sa.String(length=50), nullable=True),
        sa.Column('config_metadata', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_automation_workflows_id'), 'automation_workflows', ['id'], unique=False)
    op.create_index(op.f('ix_automation_workflows_website_id'), 'automation_workflows', ['website_id'], unique=False)

    # 2. automation_logs
    op.create_table(
        'automation_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('workflow_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('website_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='running'),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('payload_json', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('result_json', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_id'], ['automation_workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_automation_logs_id'), 'automation_logs', ['id'], unique=False)
    op.create_index(op.f('ix_automation_logs_website_id'), 'automation_logs', ['website_id'], unique=False)
    op.create_index(op.f('ix_automation_logs_workflow_id'), 'automation_logs', ['workflow_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_automation_logs_workflow_id'), table_name='automation_logs')
    op.drop_index(op.f('ix_automation_logs_website_id'), table_name='automation_logs')
    op.drop_index(op.f('ix_automation_logs_id'), table_name='automation_logs')
    op.drop_table('automation_logs')

    op.drop_index(op.f('ix_automation_workflows_website_id'), table_name='automation_workflows')
    op.drop_index(op.f('ix_automation_workflows_id'), table_name='automation_workflows')
    op.drop_table('automation_workflows')
