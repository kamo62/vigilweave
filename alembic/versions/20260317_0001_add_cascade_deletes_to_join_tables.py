"""Add cascade deletes to join tables

Revision ID: 20260317_0001
Revises: 20260316_0005
Create Date: 2026-03-17 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "20260317_0001"
down_revision: Union[str, None] = "20260316_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SQLITE_BATCH_NAMING_CONVENTION = {
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
}


def upgrade() -> None:
    """Add ON DELETE CASCADE to join table foreign keys."""

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        _replace_foreign_key(
            table_name="project_repositories",
            constrained_columns=["project_id"],
            referred_table="projects",
            referred_columns=["id"],
            constraint_name="fk_project_repositories_project_id_projects",
            ondelete="CASCADE",
        )
        _replace_foreign_key(
            table_name="portfolio_projects",
            constrained_columns=["portfolio_id"],
            referred_table="portfolios",
            referred_columns=["id"],
            constraint_name="fk_portfolio_projects_portfolio_id_portfolios",
            ondelete="CASCADE",
        )
        _replace_foreign_key(
            table_name="portfolio_projects",
            constrained_columns=["project_id"],
            referred_table="projects",
            referred_columns=["id"],
            constraint_name="fk_portfolio_projects_project_id_projects",
            ondelete="CASCADE",
        )
        return

    # Fix ProjectRepository foreign key
    with op.batch_alter_table(
        "project_repositories",
        naming_convention=SQLITE_BATCH_NAMING_CONVENTION,
    ) as batch_op:
        # Drop existing foreign key constraint
        batch_op.drop_constraint("fk_project_repositories_project_id_projects", type_="foreignkey")
        # Recreate with CASCADE
        batch_op.create_foreign_key(
            "fk_project_repositories_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="CASCADE",
        )

    # Fix PortfolioProject foreign keys
    with op.batch_alter_table(
        "portfolio_projects",
        naming_convention=SQLITE_BATCH_NAMING_CONVENTION,
    ) as batch_op:
        # Drop existing foreign key constraints
        batch_op.drop_constraint(
            "fk_portfolio_projects_portfolio_id_portfolios", type_="foreignkey"
        )
        batch_op.drop_constraint("fk_portfolio_projects_project_id_projects", type_="foreignkey")
        # Recreate with CASCADE
        batch_op.create_foreign_key(
            "fk_portfolio_projects_portfolio_id_portfolios",
            "portfolios",
            ["portfolio_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_portfolio_projects_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    """Remove ON DELETE CASCADE from join table foreign keys."""

    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        _replace_foreign_key(
            table_name="project_repositories",
            constrained_columns=["project_id"],
            referred_table="projects",
            referred_columns=["id"],
            constraint_name="fk_project_repositories_project_id_projects",
        )
        _replace_foreign_key(
            table_name="portfolio_projects",
            constrained_columns=["portfolio_id"],
            referred_table="portfolios",
            referred_columns=["id"],
            constraint_name="fk_portfolio_projects_portfolio_id_portfolios",
        )
        _replace_foreign_key(
            table_name="portfolio_projects",
            constrained_columns=["project_id"],
            referred_table="projects",
            referred_columns=["id"],
            constraint_name="fk_portfolio_projects_project_id_projects",
        )
        return

    # Revert ProjectRepository
    with op.batch_alter_table(
        "project_repositories",
        naming_convention=SQLITE_BATCH_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint("fk_project_repositories_project_id_projects", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_project_repositories_project_id_projects", "projects", ["project_id"], ["id"]
        )

    # Revert PortfolioProject
    with op.batch_alter_table(
        "portfolio_projects",
        naming_convention=SQLITE_BATCH_NAMING_CONVENTION,
    ) as batch_op:
        batch_op.drop_constraint(
            "fk_portfolio_projects_portfolio_id_portfolios", type_="foreignkey"
        )
        batch_op.drop_constraint("fk_portfolio_projects_project_id_projects", type_="foreignkey")
        batch_op.create_foreign_key(
            "fk_portfolio_projects_portfolio_id_portfolios", "portfolios", ["portfolio_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_portfolio_projects_project_id_projects", "projects", ["project_id"], ["id"]
        )


def _replace_foreign_key(
    *,
    table_name: str,
    constrained_columns: list[str],
    referred_table: str,
    referred_columns: list[str],
    constraint_name: str,
    ondelete: str | None = None,
) -> None:
    """Replace a foreign key using discovered constraint names on non-SQLite backends."""

    bind = op.get_bind()
    inspector = inspect(bind)
    for fk in inspector.get_foreign_keys(table_name):
        if fk.get("referred_table") != referred_table:
            continue
        if fk.get("constrained_columns") != constrained_columns:
            continue
        if fk.get("referred_columns") != referred_columns:
            continue
        existing_name = fk.get("name")
        if existing_name:
            op.drop_constraint(existing_name, table_name, type_="foreignkey")
        break

    op.create_foreign_key(
        constraint_name,
        table_name,
        referred_table,
        constrained_columns,
        referred_columns,
        ondelete=ondelete,
    )
