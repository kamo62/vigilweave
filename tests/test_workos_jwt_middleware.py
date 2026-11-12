import jwt

from app.core import auth_middleware
from app.core.config import settings


def test_workos_jwks_url_uses_client_specific_path(monkeypatch) -> None:
    auth_middleware.get_workos_jwks_client.cache_clear()
    monkeypatch.setattr(settings, "workos_client_id", "client_123")

    client = auth_middleware.get_workos_jwks_client()

    assert client.uri == "https://api.workos.com/sso/jwks/client_123"
    auth_middleware.get_workos_jwks_client.cache_clear()


def test_verify_workos_jwt_accepts_workos_issuer_variants(monkeypatch) -> None:
    class FakeKey:
        key = "unused"

    class FakeClient:
        @staticmethod
        def get_signing_key_from_jwt(token: str) -> FakeKey:
            assert token == "token"
            return FakeKey()

    def fake_decode(token: str, key: str, algorithms: list[str], options: dict):
        assert token == "token"
        assert key == "unused"
        assert algorithms == ["RS256"]
        assert options == {"verify_iss": False, "verify_aud": False}
        return {
            "sub": "user_123",
            "iss": "https://api.workos.com/user_management/client_123",
        }

    monkeypatch.setattr(settings, "workos_client_id", "client_123")
    monkeypatch.setattr(auth_middleware, "get_workos_jwks_client", lambda: FakeClient())
    monkeypatch.setattr(jwt, "decode", fake_decode)

    claims = auth_middleware.verify_workos_jwt("token")

    assert claims["sub"] == "user_123"


def test_verify_workos_jwt_accepts_missing_audience(monkeypatch) -> None:
    class FakeKey:
        key = "unused"

    class FakeClient:
        @staticmethod
        def get_signing_key_from_jwt(token: str) -> FakeKey:
            assert token == "token"
            return FakeKey()

    monkeypatch.setattr(settings, "workos_client_id", "client_123")
    monkeypatch.setattr(auth_middleware, "get_workos_jwks_client", lambda: FakeClient())
    monkeypatch.setattr(
        jwt,
        "decode",
        lambda *args, **kwargs: {"sub": "user_123", "iss": "https://api.workos.com"},
    )

    claims = auth_middleware.verify_workos_jwt("token")

    assert claims["sub"] == "user_123"
