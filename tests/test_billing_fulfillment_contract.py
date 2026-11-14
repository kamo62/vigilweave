"""Use the licence server's actual flat revoke/reactivate response contract."""

from sqlmodel import Session

from app.core import database
from app.models.tenant import Tenant, TenantBillingStatus
from app.services import billing


def test_flat_revoke_response_sets_revoked_status(api_client, monkeypatch):
    monkeypatch.setattr(billing, "_license_server_fulfillment_available", lambda: True)
    monkeypatch.setattr(
        billing,
        "_call_license_server_fulfillment",
        lambda *args: {
            "id": 17,
            "key_prefix": "synthetic",
            "status": "revoked",
        },
    )
    with Session(database.engine) as session:
        session.add(
            Tenant(slug="synthetic", self_hosted_license_id=17, self_hosted_license_status="active")
        )
        session.commit()
        result = billing._sync_self_hosted_fulfillment(
            session,
            tenant_slug="synthetic",
            tenant_name="Synthetic",
            billing_email=None,
            license_type="pro",
            billing_status=TenantBillingStatus.CANCELED,
        )
        assert result[3] == "revoked"
