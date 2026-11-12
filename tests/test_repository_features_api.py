import subprocess
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import create_engine

from app.core import database as database_module
from app.main import app


def _configure_test_db(tmp_path: Path, monkeypatch) -> TestClient:
    db_path = tmp_path / "repository-features.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    database_module.engine = engine
    monkeypatch.setattr(database_module, "engine", engine)
    database_module.init_db()
    return TestClient(app)


def _make_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "history-repo"
    repo_path.mkdir()
    (repo_path / "app.py").write_text("password = 'secret'\n", encoding="utf-8")
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True, text=True)
    subprocess.run(
        ["git", "config", "user.email", "history@example.com"], cwd=repo_path, check=True
    )
    subprocess.run(["git", "config", "user.name", "History User"], cwd=repo_path, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo_path, check=True)

    (repo_path / "app.py").write_text(
        "password = 'secret'\ndef run(user_input):\n    return eval(user_input)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "add risky function"], cwd=repo_path, check=True)
    return repo_path


def test_repository_history_and_blame_endpoints(tmp_path: Path, monkeypatch) -> None:
    client = _configure_test_db(tmp_path, monkeypatch)
    repo_path = _make_repo(tmp_path)
    repo_url = f"file://{repo_path}"

    for _ in range(2):
        response = client.post(
            "/api/v1/scans/",
            json={
                "repo": repo_url,
                "scan_type": "comprehensive",
                "include_quality_metrics": True,
            },
        )
        assert response.status_code == 201

    history = client.get("/api/v1/repositories/history", params={"repo": repo_url, "limit": 10})
    assert history.status_code == 200
    history_payload = history.json()
    assert history_payload["total_scans"] == 2
    assert len(history_payload["points"]) == 2
    assert history_payload["points"][0]["scan_id"] < history_payload["points"][1]["scan_id"]

    blame = client.post(
        "/api/v1/repositories/blame",
        json={
            "repo": repo_url,
            "file_path": "app.py",
            "line": 1,
        },
    )
    assert blame.status_code == 200
    blame_payload = blame.json()
    assert blame_payload["author"] == "History User"
    assert blame_payload["summary"]


def test_repository_blame_rejects_unsupported_repo_scheme(tmp_path: Path, monkeypatch) -> None:
    client = _configure_test_db(tmp_path, monkeypatch)

    response = client.post(
        "/api/v1/repositories/blame",
        json={
            "repo": "ssh://git@example.com/org/repo.git",
            "file_path": "app.py",
            "line": 1,
        },
    )

    assert response.status_code == 422
    assert "Unsupported repository URL scheme" in response.text
