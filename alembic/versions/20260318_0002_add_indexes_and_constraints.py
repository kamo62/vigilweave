"""Add unique constraints and composite indexes for performance.

Revision ID: 20260318_0002
Revises: 20260318_0001
Create Date: 2026-03-18 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260318_0002"
down_revision: Union[str, None] = "20260318_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # H10: Unique constraint on project key per tenant
    with op.batch_alter_table("projects") as batch_op:
        batch_op.create_unique_constraint("uq_projects_tenant_key", ["tenant_slug", "key"])

    # H10: Unique constraint on portfolio key per tenant
    with op.batch_alter_table("portfolios") as batch_op:
        batch_op.create_unique_constraint("uq_portfolios_tenant_key", ["tenant_slug", "key"])

    # M4: Composite indexes for common query patterns
    op.create_index(
        "ix_findings_scan_severity", "findings", ["scan_id", "severity"]
    )
    op.create_index(
        "ix_findings_scan_review_status", "findings", ["scan_id", "review_status"]
    )
    op.create_index(
        "ix_scans_tenant_repo", "scans", ["tenant_slug", "repo"]
    )
    op.create_index(
        "ix_scans_tenant_status", "scans", ["tenant_slug", "status"]
    )


def downgrade() -> None:
    op.drop_index("ix_scans_tenant_status")
    op.drop_index("ix_scans_tenant_repo")
    op.drop_index("ix_findings_scan_review_status")
    op.drop_index("ix_findings_scan_severity")
    with op.batch_alter_table("portfolios") as batch_op:
        batch_op.drop_constraint("uq_portfolios_tenant_key", type_="unique")
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("uq_projects_tenant_key", type_="unique")
