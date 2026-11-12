import subprocess
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import create_engine

from app.core import database as database_module
from app.core.config import settings
from app.main import app


def _make_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "sample-repo"
    repo_path.mkdir()
    (repo_path / "app.py").write_text(
        "password = 'secret'\ndef run(user_input):\n    return eval(user_input)\n",
        encoding="utf-8",
    )
    (repo_path / "Dockerfile").write_text("FROM python:latest\nUSER root\n", encoding="utf-8")
    (repo_path / "main.tf").write_text(
        (
            'resource "aws_security_group" "open" {\n'
            "  ingress {\n"
            '    cidr_blocks = ["0.0.0.0/0"]\n'
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_path, check=True)
    return repo_path


def test_scan_flow(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    database_module.engine = engine
    monkeypatch.setattr(database_module, "engine", engine)
    database_module.init_db()

    client = TestClient(app)
    repo_path = _make_repo(tmp_path)

    response = client.post(
        "/api/v1/scans/",
        json={
            "repo": f"file://{repo_path}",
            "scan_type": "comprehensive",
            "include_quality_metrics": True,
        },
    )
    assert response.status_code == 201
    scan = response.json()
    assert scan["status"] == "completed"
    assert scan["scan_type"] == "comprehensive"

    findings = client.get(f"/api/v1/scans/{scan['id']}/findings")
    assert findings.status_code == 200
    payload = findings.json()
    assert payload
    severities = {item["severity"] for item in payload}
    assert "High" in severities or "Medium" in severities

    stats = client.get(f"/api/v1/scans/{scan['id']}/findings/stats")
    assert stats.status_code == 200
    assert stats.json()["total_findings"] >= 2

    detail = client.get(f"/api/v1/scans/{scan['id']}")
    assert detail.status_code == 200
    assert detail.json()["tool_executions"]

    quality = client.get(f"/api/v1/scans/{scan['id']}/quality-metrics")
    assert quality.status_code == 200
    assert quality.json()["files"]

    sarif = client.get(f"/api/v1/scans/{scan['id']}/sarif")
    assert sarif.status_code == 200
    sarif_payload = sarif.json()
    assert sarif_payload["version"] == "2.1.0"
    run = sarif_payload["runs"][0]
    assert run["taxonomies"]
    assert any(rule.get("helpUri") for rule in run["tool"]["driver"]["rules"])
    assert any(
        "tags" in rule.get("properties", {}) and rule["properties"]["tags"]
        for rule in run["tool"]["driver"]["rules"]
    )
    assert all(
        result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] != "unknown"
        for result in run["results"]
    )


def test_scan_rejects_unsupported_repo_scheme(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "scheme.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    database_module.engine = engine
    monkeypatch.setattr(database_module, "engine", engine)
    database_module.init_db()

    client = TestClient(app)
    response = client.post(
        "/api/v1/scans/",
        json={
            "repo": "ssh://git@example.com/org/repo.git",
            "scan_type": "fast",
            "include_quality_metrics": False,
        },
    )

    assert response.status_code == 422
    assert "Unsupported repository URL scheme" in response.text


def test_scan_rejects_file_repo_when_local_access_disabled(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "disabled.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    database_module.engine = engine
    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(settings, "enable_file_repo_access", False)
    database_module.init_db()

    client = TestClient(app)
    repo_path = _make_repo(tmp_path)
    response = client.post(
        "/api/v1/scans/",
        json={
            "repo": f"file://{repo_path}",
            "scan_type": "fast",
            "include_quality_metrics": False,
        },
    )

    assert response.status_code == 422
    assert "Local file:// repository access is disabled" in response.text
