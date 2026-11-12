from __future__ import annotations

import pytest
from sqlmodel import Session as DBSession
from sqlmodel import select

from app.core import database as database_module
from app.core.config import settings
from app.core.token_encryption import encrypt_token
from app.models import TenantGitHubInstallation
from app.models.project import Project, ProjectRepository
from app.models.scm_connection import SCMConnection, SCMProvider
from app.tasks import scan_tasks


@pytest.fixture(autouse=True)
def configure_session_secret(monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")


def test_create_project_rejects_foreign_tenant_scm_connection(
    api_client,
    bootstrap_api_key,
) -> None:
    acme_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    with DBSession(database_module.engine) as session:
        foreign_connection = SCMConnection(
            tenant_slug="beta",
            name="beta-gh",
            provider=SCMProvider.GITHUB,
            base_url="https://github.com",
            encrypted_token=encrypt_token("beta-secret-token"),
            created_by="beta-admin",
        )
        session.add(foreign_connection)
        session.commit()
        session.refresh(foreign_connection)
        foreign_id = foreign_connection.id

    response = api_client.post(
        "/api/v1/projects/",
        headers=acme_headers,
        json={
            "key": "platform-api",
            "name": "Platform API",
            "repos": ["https://github.com/acme/platform-api.git"],
            "scm_connection_id": foreign_id,
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "SCM connection not found for this tenant"


def test_add_project_repos_rejects_foreign_tenant_scm_connection(
    api_client,
    bootstrap_api_key,
) -> None:
    acme_headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    with DBSession(database_module.engine) as session:
        session.add(Project(tenant_slug="acme", key="platform-api", name="Platform API"))
        foreign_connection = SCMConnection(
            tenant_slug="beta",
            name="beta-gh",
            provider=SCMProvider.GITHUB,
            base_url="https://github.com",
            encrypted_token=encrypt_token("beta-secret-token"),
            created_by="beta-admin",
        )
        session.add(foreign_connection)
        session.commit()
        session.refresh(foreign_connection)
        foreign_id = foreign_connection.id

    response = api_client.post(
        "/api/v1/projects/platform-api/repos",
        headers=acme_headers,
        json={
            "repos": ["https://github.com/acme/platform-api.git"],
            "scm_connection_id": foreign_id,
        },
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "SCM connection not found for this tenant"


def test_add_project_repos_backfills_missing_scm_connection_id(
    api_client,
    bootstrap_api_key,
) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")
    repo_url = "https://github.com/acme/platform-api.git"

    with DBSession(database_module.engine) as session:
        project = Project(tenant_slug="acme", key="platform-api", name="Platform API")
        connection = SCMConnection(
            tenant_slug="acme",
            name="acme-gh",
            provider=SCMProvider.GITHUB,
            base_url="https://github.com",
            encrypted_token=encrypt_token("acme-secret-token"),
            created_by="acme-admin",
        )
        session.add(project)
        session.add(connection)
        session.commit()
        session.refresh(project)
        session.refresh(connection)
        session.add(ProjectRepository(project_id=project.id, repo=repo_url))
        session.commit()
        connection_id = connection.id

    response = api_client.post(
        "/api/v1/projects/platform-api/repos",
        headers=headers,
        json={"repos": [repo_url], "scm_connection_id": connection_id},
    )

    assert response.status_code == 200, response.text

    with DBSession(database_module.engine) as session:
        link = session.exec(
            select(ProjectRepository).where(ProjectRepository.repo == repo_url)
        ).one()

    assert link.scm_connection_id == connection_id


def test_create_scan_carries_github_installation_metadata_for_project_repo(
    api_client,
    bootstrap_api_key,
    monkeypatch,
) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")
    repo_url = "https://github.com/acme/private-repo.git"

    with DBSession(database_module.engine) as session:
        project = Project(tenant_slug="acme", key="acme-project", name="Acme Project")
        installation = TenantGitHubInstallation(
            tenant_slug="acme",
            installation_id=4242,
            account_login="acme-org",
            account_type="Organization",
        )
        session.add(project)
        session.add(installation)
        session.commit()
        session.refresh(project)
        session.add(
            ProjectRepository(
                project_id=project.id,
                repo=repo_url,
                github_installation_id=installation.installation_id,
            )
        )
        session.commit()

    monkeypatch.setattr(scan_tasks.run_scan, "delay", lambda scan_id: None)
    monkeypatch.setattr(settings, "celery_task_always_eager", False)

    response = api_client.post(
        "/api/v1/scans/",
        headers=headers,
        json={
            "repo": repo_url,
            "project_key": "acme-project",
            "scan_type": "fast",
            "include_quality_metrics": False,
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["project_key"] == "acme-project"
    assert payload["scan_metadata"]["scm_connection_id"] is None
    assert payload["scan_metadata"]["github"]["installation_id"] == 4242


def test_create_scan_requires_explicit_project_key_for_scm_resolution(
    api_client,
    cross_tenant_api_key,
    monkeypatch,
) -> None:
    acme_headers = cross_tenant_api_key(tenant_slug="acme", name="acme-admin")

    with DBSession(database_module.engine) as session:
        beta_connection = SCMConnection(
            tenant_slug="beta",
            name="beta-gh",
            provider=SCMProvider.GITHUB,
            base_url="https://github.com",
            encrypted_token=encrypt_token("beta-secret-token"),
            created_by="beta-admin",
        )
        acme_connection = SCMConnection(
            tenant_slug="acme",
            name="acme-gh",
            provider=SCMProvider.GITHUB,
            base_url="https://github.com",
            encrypted_token=encrypt_token("acme-secret-token"),
            created_by="acme-admin",
        )
        session.add(beta_connection)
        session.add(acme_connection)
        session.commit()
        session.refresh(beta_connection)
        session.refresh(acme_connection)
        beta_connection_id = beta_connection.id
        acme_connection_id = acme_connection.id

        beta_project = Project(tenant_slug="beta", key="beta-project", name="Beta Project")
        acme_project = Project(tenant_slug="acme", key="acme-project", name="Acme Project")
        session.add(beta_project)
        session.add(acme_project)
        session.commit()
        session.refresh(beta_project)
        session.refresh(acme_project)

        shared_repo_url = "https://github.com/shared/private-repo.git"
        session.add(
            ProjectRepository(
                project_id=beta_project.id,
                repo=shared_repo_url,
                scm_connection_id=beta_connection_id,
            )
        )
        session.add(
            ProjectRepository(
                project_id=acme_project.id,
                repo=shared_repo_url,
                scm_connection_id=acme_connection_id,
            )
        )
        session.commit()

    monkeypatch.setattr(scan_tasks.run_scan, "delay", lambda scan_id: None)
    monkeypatch.setattr(settings, "celery_task_always_eager", False)

    response = api_client.post(
        "/api/v1/scans/",
        headers=acme_headers,
        json={
            "repo": shared_repo_url,
            "scan_type": "fast",
            "include_quality_metrics": False,
        },
    )

    assert response.status_code == 201, response.text
    assert response.json()["scan_metadata"]["scm_connection_id"] is None
    assert response.json()["project_id"] is None
    assert response.json()["project_key"] is None
    assert response.json()["assignment_status"] == "unassigned"

    explicit = api_client.post(
        "/api/v1/scans/",
        headers=acme_headers,
        json={
            "repo": shared_repo_url,
            "project_key": "acme-project",
            "scan_type": "fast",
            "include_quality_metrics": False,
        },
    )

    assert explicit.status_code == 201, explicit.text
    assert explicit.json()["scan_metadata"]["scm_connection_id"] == acme_connection_id
    assert explicit.json()["project_key"] == "acme-project"
    assert explicit.json()["assignment_status"] == "assigned"


def test_create_connection_rejects_private_or_unapproved_base_urls(
    api_client,
    bootstrap_api_key,
) -> None:
    headers = bootstrap_api_key(tenant_slug="acme", name="acme-admin")

    response = api_client.post(
        "/api/v1/scm-connections/",
        headers=headers,
        json={
            "name": "private-gh",
            "provider": "github",
            "base_url": "https://localhost/api/v3",
            "token": "secret-token",
        },
    )

    assert response.status_code == 422, response.text
    assert "Invalid SCM base URL" in response.text
