"""Fix DateTime columns to use timezone=True for consistency.

Revision ID: 20260318_0001
Revises: 20260317_0002
Create Date: 2026-03-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260318_0001"
down_revision: Union[str, None] = "20260317_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Projects table
    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column("created_at", type_=sa.DateTime(timezone=True))
        batch_op.alter_column("updated_at", type_=sa.DateTime(timezone=True))

    # Portfolios table
    with op.batch_alter_table("portfolios") as batch_op:
        batch_op.alter_column("created_at", type_=sa.DateTime(timezone=True))
        batch_op.alter_column("updated_at", type_=sa.DateTime(timezone=True))

    # Join tables
    with op.batch_alter_table("project_repositories") as batch_op:
        batch_op.alter_column("added_at", type_=sa.DateTime(timezone=True))

    with op.batch_alter_table("portfolio_projects") as batch_op:
        batch_op.alter_column("added_at", type_=sa.DateTime(timezone=True))


def downgrade() -> None:
    with op.batch_alter_table("portfolio_projects") as batch_op:
        batch_op.alter_column("added_at", type_=sa.DateTime())

    with op.batch_alter_table("project_repositories") as batch_op:
        batch_op.alter_column("added_at", type_=sa.DateTime())

    with op.batch_alter_table("portfolios") as batch_op:
        batch_op.alter_column("created_at", type_=sa.DateTime())
        batch_op.alter_column("updated_at", type_=sa.DateTime())

    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column("created_at", type_=sa.DateTime())
        batch_op.alter_column("updated_at", type_=sa.DateTime())
