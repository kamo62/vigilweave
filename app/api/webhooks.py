"""Inbound webhook endpoints."""

from __future__ import annotations

import hmac
import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.network_security import is_safe_repo_url
from app.core.rate_limiter import WEBHOOK_RATE_LIMIT, check_rate_limit
from app.models import (
    AzureWebhookResponse,
    BillingEvent,
    BillingProvider,
    GitHubWebhookResponse,
    PaddleWebhookIngestResponse,
    Scan,
    ScanType,
)
from app.services.billing import process_paddle_event, verify_paddle_webhook_signature
from app.services.github_app import handle_github_event, verify_github_webhook_signature
from app.services.project_mapping import resolve_webhook_project_link
from app.services.webhook_delivery import (
    build_payload_delivery_id,
    claim_delivery,
    get_recorded_delivery,
    record_delivery,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/github", response_model=GitHubWebhookResponse)
async def github_webhook(
    request: Request,
    session: Session = Depends(get_session),
) -> GitHubWebhookResponse:
    """Receive GitHub App webhook events."""

    check_rate_limit(request, WEBHOOK_RATE_LIMIT, resource_name="webhook")

    raw_body = await request.body()
    if len(raw_body) > settings.webhook_max_request_body_bytes:
        raise HTTPException(status_code=413, detail="Webhook payload too large")
    signature = request.headers.get("X-Hub-Signature-256")
    event = request.headers.get("X-GitHub-Event", "")
    delivery_id = request.headers.get("X-GitHub-Delivery")

    if not settings.github_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GitHub webhook secret is not configured",
        )
    if not verify_github_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    recorded = get_recorded_delivery(
        session,
        provider="github",
        delivery_id=delivery_id,
    )
    if recorded is not None:
        return GitHubWebhookResponse.model_validate(recorded)

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        ) from exc

    if not claim_delivery(session, provider="github", delivery_id=delivery_id):
        recorded = get_recorded_delivery(
            session,
            provider="github",
            delivery_id=delivery_id,
        )
        if recorded is not None:
            return GitHubWebhookResponse.model_validate(recorded)
        raise HTTPException(status_code=409, detail="Webhook delivery is already being processed")

    result = handle_github_event(
        session,
        event=event,
        payload=payload,
        delivery_id=delivery_id,
    )
    record_delivery(
        session,
        provider="github",
        delivery_id=delivery_id,
        tenant_slug=None,
        project_id=None,
        response_payload=result,
    )
    if not result.get("accepted", False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("message", "Webhook event rejected"),
        )
    return GitHubWebhookResponse.model_validate(result)


@router.post("/paddle", response_model=PaddleWebhookIngestResponse)
async def paddle_webhook(
    request: Request,
    session: Session = Depends(get_session),
) -> PaddleWebhookIngestResponse:
    """Receive Paddle billing webhooks and sync tenant billing state."""

    if not settings.commercial_activation_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paddle webhooks are disabled in the Community distribution",
        )

    check_rate_limit(request, WEBHOOK_RATE_LIMIT, resource_name="webhook")

    raw_body = await request.body()
    if len(raw_body) > settings.webhook_max_request_body_bytes:
        raise HTTPException(status_code=413, detail="Webhook payload too large")
    if not settings.paddle_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Paddle webhook secret is not configured",
        )

    signature = request.headers.get("Paddle-Signature")
    if not verify_paddle_webhook_signature(raw_body, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body"
        ) from exc

    event_id = str(payload.get("event_id") or "").strip()
    event_type = str(payload.get("event_type") or "").strip()
    if not event_id or not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Paddle webhook payload is missing event_id or event_type",
        )

    existing = session.exec(
        select(BillingEvent).where(
            BillingEvent.provider == BillingProvider.PADDLE,
            BillingEvent.provider_event_id == event_id,
        )
    ).first()
    if existing is not None:
        return PaddleWebhookIngestResponse.model_validate(existing.response_payload)

    try:
        return process_paddle_event(session, payload)
    except IntegrityError:
        session.rollback()
        existing = session.exec(
            select(BillingEvent).where(
                BillingEvent.provider == BillingProvider.PADDLE,
                BillingEvent.provider_event_id == event_id,
            )
        ).first()
        if existing is not None:
            return PaddleWebhookIngestResponse.model_validate(existing.response_payload)
        raise


@router.post("/azure-devops", response_model=AzureWebhookResponse)
async def azure_devops_webhook(
    request: Request,
    session: Session = Depends(get_session),
) -> AzureWebhookResponse:
    """Receive Azure DevOps service-hook events for pull requests."""

    check_rate_limit(request, WEBHOOK_RATE_LIMIT, resource_name="webhook")

    raw_body = await request.body()
    if len(raw_body) > settings.webhook_max_request_body_bytes:
        raise HTTPException(status_code=413, detail="Webhook payload too large")
    if not settings.azure_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure webhook endpoint is disabled — AZURE_WEBHOOK_SECRET is not configured",
        )
    provided = request.headers.get("X-VigilWeave-Webhook-Secret") or request.headers.get(
        "X-CodeGuard-Webhook-Secret"
    )
    if not hmac.compare_digest(provided or "", settings.azure_webhook_secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid secret")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        ) from exc

    event_type = str(payload.get("eventType") or "")
    delivery_id = request.headers.get("X-VSS-NotificationId") or build_payload_delivery_id(
        "azure-devops", payload
    )

    recorded = get_recorded_delivery(
        session,
        provider="azure-devops",
        delivery_id=delivery_id,
    )
    if recorded is not None:
        return AzureWebhookResponse.model_validate(recorded)
    if not claim_delivery(session, provider="azure-devops", delivery_id=delivery_id):
        recorded = get_recorded_delivery(
            session,
            provider="azure-devops",
            delivery_id=delivery_id,
        )
        if recorded is not None:
            return AzureWebhookResponse.model_validate(recorded)
        raise HTTPException(status_code=409, detail="Webhook delivery is already being processed")

    if event_type not in {"git.pullrequest.created", "git.pullrequest.updated"}:
        response = AzureWebhookResponse(
            accepted=True,
            event=event_type,
            message="Event ignored",
        )
        record_delivery(
            session,
            provider="azure-devops",
            delivery_id=delivery_id,
            tenant_slug=None,
            project_id=None,
            response_payload=response.model_dump(),
        )
        return response

    resource = payload.get("resource") or {}
    repository = resource.get("repository") or {}
    repo_url = repository.get("remoteUrl") or repository.get("url")
    source_ref = resource.get("sourceRefName") or resource.get("targetRefName")
    branch = _normalize_branch(source_ref)
    commit = (
        (resource.get("lastMergeSourceCommit") or {}).get("commitId")
        or (resource.get("sourceCommit") or {}).get("commitId")
        or (resource.get("lastMergeCommit") or {}).get("commitId")
    )
    if not isinstance(repo_url, str) or not repo_url:
        response = AzureWebhookResponse(
            accepted=False,
            event=event_type,
            message="Missing repository URL in event payload",
        )
        record_delivery(
            session,
            provider="azure-devops",
            delivery_id=delivery_id,
            tenant_slug=None,
            project_id=None,
            response_payload=response.model_dump(),
        )
        return response
    if not is_safe_repo_url(repo_url):
        response = AzureWebhookResponse(
            accepted=False,
            event=event_type,
            message="Unsupported repository URL scheme in webhook payload",
        )
        record_delivery(
            session,
            provider="azure-devops",
            delivery_id=delivery_id,
            tenant_slug=None,
            project_id=None,
            response_payload=response.model_dump(),
        )
        return response

    try:
        project_mapping = resolve_webhook_project_link(session, repo=repo_url)
    except HTTPException as exc:
        response = AzureWebhookResponse(
            accepted=False,
            event=event_type,
            message=str(exc.detail),
        )
        record_delivery(
            session,
            provider="azure-devops",
            delivery_id=delivery_id,
            tenant_slug=None,
            project_id=None,
            response_payload=response.model_dump(),
        )
        return response

    if project_mapping is None:
        response = AzureWebhookResponse(
            accepted=False,
            event=event_type,
            message="Repository is not linked to a project",
        )
        record_delivery(
            session,
            provider="azure-devops",
            delivery_id=delivery_id,
            tenant_slug=None,
            project_id=None,
            response_payload=response.model_dump(),
        )
        return response

    project, project_repo = project_mapping

    scan = Scan(
        tenant_slug=project.tenant_slug,
        project_id=project.id,
        repo=repo_url,
        branch=branch,
        commit=commit if isinstance(commit, str) else None,
        source="azure-service-hook",
        scan_type=_azure_default_scan_type(),
        include_quality_metrics=True,
        scan_metadata={
            "actor": "azure-service-hook",
            "requested_tools": [],
            "scm_connection_id": project_repo.scm_connection_id,
            "project_key": project.key,
            "azure": {
                "event_type": event_type,
                "project_id": (resource.get("repository") or {}).get("project", {}).get("id"),
                "pull_request_id": resource.get("pullRequestId"),
            },
        },
    )
    session.add(scan)
    session.commit()
    session.refresh(scan)

    if settings.celery_task_always_eager:
        from app.services.scanner import execute_scan

        execute_scan(session, scan.id)
    else:
        from app.tasks.scan_tasks import run_scan

        run_scan.delay(scan.id)

    response = AzureWebhookResponse(
        accepted=True,
        event=event_type,
        message="Pull request scan queued",
        scan_id=scan.id,
    )
    record_delivery(
        session,
        provider="azure-devops",
        delivery_id=delivery_id,
        tenant_slug=project.tenant_slug,
        project_id=project.id,
        response_payload=response.model_dump(),
    )
    return response


def _normalize_branch(ref: Any) -> str | None:
    if not isinstance(ref, str) or not ref:
        return None
    prefix = "refs/heads/"
    if ref.startswith(prefix):
        return ref[len(prefix) :]
    return ref


def _azure_default_scan_type() -> ScanType:
    value = settings.azure_default_scan_type.strip().lower()
    try:
        return ScanType(value)
    except ValueError:
        return ScanType.FAST
