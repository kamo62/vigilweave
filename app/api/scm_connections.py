"""SCM Connections API — manage PAT-based repository connections."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.network_security import ensure_safe_outbound_url, is_private_hostname
from app.core.rate_limiter import AUTH_ENDPOINT_RATE_LIMIT, check_rate_limit
from app.core.security import require_scope
from app.core.token_encryption import decrypt_token, encrypt_token
from app.models.project import ProjectRepository
from app.models.scm_connection import (
    SCMConnection,
    SCMConnectionCreate,
    SCMConnectionPublic,
    SCMConnectionTestResult,
    SCMConnectionUpdate,
    SCMImportReposRequest,
    SCMOrganization,
    SCMProvider,
    SCMRepository,
)
from app.services.scm_providers import get_scm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scm-connections", tags=["scm-connections"])

_PROVIDER_ALLOWED_HOSTS: dict[SCMProvider, list[str]] = {
    SCMProvider.GITHUB: ["api.github.com", "*.ghe.com", "*.github.example.com"],
    SCMProvider.GITLAB: ["gitlab.com", "*.gitlab.com", "*.gitlab.example.com"],
    SCMProvider.BITBUCKET: ["api.bitbucket.org"],
    SCMProvider.AZURE_DEVOPS: ["dev.azure.com", "*.dev.azure.com", "*.visualstudio.com"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_mask(plaintext: str) -> str:
    """Produce a masked representation of a token for display."""
    if len(plaintext) <= 8:
        return "****"
    return f"{plaintext[:4]}****{plaintext[-4:]}"


def _to_public(conn: SCMConnection) -> SCMConnectionPublic:
    return SCMConnectionPublic(
        id=conn.id,  # type: ignore[arg-type]
        tenant_slug=conn.tenant_slug,
        name=conn.name,
        provider=conn.provider,
        base_url=conn.base_url,
        token_masked=conn.token_masked or "****",
        extra_config=conn.extra_config,
        is_active=conn.is_active,
        last_tested_at=conn.last_tested_at,
        last_test_ok=conn.last_test_ok,
        created_at=conn.created_at,
        updated_at=conn.updated_at,
        created_by=conn.created_by,
    )


def _get_connection(session: Session, tenant_slug: str, connection_id: int) -> SCMConnection:
    conn = session.exec(
        select(SCMConnection).where(
            SCMConnection.tenant_slug == tenant_slug,
            SCMConnection.id == connection_id,
        )
    ).first()
    if conn is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="SCM connection not found"
        )
    return conn


def _validate_scm_base_url(provider: SCMProvider, base_url: str) -> str:
    """Validate and normalize an SCM API base URL."""

    normalized = base_url.strip().rstrip("/")
    try:
        ensure_safe_outbound_url(
            normalized,
            allowed_hosts=_PROVIDER_ALLOWED_HOSTS.get(provider),
            allow_http=False,
        )
    except ValueError as exc:
        if not settings.allow_private_scm_base_urls:
            raise HTTPException(status_code=422, detail=f"Invalid SCM base URL: {exc}") from exc
        from urllib.parse import urlsplit

        parsed = urlsplit(normalized)
        host = (parsed.hostname or "").strip().lower().rstrip(".")
        if parsed.scheme != "https":
            raise HTTPException(
                status_code=422, detail="Invalid SCM base URL: HTTPS is required"
            ) from None
        if not host or not is_private_hostname(host):
            raise HTTPException(status_code=422, detail=f"Invalid SCM base URL: {exc}") from exc
    return normalized


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.post("/", response_model=SCMConnectionPublic, status_code=status.HTTP_201_CREATED)
def create_connection(
    payload: SCMConnectionCreate,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> SCMConnectionPublic:
    """Create a new SCM connection."""
    conn = SCMConnection(
        tenant_slug=principal.tenant_slug,
        name=payload.name,
        provider=payload.provider,
        base_url=_validate_scm_base_url(payload.provider, payload.base_url),
        encrypted_token=encrypt_token(payload.token),
        token_masked=_compute_mask(payload.token),
        extra_config=payload.extra_config,
        created_by=principal.actor,
    )
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return _to_public(conn)


@router.get("/", response_model=list[SCMConnectionPublic])
def list_connections(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> list[SCMConnectionPublic]:
    """List SCM connections for the tenant."""
    conns = session.exec(
        select(SCMConnection).where(SCMConnection.tenant_slug == principal.tenant_slug)
    ).all()
    return [_to_public(c) for c in conns]


@router.get("/{connection_id}", response_model=SCMConnectionPublic)
def get_connection(
    connection_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> SCMConnectionPublic:
    """Get a single SCM connection (token masked)."""
    return _to_public(_get_connection(session, principal.tenant_slug, connection_id))


@router.patch("/{connection_id}", response_model=SCMConnectionPublic)
def update_connection(
    connection_id: int,
    payload: SCMConnectionUpdate,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> SCMConnectionPublic:
    """Update an SCM connection."""
    conn = _get_connection(session, principal.tenant_slug, connection_id)
    if payload.name is not None:
        conn.name = payload.name
    if payload.base_url is not None:
        conn.base_url = _validate_scm_base_url(conn.provider, payload.base_url)
    if payload.token is not None:
        conn.encrypted_token = encrypt_token(payload.token)
        conn.token_masked = _compute_mask(payload.token)
    if payload.extra_config is not None:
        conn.extra_config = payload.extra_config
    if payload.is_active is not None:
        conn.is_active = payload.is_active
    conn.updated_at = datetime.now(UTC)
    session.add(conn)
    session.commit()
    session.refresh(conn)
    return _to_public(conn)


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_connection(
    connection_id: int,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> None:
    """Delete an SCM connection."""
    conn = _get_connection(session, principal.tenant_slug, connection_id)
    linked_repo_count = len(
        session.exec(
            select(ProjectRepository).where(ProjectRepository.scm_connection_id == connection_id)
        ).all()
    )
    if linked_repo_count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "SCM connection is still linked to "
                f"{linked_repo_count} project repositor{'y' if linked_repo_count == 1 else 'ies'}"
            ),
        )
    session.delete(conn)
    session.commit()


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------


@router.post("/{connection_id}/test", response_model=SCMConnectionTestResult)
def test_connection(
    connection_id: int,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> SCMConnectionTestResult:
    """Test an SCM connection by calling the provider API."""
    check_rate_limit(request, AUTH_ENDPOINT_RATE_LIMIT, resource_name="SCM connection test")
    conn = _get_connection(session, principal.tenant_slug, connection_id)
    token = decrypt_token(conn.encrypted_token)
    client = get_scm_client(conn.provider, token, conn.base_url, conn.extra_config)

    ok, message, username = client.test_connection()

    conn.last_tested_at = datetime.now(UTC)
    conn.last_test_ok = ok
    conn.updated_at = datetime.now(UTC)
    session.add(conn)
    session.commit()

    return SCMConnectionTestResult(ok=ok, message=message, username=username)


@router.get("/{connection_id}/organizations", response_model=list[SCMOrganization])
def list_organizations(
    connection_id: int,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> list[SCMOrganization]:
    """List organizations/groups/workspaces from the SCM provider."""
    check_rate_limit(request, AUTH_ENDPOINT_RATE_LIMIT, resource_name="SCM organization listing")
    conn = _get_connection(session, principal.tenant_slug, connection_id)
    token = decrypt_token(conn.encrypted_token)
    client = get_scm_client(conn.provider, token, conn.base_url, conn.extra_config)
    return client.list_organizations()


@router.get("/{connection_id}/repositories", response_model=list[SCMRepository])
def list_repositories(
    connection_id: int,
    request: Request,
    org: str = "",
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> list[SCMRepository]:
    """List repositories for an organization from the SCM provider."""
    check_rate_limit(request, AUTH_ENDPOINT_RATE_LIMIT, resource_name="SCM repository listing")
    conn = _get_connection(session, principal.tenant_slug, connection_id)
    token = decrypt_token(conn.encrypted_token)
    client = get_scm_client(conn.provider, token, conn.base_url, conn.extra_config)
    return client.list_repositories(org)


@router.post("/{connection_id}/import-repos", response_model=dict)
def import_repos(
    connection_id: int,
    payload: SCMImportReposRequest,
    request: Request,
    session: Session = Depends(get_session),
    principal=Depends(require_scope("admin")),
) -> dict:
    """Import selected repositories into a project."""
    check_rate_limit(request, AUTH_ENDPOINT_RATE_LIMIT, resource_name="SCM repository import")
    conn = _get_connection(session, principal.tenant_slug, connection_id)

    from app.models.project import Project

    project = session.exec(
        select(Project).where(
            Project.tenant_slug == principal.tenant_slug,
            Project.key == payload.project_key,
        )
    ).first()
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Check which repos already exist
    existing = set(
        session.exec(
            select(ProjectRepository.repo).where(ProjectRepository.project_id == project.id)
        ).all()
    )

    added = 0
    for repo_url in payload.repos:
        if repo_url not in existing:
            session.add(
                ProjectRepository(
                    project_id=project.id,  # type: ignore[arg-type]
                    repo=repo_url,
                    scm_connection_id=conn.id,
                )
            )
            added += 1

    session.commit()
    return {"imported": added, "skipped": len(payload.repos) - added}
