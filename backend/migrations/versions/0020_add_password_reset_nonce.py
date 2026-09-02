"""Add password_reset_nonce to users

Revision ID: 0020
Revises: 0019
Create Date: 2026-09-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_reset_nonce", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_reset_nonce")
