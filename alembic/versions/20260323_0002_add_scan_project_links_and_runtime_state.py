"""Add explicit scan project links and runtime state tables.

Revision ID: 20260323_0002
Revises: 20260323_0001
Create Date: 2026-03-23 00:30:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260323_0002"
down_revision: Union[str, None] = "20260323_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add scan project ownership and persisted runtime state tables."""

    with op.batch_alter_table("scans") as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_scans_project_id",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_scans_project_id", ["project_id"], unique=False)

    op.create_table(
        "license_verification_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("cache_key", sa.String(), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("cached_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_license_verification_cache_cache_key",
        "license_verification_cache",
        ["cache_key"],
        unique=True,
    )
    op.create_index(
        "ix_license_verification_cache_cached_at",
        "license_verification_cache",
        ["cached_at"],
        unique=False,
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("delivery_id", sa.String(), nullable=False),
        sa.Column("tenant_slug", sa.String(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_webhook_deliveries_provider", "webhook_deliveries", ["provider"], unique=False)
    op.create_index(
        "ix_webhook_deliveries_delivery_id",
        "webhook_deliveries",
        ["delivery_id"],
        unique=False,
    )
    op.create_index(
        "ix_webhook_deliveries_tenant_slug",
        "webhook_deliveries",
        ["tenant_slug"],
        unique=False,
    )
    op.create_index(
        "ix_webhook_deliveries_received_at",
        "webhook_deliveries",
        ["received_at"],
        unique=False,
    )
    op.create_index(
        "uq_webhook_deliveries_provider_delivery_id",
        "webhook_deliveries",
        ["provider", "delivery_id"],
        unique=True,
    )

    connection = op.get_bind()
    scans = sa.table(
        "scans",
        sa.column("id", sa.Integer()),
        sa.column("tenant_slug", sa.String()),
        sa.column("repo", sa.String()),
        sa.column("project_id", sa.Integer()),
    )
    projects = sa.table(
        "projects",
        sa.column("id", sa.Integer()),
        sa.column("tenant_slug", sa.String()),
    )
    project_repositories = sa.table(
        "project_repositories",
        sa.column("project_id", sa.Integer()),
        sa.column("repo", sa.String()),
    )

    repo_rows = connection.execute(
        sa.select(
            projects.c.tenant_slug.label("tenant_slug"),
            project_repositories.c.repo.label("repo"),
            sa.func.min(projects.c.id).label("project_id"),
            sa.func.count(sa.distinct(projects.c.id)).label("project_count"),
        )
        .select_from(
            project_repositories.join(projects, project_repositories.c.project_id == projects.c.id)
        )
        .group_by(projects.c.tenant_slug, project_repositories.c.repo)
    ).mappings()

    unique_project_map = {
        (row["tenant_slug"], row["repo"]): row["project_id"]
        for row in repo_rows
        if row["project_count"] == 1
    }

    if unique_project_map:
        scan_rows = connection.execute(
            sa.select(scans.c.id, scans.c.tenant_slug, scans.c.repo).where(scans.c.project_id.is_(None))
        ).mappings()
        for row in scan_rows:
            project_id = unique_project_map.get((row["tenant_slug"], row["repo"]))
            if project_id is None:
                continue
            connection.execute(
                sa.update(scans).where(scans.c.id == row["id"]).values(project_id=project_id)
            )


def downgrade() -> None:
    """Remove scan project ownership and runtime state tables."""

    op.drop_index("uq_webhook_deliveries_provider_delivery_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_received_at", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_tenant_slug", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_delivery_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_provider", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")

    op.drop_index(
        "ix_license_verification_cache_cached_at",
        table_name="license_verification_cache",
    )
    op.drop_index(
        "ix_license_verification_cache_cache_key",
        table_name="license_verification_cache",
    )
    op.drop_table("license_verification_cache")

    with op.batch_alter_table("scans") as batch_op:
        batch_op.drop_index("ix_scans_project_id")
        batch_op.drop_constraint("fk_scans_project_id", type_="foreignkey")
        batch_op.drop_column("project_id")
