"""Add timezone to DateTime columns

Revision ID: 20260317_0002
Revises: 20260317_0001
Create Date: 2026-03-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260317_0002"
down_revision: Union[str, None] = "20260317_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add timezone=True to all DateTime columns."""

    # Projects table
    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column("created_at", type_=sa.DateTime(timezone=True))
        batch_op.alter_column("updated_at", type_=sa.DateTime(timezone=True))

    # Portfolios table
    with op.batch_alter_table("portfolios") as batch_op:
        batch_op.alter_column("created_at", type_=sa.DateTime(timezone=True))
        batch_op.alter_column("updated_at", type_=sa.DateTime(timezone=True))

    # Project repositories table
    with op.batch_alter_table("project_repositories") as batch_op:
        batch_op.alter_column("added_at", type_=sa.DateTime(timezone=True))

    # Portfolio projects table
    with op.batch_alter_table("portfolio_projects") as batch_op:
        batch_op.alter_column("added_at", type_=sa.DateTime(timezone=True))


def downgrade() -> None:
    """Remove timezone from DateTime columns."""

    # Projects table
    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column("created_at", type_=sa.DateTime(timezone=False))
        batch_op.alter_column("updated_at", type_=sa.DateTime(timezone=False))

    # Portfolios table
    with op.batch_alter_table("portfolios") as batch_op:
        batch_op.alter_column("created_at", type_=sa.DateTime(timezone=False))
        batch_op.alter_column("updated_at", type_=sa.DateTime(timezone=False))

    # Project repositories table
    with op.batch_alter_table("project_repositories") as batch_op:
        batch_op.alter_column("added_at", type_=sa.DateTime(timezone=False))

    # Portfolio projects table
    with op.batch_alter_table("portfolio_projects") as batch_op:
        batch_op.alter_column("added_at", type_=sa.DateTime(timezone=False))
