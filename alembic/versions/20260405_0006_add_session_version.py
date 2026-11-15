"""Add a revocable browser-session generation to users."""

import secrets

import sqlalchemy as sa

from alembic import op

revision = "20260405_0006"
down_revision = "20260405_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("session_version", sa.String(), nullable=True))
    connection = op.get_bind()
    users = sa.table("users", sa.column("id", sa.Integer), sa.column("session_version", sa.String))
    for user_id in connection.execute(sa.select(users.c.id)).scalars():
        connection.execute(
            users.update()
            .where(users.c.id == user_id)
            .values(session_version=secrets.token_urlsafe(32))
        )
    with op.batch_alter_table("users") as batch:
        batch.alter_column("session_version", existing_type=sa.String(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("session_version")
