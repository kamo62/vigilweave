import hashlib
import hmac
import json
import time
from types import SimpleNamespace

from sqlmodel import Session, select

from app.core import database as database_module
from app.core.config import settings
from app.models import (
    AuthProvider,
    BillingCustomer,
    BillingEvent,
    BillingSubscription,
    PlatformRole,
    SaaSTenantLicense,
    SaaSTenantTier,
    Tenant,
    UserRole,
)


def _sign_paddle_webhook(secret: str, payload: dict[str, object]) -> tuple[bytes, str]:
    timestamp = int(time.time())
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}:".encode("utf-8") + raw,
        hashlib.sha256,
    ).hexdigest()
    return raw, f"ts={timestamp};h1={signature}"


def _csrf_headers(api_client) -> dict[str, str]:
    response = api_client.get("/api/v1/auth/csrf")
    assert response.status_code == 200, response.text
    token = response.json()["csrf_token"]
    api_client.cookies.set("vigilweave_csrf", token)
    return {"X-CSRF-Token": token}


def test_billing_public_config_is_available_without_auth(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "paddle_environment", "sandbox")
    monkeypatch.setattr(settings, "paddle_client_token", "test_client_token")
    monkeypatch.setattr(settings, "paddle_price_id_pro", "pri_pro")
    monkeypatch.setattr(settings, "paddle_price_id_enterprise", "pri_ent")
    monkeypatch.setattr(settings, "vigilweave_api_base_url", "https://api.vigilweave.example")
    monkeypatch.setattr(settings, "vigilweave_web_base_url", "https://app.vigilweave.example")

    response = api_client.get("/api/v1/billing/public-config")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["provider"] == "paddle"
    assert payload["environment"] == "sandbox"
    assert payload["checkout_ready"] is True
    assert payload["pro_price_id"] == "pri_pro"
    assert payload["webhook_url"] == "https://api.vigilweave.example/api/v1/webhooks/paddle"
    assert (
        payload["default_success_url"] == "https://app.vigilweave.example/pricing?checkout=success"
    )


def test_billing_public_config_is_disabled_in_community_distribution(
    api_client, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "distribution_mode", "community")
    monkeypatch.setattr(settings, "paddle_environment", "sandbox")
    monkeypatch.setattr(settings, "paddle_client_token", "test_client_token")
    monkeypatch.setattr(settings, "paddle_price_id_pro", "pri_pro")
    monkeypatch.setattr(settings, "vigilweave_api_base_url", "https://api.vigilweave.example")
    monkeypatch.setattr(settings, "vigilweave_web_base_url", "https://app.vigilweave.example")

    response = api_client.get("/api/v1/billing/public-config")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["enabled"] is False
    assert payload["checkout_ready"] is False
    assert payload["client_token"] is None
    assert payload["pro_price_id"] is None


def test_paddle_webhook_is_disabled_in_community_distribution(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "distribution_mode", "community")
    monkeypatch.setattr(settings, "paddle_webhook_secret", "pdl_secret")

    payload = {
        "event_id": "evt_community_disabled",
        "event_type": "subscription.created",
        "data": {"id": "sub_disabled"},
    }
    raw, signature = _sign_paddle_webhook("pdl_secret", payload)

    response = api_client.post(
        "/api/v1/webhooks/paddle",
        content=raw,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 404, response.text
    assert "Community distribution" in response.json()["detail"]


def test_paddle_webhook_syncs_billing_records_and_tenant_license(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "paddle_webhook_secret", "pdl_secret")
    monkeypatch.setattr(settings, "paddle_webhook_tolerance_seconds", 60)
    monkeypatch.setattr(settings, "paddle_price_id_pro", "pri_pro")

    payload = {
        "event_id": "evt_001",
        "event_type": "subscription.created",
        "occurred_at": "2026-04-05T02:30:00Z",
        "data": {
            "id": "sub_001",
            "customer_id": "ctm_001",
            "status": "active",
            "collection_mode": "automatic",
            "currency_code": "USD",
            "started_at": "2026-04-05T02:30:00Z",
            "next_billed_at": "2027-04-05T02:30:00Z",
            "items": [{"price": {"id": "pri_pro"}}],
            "custom_data": {"tenant_slug": "workos-org-acme", "desired_tier": "pro"},
        },
    }
    raw, signature = _sign_paddle_webhook("pdl_secret", payload)

    response = api_client.post(
        "/api/v1/webhooks/paddle",
        content=raw,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "accepted": True,
        "event_id": "evt_001",
        "event_type": "subscription.created",
        "tenant_slug": "workos-org-acme",
        "message": "Paddle webhook processed",
    }

    with Session(database_module.engine) as session:
        event = session.exec(select(BillingEvent)).one()
        customer = session.exec(select(BillingCustomer)).one()
        subscription = session.exec(select(BillingSubscription)).one()
        tenant_license = session.exec(select(SaaSTenantLicense)).one()
        tenant = session.exec(select(Tenant).where(Tenant.slug == "workos-org-acme")).one()

    assert event.provider_event_id == "evt_001"
    assert customer.provider_customer_id == "ctm_001"
    assert customer.tenant_slug == "workos-org-acme"
    assert subscription.provider_subscription_id == "sub_001"
    assert subscription.plan_tier == SaaSTenantTier.PRO
    assert subscription.status == "active"
    assert tenant_license.tenant_slug == "workos-org-acme"
    assert tenant_license.tier == SaaSTenantTier.PRO
    assert tenant_license.assigned_by == "paddle:webhook"
    assert tenant.plan_tier == SaaSTenantTier.PRO
    assert tenant.billing_status.value == "active"


def test_paddle_webhook_replay_returns_existing_result(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "paddle_webhook_secret", "pdl_secret")
    monkeypatch.setattr(settings, "paddle_webhook_tolerance_seconds", 60)
    monkeypatch.setattr(settings, "paddle_price_id_pro", "pri_pro")

    payload = {
        "event_id": "evt_replay",
        "event_type": "transaction.completed",
        "occurred_at": "2026-04-05T02:45:00Z",
        "data": {
            "id": "txn_001",
            "subscription_id": "sub_001",
            "customer_id": "ctm_001",
            "status": "completed",
            "items": [{"price": {"id": "pri_pro"}}],
            "custom_data": {"tenant_slug": "workos-org-acme", "desired_tier": "pro"},
        },
    }
    raw, signature = _sign_paddle_webhook("pdl_secret", payload)

    first = api_client.post(
        "/api/v1/webhooks/paddle",
        content=raw,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )
    second = api_client.post(
        "/api/v1/webhooks/paddle",
        content=raw,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json() == first.json()

    with Session(database_module.engine) as session:
        assert len(session.exec(select(BillingEvent)).all()) == 1


def test_paddle_cancellation_downgrades_tenant_to_community(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "paddle_webhook_secret", "pdl_secret")
    monkeypatch.setattr(settings, "paddle_webhook_tolerance_seconds", 60)
    monkeypatch.setattr(settings, "paddle_price_id_pro", "pri_pro")

    created_payload = {
        "event_id": "evt_active",
        "event_type": "subscription.created",
        "occurred_at": "2026-04-05T03:00:00Z",
        "data": {
            "id": "sub_cancel",
            "customer_id": "ctm_cancel",
            "status": "active",
            "items": [{"price": {"id": "pri_pro"}}],
            "custom_data": {"tenant_slug": "workos-org-acme", "desired_tier": "pro"},
        },
    }
    canceled_payload = {
        "event_id": "evt_canceled",
        "event_type": "subscription.canceled",
        "occurred_at": "2026-05-05T03:00:00Z",
        "data": {
            "id": "sub_cancel",
            "customer_id": "ctm_cancel",
            "status": "canceled",
            "canceled_at": "2026-05-05T03:00:00Z",
        },
    }

    created_raw, created_signature = _sign_paddle_webhook("pdl_secret", created_payload)
    canceled_raw, canceled_signature = _sign_paddle_webhook("pdl_secret", canceled_payload)

    created = api_client.post(
        "/api/v1/webhooks/paddle",
        content=created_raw,
        headers={"Paddle-Signature": created_signature, "Content-Type": "application/json"},
    )
    canceled = api_client.post(
        "/api/v1/webhooks/paddle",
        content=canceled_raw,
        headers={"Paddle-Signature": canceled_signature, "Content-Type": "application/json"},
    )

    assert created.status_code == 200, created.text
    assert canceled.status_code == 200, canceled.text

    with Session(database_module.engine) as session:
        tenant_license = session.exec(
            select(SaaSTenantLicense).where(SaaSTenantLicense.tenant_slug == "workos-org-acme")
        ).one()
        subscription = session.exec(
            select(BillingSubscription).where(
                BillingSubscription.provider_subscription_id == "sub_cancel"
            )
        ).one()

    assert subscription.status == "canceled"
    assert tenant_license.tier == SaaSTenantTier.COMMUNITY


def test_current_tenant_subscription_endpoint_returns_latest_synced_subscription(
    api_client, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "workos")
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")

    with Session(database_module.engine) as session:
        session.add(
            BillingSubscription(
                provider_subscription_id="sub_current",
                tenant_slug="workos-org-acme",
                plan_tier=SaaSTenantTier.PRO,
                status="active",
            )
        )
        session.commit()

    user = SimpleNamespace(
        id=1,
        email="tenant-admin@example.com",
        tenant_slug="workos-org-acme",
        auth_provider=AuthProvider.WORKOS,
        role=UserRole.ADMIN,
        platform_role=PlatformRole.NONE,
    )

    monkeypatch.setattr("app.core.security.get_authenticated_user", lambda db, token: user)
    api_client.cookies.set("vigilweave_session", "test-session")

    response = api_client.get("/api/v1/billing/subscription")

    assert response.status_code == 200, response.text
    assert response.json()["provider_subscription_id"] == "sub_current"
    assert response.json()["plan_tier"] == "pro"


def test_current_tenant_summary_endpoint_returns_first_class_tenant(
    api_client, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "auth_mode", "workos")
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")

    with Session(database_module.engine) as session:
        session.add(
            Tenant(slug="workos-org-acme", display_name="Acme", plan_tier=SaaSTenantTier.PRO)
        )
        session.commit()

    user = SimpleNamespace(
        id=1,
        email="tenant-admin@example.com",
        tenant_slug="workos-org-acme",
        auth_provider=AuthProvider.WORKOS,
        role=UserRole.ADMIN,
        platform_role=PlatformRole.NONE,
    )

    monkeypatch.setattr("app.core.security.get_authenticated_user", lambda db, token: user)
    api_client.cookies.set("vigilweave_session", "test-session")

    response = api_client.get("/api/v1/billing/tenant")

    assert response.status_code == 200, response.text
    assert response.json()["slug"] == "workos-org-acme"
    assert response.json()["display_name"] == "Acme"


def test_billing_portal_session_endpoint_returns_paddle_portal_url(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "auth_mode", "workos")
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")
    monkeypatch.setattr(settings, "paddle_api_key", "pdl_api")

    with Session(database_module.engine) as session:
        session.add(
            Tenant(
                slug="workos-org-acme",
                display_name="Acme",
                paddle_customer_id="ctm_portal",
                paddle_subscription_id="sub_portal",
            )
        )
        session.commit()

    user = SimpleNamespace(
        id=1,
        email="tenant-admin@example.com",
        tenant_slug="workos-org-acme",
        auth_provider=AuthProvider.WORKOS,
        role=UserRole.ADMIN,
        platform_role=PlatformRole.NONE,
    )

    class _FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "data": {
                    "id": "cpls_123",
                    "customer_id": "ctm_portal",
                    "created_at": "2026-04-05T04:00:00Z",
                    "urls": {
                        "general": {"overview": "https://vendor.example/portal"},
                        "subscriptions": [
                            {"id": "sub_portal", "overview": "https://vendor.example/sub"}
                        ],
                    },
                }
            }

    monkeypatch.setattr("app.core.security.get_authenticated_user", lambda db, token: user)
    monkeypatch.setattr("app.services.billing.httpx.post", lambda *args, **kwargs: _FakeResponse())
    api_client.cookies.set("vigilweave_session", "test-session")

    response = api_client.post("/api/v1/billing/portal-session", headers=_csrf_headers(api_client))

    assert response.status_code == 200, response.text
    assert response.json()["overview_url"] == "https://vendor.example/portal"
    assert response.json()["customer_id"] == "ctm_portal"


def test_self_hosted_webhook_issues_and_exposes_license(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")
    monkeypatch.setattr(settings, "auth_mode", "workos")
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "paddle_webhook_secret", "pdl_secret")
    monkeypatch.setattr(settings, "paddle_webhook_tolerance_seconds", 60)
    monkeypatch.setattr(settings, "license_server_shared_secret", "fulfillment-secret")
    monkeypatch.setattr(
        settings, "license_server_api_base_url", "https://license.vigilweave.example"
    )

    def _fake_post(url: str, *args, **kwargs):
        class _FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                if url.endswith("/v1/fulfillment/issue"):
                    return {
                        "license_key": "vw-pro-acme-self-hosted-deadbeef",
                        "record": {
                            "id": 17,
                            "key_prefix": "vw-pro-acme-self-hosted",
                            "status": "active",
                        },
                    }
                raise AssertionError(f"Unexpected URL {url}")

        return _FakeResponse()

    monkeypatch.setattr("app.services.billing.httpx.post", _fake_post)

    payload = {
        "event_id": "evt_self_hosted",
        "event_type": "subscription.created",
        "occurred_at": "2026-04-05T04:30:00Z",
        "data": {
            "id": "sub_self_hosted",
            "customer_id": "ctm_self_hosted",
            "status": "active",
            "items": [{"price": {"id": "pri_custom"}}],
            "custom_data": {
                "tenant_slug": "acme-self-hosted",
                "tenant_name": "Acme Self Hosted",
                "deployment_mode": "self_hosted",
                "license_type": "pro",
                "billing_email": "billing@acme.example",
            },
        },
    }
    raw, signature = _sign_paddle_webhook("pdl_secret", payload)

    webhook_response = api_client.post(
        "/api/v1/webhooks/paddle",
        content=raw,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert webhook_response.status_code == 200, webhook_response.text
    assert "self-hosted fulfillment" in webhook_response.json()["message"]

    user = SimpleNamespace(
        id=1,
        email="tenant-admin@example.com",
        tenant_slug="acme-self-hosted",
        auth_provider=AuthProvider.WORKOS,
        role=UserRole.ADMIN,
        platform_role=PlatformRole.NONE,
    )

    monkeypatch.setattr("app.core.security.get_authenticated_user", lambda db, token: user)
    api_client.cookies.set("vigilweave_session", "test-session")

    license_response = api_client.get("/api/v1/billing/self-hosted-license")

    assert license_response.status_code == 200, license_response.text
    assert license_response.json()["license_id"] == 17
    assert license_response.json()["license_key"] == "vw-pro-acme-self-hosted-deadbeef"


def test_self_hosted_price_id_infers_pro_tier_for_fulfillment(api_client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")
    monkeypatch.setattr(settings, "auth_mode", "workos")
    monkeypatch.setattr(settings, "saas_enabled", True)
    monkeypatch.setattr(settings, "paddle_webhook_secret", "pdl_secret")
    monkeypatch.setattr(settings, "paddle_webhook_tolerance_seconds", 60)
    monkeypatch.setattr(settings, "paddle_price_id_self_hosted_pro", "pri_self_hosted_pro")
    monkeypatch.setattr(settings, "license_server_shared_secret", "fulfillment-secret")
    monkeypatch.setattr(
        settings, "license_server_api_base_url", "https://license.vigilweave.example"
    )

    def _fake_post(url: str, *args, **kwargs):
        class _FakeResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                if url.endswith("/v1/fulfillment/issue"):
                    return {
                        "license_key": "vw-pro-acme-self-hosted-cafebabe",
                        "record": {
                            "id": 23,
                            "key_prefix": "vw-pro-acme-self-hosted",
                            "status": "active",
                        },
                    }
                raise AssertionError(f"Unexpected URL {url}")

        return _FakeResponse()

    monkeypatch.setattr("app.services.billing.httpx.post", _fake_post)

    payload = {
        "event_id": "evt_self_hosted_price_id",
        "event_type": "subscription.created",
        "occurred_at": "2026-04-05T04:45:00Z",
        "data": {
            "id": "sub_self_hosted_pro",
            "customer_id": "ctm_self_hosted_pro",
            "status": "active",
            "items": [{"price": {"id": "pri_self_hosted_pro"}}],
            "custom_data": {
                "tenant_slug": "acme-self-hosted-pro",
                "tenant_name": "Acme Self Hosted Pro",
                "deployment_mode": "self_hosted",
                "billing_email": "billing@acme.example",
            },
        },
    }
    raw, signature = _sign_paddle_webhook("pdl_secret", payload)

    response = api_client.post(
        "/api/v1/webhooks/paddle",
        content=raw,
        headers={"Paddle-Signature": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200, response.text

    with Session(database_module.engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == "acme-self-hosted-pro")).one()
        subscription = session.exec(
            select(BillingSubscription).where(
                BillingSubscription.provider_subscription_id == "sub_self_hosted_pro"
            )
        ).one()
        tenant_license = session.exec(
            select(SaaSTenantLicense).where(SaaSTenantLicense.tenant_slug == "acme-self-hosted-pro")
        ).one()

    assert subscription.plan_tier == SaaSTenantTier.PRO
    assert tenant.plan_tier == SaaSTenantTier.PRO
    assert tenant.self_hosted_license_id == 23
    assert tenant_license.tier == SaaSTenantTier.PRO
