from sqlalchemy import inspect
from sqlmodel import create_engine

from app.core import database as database_module


def test_init_db_runs_alembic_upgrade(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "migrations.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    monkeypatch.setattr(database_module, "engine", engine)

    database_module.init_db()

    with engine.begin() as connection:
        inspector = inspect(connection)
        tables = set(inspector.get_table_names())
        assert "alembic_version" in tables
        assert "scans" in tables
        assert "findings" in tables
