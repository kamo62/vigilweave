import subprocess
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import create_engine

from app.core import database as database_module
from app.main import app


def _configure_test_db(tmp_path: Path, monkeypatch) -> TestClient:
    db_path = tmp_path / "observability.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    database_module.engine = engine
    monkeypatch.setattr(database_module, "engine", engine)
    database_module.init_db()
    return TestClient(app)


def _make_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "obs-repo"
    repo_path.mkdir()
    (repo_path / "app.py").write_text(
        "password = 'secret'\ndef run(user_input):\n    return eval(user_input)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "obs@example.com"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Obs User"], cwd=repo_path, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_path, check=True)
    return repo_path


def test_metrics_and_tool_telemetry_endpoints(tmp_path: Path, monkeypatch) -> None:
    client = _configure_test_db(tmp_path, monkeypatch)
    repo_path = _make_repo(tmp_path)

    created = client.post(
        "/api/v1/scans/",
        json={"repo": f"file://{repo_path}", "scan_type": "comprehensive"},
    )
    assert created.status_code == 201

    metrics = client.get("/api/v1/system/metrics")
    assert metrics.status_code == 200
    metrics_payload = metrics.json()
    assert "scan_runs_total" in metrics_payload["counters"]
    assert metrics_payload["uptime_seconds"] >= 0

    telemetry = client.get("/api/v1/system/tool-telemetry")
    assert telemetry.status_code == 200
    telemetry_payload = telemetry.json()
    assert telemetry_payload
    assert any(row["tool"] == "semgrep" for row in telemetry_payload)
