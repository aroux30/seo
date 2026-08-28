"""calendar ai auto unique index

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-22 05:26:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0016'
down_revision: Union[str, None] = '0015'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add partial unique index to prevent duplicate scheduling for the same AI opportunity
    op.create_index(
        'idx_calendar_ai_auto_unique',
        'content_calendar_entries',
        ['website_id', 'opportunity_id'],
        unique=True,
        postgresql_where=sa.text("source = 'ai_auto' AND opportunity_id IS NOT NULL")
    )


def downgrade() -> None:
    op.drop_index('idx_calendar_ai_auto_unique', table_name='content_calendar_entries')
