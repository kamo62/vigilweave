import subprocess
from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import create_engine

from app.core import database as database_module
from app.main import app


def _configure_test_db(tmp_path: Path, monkeypatch) -> TestClient:
    db_path = tmp_path / "platform.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    database_module.engine = engine
    monkeypatch.setattr(database_module, "engine", engine)
    database_module.init_db()
    return TestClient(app)


def _make_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "sample-repo"
    repo_path.mkdir()
    (repo_path / "app.py").write_text(
        "password = 'secret'\ndef run(user_input):\n    return eval(user_input)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True)
    subprocess.run(["git", "add", "."], cwd=repo_path, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_path, check=True)
    return repo_path


def _bootstrap_key(client: TestClient, tenant_slug: str = "acme") -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/api-keys",
        json={
            "name": "integration-admin",
            "scopes": ["admin", "scan:read", "scan:write"],
        },
        headers={"X-VigilWeave-Tenant": tenant_slug},
    )
    assert response.status_code == 201
    api_key = response.json()["api_key"]
    return {
        "Authorization": f"Bearer {api_key}",
        "X-VigilWeave-Tenant": tenant_slug,
    }


def test_authenticated_scan_policy_and_waiver_flow(
    tmp_path: Path,
    monkeypatch,
    enterprise_license,
) -> None:
    del enterprise_license
    client = _configure_test_db(tmp_path, monkeypatch)
    headers = _bootstrap_key(client)
    repo_path = _make_repo(tmp_path)

    policy = client.post(
        "/api/v1/policies/",
        headers=headers,
        json={
            "name": "strict-default",
            "description": "Block critical issues",
            "is_default": True,
            "max_critical_findings": 0,
            "max_high_findings": 1,
            "min_quality_score": 50,
        },
    )
    assert policy.status_code == 201

    waiver = client.post(
        "/api/v1/policies/waivers",
        headers=headers,
        json={
            "repo_pattern": f"file://{repo_path}",
            "category": "secret",
            "reason": "Legacy secret accepted during migration",
            "created_by": "integration-admin",
        },
    )
    assert waiver.status_code == 201

    response = client.post(
        "/api/v1/scans/",
        headers=headers,
        json={
            "repo": f"file://{repo_path}",
            "scan_type": "comprehensive",
            "include_quality_metrics": True,
        },
    )
    assert response.status_code == 201
    scan = response.json()
    assert scan["tenant_slug"] == "acme"
    assert scan["suppressed_findings"] >= 1
    assert scan["scan_metadata"]["policy"]["matched"] is True

    findings = client.get(f"/api/v1/scans/{scan['id']}/findings", headers=headers)
    assert findings.status_code == 200
    categories = {item["category"] for item in findings.json()}
    assert "secret" not in categories
    assert "security" in categories

    audit = client.get("/api/v1/policies/audit", headers=headers)
    assert audit.status_code == 200
    assert audit.json()


def test_prisma_import_and_ide_analysis(tmp_path: Path, monkeypatch, enterprise_license) -> None:
    del enterprise_license
    client = _configure_test_db(tmp_path, monkeypatch)
    headers = _bootstrap_key(client)

    prisma_response = client.post(
        "/api/v1/integrations/prisma/import",
        headers=headers,
        json={
            "repo": "https://example.com/org/repo.git",
            "findings": [
                {
                    "severity": "critical",
                    "title": "Public S3 bucket",
                    "message": "Bucket is publicly accessible",
                    "category": "iac",
                    "file_path": "main.tf",
                    "line": 8,
                    "rule_id": "BC_AWS_1",
                }
            ],
        },
    )
    assert prisma_response.status_code == 201
    imported = prisma_response.json()
    assert imported["scan"]["source"] == "prisma"
    assert imported["findings_imported"] == 1

    file_content = "password = 'secret'\ndef run(user_input):\n    return eval(user_input)\n"

    ide_response = client.post(
        "/api/v1/ide/analyze",
        headers=headers,
        json={
            "scan_type": "fast",
            "persist_scan": False,
            "include_quality_metrics": True,
            "files": [
                {
                    "path": "src/example.py",
                    "content": file_content,
                }
            ],
        },
    )
    assert ide_response.status_code == 200
    ide_payload = ide_response.json()
    assert ide_payload["scan"] is None
    assert ide_payload["findings"]
    assert "Medium" in ide_payload["severities"] or "High" in ide_payload["severities"]

    capabilities = client.get("/api/v1/system/capabilities", headers=headers)
    assert capabilities.status_code == 200
    assert capabilities.json()["integrations"]["prisma_cloud"] is True
    assert "python" in capabilities.json()["languages"]


def test_ide_analyze_rejects_path_traversal(
    tmp_path: Path, monkeypatch, enterprise_license
) -> None:
    del enterprise_license
    client = _configure_test_db(tmp_path, monkeypatch)
    headers = _bootstrap_key(client)

    response = client.post(
        "/api/v1/ide/analyze",
        headers=headers,
        json={
            "scan_type": "fast",
            "persist_scan": False,
            "include_quality_metrics": False,
            "files": [
                {
                    "path": "../../outside.py",
                    "content": "print('escape')\n",
                }
            ],
        },
    )

    assert response.status_code == 422
    assert "Invalid IDE file path" in response.text
