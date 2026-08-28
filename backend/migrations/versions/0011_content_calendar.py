"""content calendar entries (publish planning, deadlines, kanban board)

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-10 00:00:00.000000

Backs app/models/calendar.py. One table: publish slots for a website.

Two details worth keeping in mind when editing this later:

* `deleted_at` exists because slots are soft-deleted. The auto-scheduler dedups
  on `opportunity_id` across *all* rows including deleted ones, so hard-deleting
  a declined slot would make that opportunity eligible again on the next run.
* No unique index on `opportunity_id`. The dedup rule is enforced in
  `calendar_service.auto_schedule_from_opportunities`, because a unique index
  would also block a human from deliberately planning a second slot for the same
  opportunity (a follow-up article on the same query is legitimate).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'content_calendar_entries',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('organization_id', sa.Uuid(), nullable=False),
        sa.Column('website_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('brief_id', sa.Uuid(), nullable=True),
        sa.Column('article_id', sa.Uuid(), nullable=True),
        sa.Column('opportunity_id', sa.Uuid(), nullable=True),
        # server_default mirrors the model's python-side default so a raw INSERT
        # cannot leave these NULL and break the status/priority vocabularies.
        sa.Column('status', sa.String(length=20), server_default='planned', nullable=False),
        sa.Column('priority', sa.String(length=20), server_default='normal', nullable=False),
        sa.Column('source', sa.String(length=20), server_default='manual', nullable=False),
        # scheduled_for = when it goes live; deadline = when the author must be
        # done. Separate columns on purpose: collapsing them makes "overdue"
        # ambiguous. published_at is stamped by the service, never by a client.
        sa.Column('scheduled_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deadline', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assigned_to', sa.Uuid(), nullable=True),
        sa.Column('target_keyword', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ),
        sa.ForeignKeyConstraint(['website_id'], ['websites.id'], ),
        sa.ForeignKeyConstraint(['brief_id'], ['content_briefs.id'], ),
        sa.ForeignKeyConstraint(['article_id'], ['content_articles.id'], ),
        sa.ForeignKeyConstraint(['opportunity_id'], ['opportunities.id'], ),
        sa.ForeignKeyConstraint(['assigned_to'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    # Month/week grid: one website, entries inside a date range.
    op.create_index('idx_calendar_website_scheduled', 'content_calendar_entries', ['website_id', 'scheduled_for'], unique=False)
    # Kanban board: one org, grouped by status column.
    op.create_index('idx_calendar_org_status', 'content_calendar_entries', ['organization_id', 'status'], unique=False)
    # "My queue": entries assigned to me, by status.
    op.create_index('idx_calendar_assignee_status', 'content_calendar_entries', ['assigned_to', 'status'], unique=False)
    op.create_index(op.f('ix_content_calendar_entries_organization_id'), 'content_calendar_entries', ['organization_id'], unique=False)
    op.create_index(op.f('ix_content_calendar_entries_website_id'), 'content_calendar_entries', ['website_id'], unique=False)
    # Not unique — see module docstring for why the dedup lives in the service.
    op.create_index(op.f('ix_content_calendar_entries_opportunity_id'), 'content_calendar_entries', ['opportunity_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_content_calendar_entries_opportunity_id'), table_name='content_calendar_entries')
    op.drop_index(op.f('ix_content_calendar_entries_website_id'), table_name='content_calendar_entries')
    op.drop_index(op.f('ix_content_calendar_entries_organization_id'), table_name='content_calendar_entries')
    op.drop_index('idx_calendar_assignee_status', table_name='content_calendar_entries')
    op.drop_index('idx_calendar_org_status', table_name='content_calendar_entries')
    op.drop_index('idx_calendar_website_scheduled', table_name='content_calendar_entries')
    op.drop_table('content_calendar_entries')
