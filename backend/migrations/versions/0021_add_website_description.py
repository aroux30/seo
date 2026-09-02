"""Add description field to websites table

Revision ID: 0021
Revises: 0020
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("websites", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("websites", "description")
