"""Add token_masked column to scm_connections.

Revision ID: 20260324_0001
Revises: 20260323_0003
Create Date: 2026-03-24 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260324_0001"
down_revision: Union[str, None] = "20260323_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("scm_connections") as batch_op:
        batch_op.add_column(sa.Column("token_masked", sa.String(), server_default="****", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("scm_connections") as batch_op:
        batch_op.drop_column("token_masked")
