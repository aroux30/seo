"""insights layer: opportunities, alerts, notifications

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-10 00:00:00.000000

Backs app/models/insights.py. The three tables ship together because the
dispatcher path writes all of them in one transaction: a detector inserts an
Opportunity or Alert, and the notification fan-out immediately references it by
FK. Creating them in separate revisions would leave a head where notifications
has a dangling FK target.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'opportunities',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('website_id', sa.Uuid(), nullable=False),
        sa.Column('opportunity_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='open', nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('query', sa.Text(), nullable=True),
        sa.Column('page_url', sa.Text(), nullable=True),
        sa.Column('keyword_id', sa.Uuid(), nullable=True),
        sa.Column('priority_score', sa.Integer(), server_default='0', nullable=False),
        sa.Column('estimated_traffic_gain', sa.Integer(), server_default='0', nullable=False),
        sa.Column('current_position', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('current_clicks', sa.Integer(), server_default='0', nullable=False),
        sa.Column('current_impressions', sa.Integer(), server_default='0', nullable=False),
        sa.Column('current_ctr', sa.Numeric(precision=6, scale=4), nullable=True),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('recommended_action', sa.Text(), nullable=True),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actioned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dismissed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('dismissed_by', sa.Uuid(), nullable=True),
        sa.Column('dismiss_reason', sa.Text(), nullable=True),
        sa.Column('linked_brief_id', sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ),
        sa.ForeignKeyConstraint(['keyword_id'], ['keywords.id'], ),
        sa.ForeignKeyConstraint(['dismissed_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['linked_brief_id'], ['content_briefs.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_opp_website_status', 'opportunities', ['website_id', 'status'], unique=False)
    op.create_index('idx_opp_org_status', 'opportunities', ['organization_id', 'status'], unique=False)
    op.create_index('idx_opp_type', 'opportunities', ['opportunity_type'], unique=False)
    op.create_index('idx_opp_fingerprint', 'opportunities', ['website_id', 'fingerprint'], unique=True)
    op.create_index(op.f('ix_opportunities_organization_id'), 'opportunities', ['organization_id'], unique=False)
    op.create_index(op.f('ix_opportunities_website_id'), 'opportunities', ['website_id'], unique=False)
    op.create_index(op.f('ix_opportunities_priority_score'), 'opportunities', ['priority_score'], unique=False)
    op.create_index(op.f('ix_opportunities_detected_at'), 'opportunities', ['detected_at'], unique=False)

    op.create_table(
        'alerts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('website_id', sa.Uuid(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), server_default='warning', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=True),
        sa.Column('current_value', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('previous_value', sa.Numeric(precision=14, scale=4), nullable=True),
        sa.Column('change_percent', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('entity_type', sa.String(length=50), nullable=True),
        sa.Column('entity_id', sa.Uuid(), nullable=True),
        sa.Column('fingerprint', sa.String(length=64), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('occurrence_count', sa.Integer(), server_default='1', nullable=False),
        sa.Column('triggered_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('acknowledged_by', sa.Uuid(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('resolved_by', sa.Uuid(), nullable=True),
        sa.Column('resolution_note', sa.Text(), nullable=True),
        sa.Column('muted_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('notified_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ),
        sa.ForeignKeyConstraint(['acknowledged_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_alert_website_status', 'alerts', ['website_id', 'status'], unique=False)
    op.create_index('idx_alert_org_status', 'alerts', ['organization_id', 'status'], unique=False)
    op.create_index('idx_alert_severity', 'alerts', ['severity'], unique=False)
    op.create_index('idx_alert_fingerprint', 'alerts', ['website_id', 'fingerprint'], unique=True)
    op.create_index(op.f('ix_alerts_organization_id'), 'alerts', ['organization_id'], unique=False)
    op.create_index(op.f('ix_alerts_website_id'), 'alerts', ['website_id'], unique=False)
    op.create_index(op.f('ix_alerts_triggered_at'), 'alerts', ['triggered_at'], unique=False)

    op.create_table(
        'notifications',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('website_id', sa.Uuid(), nullable=True),
        sa.Column('channel', sa.String(length=20), server_default='dashboard', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='pending', nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('action_url', sa.Text(), nullable=True),
        sa.Column('alert_id', sa.Uuid(), nullable=True),
        sa.Column('opportunity_id', sa.Uuid(), nullable=True),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_notif_user_read', 'notifications', ['user_id', 'read_at'], unique=False)
    op.create_index('idx_notif_org', 'notifications', ['organization_id'], unique=False)
    op.create_index('idx_notif_status_channel', 'notifications', ['status', 'channel'], unique=False)
    op.create_index(op.f('ix_notifications_organization_id'), 'notifications', ['organization_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notifications_organization_id'), table_name='notifications')
    op.drop_index('idx_notif_status_channel', table_name='notifications')
    op.drop_index('idx_notif_org', table_name='notifications')
    op.drop_index('idx_notif_user_read', table_name='notifications')
    op.drop_table('notifications')

    op.drop_index(op.f('ix_alerts_triggered_at'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_website_id'), table_name='alerts')
    op.drop_index(op.f('ix_alerts_organization_id'), table_name='alerts')
    op.drop_index('idx_alert_fingerprint', table_name='alerts')
    op.drop_index('idx_alert_severity', table_name='alerts')
    op.drop_index('idx_alert_org_status', table_name='alerts')
    op.drop_index('idx_alert_website_status', table_name='alerts')
    op.drop_table('alerts')

    op.drop_index(op.f('ix_opportunities_detected_at'), table_name='opportunities')
    op.drop_index(op.f('ix_opportunities_priority_score'), table_name='opportunities')
    op.drop_index(op.f('ix_opportunities_website_id'), table_name='opportunities')
    op.drop_index(op.f('ix_opportunities_organization_id'), table_name='opportunities')
    op.drop_index('idx_opp_fingerprint', table_name='opportunities')
    op.drop_index('idx_opp_type', table_name='opportunities')
    op.drop_index('idx_opp_org_status', table_name='opportunities')
    op.drop_index('idx_opp_website_status', table_name='opportunities')
    op.drop_table('opportunities')
