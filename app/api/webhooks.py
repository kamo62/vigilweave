"""Inbound webhook endpoints."""

from __future__ import annotations

import hmac
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.rate_limiter import WEBHOOK_RATE_LIMIT, check_rate_limit
from app.models import (
    AzureWebhookResponse,
    BillingEvent,
    BillingProvider,
    GitHubWebhookResponse,
    PaddleWebhookIngestResponse,
)
from app.services.billing import process_paddle_event, verify_paddle_webhook_signature
from app.services.github_app import handle_github_event, verify_github_webhook_signature
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


@router.post(
    "/azure-devops",
    response_model=AzureWebhookResponse,
    responses={
        503: {"description": "Missing webhook secret or tenant-owned PR subscription binding"}
    },
)
async def azure_devops_webhook(
    request: Request,
    session: Session = Depends(get_session),
) -> AzureWebhookResponse:
    """Receive service hooks. PR events require a tenant-owned subscription binding."""

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
    # A deployment-wide secret does not identify a tenant or project subscription.
    if event_type in {"git.pullrequest.created", "git.pullrequest.updated"}:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Azure webhook tenant ownership is not configured",
        )
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

    response = AzureWebhookResponse(accepted=True, event=event_type, message="Event ignored")
    record_delivery(
        session,
        provider="azure-devops",
        delivery_id=delivery_id,
        tenant_slug=None,
        project_id=None,
        response_payload=response.model_dump(),
    )
    return response
