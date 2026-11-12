"""Azure Marketplace onboarding helpers for automatic project subscription."""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import settings
from app.core.network_security import ensure_safe_outbound_url
from app.models import AzureMarketplaceOnboardRequest, AzureMarketplaceOnboardResponse


def onboard_azure_project(
    payload: AzureMarketplaceOnboardRequest,
) -> AzureMarketplaceOnboardResponse:
    """Create Azure DevOps service hook subscriptions for a project."""

    _validate_azure_onboarding_urls(payload)

    project_id = _resolve_project_id(payload)
    subscriptions: list[dict[str, Any]] = []
    for event in payload.events:
        created = _create_subscription(payload, project_id=project_id, event_type=event)
        subscriptions.append(
            {
                "event": event,
                "id": created.get("id"),
                "status": created.get("status"),
                "created_by": created.get("createdBy"),
            }
        )

    return AzureMarketplaceOnboardResponse(
        project=payload.project,
        subscriptions_created=len(subscriptions),
        subscriptions=subscriptions,
    )


def _resolve_project_id(payload: AzureMarketplaceOnboardRequest) -> str:
    url = (
        f"{payload.organization_url.rstrip('/')}"
        f"/_apis/projects/{payload.project}?api-version=7.1-preview.4"
    )
    response = httpx.get(
        url,
        headers=_auth_headers(payload),
        timeout=settings.azure_api_timeout_seconds,
    )
    response.raise_for_status()
    body = response.json()
    project_id = body.get("id")
    if not isinstance(project_id, str) or not project_id:
        raise ValueError("Unable to resolve Azure DevOps project ID")
    return project_id


def _create_subscription(
    payload: AzureMarketplaceOnboardRequest, *, project_id: str, event_type: str
) -> dict[str, Any]:
    url = f"{payload.organization_url.rstrip('/')}/_apis/hooks/subscriptions?api-version=7.1"

    publisher_inputs: dict[str, str] = {"projectId": project_id}
    if payload.repository:
        publisher_inputs["repository"] = payload.repository
    if payload.branch:
        publisher_inputs["branch"] = payload.branch

    consumer_inputs: dict[str, str] = {
        "url": payload.webhook_url,
        "resourceDetailsToSend": "all",
        "messagesToSend": "detailed" if payload.detailed_messages_to_send else "minimal",
    }
    if payload.secret:
        consumer_inputs["httpHeaders"] = json.dumps({"X-VigilWeave-Webhook-Secret": payload.secret})

    body = {
        "publisherId": "tfs",
        "eventType": event_type,
        "resourceVersion": "1.0",
        "consumerId": "webHooks",
        "consumerActionId": "httpRequest",
        "publisherInputs": publisher_inputs,
        "consumerInputs": consumer_inputs,
    }
    response = httpx.post(
        url,
        headers=_auth_headers(payload),
        json=body,
        timeout=settings.azure_api_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _auth_headers(payload: AzureMarketplaceOnboardRequest) -> dict[str, str]:
    auth_scheme = payload.auth_scheme.strip().lower()
    if auth_scheme == "basic":
        encoded = base64.b64encode(f":{payload.access_token}".encode("utf-8")).decode("ascii")
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
        }
    return {
        "Authorization": f"Bearer {payload.access_token}",
        "Content-Type": "application/json",
    }


def _validate_azure_onboarding_urls(payload: AzureMarketplaceOnboardRequest) -> None:
    ensure_safe_outbound_url(
        payload.organization_url,
        allow_http=settings.allow_http_outbound,
    )
    ensure_safe_outbound_url(
        payload.webhook_url,
        allow_http=settings.allow_http_outbound,
    )

    org_host = (urlsplit(payload.organization_url).hostname or "").lower()
    if org_host not in {"dev.azure.com", "visualstudio.com"} and not org_host.endswith(
        ".visualstudio.com"
    ):
        raise ValueError("organization_url must point to Azure DevOps")
