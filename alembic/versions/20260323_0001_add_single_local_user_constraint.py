"""Ensure only one local bootstrap user can exist.

Revision ID: 20260323_0001
Revises: 20260322_0001
Create Date: 2026-03-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260323_0001"
down_revision: Union[str, None] = "20260322_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Allow at most one built-in local account."""

    op.create_index(
        "uq_users_single_local_account",
        "users",
        ["auth_provider"],
        unique=True,
        sqlite_where=sa.text("auth_provider = 'LOCAL'"),
        postgresql_where=sa.text("auth_provider = 'LOCAL'"),
    )


def downgrade() -> None:
    """Remove the local-account singleton constraint."""

    op.drop_index("uq_users_single_local_account", table_name="users")
