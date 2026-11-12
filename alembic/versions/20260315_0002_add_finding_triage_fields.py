"""Add finding triage fields."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260315_0002"
down_revision = "20260315_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("findings", sa.Column("review_status", sa.String(), server_default="open", nullable=False))
    op.add_column("findings", sa.Column("reviewed_by", sa.String(), nullable=True))
    op.add_column("findings", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.create_index(op.f("ix_findings_review_status"), "findings", ["review_status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_findings_review_status"), table_name="findings")
    op.drop_column("findings", "reviewed_at")
    op.drop_column("findings", "reviewed_by")
    op.drop_column("findings", "review_status")
