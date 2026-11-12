"""Add local authentication fields to users

Revision ID: 20260320_0001
Revises: 20260319_0001
Create Date: 2026-03-20 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260320_0001"
down_revision: Union[str, None] = "20260319_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add built-in local-user auth support to the users table."""

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "workos_user_id",
            existing_type=sa.String(),
            nullable=True,
        )
        batch_op.add_column(
            sa.Column(
                "auth_provider",
                sa.String(),
                nullable=False,
                server_default="workos",
            )
        )
        batch_op.add_column(sa.Column("password_hash", sa.String(), nullable=True))


def downgrade() -> None:
    """Remove local authentication fields from the users table."""

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("password_hash")
        batch_op.drop_column("auth_provider")
        batch_op.alter_column(
            "workos_user_id",
            existing_type=sa.String(),
            nullable=False,
        )
