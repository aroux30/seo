"""Add search_type to GSC tables so each search type is stored separately

Revision ID: 0022
Revises: 0021
Create Date: 2026-09-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GSC_TABLES = (
    "gsc_queries",
    "gsc_pages",
    "gsc_countries",
    "gsc_devices",
    "gsc_dates",
)


def upgrade() -> None:
    for table in _GSC_TABLES:
        op.add_column(
            table,
            sa.Column("search_type", sa.String(20), nullable=False, server_default="web"),
        )
        op.create_index(
            f"idx_{table}_search_type", table, ["website_id", "search_type", "date_metric"]
        )

    # gsc_dates was unique per (website_id, date_metric); one row per day cannot
    # hold both web and (say) image traffic. Widen the key to include the type.
    op.drop_constraint("uq_gsc_dates_site_date", "gsc_dates", type_="unique")
    op.create_unique_constraint(
        "uq_gsc_dates_site_date_type", "gsc_dates",
        ["website_id", "date_metric", "search_type"],
    )


def downgrade() -> None:
    # Collapse back to one row per day (keep the earliest inserted, i.e. web).
    op.delete("gsc_dates", sa.text("search_type <> 'web'"))
    op.drop_constraint("uq_gsc_dates_site_date_type", "gsc_dates", type_="unique")
    op.create_unique_constraint(
        "uq_gsc_dates_site_date", "gsc_dates", ["website_id", "date_metric"]
    )
    for table in _GSC_TABLES:
        op.drop_index(f"idx_{table}_search_type", table_name=table)
        op.drop_column(table, "search_type")
