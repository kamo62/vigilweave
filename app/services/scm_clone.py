"""Helper to resolve authenticated clone URLs via SCM connections."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

from sqlmodel import Session

from app.core.network_security import sanitize_url
from app.core.token_encryption import decrypt_token
from app.models.scm_connection import SCMConnection
from app.services.github_app import github_app_configured
from app.services.scm_providers import get_scm_client

logger = logging.getLogger(__name__)


def resolve_clone_url(
    session: Session,
    repo_url: str,
    scan_metadata: dict[str, Any] | None,
) -> str:
    """Return an authenticated clone URL when a linked SCM credential exists."""

    if not scan_metadata:
        return repo_url

    connection_id = scan_metadata.get("scm_connection_id")
    if not connection_id:
        github_context = scan_metadata.get("github")
        if github_app_configured() and isinstance(github_context, dict):
            installation_id = github_context.get("installation_id")
            if isinstance(installation_id, int):
                token = _github_installation_token(installation_id)
                if token:
                    return _inject_basic_auth_token(repo_url, token)
        return repo_url

    conn = session.get(SCMConnection, int(connection_id))
    if conn is None or not conn.is_active:
        logger.warning(
            "SCM connection %s not found or inactive, falling back to plain URL", connection_id
        )
        return repo_url

    token = decrypt_token(conn.encrypted_token)
    client = get_scm_client(conn.provider, token, conn.base_url, conn.extra_config)
    return client.authenticated_clone_url(repo_url)


def _github_installation_token(installation_id: int) -> str | None:
    """Fetch a GitHub App installation token without exposing private helpers."""

    from app.services.github_app import _installation_access_token

    return _installation_access_token(installation_id)


def _inject_basic_auth_token(repo_url: str, token: str) -> str:
    """Inject a bearer-like token into an HTTPS clone URL."""

    if not repo_url.startswith("https://"):
        return repo_url
    encoded = quote(token, safe="")
    return repo_url.replace("https://", f"https://x-access-token:{encoded}@", 1)


def safe_clone_url_for_logs(repo_url: str) -> str:
    """Return a clone URL suitable for logs and metadata."""

    return sanitize_url(repo_url)
