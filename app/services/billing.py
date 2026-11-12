"""Paddle billing helpers and local subscription sync."""

from __future__ import annotations

import hashlib
import hmac
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlmodel import Session, select

from app.core.config import settings
from app.core.licensing import clear_license_cache
from app.core.token_encryption import encrypt_token
from app.models import (
    BillingCustomer,
    BillingEvent,
    BillingPortalSessionPublic,
    BillingProvider,
    BillingSubscription,
    PaddleBillingPublicConfig,
    PaddleWebhookIngestResponse,
    SaaSTenantLicense,
    SaaSTenantTier,
    Tenant,
    TenantBillingStatus,
    TenantDeploymentMode,
)
from app.services.tenants import upsert_tenant


def _public_api_url(path: str) -> str:
    base_url = settings.vigilweave_api_base_url.rstrip("/")
    return f"{base_url}{settings.api_v1_prefix}{path}"


def paddle_public_config() -> PaddleBillingPublicConfig:
    """Return public Paddle.js configuration for the frontend."""

    if not settings.commercial_activation_enabled():
        default_success_url = f"{settings.vigilweave_web_base_url.rstrip('/')}/pricing"
        return PaddleBillingPublicConfig(
            enabled=False,
            environment=settings.paddle_environment,
            client_token=None,
            checkout_ready=False,
            pro_price_id=None,
            enterprise_price_id=None,
            default_success_url=default_success_url,
            webhook_url=_public_api_url("/webhooks/paddle"),
        )

    checkout_ready = bool(settings.paddle_client_token and settings.paddle_price_id_pro)
    default_success_url = f"{settings.vigilweave_web_base_url.rstrip('/')}/pricing?checkout=success"
    return PaddleBillingPublicConfig(
        enabled=bool(
            settings.paddle_client_token
            or settings.paddle_api_key
            or settings.paddle_webhook_secret
        ),
        environment=settings.paddle_environment,
        client_token=settings.paddle_client_token,
        checkout_ready=checkout_ready,
        pro_price_id=settings.paddle_price_id_pro,
        enterprise_price_id=settings.paddle_price_id_enterprise,
        default_success_url=default_success_url,
        webhook_url=_public_api_url("/webhooks/paddle"),
    )


def paddle_customer_portal_configured() -> bool:
    """Return whether Paddle management API calls can be made."""

    return settings.commercial_activation_enabled() and bool(settings.paddle_api_key)


def _paddle_api_headers() -> dict[str, str]:
    if not settings.paddle_api_key:
        raise RuntimeError("PADDLE_API_KEY is not configured")
    return {
        "Authorization": f"Bearer {settings.paddle_api_key}",
        "Content-Type": "application/json",
    }


def _paddle_api_post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(
        f"https://api.paddle.com{path}",
        json=payload,
        headers=_paddle_api_headers(),
        timeout=settings.external_api_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def create_customer_portal_session(
    session: Session,
    *,
    tenant_slug: str,
) -> BillingPortalSessionPublic:
    """Create an authenticated Paddle customer portal session for a tenant."""

    if not paddle_customer_portal_configured():
        raise RuntimeError("PADDLE_API_KEY is not configured")

    tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if tenant is None or not tenant.paddle_customer_id:
        raise LookupError("No Paddle customer is linked to this tenant")

    subscription_ids: list[str] = []
    if tenant.paddle_subscription_id:
        subscription_ids.append(tenant.paddle_subscription_id)

    payload: dict[str, Any] = {}
    if subscription_ids:
        payload["subscription_ids"] = subscription_ids

    body = _paddle_api_post(
        f"/customers/{tenant.paddle_customer_id}/portal-sessions",
        payload,
    )
    data = _mapping(body.get("data"))
    urls = _mapping(data.get("urls"))
    general = _mapping(urls.get("general"))

    return BillingPortalSessionPublic(
        customer_id=str(data.get("customer_id") or tenant.paddle_customer_id),
        session_id=str(data.get("id") or ""),
        overview_url=general.get("overview") if isinstance(general.get("overview"), str) else None,
        subscription_urls=[item for item in urls.get("subscriptions", []) if isinstance(item, dict)]
        if isinstance(urls.get("subscriptions"), list)
        else [],
        created_at=_parse_datetime(data.get("created_at")),
    )


def verify_paddle_webhook_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Verify Paddle-Signature using the configured endpoint secret."""

    secret = settings.paddle_webhook_secret
    if not secret or not signature_header:
        return False

    timestamp: str | None = None
    signatures: list[str] = []
    for part in signature_header.split(";"):
        key, separator, value = part.strip().partition("=")
        if not separator:
            continue
        if key == "ts":
            timestamp = value
        elif key == "h1" and value:
            signatures.append(value)

    if not timestamp or not signatures:
        return False

    try:
        timestamp_int = int(timestamp)
    except ValueError:
        return False

    tolerance = max(settings.paddle_webhook_tolerance_seconds, 0)
    if tolerance and abs(int(time.time()) - timestamp_int) > tolerance:
        return False

    signed_payload = timestamp.encode("utf-8") + b":" + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, candidate) for candidate in signatures)


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalized_slug(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    slug = value.strip()
    return slug or None


def _normalized_tier(value: Any) -> SaaSTenantTier | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if candidate not in {tier.value for tier in SaaSTenantTier}:
        return None
    return SaaSTenantTier(candidate)


def _normalized_deployment_mode(value: Any) -> TenantDeploymentMode | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if candidate == TenantDeploymentMode.SELF_HOSTED.value:
        return TenantDeploymentMode.SELF_HOSTED
    if candidate == TenantDeploymentMode.SAAS.value:
        return TenantDeploymentMode.SAAS
    return None


def _normalized_billing_status(value: Any) -> TenantBillingStatus | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if candidate in {status.value for status in TenantBillingStatus}:
        return TenantBillingStatus(candidate)
    if candidate in {"paid", "completed"}:
        return TenantBillingStatus.ACTIVE
    return None


def _price_id_from_items(items: Any) -> str | None:
    if not isinstance(items, list):
        return None
    for item in items:
        item_map = _mapping(item)
        direct = item_map.get("price_id")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        price = _mapping(item_map.get("price"))
        nested = price.get("id")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
    return None


def _tier_from_price_id(price_id: str | None) -> SaaSTenantTier | None:
    if not price_id:
        return None

    pro_price_ids = {
        candidate
        for candidate in (
            settings.paddle_price_id_pro,
            settings.paddle_price_id_self_hosted_pro,
        )
        if candidate
    }
    if price_id in pro_price_ids:
        return SaaSTenantTier.PRO

    enterprise_price_ids = {
        candidate
        for candidate in (
            settings.paddle_price_id_enterprise,
            settings.paddle_price_id_self_hosted_enterprise,
        )
        if candidate
    }
    if price_id in enterprise_price_ids:
        return SaaSTenantTier.ENTERPRISE
    return None


def _resolve_tenant_slug(
    session: Session, data: dict[str, Any], custom_data: dict[str, Any]
) -> str | None:
    tenant_slug = _normalized_slug(custom_data.get("tenant_slug"))
    if tenant_slug:
        return tenant_slug

    subscription_id = (
        data.get("id")
        if str(data.get("id", "")).startswith("sub_")
        else data.get("subscription_id")
    )
    if isinstance(subscription_id, str) and subscription_id:
        existing_subscription = session.exec(
            select(BillingSubscription).where(
                BillingSubscription.provider == BillingProvider.PADDLE,
                BillingSubscription.provider_subscription_id == subscription_id,
            )
        ).first()
        if existing_subscription and existing_subscription.tenant_slug:
            return existing_subscription.tenant_slug

    customer_id = data.get("customer_id")
    if isinstance(customer_id, str) and customer_id:
        existing_customer = session.exec(
            select(BillingCustomer).where(
                BillingCustomer.provider == BillingProvider.PADDLE,
                BillingCustomer.provider_customer_id == customer_id,
            )
        ).first()
        if existing_customer and existing_customer.tenant_slug:
            return existing_customer.tenant_slug

    return None


def _resolve_plan_tier(
    session: Session,
    data: dict[str, Any],
    custom_data: dict[str, Any],
    subscription_id: str | None,
) -> SaaSTenantTier | None:
    tier = _normalized_tier(
        custom_data.get("desired_tier") or custom_data.get("tier") or custom_data.get("plan")
    )
    if tier is not None:
        return tier

    tier = _tier_from_price_id(_price_id_from_items(data.get("items")))
    if tier is not None:
        return tier

    if subscription_id:
        existing_subscription = session.exec(
            select(BillingSubscription).where(
                BillingSubscription.provider == BillingProvider.PADDLE,
                BillingSubscription.provider_subscription_id == subscription_id,
            )
        ).first()
        if existing_subscription and existing_subscription.plan_tier is not None:
            return existing_subscription.plan_tier

    return None


def _resolve_deployment_mode(
    session: Session,
    *,
    tenant_slug: str | None,
    custom_data: dict[str, Any],
) -> TenantDeploymentMode:
    deployment_mode = _normalized_deployment_mode(custom_data.get("deployment_mode"))
    if deployment_mode is not None:
        return deployment_mode

    if tenant_slug:
        tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
        if tenant is not None:
            return tenant.deployment_mode

    return TenantDeploymentMode.SAAS


def _resolve_license_type(
    custom_data: dict[str, Any], plan_tier: SaaSTenantTier | None
) -> str | None:
    requested = str(custom_data.get("license_type") or "").strip().lower()
    if requested in {"pro", "enterprise_standard", "enterprise_offline"}:
        return requested
    if plan_tier == SaaSTenantTier.PRO:
        return "pro"
    if plan_tier == SaaSTenantTier.ENTERPRISE:
        return "enterprise_standard"
    return None


def _upsert_customer(
    session: Session,
    provider_customer_id: str,
    *,
    tenant_slug: str | None,
    email: str | None,
    name: str | None,
    status: str | None,
    custom_data: dict[str, Any],
) -> BillingCustomer:
    now = datetime.now(UTC)
    customer = session.exec(
        select(BillingCustomer).where(
            BillingCustomer.provider == BillingProvider.PADDLE,
            BillingCustomer.provider_customer_id == provider_customer_id,
        )
    ).first()

    if customer is None:
        customer = BillingCustomer(
            provider=BillingProvider.PADDLE,
            provider_customer_id=provider_customer_id,
            tenant_slug=tenant_slug,
            email=email,
            name=name,
            status=status,
            custom_data=custom_data,
            created_at=now,
            updated_at=now,
        )
    else:
        customer.tenant_slug = tenant_slug or customer.tenant_slug
        customer.email = email or customer.email
        customer.name = name or customer.name
        customer.status = status or customer.status
        customer.custom_data = custom_data or customer.custom_data
        customer.updated_at = now

    session.add(customer)
    return customer


def _upsert_subscription(
    session: Session,
    provider_subscription_id: str,
    *,
    provider_customer_id: str | None,
    tenant_slug: str | None,
    plan_tier: SaaSTenantTier | None,
    status: str | None,
    collection_mode: str | None,
    currency_code: str | None,
    price_id: str | None,
    custom_data: dict[str, Any],
    started_at: datetime | None,
    first_billed_at: datetime | None,
    next_billed_at: datetime | None,
    canceled_at: datetime | None,
) -> BillingSubscription:
    now = datetime.now(UTC)
    subscription = session.exec(
        select(BillingSubscription).where(
            BillingSubscription.provider == BillingProvider.PADDLE,
            BillingSubscription.provider_subscription_id == provider_subscription_id,
        )
    ).first()

    if subscription is None:
        subscription = BillingSubscription(
            provider=BillingProvider.PADDLE,
            provider_subscription_id=provider_subscription_id,
            provider_customer_id=provider_customer_id,
            tenant_slug=tenant_slug,
            plan_tier=plan_tier,
            status=status,
            collection_mode=collection_mode,
            currency_code=currency_code,
            price_id=price_id,
            custom_data=custom_data,
            started_at=started_at,
            first_billed_at=first_billed_at,
            next_billed_at=next_billed_at,
            canceled_at=canceled_at,
            created_at=now,
            updated_at=now,
        )
    else:
        subscription.provider_customer_id = (
            provider_customer_id or subscription.provider_customer_id
        )
        subscription.tenant_slug = tenant_slug or subscription.tenant_slug
        subscription.plan_tier = plan_tier or subscription.plan_tier
        subscription.status = status or subscription.status
        subscription.collection_mode = collection_mode or subscription.collection_mode
        subscription.currency_code = currency_code or subscription.currency_code
        subscription.price_id = price_id or subscription.price_id
        subscription.custom_data = custom_data or subscription.custom_data
        subscription.started_at = started_at or subscription.started_at
        subscription.first_billed_at = first_billed_at or subscription.first_billed_at
        subscription.next_billed_at = next_billed_at or subscription.next_billed_at
        subscription.canceled_at = canceled_at or subscription.canceled_at
        subscription.updated_at = now

    session.add(subscription)
    return subscription


def _effective_license_tier(
    status: str | None, purchased_tier: SaaSTenantTier | None
) -> SaaSTenantTier | None:
    if purchased_tier is None:
        return None
    normalized_status = (status or "").strip().lower()
    if normalized_status in {"", "active", "trialing", "paused", "paid", "completed"}:
        return purchased_tier
    if normalized_status in {"canceled", "past_due"}:
        return SaaSTenantTier.COMMUNITY
    return None


def _sync_tenant_license(
    session: Session,
    *,
    tenant_slug: str | None,
    purchased_tier: SaaSTenantTier | None,
    status: str | None,
    event_type: str,
) -> None:
    if not tenant_slug or not settings.saas_enabled:
        return

    effective_tier = _effective_license_tier(status, purchased_tier)
    if effective_tier is None:
        return

    now = datetime.now(UTC)
    record = session.exec(
        select(SaaSTenantLicense).where(SaaSTenantLicense.tenant_slug == tenant_slug)
    ).first()
    note = f"Paddle synced from {event_type} ({(status or 'unknown').lower()})"
    if record is None:
        record = SaaSTenantLicense(
            tenant_slug=tenant_slug,
            tier=effective_tier,
            assigned_by="paddle:webhook",
            note=note,
            created_at=now,
            updated_at=now,
        )
    else:
        record.tier = effective_tier
        record.assigned_by = "paddle:webhook"
        record.note = note
        record.updated_at = now

    session.add(record)


def _license_server_base_url() -> str | None:
    if settings.license_server_api_base_url:
        return settings.license_server_api_base_url.rstrip("/")
    verify_url = settings.license_server_url.strip()
    if verify_url.endswith("/v1/verify"):
        return verify_url.removesuffix("/v1/verify")
    return None


def _license_server_fulfillment_available() -> bool:
    return bool(_license_server_base_url() and settings.license_server_shared_secret)


def _call_license_server_fulfillment(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    base_url = _license_server_base_url()
    if not base_url or not settings.license_server_shared_secret:
        raise RuntimeError("License server fulfillment is not configured")

    response = httpx.post(
        f"{base_url}{path}",
        json=payload,
        headers={
            "Authorization": f"Bearer {settings.license_server_shared_secret}",
            "Content-Type": "application/json",
        },
        timeout=settings.external_api_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _sync_self_hosted_fulfillment(
    session: Session,
    *,
    tenant_slug: str | None,
    tenant_name: str,
    billing_email: str | None,
    license_type: str | None,
    billing_status: TenantBillingStatus | None,
) -> tuple[int | None, str | None, str | None, str | None, datetime | None]:
    if (
        not tenant_slug
        or not license_type
        or billing_status is None
        or not _license_server_fulfillment_available()
    ):
        return None, None, None, None, None

    tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if tenant is None:
        return None, None, None, None, None

    if billing_status in {
        TenantBillingStatus.ACTIVE,
        TenantBillingStatus.TRIALING,
        TenantBillingStatus.PAUSED,
    }:
        if tenant.self_hosted_license_id and tenant.self_hosted_license_status == "active":
            return (
                tenant.self_hosted_license_id,
                tenant.self_hosted_license_key_prefix,
                tenant.encrypted_self_hosted_license_key,
                tenant.self_hosted_license_status,
                tenant.self_hosted_last_fulfilled_at,
            )

        if tenant.self_hosted_license_id and tenant.self_hosted_license_status == "revoked":
            reactivated = _call_license_server_fulfillment(
                f"/v1/fulfillment/licenses/{tenant.self_hosted_license_id}/reactivate",
                {},
            )
            record = _mapping(reactivated.get("record"))
            return (
                int(record.get("id") or tenant.self_hosted_license_id),
                str(record.get("key_prefix") or tenant.self_hosted_license_key_prefix or ""),
                tenant.encrypted_self_hosted_license_key,
                str(record.get("status") or "active"),
                datetime.now(UTC),
            )

        issued = _call_license_server_fulfillment(
            "/v1/fulfillment/issue",
            {
                "license_type": license_type,
                "organization": tenant_name,
                "customer_metadata": {
                    "tenant_slug": tenant_slug,
                    "billing_email": billing_email,
                    "source": "paddle",
                },
            },
        )
        record = _mapping(issued.get("record"))
        raw_license_key = str(issued.get("license_key") or "").strip()
        encrypted = encrypt_token(raw_license_key) if raw_license_key else None
        return (
            int(record.get("id") or 0) or None,
            str(record.get("key_prefix") or "") or None,
            encrypted,
            str(record.get("status") or "active"),
            datetime.now(UTC),
        )

    if (
        billing_status in {TenantBillingStatus.CANCELED, TenantBillingStatus.PAST_DUE}
        and tenant.self_hosted_license_id
    ):
        revoked = _call_license_server_fulfillment(
            f"/v1/fulfillment/licenses/{tenant.self_hosted_license_id}/revoke",
            {"reason": f"Billing status changed to {billing_status.value}"},
        )
        record = _mapping(revoked.get("record"))
        return (
            int(record.get("id") or tenant.self_hosted_license_id),
            str(record.get("key_prefix") or tenant.self_hosted_license_key_prefix or ""),
            tenant.encrypted_self_hosted_license_key,
            str(record.get("status") or billing_status.value),
            datetime.now(UTC),
        )

    return (
        tenant.self_hosted_license_id,
        tenant.self_hosted_license_key_prefix,
        tenant.encrypted_self_hosted_license_key,
        tenant.self_hosted_license_status,
        tenant.self_hosted_last_fulfilled_at,
    )


def process_paddle_event(session: Session, payload: dict[str, Any]) -> PaddleWebhookIngestResponse:
    """Persist a Paddle event and sync local billing state."""

    event_id = str(payload.get("event_id") or "").strip()
    event_type = str(payload.get("event_type") or "").strip()
    occurred_at = _parse_datetime(payload.get("occurred_at"))
    data = _mapping(payload.get("data"))
    custom_data = _mapping(data.get("custom_data"))

    tenant_slug = _resolve_tenant_slug(session, data, custom_data)
    customer_record: BillingCustomer | None = None
    provider_customer_id = (
        data.get("customer_id") if isinstance(data.get("customer_id"), str) else None
    )

    if (
        event_type.startswith("customer.")
        and isinstance(data.get("id"), str)
        and str(data.get("id")).startswith("ctm_")
    ):
        provider_customer_id = str(data["id"])

    if provider_customer_id:
        customer_record = _upsert_customer(
            session,
            provider_customer_id,
            tenant_slug=tenant_slug,
            email=data.get("email") if isinstance(data.get("email"), str) else None,
            name=data.get("name") if isinstance(data.get("name"), str) else None,
            status=data.get("status") if isinstance(data.get("status"), str) else None,
            custom_data=custom_data,
        )

    subscription_id: str | None = None
    if event_type.startswith("subscription.") and isinstance(data.get("id"), str):
        subscription_id = str(data["id"])
    elif isinstance(data.get("subscription_id"), str):
        subscription_id = str(data["subscription_id"])

    plan_tier = _resolve_plan_tier(session, data, custom_data, subscription_id)
    status_value = data.get("status") if isinstance(data.get("status"), str) else None
    price_id = _price_id_from_items(data.get("items"))
    deployment_mode = _resolve_deployment_mode(
        session,
        tenant_slug=tenant_slug,
        custom_data=custom_data,
    )
    billing_status = _normalized_billing_status(
        status_value or ("completed" if event_type.startswith("transaction.") else None)
    )
    tenant_name = (
        _normalized_slug(custom_data.get("tenant_name"))
        or (customer_record.name if customer_record and customer_record.name else None)
        or tenant_slug
        or "Unnamed Tenant"
    )
    billing_email = (
        (customer_record.email if customer_record and customer_record.email else None)
        or (
            _normalized_slug(custom_data.get("billing_email"))
            if custom_data.get("billing_email")
            else None
        )
        or (data.get("email") if isinstance(data.get("email"), str) else None)
    )

    if subscription_id:
        _upsert_subscription(
            session,
            subscription_id,
            provider_customer_id=provider_customer_id,
            tenant_slug=tenant_slug,
            plan_tier=plan_tier,
            status=status_value,
            collection_mode=data.get("collection_mode")
            if isinstance(data.get("collection_mode"), str)
            else None,
            currency_code=data.get("currency_code")
            if isinstance(data.get("currency_code"), str)
            else None,
            price_id=price_id,
            custom_data=custom_data,
            started_at=_parse_datetime(data.get("started_at")),
            first_billed_at=_parse_datetime(data.get("first_billed_at")),
            next_billed_at=_parse_datetime(data.get("next_billed_at")),
            canceled_at=_parse_datetime(data.get("canceled_at")),
        )

    if tenant_slug:
        upsert_tenant(
            session,
            slug=tenant_slug,
            display_name=tenant_name,
            billing_email=billing_email,
            deployment_mode=deployment_mode,
            plan_tier=plan_tier,
            billing_status=billing_status,
            paddle_customer_id=provider_customer_id,
            paddle_subscription_id=subscription_id,
        )

        fulfillment_license_id = None
        fulfillment_key_prefix = None
        fulfillment_encrypted_key = None
        fulfillment_status = None
        fulfillment_time = None

        if deployment_mode == TenantDeploymentMode.SELF_HOSTED:
            (
                fulfillment_license_id,
                fulfillment_key_prefix,
                fulfillment_encrypted_key,
                fulfillment_status,
                fulfillment_time,
            ) = _sync_self_hosted_fulfillment(
                session,
                tenant_slug=tenant_slug,
                tenant_name=tenant_name,
                billing_email=billing_email,
                license_type=_resolve_license_type(custom_data, plan_tier),
                billing_status=billing_status,
            )

        upsert_tenant(
            session,
            slug=tenant_slug,
            display_name=tenant_name,
            billing_email=billing_email,
            deployment_mode=deployment_mode,
            plan_tier=plan_tier,
            billing_status=billing_status,
            paddle_customer_id=provider_customer_id,
            paddle_subscription_id=subscription_id,
            self_hosted_license_id=fulfillment_license_id,
            self_hosted_license_key_prefix=fulfillment_key_prefix,
            encrypted_self_hosted_license_key=fulfillment_encrypted_key,
            self_hosted_license_status=fulfillment_status,
            self_hosted_last_fulfilled_at=fulfillment_time,
        )

    if event_type in {
        "subscription.created",
        "subscription.updated",
        "subscription.activated",
        "subscription.trialing",
        "subscription.resumed",
        "subscription.paused",
        "subscription.canceled",
        "subscription.past_due",
        "transaction.paid",
        "transaction.completed",
    }:
        _sync_tenant_license(
            session,
            tenant_slug=tenant_slug,
            purchased_tier=plan_tier,
            status=status_value or ("completed" if event_type.startswith("transaction.") else None),
            event_type=event_type,
        )

    response = PaddleWebhookIngestResponse(
        event_id=event_id,
        event_type=event_type,
        tenant_slug=tenant_slug,
        message=(
            "Paddle webhook processed"
            if deployment_mode == TenantDeploymentMode.SAAS
            else "Paddle webhook processed and self-hosted fulfillment synced"
        ),
    )

    event_record = BillingEvent(
        provider=BillingProvider.PADDLE,
        provider_event_id=event_id,
        event_type=event_type,
        tenant_slug=tenant_slug,
        processing_status="processed",
        occurred_at=occurred_at,
        raw_payload=payload,
        response_payload=response.model_dump(),
        processed_at=datetime.now(UTC),
    )
    session.add(event_record)
    session.commit()
    clear_license_cache()
    return response
