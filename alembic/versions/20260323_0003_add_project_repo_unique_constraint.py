"""Add uniqueness constraint for project repository links.

Revision ID: 20260323_0003
Revises: 20260323_0002
Create Date: 2026-03-23 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "20260323_0003"
down_revision: Union[str, None] = "20260323_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Enforce one row per (project_id, repo) mapping."""

    op.create_index(
        "uq_project_repositories_project_repo",
        "project_repositories",
        ["project_id", "repo"],
        unique=True,
    )


def downgrade() -> None:
    """Drop project repository uniqueness constraint."""

    op.drop_index("uq_project_repositories_project_repo", table_name="project_repositories")
