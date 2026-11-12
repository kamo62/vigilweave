"""Add policy preset metadata."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260316_0004"
down_revision = "20260315_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("policy_profiles") as batch_op:
        batch_op.add_column(
            sa.Column(
                "kind",
                sa.String(),
                nullable=False,
                server_default="custom",
            )
        )
        batch_op.add_column(sa.Column("preset_key", sa.String(), nullable=True))
        batch_op.create_index("ix_policy_profiles_kind", ["kind"], unique=False)
        batch_op.create_index("ix_policy_profiles_preset_key", ["preset_key"], unique=False)

    with op.batch_alter_table("waivers") as batch_op:
        batch_op.alter_column(
            "created_by",
            existing_type=sa.String(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("waivers") as batch_op:
        batch_op.alter_column(
            "created_by",
            existing_type=sa.String(),
            nullable=False,
        )

    with op.batch_alter_table("policy_profiles") as batch_op:
        batch_op.drop_index("ix_policy_profiles_preset_key")
        batch_op.drop_index("ix_policy_profiles_kind")
        batch_op.drop_column("preset_key")
        batch_op.drop_column("kind")
