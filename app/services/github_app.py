"""GitHub App webhook and check-run integration helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import quote

import httpx
import jwt
from fastapi import HTTPException
from sqlmodel import Session

from app.core.config import settings
from app.core.network_security import is_safe_repo_url
from app.models import Scan, ScanStatus, ScanType
from app.models.scm_connection import SCMRepository
from app.services.project_mapping import resolve_webhook_project_link

PULL_REQUEST_ACTIONS = {"opened", "reopened", "synchronize", "ready_for_review"}


def github_app_configured() -> bool:
    """Return whether GitHub App runtime credentials are configured."""

    return bool(settings.github_app_id and settings.github_app_private_key)


def github_app_install_url(state: str) -> str | None:
    """Return the GitHub App installation URL when the app is fully configured."""

    slug = (settings.github_app_slug or "").strip()
    if not github_app_configured() or not slug or not state:
        return None
    encoded_state = quote(state, safe="")
    return f"https://github.com/apps/{slug}/installations/new?state={encoded_state}"


def get_installation(installation_id: int) -> dict[str, Any] | None:
    """Return installation metadata for a GitHub App installation."""

    app_jwt = _app_jwt()
    if app_jwt is None:
        return None

    endpoint = f"{settings.github_api_url.rstrip('/')}/app/installations/{installation_id}"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {app_jwt}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        response = httpx.get(
            endpoint,
            headers=headers,
            timeout=settings.github_api_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else None
    except Exception:  # noqa: BLE001
        return None


def list_installation_repositories(installation_id: int) -> list[SCMRepository]:
    """List repositories available to a GitHub App installation."""

    token = _installation_access_token(installation_id)
    if token is None:
        return []

    endpoint = f"{settings.github_api_url.rstrip('/')}/installation/repositories"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        response = httpx.get(
            endpoint,
            headers=headers,
            params={"per_page": 100},
            timeout=settings.github_api_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception:  # noqa: BLE001
        return []

    repositories = payload.get("repositories") if isinstance(payload, dict) else None
    if not isinstance(repositories, list):
        return []

    return [_to_scm_repository(item) for item in repositories if isinstance(item, dict)]


def _to_scm_repository(payload: dict[str, Any]) -> SCMRepository:
    owner = payload.get("owner") or {}
    login = owner.get("login") if isinstance(owner, dict) else None
    name = str(payload.get("name") or "")
    full_name = str(payload.get("full_name") or (f"{login}/{name}" if login else name))
    clone_url = str(payload.get("clone_url") or payload.get("html_url") or "")
    return SCMRepository(
        id=str(payload.get("id") or full_name),
        name=name,
        full_name=full_name,
        clone_url=clone_url,
        default_branch=payload.get("default_branch"),
        description=payload.get("description"),
        language=payload.get("language"),
        is_private=bool(payload.get("private", False)),
        updated_at=payload.get("updated_at"),
    )


def verify_github_webhook_signature(raw_body: bytes, signature: str | None) -> bool:
    """Verify X-Hub-Signature-256 against configured webhook secret."""

    secret = settings.github_webhook_secret
    if not secret or not signature:
        return False
    expected = (
        "sha256="
        + hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature.strip())


def handle_github_event(
    session: Session,
    *,
    event: str,
    payload: dict[str, Any],
    delivery_id: str | None,
) -> dict[str, Any]:
    """Process a GitHub webhook event and queue scans when appropriate."""

    if event == "ping":
        return {
            "accepted": True,
            "event": event,
            "message": "GitHub webhook ping received",
        }

    if event != "pull_request":
        return {
            "accepted": True,
            "event": event,
            "message": "Event ignored",
        }

    action = str(payload.get("action") or "")
    if action not in PULL_REQUEST_ACTIONS:
        return {
            "accepted": True,
            "event": event,
            "action": action,
            "message": "Pull request action ignored",
        }

    pull_request = payload.get("pull_request") or {}
    repository = payload.get("repository") or {}
    installation = payload.get("installation") or {}
    repo_url = repository.get("clone_url") or repository.get("ssh_url")
    head = pull_request.get("head") or {}
    commit_sha = head.get("sha")
    branch = head.get("ref")
    owner = (repository.get("owner") or {}).get("login")
    repo_name = repository.get("name")
    installation_id = installation.get("id")
    pr_number = pull_request.get("number")

    if not repo_url or not commit_sha or not owner or not repo_name or not installation_id:
        return {
            "accepted": False,
            "event": event,
            "action": action,
            "message": "Payload is missing required repository or installation fields",
        }
    if not is_safe_repo_url(repo_url):
        return {
            "accepted": False,
            "event": event,
            "action": action,
            "message": "Unsupported repository URL scheme in webhook payload",
        }

    try:
        project_mapping = resolve_webhook_project_link(session, repo=repo_url)
    except HTTPException as exc:
        return {
            "accepted": False,
            "event": event,
            "action": action,
            "message": str(exc.detail),
        }
    if project_mapping is None:
        return {
            "accepted": False,
            "event": event,
            "action": action,
            "message": "Repository is not linked to a project",
        }
    project, project_repo = project_mapping

    github_context: dict[str, Any] = {
        "delivery_id": delivery_id,
        "installation_id": int(installation_id),
        "owner": owner,
        "repo": repo_name,
        "pr_number": pr_number,
        "head_sha": commit_sha,
        "head_ref": branch,
        "html_url": pull_request.get("html_url"),
    }

    check_run_id: int | None = None
    if github_app_configured():
        check_run_id = _create_check_run(github_context, external_id=None)
        if check_run_id is not None:
            github_context["check_run_id"] = check_run_id

    scan = Scan(
        tenant_slug=project.tenant_slug,
        project_id=project.id,
        repo=repo_url,
        branch=branch,
        commit=commit_sha,
        source="github-app",
        scan_type=_default_scan_type(),
        include_quality_metrics=True,
        scan_metadata={
            "requested_tools": [],
            "actor": "github-app",
            "scm_connection_id": project_repo.scm_connection_id,
            "project_key": project.key,
            "github": github_context,
        },
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)

    if check_run_id is not None:
        update = _update_check_run(
            github_context,
            check_run_id,
            status="in_progress",
            conclusion=None,
            output_title=settings.github_check_name,
            output_summary=f"VigilWeave scan #{scan.id} is running.",
            external_id=scan.id,
        )
        if update:
            github_context["check_run_id"] = check_run_id
            scan.scan_metadata = {
                **(scan.scan_metadata or {}),
                "github": github_context,
            }
            session.add(scan)
            session.commit()

    if settings.celery_task_always_eager:
        from app.services.scanner import execute_scan

        execute_scan(session, scan.id)
    else:
        from app.tasks.scan_tasks import run_scan

        run_scan.delay(scan.id)
    session.refresh(scan)

    return {
        "accepted": True,
        "event": event,
        "action": action,
        "message": "Pull request scan queued",
        "scan_id": scan.id,
        "check_run_id": github_context.get("check_run_id"),
    }


def complete_github_check_run(
    scan: Scan, *, error_message: str | None = None
) -> dict[str, Any] | None:
    """Complete the GitHub check run associated with a scan, when available."""

    metadata = scan.scan_metadata or {}
    github_context = metadata.get("github")
    if not isinstance(github_context, dict):
        return None
    check_run_id = github_context.get("check_run_id")
    if not isinstance(check_run_id, int):
        return None

    if error_message or scan.status == ScanStatus.FAILED:
        conclusion = "failure"
        summary = error_message or "VigilWeave scan failed."
    elif scan.quality_gate_passed is False:
        conclusion = "failure"
        summary = (
            "VigilWeave quality gate failed. "
            f"Critical: {scan.critical_findings}, High: {scan.high_findings}, "
            f"Total findings: {scan.total_findings}."
        )
    else:
        conclusion = "success"
        summary = (
            "VigilWeave scan passed. "
            f"Critical: {scan.critical_findings}, High: {scan.high_findings}, "
            f"Total findings: {scan.total_findings}."
        )

    updated = _update_check_run(
        github_context,
        check_run_id,
        status="completed",
        conclusion=conclusion,
        output_title=settings.github_check_name,
        output_summary=summary,
        external_id=scan.id,
    )
    if not updated:
        return {
            "updated": False,
            "check_run_id": check_run_id,
            "conclusion": conclusion,
        }
    return {
        "updated": True,
        "check_run_id": check_run_id,
        "conclusion": conclusion,
        "completed_at": datetime.now(UTC).isoformat(),
    }


def _default_scan_type() -> ScanType:
    raw = settings.github_default_scan_type.strip().lower()
    try:
        return ScanType(raw)
    except ValueError:
        return ScanType.FAST


def _create_check_run(context: dict[str, Any], external_id: int | None) -> int | None:
    return _update_check_run(
        context,
        check_run_id=None,
        status="queued",
        conclusion=None,
        output_title=settings.github_check_name,
        output_summary="VigilWeave accepted the pull request event.",
        external_id=external_id,
    )


def _update_check_run(
    context: dict[str, Any],
    check_run_id: int | None,
    *,
    status: str,
    conclusion: str | None,
    output_title: str,
    output_summary: str,
    external_id: int | None,
) -> int | None:
    installation_id = context.get("installation_id")
    owner = context.get("owner")
    repo = context.get("repo")
    head_sha = context.get("head_sha")
    if not isinstance(installation_id, int):
        return None
    if not isinstance(owner, str) or not isinstance(repo, str) or not isinstance(head_sha, str):
        return None

    token = _installation_access_token(installation_id)
    if token is None:
        return None

    endpoint = f"{settings.github_api_url.rstrip('/')}/repos/{owner}/{repo}/check-runs"
    details_url = (
        f"{settings.vigilweave_web_base_url.rstrip('/')}/scans/{external_id}"
        if external_id
        else None
    )
    payload: dict[str, Any] = {
        "name": settings.github_check_name,
        "head_sha": head_sha,
        "status": status,
        "output": {
            "title": output_title,
            "summary": output_summary,
        },
    }
    if details_url:
        payload["details_url"] = details_url
    if external_id is not None:
        payload["external_id"] = str(external_id)
    now_iso = datetime.now(UTC).isoformat()
    if status in {"queued", "in_progress"}:
        payload["started_at"] = now_iso
    if status == "completed":
        payload["completed_at"] = now_iso
        payload["conclusion"] = conclusion or "neutral"

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    try:
        if check_run_id is None:
            response = httpx.post(
                endpoint,
                headers=headers,
                json=payload,
                timeout=settings.github_api_timeout_seconds,
            )
        else:
            response = httpx.patch(
                f"{endpoint}/{check_run_id}",
                headers=headers,
                json=payload,
                timeout=settings.github_api_timeout_seconds,
            )
        response.raise_for_status()
        body = response.json()
        return int(body.get("id")) if body.get("id") is not None else check_run_id
    except Exception:  # noqa: BLE001
        return None


def _installation_access_token(installation_id: int) -> str | None:
    app_jwt = _app_jwt()
    if app_jwt is None:
        return None

    endpoint = (
        f"{settings.github_api_url.rstrip('/')}/app/installations/{installation_id}/access_tokens"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {app_jwt}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        response = httpx.post(
            endpoint,
            headers=headers,
            timeout=settings.github_api_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("token")
        if isinstance(token, str) and token:
            return token
    except Exception:  # noqa: BLE001
        return None
    return None


def _app_jwt() -> str | None:
    app_id = settings.github_app_id
    private_key = settings.github_app_private_key
    if not app_id or not private_key:
        return None

    key_material = private_key.strip()
    if "-----BEGIN" not in key_material:
        try:
            key_material = base64.b64decode(key_material.encode("utf-8")).decode("utf-8")
        except Exception:  # noqa: BLE001
            return None
    key_material = key_material.replace("\\n", "\n")

    now = datetime.now(UTC)
    payload = {
        "iat": int((now - timedelta(seconds=60)).timestamp()),
        "exp": int((now + timedelta(minutes=9)).timestamp()),
        "iss": app_id,
    }
    try:
        token = jwt.encode(payload, key_material, algorithm="RS256")
    except Exception:  # noqa: BLE001
        return None
    return token if isinstance(token, str) else str(token)
