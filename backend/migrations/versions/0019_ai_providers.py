"""Add ai_provider_keys table for multi-key pool and rotation

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_provider_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
        sa.Column("provider_name", sa.String(length=50), nullable=False, server_default="gemini"),
        sa.Column("label", sa.String(length=100), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False, server_default="gemini-2.0-flash"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("meta_info", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "idx_ai_provider_org_prio",
        "ai_provider_keys",
        ["organization_id", "is_active", "priority"],
    )
    op.create_index(
        "ix_ai_provider_keys_organization_id",
        "ai_provider_keys",
        ["organization_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_provider_keys_organization_id", table_name="ai_provider_keys")
    op.drop_index("idx_ai_provider_org_prio", table_name="ai_provider_keys")
    op.drop_table("ai_provider_keys")
