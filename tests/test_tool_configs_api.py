from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import create_engine

from app.core import database as database_module
from app.main import app
from app.services import config_loader


def _configure_test_db(tmp_path: Path, monkeypatch) -> TestClient:
    db_path = tmp_path / "tool-configs.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    database_module.engine = engine
    monkeypatch.setattr(database_module, "engine", engine)
    database_module.init_db()
    return TestClient(app)


def test_tool_config_snapshot_and_patch(tmp_path: Path, monkeypatch) -> None:
    source_path = Path(__file__).resolve().parents[1] / "tools_config.yaml"
    temp_config_path = tmp_path / "tools_config.yaml"
    temp_config_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(config_loader, "CONFIG_PATH", temp_config_path)
    config_loader.clear_tool_config_cache()

    client = _configure_test_db(tmp_path, monkeypatch)
    snapshot = client.get("/api/v1/tool-configs/")
    assert snapshot.status_code == 200
    tools = {item["tool"]: item for item in snapshot.json()["tools"]}
    assert "semgrep" in tools
    assert tools["semgrep"]["enabled"] is True

    patch = client.patch(
        "/api/v1/tool-configs/tools/semgrep",
        json={
            "enabled": False,
            "languages": ["python", "go"],
        },
    )
    assert patch.status_code == 200
    patched = patch.json()
    assert patched["enabled"] is False
    assert patched["languages"] == ["go", "python"]

    after = client.get("/api/v1/tool-configs/")
    assert after.status_code == 200
    after_tools = {item["tool"]: item for item in after.json()["tools"]}
    assert after_tools["semgrep"]["enabled"] is False
    assert after_tools["semgrep"]["languages"] == ["go", "python"]

    invalid = client.patch("/api/v1/tool-configs/tools/semgrep", json={})
    assert invalid.status_code == 422
