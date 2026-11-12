"""Database engine and session helpers."""

from collections.abc import Generator
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect
from sqlmodel import Session, create_engine

from alembic import command
from app.core.config import settings

sqlite_connect_args = {}
if settings.database_url.startswith("sqlite"):
    sqlite_connect_args["check_same_thread"] = False

engine = create_engine(settings.database_url, echo=False, connect_args=sqlite_connect_args)


def _alembic_config() -> Config:
    root_dir = Path(__file__).resolve().parents[2]
    config = Config(str(root_dir / "alembic.ini"))
    config.set_main_option("script_location", str(root_dir / "alembic"))
    config.attributes["configure_logger"] = False
    return config


def init_db() -> None:
    """Bring the database up to the current Alembic revision."""

    config = _alembic_config()

    with engine.begin() as connection:
        inspector = inspect(connection)
        existing_tables = set(inspector.get_table_names())

        config.attributes["connection"] = connection
        if existing_tables and "alembic_version" not in existing_tables:
            raise RuntimeError(
                "Database has existing tables but no alembic_version metadata. "
                "Refusing automatic stamp-to-head because it can skip migrations. "
                "Create/repair alembic_version manually, or migrate from a clean backup."
            )
        command.upgrade(config, "head")


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for request handlers."""

    with Session(engine) as session:
        yield session
