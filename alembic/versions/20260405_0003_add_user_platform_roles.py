"""Add persistent platform operator roles to users.

Revision ID: 20260405_0003
Revises: 20260405_0002
Create Date: 2026-04-05 01:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260405_0003"
down_revision: Union[str, None] = "20260405_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("platform_role", sa.String(), nullable=False, server_default="none")
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("platform_role")
