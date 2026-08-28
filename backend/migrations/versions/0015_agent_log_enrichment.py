"""agent log enrichment: audit trail, confidence and cost on ai_agent_logs

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-10 00:00:00.000000

Backs the Agent Activity Center. `ai_agent_logs` already existed (created in
0003) and already has rows: it recorded that an agent ran and how many tokens it
burned, but not what it decided, how confident it was, what it was handed, what
it produced, how long it took, or what it cost.

**Every column added here is nullable or carries a server_default, and that is
not a style choice.** `ALTER TABLE ... ADD COLUMN ... NOT NULL` with no default
is rejected by Postgres when the table is non-empty, because the existing rows
have no value to put there and none can be invented. Where a value genuinely
must always be present (`agent_type`) a server_default is supplied so the
backfill is implicit; where NULL is meaningful (`confidence_score` — the agent
reported nothing, which is not the same as reporting zero) the column stays
nullable on purpose.

`organization_id` is nullable for the same reason and one more: it is a
denormalised copy of `websites.organization_id`, so pre-0015 rows can be
backfilled by a join, but until that backfill runs a NOT NULL would make the
migration itself fail. Readers must therefore treat NULL as "unknown tenant"
and resolve the org through `websites` — see agent_activity_service for the
single place that decision is made.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '0015'
down_revision: Union[str, None] = '0014'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- tenant ------------------------------------------------------------
    op.add_column(
        'ai_agent_logs',
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        'fk_ai_agent_logs_organization_id',
        'ai_agent_logs',
        'organizations',
        ['organization_id'],
        ['id'],
    )

    # --- classification ----------------------------------------------------
    # server_default 'other' rather than NULL: 'other' is a real member of
    # AGENT_TYPES, so legacy rows land in a valid bucket the UI can group.
    op.add_column(
        'ai_agent_logs',
        sa.Column('agent_type', sa.String(length=50), server_default='other', nullable=False),
    )

    # --- decision / audit trail -------------------------------------------
    op.add_column(
        'ai_agent_logs',
        sa.Column('confidence_score', sa.Numeric(precision=5, scale=2), nullable=True),
    )
    op.add_column('ai_agent_logs', sa.Column('decision_summary', sa.Text(), nullable=True))
    op.add_column(
        'ai_agent_logs',
        sa.Column('input_context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        'ai_agent_logs',
        sa.Column('output_result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )

    # --- execution facts ---------------------------------------------------
    op.add_column('ai_agent_logs', sa.Column('duration_ms', sa.Integer(), nullable=True))
    op.add_column('ai_agent_logs', sa.Column('error_message', sa.Text(), nullable=True))
    # 6dp: a single cheap call costs well under a cent; 2dp would report every
    # such run as 0.00 and the cost column would look broken.
    op.add_column(
        'ai_agent_logs',
        sa.Column('estimated_cost_usd', sa.Numeric(precision=10, scale=6), nullable=True),
    )

    # --- loose back-pointer ------------------------------------------------
    # No FK: the target spans several tables, and a hard FK would block
    # deleting an article whose generation run is still in the audit trail.
    op.add_column(
        'ai_agent_logs',
        sa.Column('related_entity_type', sa.String(length=50), nullable=True),
    )
    op.add_column(
        'ai_agent_logs',
        sa.Column('related_entity_id', postgresql.UUID(as_uuid=True), nullable=True),
    )

    # --- backfill ----------------------------------------------------------
    # Resolve the tenant for rows that predate the column. Done as one UPDATE
    # ... FROM rather than a Python loop so it stays inside the migration's
    # transaction and does not depend on the app being importable.
    op.execute(
        """
        UPDATE ai_agent_logs AS l
           SET organization_id = w.organization_id
          FROM websites AS w
         WHERE l.website_id = w.id
           AND l.organization_id IS NULL
        """
    )

    # --- indexes -----------------------------------------------------------
    op.create_index(
        'idx_ai_agent_log_org_created', 'ai_agent_logs',
        ['organization_id', 'created_at'], unique=False,
    )
    op.create_index(
        'idx_ai_agent_log_website_agent', 'ai_agent_logs',
        ['website_id', 'agent_name'], unique=False,
    )
    op.create_index('idx_ai_agent_log_status', 'ai_agent_logs', ['status'], unique=False)
    op.create_index(
        op.f('ix_ai_agent_logs_organization_id'), 'ai_agent_logs',
        ['organization_id'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_agent_logs_organization_id'), table_name='ai_agent_logs')
    op.drop_index('idx_ai_agent_log_status', table_name='ai_agent_logs')
    op.drop_index('idx_ai_agent_log_website_agent', table_name='ai_agent_logs')
    op.drop_index('idx_ai_agent_log_org_created', table_name='ai_agent_logs')

    op.drop_column('ai_agent_logs', 'related_entity_id')
    op.drop_column('ai_agent_logs', 'related_entity_type')
    op.drop_column('ai_agent_logs', 'estimated_cost_usd')
    op.drop_column('ai_agent_logs', 'error_message')
    op.drop_column('ai_agent_logs', 'duration_ms')
    op.drop_column('ai_agent_logs', 'output_result')
    op.drop_column('ai_agent_logs', 'input_context')
    op.drop_column('ai_agent_logs', 'decision_summary')
    op.drop_column('ai_agent_logs', 'confidence_score')

    op.drop_constraint(
        'fk_ai_agent_logs_organization_id', 'ai_agent_logs', type_='foreignkey'
    )
    op.drop_column('ai_agent_logs', 'agent_type')
    op.drop_column('ai_agent_logs', 'organization_id')
