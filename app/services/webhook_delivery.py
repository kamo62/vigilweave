"""Webhook replay protection helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models.runtime_state import WebhookDelivery


def get_recorded_delivery(
    session: Session,
    *,
    provider: str,
    delivery_id: str | None,
) -> dict[str, Any] | None:
    """Return a previously recorded webhook response, if present."""

    if not delivery_id:
        return None
    record = session.exec(
        select(WebhookDelivery).where(
            WebhookDelivery.provider == provider,
            WebhookDelivery.delivery_id == delivery_id,
        )
    ).first()
    if record is None:
        return None
    if not record.response_payload:
        return None
    return dict(record.response_payload)


def claim_delivery(
    session: Session,
    *,
    provider: str,
    delivery_id: str | None,
    tenant_slug: str | None = None,
    project_id: int | None = None,
) -> bool:
    """Claim a delivery id before processing to prevent duplicate side effects."""

    if not delivery_id:
        return True

    session.add(
        WebhookDelivery(
            provider=provider,
            delivery_id=delivery_id,
            tenant_slug=tenant_slug,
            project_id=project_id,
            response_payload={},
        )
    )
    try:
        session.commit()
        return True
    except IntegrityError:
        session.rollback()
        return False


def record_delivery(
    session: Session,
    *,
    provider: str,
    delivery_id: str | None,
    tenant_slug: str | None,
    project_id: int | None,
    response_payload: dict[str, Any],
) -> None:
    """Persist a webhook outcome for later replay detection."""

    if not delivery_id:
        return

    record = session.exec(
        select(WebhookDelivery).where(
            WebhookDelivery.provider == provider,
            WebhookDelivery.delivery_id == delivery_id,
        )
    ).first()
    if record is None:
        record = WebhookDelivery(provider=provider, delivery_id=delivery_id)

    record.tenant_slug = tenant_slug
    record.project_id = project_id
    record.response_payload = response_payload
    session.add(record)
    session.commit()


def build_payload_delivery_id(provider: str, payload: dict[str, Any]) -> str:
    """Build a stable delivery ID when a provider does not send one."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"{provider}:{digest}"
