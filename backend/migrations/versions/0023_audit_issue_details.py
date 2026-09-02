"""Add details JSONB to seo_audit_issues (Lighthouse evidence per issue)

Revision ID: 0023
Revises: 0022
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: Union[str, None] = "0022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "seo_audit_issues",
        sa.Column("details", JSONB(), nullable=False, server_default="{}"),
    )
    # server_default does not backfill existing rows; legacy issues must read
    # as empty details, not NULL (the read schema expects an object).
    op.execute("UPDATE seo_audit_issues SET details = '{}' WHERE details IS NULL")


def downgrade() -> None:
    op.drop_column("seo_audit_issues", "details")
