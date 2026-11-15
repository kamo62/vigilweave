"""Add private ownership and heartbeat fields to scans."""

import sqlalchemy as sa

from alembic import op

revision = "20260405_0007"
down_revision = "20260405_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("scans", sa.Column("lifecycle_token", sa.String(), nullable=True))
    op.add_column("scans", sa.Column("lifecycle_heartbeat_at", sa.DateTime(), nullable=True))
    op.create_index("ix_scans_lifecycle_token", "scans", ["lifecycle_token"])


def downgrade() -> None:
    op.drop_index("ix_scans_lifecycle_token", table_name="scans")
    op.drop_column("scans", "lifecycle_heartbeat_at")
    op.drop_column("scans", "lifecycle_token")
