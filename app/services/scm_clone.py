"""Helper to resolve authenticated clone URLs via SCM connections."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from sqlmodel import Session, select

from app.core.network_security import sanitize_url
from app.core.token_encryption import decrypt_token
from app.models import TenantGitHubInstallation
from app.models.scm_connection import SCMConnection
from app.services.github_app import github_app_configured
from app.services.scm_providers import GitHubClient, get_scm_client


def resolve_clone_url(
    session: Session,
    repo_url: str,
    scan_metadata: dict[str, Any] | None,
    *,
    tenant_slug: str,
) -> str:
    """Return an authenticated clone URL when a linked SCM credential exists."""

    if not scan_metadata:
        return repo_url

    connection_id = scan_metadata.get("scm_connection_id")
    if not connection_id:
        github_context = scan_metadata.get("github")
        if isinstance(github_context, dict) and github_context.get("installation_id") is not None:
            if not github_app_configured():
                raise ValueError("GitHub App credentials are not configured")
            installation_id = github_context.get("installation_id")
            if isinstance(installation_id, int) and not isinstance(installation_id, bool):
                installation = session.exec(
                    select(TenantGitHubInstallation).where(
                        TenantGitHubInstallation.installation_id == installation_id,
                        TenantGitHubInstallation.tenant_slug == tenant_slug,
                    )
                ).first()
                if installation is None:
                    raise ValueError("GitHub App installation is unavailable for this tenant")
                GitHubClient("").authenticated_clone_url(repo_url)
                if (
                    urlsplit(repo_url).path.split("/")[1].lower()
                    != installation.account_login.lower()
                ):
                    raise ValueError("Repository does not belong to the GitHub App account")
                token = _github_installation_token(installation_id)
                if token:
                    return GitHubClient(token).authenticated_clone_url(repo_url)
                raise ValueError("GitHub App installation token is unavailable")
            raise ValueError("Invalid GitHub App installation ID")
        return repo_url

    conn = session.get(SCMConnection, int(connection_id))
    if conn is None or not conn.is_active or conn.tenant_slug != tenant_slug:
        raise ValueError("SCM connection is unavailable for this tenant")

    # Validate the destination before decrypting any credential.
    get_scm_client(conn.provider, "", conn.base_url, conn.extra_config).authenticated_clone_url(
        repo_url
    )
    token = decrypt_token(conn.encrypted_token)
    client = get_scm_client(conn.provider, token, conn.base_url, conn.extra_config)
    return client.authenticated_clone_url(repo_url)


def _github_installation_token(installation_id: int) -> str | None:
    """Fetch a GitHub App installation token without exposing private helpers."""

    from app.services.github_app import _installation_access_token

    return _installation_access_token(installation_id)


def safe_clone_url_for_logs(repo_url: str) -> str:
    """Return a clone URL suitable for logs and metadata."""

    return sanitize_url(repo_url)
