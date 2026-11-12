"""Add unique constraint for tenant-scoped policy presets."""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260316_0005"
down_revision: str | Sequence[str] | None = "20260316_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("policy_profiles") as batch_op:
        batch_op.create_unique_constraint(
            "uq_policy_profiles_tenant_preset_key",
            ["tenant_slug", "preset_key"],
        )


def downgrade() -> None:
    with op.batch_alter_table("policy_profiles") as batch_op:
        batch_op.drop_constraint(
            "uq_policy_profiles_tenant_preset_key",
            type_="unique",
        )
