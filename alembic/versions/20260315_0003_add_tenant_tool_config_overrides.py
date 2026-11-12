"""Add tenant-scoped tool config overrides."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260315_0003"
down_revision = "20260315_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenant_tool_config_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_slug", sa.String(), nullable=False),
        sa.Column("tool", sa.String(), nullable=False),
        sa.Column("override", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_slug", "tool", name="uq_tenant_tool_override"),
    )
    op.create_index(
        op.f("ix_tenant_tool_config_overrides_tenant_slug"),
        "tenant_tool_config_overrides",
        ["tenant_slug"],
        unique=False,
    )
    op.create_index(
        op.f("ix_tenant_tool_config_overrides_tool"),
        "tenant_tool_config_overrides",
        ["tool"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_tenant_tool_config_overrides_tool"),
        table_name="tenant_tool_config_overrides",
    )
    op.drop_index(
        op.f("ix_tenant_tool_config_overrides_tenant_slug"),
        table_name="tenant_tool_config_overrides",
    )
    op.drop_table("tenant_tool_config_overrides")
