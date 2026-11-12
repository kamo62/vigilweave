"""Add projects and portfolios tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260315_0001"
down_revision = "20260314_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("tenant_slug", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("default_branch", sa.String(), nullable=False, server_default="main"),
        sa.Column("quality_gate_policy_id", sa.Integer(), nullable=True),
        sa.Column("azure_devops_project", sa.String(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["quality_gate_policy_id"], ["policy_profiles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_projects_tenant_slug"), "projects", ["tenant_slug"], unique=False)
    op.create_index(op.f("ix_projects_key"), "projects", ["key"], unique=False)

    op.create_table(
        "portfolios",
        sa.Column("tenant_slug", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.Column("selection_mode", sa.String(), nullable=False, server_default="manual"),
        sa.Column("selection_value", sa.String(), nullable=True),
        sa.Column("azure_devops_org", sa.String(), nullable=True),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["portfolios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_portfolios_tenant_slug"), "portfolios", ["tenant_slug"], unique=False)
    op.create_index(op.f("ix_portfolios_key"), "portfolios", ["key"], unique=False)

    op.create_table(
        "project_repositories",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("repo", sa.String(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_repositories_project_id"),
        "project_repositories",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_repositories_repo"),
        "project_repositories",
        ["repo"],
        unique=False,
    )

    op.create_table(
        "portfolio_projects",
        sa.Column("portfolio_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_portfolio_projects_portfolio_id"),
        "portfolio_projects",
        ["portfolio_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_portfolio_projects_project_id"),
        "portfolio_projects",
        ["project_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("portfolio_projects")
    op.drop_table("project_repositories")
    op.drop_table("portfolios")
    op.drop_table("projects")
