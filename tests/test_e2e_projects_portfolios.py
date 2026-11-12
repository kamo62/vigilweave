from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session as DBSession

from app.core import database as database_module
from app.models.project import Project

pytestmark = pytest.mark.e2e


def test_e2e_project_and_portfolio_crud_with_rollups(
    api_client: TestClient,
    bootstrap_api_key,
    git_repo_factory,
    enterprise_license,
) -> None:
    del enterprise_license
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    repo_a = git_repo_factory(name="repo-a")
    repo_b = git_repo_factory(
        name="repo-b",
        initial_files={"service.py": "def run(user_input):\n    return eval(user_input)\n"},
        second_commit_files={"service.py": "def run(user_input):\n    return user_input\n"},
    )
    repo_a_url = f"file://{repo_a}"
    repo_b_url = f"file://{repo_b}"

    project_a = api_client.post(
        "/api/v1/projects/",
        headers=admin_headers,
        json={
            "key": "platform-api",
            "name": "Platform API",
            "description": "Primary backend",
            "tags": ["backend", "critical"],
            "default_branch": "main",
            "repos": [repo_a_url],
        },
    )
    assert project_a.status_code == 201

    project_b = api_client.post(
        "/api/v1/projects/",
        headers=admin_headers,
        json={
            "key": "mobile-app",
            "name": "Mobile App",
            "description": "Client app",
            "tags": ["mobile"],
            "default_branch": "main",
            "repos": [repo_b_url],
        },
    )
    assert project_b.status_code == 201

    created_a = api_client.post(
        "/api/v1/scans/",
        headers=admin_headers,
        json={
            "repo": repo_a_url,
            "project_key": "platform-api",
            "scan_type": "comprehensive",
            "include_quality_metrics": True,
        },
    )
    assert created_a.status_code == 201

    created_b = api_client.post(
        "/api/v1/scans/",
        headers=admin_headers,
        json={
            "repo": repo_b_url,
            "project_key": "mobile-app",
            "scan_type": "comprehensive",
            "include_quality_metrics": True,
        },
    )
    assert created_b.status_code == 201

    listed = api_client.get("/api/v1/projects/", headers=admin_headers)
    assert listed.status_code == 200
    assert {item["key"] for item in listed.json()} == {"platform-api", "mobile-app"}

    metrics = api_client.get("/api/v1/projects/platform-api", headers=admin_headers)
    assert metrics.status_code == 200
    assert metrics.json()["repo_count"] == 1
    assert metrics.json()["total_findings"] >= 1

    updated = api_client.patch(
        "/api/v1/projects/platform-api",
        headers=admin_headers,
        json={"name": "Platform API Service"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Platform API Service"

    added_repo = api_client.post(
        "/api/v1/projects/platform-api/repos",
        headers=admin_headers,
        json={"repos": [repo_b_url]},
    )
    assert added_repo.status_code == 200
    assert repo_b_url in added_repo.json()["repos"]

    removed_repo = api_client.delete(
        "/api/v1/projects/platform-api/repos",
        headers=admin_headers,
        params={"repo": repo_b_url},
    )
    assert removed_repo.status_code == 200
    assert repo_b_url not in removed_repo.json()["repos"]

    manual_portfolio = api_client.post(
        "/api/v1/portfolios/",
        headers=admin_headers,
        json={
            "key": "engineering",
            "name": "Engineering",
            "description": "Manual portfolio",
            "selection_mode": "manual",
        },
    )
    assert manual_portfolio.status_code == 201

    add_projects = api_client.post(
        "/api/v1/portfolios/engineering/projects",
        headers=admin_headers,
        json={"project_keys": ["platform-api", "mobile-app"]},
    )
    assert add_projects.status_code == 200
    assert add_projects.json()["project_count"] == 2

    detail = api_client.get("/api/v1/portfolios/engineering", headers=admin_headers)
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert len(detail_payload["projects"]) == 2
    assert detail_payload["total_findings"] >= 1

    removed_project = api_client.delete(
        "/api/v1/portfolios/engineering/projects/mobile-app",
        headers=admin_headers,
    )
    assert removed_project.status_code == 200
    assert removed_project.json()["project_count"] == 1

    tags_portfolio = api_client.post(
        "/api/v1/portfolios/",
        headers=admin_headers,
        json={
            "key": "backend-portfolio",
            "name": "Backend Portfolio",
            "selection_mode": "tags",
            "selection_value": "backend",
        },
    )
    assert tags_portfolio.status_code == 201

    regex_portfolio = api_client.post(
        "/api/v1/portfolios/",
        headers=admin_headers,
        json={
            "key": "platform-regex",
            "name": "Platform Regex",
            "selection_mode": "regex",
            "selection_value": "^platform-.*",
        },
    )
    assert regex_portfolio.status_code == 201

    all_portfolio = api_client.post(
        "/api/v1/portfolios/",
        headers=admin_headers,
        json={
            "key": "all-products",
            "name": "All Products",
            "selection_mode": "all",
        },
    )
    assert all_portfolio.status_code == 201

    non_manual_add = api_client.post(
        "/api/v1/portfolios/backend-portfolio/projects",
        headers=admin_headers,
        json={"project_keys": ["platform-api"]},
    )
    assert non_manual_add.status_code == 400

    listed_portfolios = api_client.get("/api/v1/portfolios/", headers=admin_headers)
    assert listed_portfolios.status_code == 200
    by_key = {item["key"]: item for item in listed_portfolios.json()}
    assert by_key["backend-portfolio"]["project_count"] == 1
    assert by_key["platform-regex"]["project_count"] == 1
    assert by_key["all-products"]["project_count"] == 2

    delete_all = api_client.delete("/api/v1/portfolios/all-products", headers=admin_headers)
    assert delete_all.status_code == 204

    delete_project = api_client.delete("/api/v1/projects/mobile-app", headers=admin_headers)
    assert delete_project.status_code == 204

    missing = api_client.get("/api/v1/projects/mobile-app", headers=admin_headers)
    assert missing.status_code == 404


def test_create_project_requires_non_blank_key_and_name(
    api_client: TestClient,
    bootstrap_api_key,
) -> None:
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    missing_key = api_client.post(
        "/api/v1/projects/",
        headers=admin_headers,
        json={"key": "   ", "name": "Platform API"},
    )
    assert missing_key.status_code == 422
    assert "Project key is required" in missing_key.text

    missing_name = api_client.post(
        "/api/v1/projects/",
        headers=admin_headers,
        json={"key": "platform-api", "name": "   "},
    )
    assert missing_name.status_code == 422
    assert "Project name is required" in missing_name.text


def test_delete_project_by_id_supports_legacy_blank_key_records(
    api_client: TestClient,
    bootstrap_api_key,
) -> None:
    admin_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    with DBSession(database_module.engine) as session:
        legacy_project = Project(tenant_slug="acme", key="", name="Legacy Project")
        session.add(legacy_project)
        session.commit()
        session.refresh(legacy_project)
        legacy_project_id = legacy_project.id

    response = api_client.delete(
        f"/api/v1/projects/by-id/{legacy_project_id}",
        headers=admin_headers,
    )
    assert response.status_code == 204

    with DBSession(database_module.engine) as session:
        deleted = session.get(Project, legacy_project_id)

    assert deleted is None
