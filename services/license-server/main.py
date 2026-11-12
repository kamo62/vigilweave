"""VigilWeave license server with operator console and auditable key lifecycle."""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import io
import json
import secrets
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any

import ldap3
from cryptography.fernet import Fernet
from fastapi import (
    Cookie,
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    and_,
    case,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "sqlite:///./license_server.db"
    session_secret: str | None = None
    config_encryption_key: str | None = None
    offline_signing_secret: str | None = None
    session_cookie_name: str = "vw_license_session"
    session_ttl_hours: int = 12
    allowed_origins: list[str] = [
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]
    verify_rate_limit_max_requests: int = 120
    verify_rate_limit_window_seconds: int = 60
    auth_rate_limit_max_requests: int = 20
    auth_rate_limit_window_seconds: int = 300
    key_list_default_page_size: int = 25
    key_list_max_page_size: int = 100
    fulfillment_shared_secret: str | None = None

    def validate_production_requirements(self) -> None:
        if self.environment in {"development", "test"}:
            return
        if self.database_url.startswith("sqlite"):
            raise RuntimeError("PostgreSQL is required for production license-server deployments")
        missing = []
        if not self.session_secret:
            missing.append("SESSION_SECRET")
        if not self.config_encryption_key:
            missing.append("CONFIG_ENCRYPTION_KEY")
        if not self.offline_signing_secret:
            missing.append("OFFLINE_SIGNING_SECRET")
        if missing:
            raise RuntimeError(f"Missing required production secrets: {', '.join(missing)}")
        insecure_defaults = {
            "change-me-in-production",
            "dev-session-secret",
            "dev-config-secret",
            "dev-offline-secret",
            "dev-offline-signing-secret",
        }
        insecure = []
        if self.session_secret in insecure_defaults:
            insecure.append("SESSION_SECRET")
        if self.config_encryption_key in insecure_defaults:
            insecure.append("CONFIG_ENCRYPTION_KEY")
        if self.offline_signing_secret in insecure_defaults:
            insecure.append("OFFLINE_SIGNING_SECRET")
        if insecure:
            raise RuntimeError(
                f"Insecure default production secrets are not allowed: {', '.join(insecure)}"
            )


settings = Settings()


class Base(DeclarativeBase):
    pass


class OperatorUser(Base):
    __tablename__ = "operator_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="viewer")
    auth_provider: Mapped[str] = mapped_column(String(32), default="local")
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sessions: Mapped[list["OperatorSession"]] = relationship(back_populates="user")


class OperatorSession(Base):
    __tablename__ = "operator_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("operator_users.id", ondelete="CASCADE"))
    session_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    user: Mapped[OperatorUser] = relationship(back_populates="sessions")


class OperatorAuditLog(Base):
    __tablename__ = "operator_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("operator_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(128), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(128), index=True)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class DirectoryConfig(Base):
    __tablename__ = "directory_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    server_uri: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bind_dn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_bind_password: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    user_base_dn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_filter: Mapped[str] = mapped_column(String(255), default="(mail={email})")
    group_base_dn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    admin_group_dn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    viewer_group_dn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    use_ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    start_tls: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class LicenseKey(Base):
    __tablename__ = "license_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_prefix: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    key_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    license_type: Mapped[str] = mapped_column(String(64), index=True)
    organization: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_seats: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    customer_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("operator_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("operator_users.id", ondelete="SET NULL"),
        nullable=True,
    )
    revoked_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    replaced_by_license_id: Mapped[int | None] = mapped_column(
        ForeignKey("license_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_count: Mapped[int] = mapped_column(Integer, default=0)


class VerificationLog(Base):
    __tablename__ = "verification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    license_key_id: Mapped[int | None] = mapped_column(
        ForeignKey("license_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
    attempted_prefix: Mapped[str] = mapped_column(String(80), index=True)
    instance_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)


def create_session_factory(url: str) -> sessionmaker[Session]:
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    engine = create_engine(url, connect_args=connect_args)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, expire_on_commit=False)


SessionLocal: sessionmaker[Session] | None = None


@dataclass(slots=True)
class RateLimitConfig:
    max_requests: int
    window_seconds: int


class MemoryRateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = {}
        self._lock = Lock()

    def allow(self, key: str, config: RateLimitConfig) -> bool:
        now = datetime.now(UTC).timestamp()
        cutoff = now - config.window_seconds
        with self._lock:
            timestamps = [stamp for stamp in self._buckets.get(key, []) if stamp > cutoff]
            if len(timestamps) >= config.max_requests:
                self._buckets[key] = timestamps
                return False
            timestamps.append(now)
            self._buckets[key] = timestamps
            return True


rate_limiter = MemoryRateLimiter()


FEATURES_BY_TYPE = {
    "pro": [
        "bulk_triage",
        "custom_policies",
        "notifications",
        "scan_scheduling",
        "reporting",
        "audit_extended",
    ],
    "enterprise_standard": [
        "bulk_triage",
        "custom_policies",
        "notifications",
        "scan_scheduling",
        "reporting",
        "audit_extended",
        "sso_saml",
        "rbac",
        "multi_tenancy",
        "advanced_policies",
        "portfolios",
        "custom_adapters",
        "white_label",
        "security_reports",
        "executive_reporting",
    ],
    "enterprise_offline": [
        "bulk_triage",
        "custom_policies",
        "notifications",
        "scan_scheduling",
        "reporting",
        "audit_extended",
        "sso_saml",
        "rbac",
        "multi_tenancy",
        "advanced_policies",
        "portfolios",
        "custom_adapters",
        "white_label",
        "security_reports",
        "executive_reporting",
    ],
}

TIER_BY_TYPE = {
    "pro": "pro",
    "enterprise_standard": "enterprise",
    "enterprise_offline": "enterprise",
}

LICENSE_TYPE_TO_PREFIX = {
    "pro": "vw-pro",
    "enterprise_standard": "vw-ent",
    "enterprise_offline": "vw-ent-offline",
}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class BootstrapRequest(LoginRequest):
    name: str = Field(min_length=1, max_length=255)


class OperatorUserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: str
    auth_provider: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class OperatorCreateRequest(BaseModel):
    email: EmailStr
    name: str
    password: str = Field(min_length=12)
    role: str = Field(pattern="^(admin|viewer)$")


class OperatorUpdateRequest(BaseModel):
    name: str | None = None
    role: str | None = Field(default=None, pattern="^(admin|viewer)$")
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=12)


class DirectoryConfigRequest(BaseModel):
    enabled: bool = False
    server_uri: str | None = None
    bind_dn: str | None = None
    bind_password: str | None = None
    user_base_dn: str | None = None
    user_filter: str = "(mail={email})"
    group_base_dn: str | None = None
    admin_group_dn: str | None = None
    viewer_group_dn: str | None = None
    use_ssl: bool = True
    start_tls: bool = False


class DirectoryConfigResponse(BaseModel):
    enabled: bool
    server_uri: str | None
    bind_dn: str | None
    user_base_dn: str | None
    user_filter: str
    group_base_dn: str | None
    admin_group_dn: str | None
    viewer_group_dn: str | None
    use_ssl: bool
    start_tls: bool
    bind_password_configured: bool
    updated_at: datetime | None


class DirectoryLoginTestRequest(BaseModel):
    email: EmailStr
    password: str


class GenerateKeyRequest(BaseModel):
    license_type: str = Field(pattern="^(pro|enterprise_standard|enterprise_offline)$")
    organization: str = Field(min_length=1, max_length=255)
    expires_days: int | None = Field(default=None, ge=1, le=3650)
    max_seats: int | None = Field(default=None, ge=1, le=100000)
    notes: str | None = None
    customer_metadata: dict[str, Any] = Field(default_factory=dict)


class LicenseKeyUpdateRequest(BaseModel):
    expires_at: datetime | None = None
    max_seats: int | None = Field(default=None, ge=1, le=100000)
    notes: str | None = None
    customer_metadata: dict[str, Any] | None = None


class RevokeKeyRequest(BaseModel):
    reason: str | None = None


class ReissueKeyRequest(BaseModel):
    expires_days: int | None = Field(default=None, ge=1, le=3650)
    max_seats: int | None = Field(default=None, ge=1, le=100000)
    notes: str | None = None
    customer_metadata: dict[str, Any] | None = None


class BulkKeyActionRequest(BaseModel):
    action: str = Field(pattern="^(revoke|reactivate)$")
    key_ids: list[int] = Field(min_length=1, max_length=500)
    reason: str | None = None


class VerificationRequest(BaseModel):
    license_key: str
    instance_id: str | None = None


class VerificationResponse(BaseModel):
    valid: bool
    license_type: str
    tier: str
    organization: str | None
    expires_at: str | None
    features: list[str]
    error_message: str | None = None


class LicenseKeyResponse(BaseModel):
    id: int
    key_prefix: str
    license_type: str
    organization: str
    status: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    max_seats: int | None
    notes: str | None
    customer_metadata: dict[str, Any]
    revoked_reason: str | None
    replaced_by_license_id: int | None
    last_verified_at: datetime | None
    verification_count: int


class GenerateKeyResponse(BaseModel):
    license_key: str
    record: LicenseKeyResponse


class VerificationLogResponse(BaseModel):
    id: int
    attempted_prefix: str
    instance_id: str | None
    ip_address: str | None
    verified_at: datetime
    success: bool
    error_message: str | None


class PagedLicenseKeysResponse(BaseModel):
    items: list[LicenseKeyResponse]
    page: int
    page_size: int
    total: int


class OperatorAuditLogResponse(BaseModel):
    id: int
    actor_user_id: int | None
    actor_email: str | None
    action: str
    entity_type: str
    entity_id: str
    details_json: dict[str, Any]
    created_at: datetime


class PagedAuditLogsResponse(BaseModel):
    items: list[OperatorAuditLogResponse]
    page: int
    page_size: int
    total: int


def get_db() -> Session:
    if SessionLocal is None:
        raise HTTPException(status_code=503, detail="Database is not initialized")
    with SessionLocal() as session:
        yield session


def _now() -> datetime:
    return datetime.now(UTC)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _hash_value(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_org_slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value.strip())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return cleaned or "org"


def _fernet_secret(raw_secret: str | None, *, purpose: str) -> str:
    if raw_secret:
        return raw_secret
    if settings.environment in {"development", "test"}:
        return f"vigilweave-{purpose}-dev-secret"
    raise RuntimeError(f"{purpose} secret is required in non-development environments")


def _build_fernet(raw_secret: str | None, *, purpose: str) -> Fernet:
    digest = hashlib.sha256(_fernet_secret(raw_secret, purpose=purpose).encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_config_value(value: str) -> str:
    return (
        _build_fernet(settings.config_encryption_key, purpose="config")
        .encrypt(value.encode("utf-8"))
        .decode("utf-8")
    )


def decrypt_config_value(value: str) -> str:
    return (
        _build_fernet(settings.config_encryption_key, purpose="config")
        .decrypt(value.encode("utf-8"))
        .decode("utf-8")
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return f"pbkdf2_sha256${base64.b64encode(salt).decode()}${base64.b64encode(derived).decode()}"


def verify_password(password: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        _, salt_b64, hash_b64 = encoded.split("$", 2)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000)
    return hmac.compare_digest(candidate, expected)


def create_session_token() -> str:
    secret = _fernet_secret(settings.session_secret, purpose="session")
    raw = secrets.token_urlsafe(32)
    signature = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{raw}.{signature}"


def verify_session_token(token: str) -> bool:
    try:
        raw, signature = token.split(".", 1)
    except ValueError:
        return False
    secret = _fernet_secret(settings.session_secret, purpose="session")
    expected = hmac.new(secret.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.environment not in {"development", "test"},
        samesite="lax",
        max_age=settings.session_ttl_hours * 3600,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(settings.session_cookie_name)


def _license_prefix(license_type: str, organization: str) -> str:
    return f"{LICENSE_TYPE_TO_PREFIX[license_type]}-{_normalize_org_slug(organization)}"


def _stored_key_prefix(license_key: str) -> str:
    return license_key[:48]


def _generate_online_key(license_type: str, organization: str) -> str:
    suffix = secrets.token_hex(32)
    return f"{_license_prefix(license_type, organization)}-{suffix}"


def _generate_offline_signature(organization: str) -> str:
    secret = _fernet_secret(settings.offline_signing_secret, purpose="offline-signing")
    payload = _license_prefix("enterprise_offline", organization)
    digest = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def _generate_license_key(license_type: str, organization: str) -> str:
    if license_type == "enterprise_offline":
        return (
            f"{_license_prefix(license_type, organization)}-"
            f"{_generate_offline_signature(organization)}"
        )
    return _generate_online_key(license_type, organization)


def _parse_license_key(key: str) -> tuple[str, str, str] | None:
    if key.startswith("vw-ent-offline-"):
        parsed = _parse_key_with_prefix(key, prefix="vw-ent-offline-")
        if parsed is not None:
            organization, signature = parsed
            return "enterprise_offline", organization, signature
    if key.startswith("vw-ent-"):
        parsed = _parse_key_with_prefix(key, prefix="vw-ent-")
        if parsed is not None:
            organization, suffix = parsed
            return "enterprise_standard", organization, suffix
    if key.startswith("vw-pro-"):
        parsed = _parse_key_with_prefix(key, prefix="vw-pro-")
        if parsed is not None:
            organization, suffix = parsed
            return "pro", organization, suffix
    return None


def _parse_key_with_prefix(key: str, *, prefix: str) -> tuple[str, str] | None:
    remainder = key.removeprefix(prefix)
    organization, separator, suffix = remainder.rpartition("-")
    if not separator or not organization or not suffix:
        return None
    return organization, suffix


def _record_audit(
    session: Session,
    *,
    actor_user_id: int | None,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any],
) -> None:
    session.add(
        OperatorAuditLog(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details_json=details,
        )
    )
    session.commit()


def _rate_limit_key(request: Request) -> str:
    client_ip = request.client.host if request.client else "unknown"
    return f"{client_ip}:{request.url.path}"


def enforce_rate_limit(request: Request, config: RateLimitConfig, *, resource: str) -> None:
    if not rate_limiter.allow(_rate_limit_key(request), config):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for {resource}",
        )


def _current_operator(
    session: Session = Depends(get_db),
    license_session: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> OperatorUser:
    if not license_session or not verify_session_token(license_session):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    record = (
        session.query(OperatorSession)
        .filter_by(session_hash=_hash_value(license_session))
        .one_or_none()
    )
    if record is None or (_normalize_datetime(record.expires_at) or _now()) <= _now():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )
    user = session.get(OperatorUser, record.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Operator account is inactive",
        )
    return user


def require_operator(role: str | None = None):
    def dependency(
        session: Session = Depends(get_db),
        user: OperatorUser = Depends(_current_operator),
    ) -> OperatorUser:
        del session
        if role == "admin" and user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
        return user

    return dependency


def _bootstrap_required(session: Session) -> bool:
    return session.query(func.count(OperatorUser.id)).scalar() == 0


def _operator_to_response(user: OperatorUser) -> OperatorUserResponse:
    return OperatorUserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        auth_provider=user.auth_provider,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def _license_to_response(record: LicenseKey) -> LicenseKeyResponse:
    return LicenseKeyResponse(
        id=record.id,
        key_prefix=record.key_prefix,
        license_type=record.license_type,
        organization=record.organization,
        status=_effective_license_status(record),
        created_at=record.created_at,
        updated_at=record.updated_at,
        expires_at=record.expires_at,
        max_seats=record.max_seats,
        notes=record.notes,
        customer_metadata=record.customer_metadata or {},
        revoked_reason=record.revoked_reason,
        replaced_by_license_id=record.replaced_by_license_id,
        last_verified_at=record.last_verified_at,
        verification_count=record.verification_count,
    )


def _audit_to_response(session: Session, record: OperatorAuditLog) -> OperatorAuditLogResponse:
    actor_email: str | None = None
    if record.actor_user_id is not None:
        actor = session.get(OperatorUser, record.actor_user_id)
        actor_email = actor.email if actor is not None else None
    return OperatorAuditLogResponse(
        id=record.id,
        actor_user_id=record.actor_user_id,
        actor_email=actor_email,
        action=record.action,
        entity_type=record.entity_type,
        entity_id=record.entity_id,
        details_json=record.details_json or {},
        created_at=record.created_at,
    )


def _directory_to_response(record: DirectoryConfig | None) -> DirectoryConfigResponse:
    if record is None:
        return DirectoryConfigResponse(
            enabled=False,
            server_uri=None,
            bind_dn=None,
            user_base_dn=None,
            user_filter="(mail={email})",
            group_base_dn=None,
            admin_group_dn=None,
            viewer_group_dn=None,
            use_ssl=True,
            start_tls=False,
            bind_password_configured=False,
            updated_at=None,
        )
    return DirectoryConfigResponse(
        enabled=record.enabled,
        server_uri=record.server_uri,
        bind_dn=record.bind_dn,
        user_base_dn=record.user_base_dn,
        user_filter=record.user_filter,
        group_base_dn=record.group_base_dn,
        admin_group_dn=record.admin_group_dn,
        viewer_group_dn=record.viewer_group_dn,
        use_ssl=record.use_ssl,
        start_tls=record.start_tls,
        bind_password_configured=bool(record.encrypted_bind_password),
        updated_at=record.updated_at,
    )


def _effective_license_status(record: LicenseKey) -> str:
    if record.status == "replaced":
        return "replaced"
    if record.status == "revoked":
        return "revoked"
    normalized_expiry = _normalize_datetime(record.expires_at)
    if normalized_expiry and normalized_expiry <= _now():
        return "expired"
    return "active"


def _effective_status_expression():
    now = _now()
    return case(
        (LicenseKey.status == "replaced", "replaced"),
        (LicenseKey.status == "revoked", "revoked"),
        (and_(LicenseKey.expires_at.is_not(None), LicenseKey.expires_at <= now), "expired"),
        else_="active",
    )


def _get_directory_config(session: Session) -> DirectoryConfig | None:
    return session.query(DirectoryConfig).order_by(DirectoryConfig.id.asc()).first()


def _ldap_connection(record: DirectoryConfig) -> ldap3.Connection:
    server = ldap3.Server(record.server_uri or "", use_ssl=record.use_ssl, get_info=ldap3.NONE)
    password = (
        decrypt_config_value(record.encrypted_bind_password)
        if record.encrypted_bind_password
        else None
    )
    connection = ldap3.Connection(
        server,
        user=record.bind_dn,
        password=password,
        auto_bind=False,
    )
    if not connection.open():
        raise RuntimeError("Failed to open LDAP connection")
    if record.start_tls:
        if not connection.start_tls():
            raise RuntimeError("LDAP StartTLS negotiation failed")
    if not connection.bind():
        raise RuntimeError("LDAP bind failed")
    return connection


def _ldap_lookup_and_authenticate(
    record: DirectoryConfig,
    *,
    email: str,
    password: str,
) -> tuple[str, str]:
    if not record.server_uri or not record.user_base_dn:
        raise HTTPException(status_code=400, detail="Directory configuration is incomplete")
    service_conn = _ldap_connection(record)
    user_filter = (record.user_filter or "(mail={email})").replace("{email}", email)
    try:
        service_conn.search(record.user_base_dn, user_filter, attributes=["cn", "mail", "memberOf"])
        if not service_conn.entries:
            raise HTTPException(status_code=401, detail="Directory user not found")
        entry = service_conn.entries[0]
        user_dn = entry.entry_dn
        name = str(getattr(entry, "cn", email))
        user_conn = ldap3.Connection(
            service_conn.server,
            user=user_dn,
            password=password,
            auto_bind=True,
        )
        user_conn.unbind()

        groups = {str(group) for group in entry.entry_attributes_as_dict.get("memberOf", [])}
        role = None
        if record.admin_group_dn and record.admin_group_dn in groups:
            role = "admin"
        elif record.viewer_group_dn and record.viewer_group_dn in groups:
            role = "viewer"
        if role is None:
            raise HTTPException(
                status_code=403,
                detail="Directory user is not mapped to a license-server role",
            )
        return name, role
    finally:
        service_conn.unbind()


def _create_or_refresh_shadow_operator(
    session: Session,
    *,
    email: str,
    name: str,
    role: str,
) -> OperatorUser:
    user = session.query(OperatorUser).filter_by(email=email).one_or_none()
    if user is None:
        user = OperatorUser(
            email=email,
            name=name,
            role=role,
            auth_provider="ldap",
            password_hash=None,
            is_active=True,
        )
    else:
        user.name = name
        user.role = role
        user.auth_provider = "ldap"
        user.is_active = True
    user.updated_at = _now()
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _start_operator_session(
    session: Session,
    response: Response,
    user: OperatorUser,
) -> OperatorUserResponse:
    token = create_session_token()
    record = OperatorSession(
        user_id=user.id,
        session_hash=_hash_value(token),
        expires_at=_now() + timedelta(hours=settings.session_ttl_hours),
    )
    user.last_login_at = _now()
    session.add(user)
    session.add(record)
    session.commit()
    set_session_cookie(response, token)
    return _operator_to_response(user)


def _active_admin_count(session: Session, *, exclude_user_id: int | None = None) -> int:
    query = session.query(func.count(OperatorUser.id)).filter(
        OperatorUser.role == "admin",
        OperatorUser.is_active.is_(True),
    )
    if exclude_user_id is not None:
        query = query.filter(OperatorUser.id != exclude_user_id)
    return int(query.scalar() or 0)


def _assert_admin_floor(
    session: Session,
    *,
    operator: OperatorUser,
    next_role: str,
    next_is_active: bool,
) -> None:
    if (
        operator.role == "admin"
        and operator.is_active
        and (next_role != "admin" or not next_is_active)
    ):
        if _active_admin_count(session, exclude_user_id=operator.id) == 0:
            raise HTTPException(
                status_code=400,
                detail="At least one active admin must remain",
            )


def _log_verification(
    session: Session,
    *,
    record: LicenseKey | None,
    attempted_prefix: str,
    request: VerificationRequest,
    request_obj: Request,
    success: bool,
    error_message: str | None,
) -> None:
    if record is not None and success:
        record.last_verified_at = _now()
        record.verification_count += 1
        session.add(record)
    session.add(
        VerificationLog(
            license_key_id=record.id if record is not None else None,
            attempted_prefix=attempted_prefix[:80],
            instance_id=request.instance_id,
            ip_address=request_obj.client.host if request_obj.client else None,
            success=success,
            error_message=error_message,
        )
    )
    session.commit()


def _verify_license_record(
    session: Session,
    request: VerificationRequest,
    request_obj: Request,
) -> VerificationResponse:
    parsed = _parse_license_key(request.license_key)
    if parsed is None:
        _log_verification(
            session,
            record=None,
            attempted_prefix=request.license_key[:80],
            request=request,
            request_obj=request_obj,
            success=False,
            error_message="Invalid license key format",
        )
        return VerificationResponse(
            valid=False,
            license_type="community",
            tier="community",
            organization=None,
            expires_at=None,
            features=[],
            error_message="Invalid license key format",
        )

    license_type, organization, tail = parsed
    prefix = _license_prefix(license_type, organization)

    if license_type == "enterprise_offline":
        expected_signature = _generate_offline_signature(organization)
        if not hmac.compare_digest(tail, expected_signature):
            _log_verification(
                session,
                record=None,
                attempted_prefix=prefix,
                request=request,
                request_obj=request_obj,
                success=False,
                error_message="Invalid offline key signature",
            )
            return VerificationResponse(
                valid=False,
                license_type="community",
                tier="community",
                organization=None,
                expires_at=None,
                features=[],
                error_message="Invalid license key signature",
            )

    record = (
        session.query(LicenseKey).filter_by(key_hash=_hash_value(request.license_key)).one_or_none()
    )
    if record is None:
        _log_verification(
            session,
            record=None,
            attempted_prefix=prefix,
            request=request,
            request_obj=request_obj,
            success=False,
            error_message="License key not found",
        )
        return VerificationResponse(
            valid=False,
            license_type="community",
            tier="community",
            organization=None,
            expires_at=None,
            features=[],
            error_message="License key not found",
        )

    effective_status = _effective_license_status(record)
    if effective_status != "active":
        _log_verification(
            session,
            record=record,
            attempted_prefix=record.key_prefix,
            request=request,
            request_obj=request_obj,
            success=False,
            error_message=f"License is {effective_status}",
        )
        return VerificationResponse(
            valid=False,
            license_type="community",
            tier="community",
            organization=None,
            expires_at=record.expires_at.isoformat() if record.expires_at else None,
            features=[],
            error_message=f"License is {effective_status}",
        )

    _log_verification(
        session,
        record=record,
        attempted_prefix=record.key_prefix,
        request=request,
        request_obj=request_obj,
        success=True,
        error_message=None,
    )
    return VerificationResponse(
        valid=True,
        license_type=record.license_type,
        tier=TIER_BY_TYPE[record.license_type],
        organization=record.organization,
        expires_at=record.expires_at.isoformat() if record.expires_at else None,
        features=FEATURES_BY_TYPE[record.license_type],
        error_message=None,
    )


def _issue_license(
    session: Session,
    *,
    actor: OperatorUser | None,
    request: GenerateKeyRequest,
) -> GenerateKeyResponse:
    license_key = _generate_license_key(request.license_type, request.organization)
    expires_at = _now() + timedelta(days=request.expires_days) if request.expires_days else None
    record = LicenseKey(
        key_prefix=_stored_key_prefix(license_key),
        key_hash=_hash_value(license_key),
        license_type=request.license_type,
        organization=request.organization,
        status="active",
        expires_at=expires_at,
        max_seats=request.max_seats,
        notes=request.notes,
        customer_metadata=request.customer_metadata,
        created_by_user_id=actor.id if actor is not None else None,
        updated_by_user_id=actor.id if actor is not None else None,
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    _record_audit(
        session,
        actor_user_id=actor.id if actor is not None else None,
        action="license.generated",
        entity_type="license_key",
        entity_id=str(record.id),
        details={"key_prefix": record.key_prefix, "license_type": record.license_type},
    )
    return GenerateKeyResponse(license_key=license_key, record=_license_to_response(record))


def require_fulfillment_auth(authorization: str | None = Header(default=None)) -> None:
    expected = (settings.fulfillment_shared_secret or "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fulfillment API is not configured",
        )

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token or not hmac.compare_digest(token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization"
        )


def _database_ready() -> bool:
    if SessionLocal is None:
        return False
    try:
        with SessionLocal() as session:
            session.execute(select(1))
        return True
    except Exception:  # noqa: BLE001
        return False


@asynccontextmanager
async def lifespan(_: FastAPI):
    global SessionLocal
    settings.validate_production_requirements()
    SessionLocal = create_session_factory(settings.database_url)
    yield


app = FastAPI(
    title="VigilWeave License Server",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With"],
)

static_dir = Path(__file__).resolve().parent / "static"
assets_dir = static_dir / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy", "service": "license-server"}


@app.get("/ready")
def readiness() -> Response:
    report = {
        "database": _database_ready(),
        "session_secret": bool(settings.session_secret),
        "config_encryption_key": bool(settings.config_encryption_key),
        "offline_signing_secret": bool(settings.offline_signing_secret),
    }
    try:
        _build_fernet(settings.config_encryption_key, purpose="config")
        report["config_encryption"] = True
    except Exception:  # noqa: BLE001
        report["config_encryption"] = False
    report["status"] = "ok" if all(report.values()) else "degraded"
    return Response(
        content=json.dumps(report),
        media_type="application/json",
        status_code=200 if report["status"] == "ok" else 503,
    )


@app.get("/api/auth/bootstrap-required")
def bootstrap_required(session: Session = Depends(get_db)) -> dict[str, bool]:
    return {"bootstrap_required": _bootstrap_required(session)}


@app.post("/api/auth/bootstrap", response_model=OperatorUserResponse)
def bootstrap_operator(
    payload: BootstrapRequest,
    response: Response,
    request: Request,
    session: Session = Depends(get_db),
) -> OperatorUserResponse:
    enforce_rate_limit(
        request,
        RateLimitConfig(
            settings.auth_rate_limit_max_requests,
            settings.auth_rate_limit_window_seconds,
        ),
        resource="authentication",
    )
    if not _bootstrap_required(session):
        raise HTTPException(status_code=409, detail="Bootstrap is no longer available")
    operator = OperatorUser(
        email=payload.email,
        name=payload.name,
        role="admin",
        auth_provider="local",
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    session.add(operator)
    session.commit()
    session.refresh(operator)
    _record_audit(
        session,
        actor_user_id=operator.id,
        action="operator.bootstrap",
        entity_type="operator",
        entity_id=str(operator.id),
        details={"email": operator.email},
    )
    return _start_operator_session(session, response, operator)


@app.post("/api/auth/login", response_model=OperatorUserResponse)
def login_operator(
    payload: LoginRequest,
    response: Response,
    request: Request,
    session: Session = Depends(get_db),
) -> OperatorUserResponse:
    enforce_rate_limit(
        request,
        RateLimitConfig(
            settings.auth_rate_limit_max_requests,
            settings.auth_rate_limit_window_seconds,
        ),
        resource="authentication",
    )

    operator = session.query(OperatorUser).filter_by(email=payload.email).one_or_none()
    if (
        operator is not None
        and operator.auth_provider == "local"
        and verify_password(payload.password, operator.password_hash)
    ):
        if not operator.is_active:
            _record_audit(
                session,
                actor_user_id=operator.id,
                action="operator.login_blocked",
                entity_type="operator",
                entity_id=str(operator.id),
                details={"email": payload.email, "reason": "inactive"},
            )
            raise HTTPException(status_code=403, detail="Operator account is inactive")
        return _start_operator_session(session, response, operator)

    directory = _get_directory_config(session)
    if directory and directory.enabled:
        name, role = _ldap_lookup_and_authenticate(
            directory,
            email=payload.email,
            password=payload.password,
        )
        operator = _create_or_refresh_shadow_operator(
            session,
            email=payload.email,
            name=name,
            role=role,
        )
        return _start_operator_session(session, response, operator)

    _record_audit(
        session,
        actor_user_id=operator.id if operator is not None else None,
        action="operator.login_failed",
        entity_type="operator",
        entity_id=payload.email,
        details={"email": payload.email},
    )
    raise HTTPException(status_code=401, detail="Invalid email or password")


@app.post("/api/auth/logout")
def logout_operator(
    response: Response,
    session: Session = Depends(get_db),
    current: OperatorUser = Depends(_current_operator),
    license_session: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> dict[str, str]:
    if license_session:
        record = (
            session.query(OperatorSession)
            .filter_by(session_hash=_hash_value(license_session))
            .one_or_none()
        )
        if record is not None:
            session.delete(record)
            session.commit()
    _record_audit(
        session,
        actor_user_id=current.id,
        action="operator.logout",
        entity_type="operator",
        entity_id=str(current.id),
        details={},
    )
    clear_session_cookie(response)
    return {"status": "logged_out"}


@app.get("/api/auth/me", response_model=OperatorUserResponse)
def current_operator(current: OperatorUser = Depends(_current_operator)) -> OperatorUserResponse:
    return _operator_to_response(current)


@app.get("/api/admin/operators", response_model=list[OperatorUserResponse])
def list_operators(
    session: Session = Depends(get_db),
    _: OperatorUser = Depends(require_operator("admin")),
) -> list[OperatorUserResponse]:
    users = session.query(OperatorUser).order_by(OperatorUser.created_at).all()
    return [_operator_to_response(user) for user in users]


@app.post(
    "/api/admin/operators",
    response_model=OperatorUserResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_operator(
    payload: OperatorCreateRequest,
    session: Session = Depends(get_db),
    current: OperatorUser = Depends(require_operator("admin")),
) -> OperatorUserResponse:
    if session.query(OperatorUser).filter_by(email=payload.email).one_or_none():
        raise HTTPException(status_code=409, detail="Operator already exists")
    operator = OperatorUser(
        email=payload.email,
        name=payload.name,
        role=payload.role,
        auth_provider="local",
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    session.add(operator)
    session.commit()
    session.refresh(operator)
    _record_audit(
        session,
        actor_user_id=current.id,
        action="operator.created",
        entity_type="operator",
        entity_id=str(operator.id),
        details={"email": operator.email, "role": operator.role},
    )
    return _operator_to_response(operator)


@app.patch("/api/admin/operators/{operator_id}", response_model=OperatorUserResponse)
def update_operator(
    operator_id: int,
    payload: OperatorUpdateRequest,
    session: Session = Depends(get_db),
    current: OperatorUser = Depends(require_operator("admin")),
) -> OperatorUserResponse:
    operator = session.get(OperatorUser, operator_id)
    if operator is None:
        raise HTTPException(status_code=404, detail="Operator not found")
    next_role = payload.role if payload.role is not None else operator.role
    next_is_active = payload.is_active if payload.is_active is not None else operator.is_active
    _assert_admin_floor(
        session,
        operator=operator,
        next_role=next_role,
        next_is_active=next_is_active,
    )
    if payload.name is not None:
        operator.name = payload.name
    if payload.role is not None:
        operator.role = payload.role
    if payload.is_active is not None:
        operator.is_active = payload.is_active
    if payload.password:
        if operator.auth_provider != "local":
            raise HTTPException(
                status_code=400,
                detail="Passwords can only be set for local operators",
            )
        operator.password_hash = hash_password(payload.password)
    operator.updated_at = _now()
    session.add(operator)
    session.commit()
    session.refresh(operator)
    _record_audit(
        session,
        actor_user_id=current.id,
        action="operator.updated",
        entity_type="operator",
        entity_id=str(operator.id),
        details=payload.model_dump(exclude_unset=True),
    )
    return _operator_to_response(operator)


@app.get("/api/admin/directory-config", response_model=DirectoryConfigResponse)
def get_directory_config(
    session: Session = Depends(get_db),
    _: OperatorUser = Depends(require_operator("admin")),
) -> DirectoryConfigResponse:
    return _directory_to_response(_get_directory_config(session))


@app.put("/api/admin/directory-config", response_model=DirectoryConfigResponse)
def update_directory_config(
    payload: DirectoryConfigRequest,
    session: Session = Depends(get_db),
    current: OperatorUser = Depends(require_operator("admin")),
) -> DirectoryConfigResponse:
    record = _get_directory_config(session)
    if record is None:
        record = DirectoryConfig()
    for field in [
        "enabled",
        "server_uri",
        "bind_dn",
        "user_base_dn",
        "user_filter",
        "group_base_dn",
        "admin_group_dn",
        "viewer_group_dn",
        "use_ssl",
        "start_tls",
    ]:
        setattr(record, field, getattr(payload, field))
    if payload.bind_password is not None:
        record.encrypted_bind_password = (
            encrypt_config_value(payload.bind_password) if payload.bind_password else None
        )
    record.updated_at = _now()
    session.add(record)
    session.commit()
    _record_audit(
        session,
        actor_user_id=current.id,
        action="directory.updated",
        entity_type="directory_config",
        entity_id=str(record.id),
        details={"enabled": record.enabled, "server_uri": record.server_uri},
    )
    return _directory_to_response(record)


@app.post("/api/admin/directory-config/test-connection")
def test_directory_connection(
    session: Session = Depends(get_db),
    _: OperatorUser = Depends(require_operator("admin")),
) -> dict[str, str]:
    record = _get_directory_config(session)
    if record is None:
        raise HTTPException(status_code=404, detail="Directory configuration not found")
    try:
        connection = _ldap_connection(record)
        connection.unbind()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Connection test failed: {exc}") from exc
    return {"status": "ok"}


@app.post("/api/admin/directory-config/test-login")
def test_directory_login(
    payload: DirectoryLoginTestRequest,
    session: Session = Depends(get_db),
    _: OperatorUser = Depends(require_operator("admin")),
) -> dict[str, str]:
    record = _get_directory_config(session)
    if record is None or not record.enabled:
        raise HTTPException(status_code=400, detail="Directory login is not enabled")
    name, role = _ldap_lookup_and_authenticate(
        record,
        email=payload.email,
        password=payload.password,
    )
    return {"status": "ok", "name": name, "role": role}


@app.get("/api/admin/keys", response_model=PagedLicenseKeysResponse)
def list_keys(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=settings.key_list_default_page_size,
        ge=1,
        le=settings.key_list_max_page_size,
    ),
    organization: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    license_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    session: Session = Depends(get_db),
    _: OperatorUser = Depends(require_operator()),
) -> PagedLicenseKeysResponse:
    effective_status = _effective_status_expression()
    query = session.query(LicenseKey)
    if organization:
        query = query.filter(LicenseKey.organization.ilike(f"%{organization}%"))
    if status_filter:
        query = query.filter(effective_status == status_filter)
    if license_type:
        query = query.filter(LicenseKey.license_type == license_type)
    if search:
        query = query.filter(
            (LicenseKey.organization.ilike(f"%{search}%"))
            | (LicenseKey.key_prefix.ilike(f"%{search}%"))
        )
    total = query.count()
    items = (
        query.order_by(LicenseKey.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PagedLicenseKeysResponse(
        items=[_license_to_response(item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@app.get("/api/admin/keys/export.csv")
def export_keys_csv(
    session: Session = Depends(get_db),
    _: OperatorUser = Depends(require_operator()),
) -> StreamingResponse:
    rows = session.query(LicenseKey).order_by(LicenseKey.created_at.desc()).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "id",
            "key_prefix",
            "organization",
            "license_type",
            "status",
            "created_at",
            "expires_at",
            "max_seats",
            "verification_count",
            "last_verified_at",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                row.id,
                row.key_prefix,
                row.organization,
                row.license_type,
                _effective_license_status(row),
                row.created_at.isoformat(),
                row.expires_at.isoformat() if row.expires_at else "",
                row.max_seats or "",
                row.verification_count,
                row.last_verified_at.isoformat() if row.last_verified_at else "",
            ]
        )
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="vigilweave-license-keys.csv"'},
    )


@app.get("/api/admin/keys/{key_id}", response_model=LicenseKeyResponse)
def get_key(
    key_id: int,
    session: Session = Depends(get_db),
    _: OperatorUser = Depends(require_operator()),
) -> LicenseKeyResponse:
    record = session.get(LicenseKey, key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="License key not found")
    return _license_to_response(record)


@app.get("/api/admin/keys/{key_id}/verifications", response_model=list[VerificationLogResponse])
def list_verifications(
    key_id: int,
    session: Session = Depends(get_db),
    _: OperatorUser = Depends(require_operator()),
) -> list[VerificationLogResponse]:
    rows = (
        session.query(VerificationLog)
        .filter(VerificationLog.license_key_id == key_id)
        .order_by(VerificationLog.verified_at.desc())
        .limit(200)
        .all()
    )
    return [
        VerificationLogResponse(
            id=row.id,
            attempted_prefix=row.attempted_prefix,
            instance_id=row.instance_id,
            ip_address=row.ip_address,
            verified_at=row.verified_at,
            success=row.success,
            error_message=row.error_message,
        )
        for row in rows
    ]


@app.post(
    "/api/admin/keys/generate",
    response_model=GenerateKeyResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_key(
    payload: GenerateKeyRequest,
    session: Session = Depends(get_db),
    current: OperatorUser = Depends(require_operator("admin")),
) -> GenerateKeyResponse:
    return _issue_license(session, actor=current, request=payload)


@app.patch("/api/admin/keys/{key_id}", response_model=LicenseKeyResponse)
def update_key(
    key_id: int,
    payload: LicenseKeyUpdateRequest,
    session: Session = Depends(get_db),
    current: OperatorUser = Depends(require_operator("admin")),
) -> LicenseKeyResponse:
    record = session.get(LicenseKey, key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="License key not found")
    if payload.expires_at is not None:
        record.expires_at = payload.expires_at
    if payload.max_seats is not None:
        record.max_seats = payload.max_seats
    if payload.notes is not None:
        record.notes = payload.notes
    if payload.customer_metadata is not None:
        record.customer_metadata = payload.customer_metadata
    record.updated_by_user_id = current.id
    record.updated_at = _now()
    session.add(record)
    session.commit()
    session.refresh(record)
    _record_audit(
        session,
        actor_user_id=current.id,
        action="license.updated",
        entity_type="license_key",
        entity_id=str(record.id),
        details=payload.model_dump(exclude_unset=True),
    )
    return _license_to_response(record)


@app.post("/api/admin/keys/{key_id}/revoke", response_model=LicenseKeyResponse)
def revoke_key(
    key_id: int,
    payload: RevokeKeyRequest,
    session: Session = Depends(get_db),
    current: OperatorUser = Depends(require_operator("admin")),
) -> LicenseKeyResponse:
    record = session.get(LicenseKey, key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="License key not found")
    record.status = "revoked"
    record.revoked_reason = payload.reason
    record.updated_by_user_id = current.id
    record.updated_at = _now()
    session.add(record)
    session.commit()
    session.refresh(record)
    _record_audit(
        session,
        actor_user_id=current.id,
        action="license.revoked",
        entity_type="license_key",
        entity_id=str(record.id),
        details={"reason": payload.reason},
    )
    return _license_to_response(record)


@app.post("/api/admin/keys/{key_id}/reactivate", response_model=LicenseKeyResponse)
def reactivate_key(
    key_id: int,
    session: Session = Depends(get_db),
    current: OperatorUser = Depends(require_operator("admin")),
) -> LicenseKeyResponse:
    record = session.get(LicenseKey, key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="License key not found")
    if record.status != "revoked" or record.replaced_by_license_id is not None:
        raise HTTPException(status_code=400, detail="Only revoked keys can be reactivated")
    normalized_expiry = _normalize_datetime(record.expires_at)
    if normalized_expiry and normalized_expiry <= _now():
        raise HTTPException(status_code=400, detail="Expired keys cannot be reactivated")
    record.status = "active"
    record.revoked_reason = None
    record.updated_by_user_id = current.id
    record.updated_at = _now()
    session.add(record)
    session.commit()
    session.refresh(record)
    _record_audit(
        session,
        actor_user_id=current.id,
        action="license.reactivated",
        entity_type="license_key",
        entity_id=str(record.id),
        details={},
    )
    return _license_to_response(record)


@app.post("/api/admin/keys/{key_id}/reissue", response_model=GenerateKeyResponse)
def reissue_key(
    key_id: int,
    payload: ReissueKeyRequest,
    session: Session = Depends(get_db),
    current: OperatorUser = Depends(require_operator("admin")),
) -> GenerateKeyResponse:
    record = session.get(LicenseKey, key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="License key not found")
    request = GenerateKeyRequest(
        license_type=record.license_type,
        organization=record.organization,
        expires_days=payload.expires_days,
        max_seats=payload.max_seats if payload.max_seats is not None else record.max_seats,
        notes=payload.notes if payload.notes is not None else record.notes,
        customer_metadata=(
            payload.customer_metadata
            if payload.customer_metadata is not None
            else record.customer_metadata
        ),
    )
    replacement = _issue_license(session, actor=current, request=request)
    record.status = "replaced"
    record.replaced_by_license_id = replacement.record.id
    record.updated_by_user_id = current.id
    record.updated_at = _now()
    session.add(record)
    session.commit()
    _record_audit(
        session,
        actor_user_id=current.id,
        action="license.reissued",
        entity_type="license_key",
        entity_id=str(record.id),
        details={"replacement_id": replacement.record.id},
    )
    return replacement


@app.post("/v1/fulfillment/issue", response_model=GenerateKeyResponse)
def fulfill_license_issue(
    payload: GenerateKeyRequest,
    session: Session = Depends(get_db),
    _: None = Depends(require_fulfillment_auth),
) -> GenerateKeyResponse:
    """Issue a commercial key for an external paid fulfillment flow."""

    return _issue_license(session, actor=None, request=payload)


@app.post("/v1/fulfillment/licenses/{key_id}/revoke", response_model=LicenseKeyResponse)
def fulfill_license_revoke(
    key_id: int,
    payload: RevokeKeyRequest,
    session: Session = Depends(get_db),
    _: None = Depends(require_fulfillment_auth),
) -> LicenseKeyResponse:
    """Revoke a previously issued commercial key from an external fulfillment flow."""

    record = session.get(LicenseKey, key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="License key not found")

    record.status = "revoked"
    record.revoked_reason = payload.reason or "Fulfillment revoke requested"
    record.updated_at = _now()
    session.add(record)
    session.commit()
    session.refresh(record)
    _record_audit(
        session,
        actor_user_id=None,
        action="license.fulfillment_revoked",
        entity_type="license_key",
        entity_id=str(record.id),
        details={"key_prefix": record.key_prefix, "reason": record.revoked_reason},
    )
    return _license_to_response(record)


@app.post("/v1/fulfillment/licenses/{key_id}/reactivate", response_model=LicenseKeyResponse)
def fulfill_license_reactivate(
    key_id: int,
    session: Session = Depends(get_db),
    _: None = Depends(require_fulfillment_auth),
) -> LicenseKeyResponse:
    """Reactivate a previously revoked commercial key from an external fulfillment flow."""

    record = session.get(LicenseKey, key_id)
    if record is None:
        raise HTTPException(status_code=404, detail="License key not found")

    record.status = "active"
    record.revoked_reason = None
    record.updated_at = _now()
    session.add(record)
    session.commit()
    session.refresh(record)
    _record_audit(
        session,
        actor_user_id=None,
        action="license.fulfillment_reactivated",
        entity_type="license_key",
        entity_id=str(record.id),
        details={"key_prefix": record.key_prefix},
    )
    return _license_to_response(record)


@app.post("/api/admin/keys/bulk")
def bulk_key_action(
    payload: BulkKeyActionRequest,
    session: Session = Depends(get_db),
    current: OperatorUser = Depends(require_operator("admin")),
) -> dict[str, int]:
    updated = 0
    for key_id in payload.key_ids:
        record = session.get(LicenseKey, key_id)
        if record is None:
            continue
        if payload.action == "revoke" and record.status == "active":
            record.status = "revoked"
            record.revoked_reason = payload.reason
            updated += 1
        elif payload.action == "reactivate" and record.status == "revoked":
            normalized_expiry = _normalize_datetime(record.expires_at)
            if record.replaced_by_license_id is None and (
                not normalized_expiry or normalized_expiry > _now()
            ):
                record.status = "active"
                record.revoked_reason = None
                updated += 1
        record.updated_by_user_id = current.id
        record.updated_at = _now()
        session.add(record)
    session.commit()
    _record_audit(
        session,
        actor_user_id=current.id,
        action=f"license.bulk_{payload.action}",
        entity_type="license_key",
        entity_id="bulk",
        details={"key_ids": payload.key_ids, "updated": updated, "reason": payload.reason},
    )
    return {"updated": updated}


@app.get("/api/admin/stats")
def get_stats(
    session: Session = Depends(get_db),
    _: OperatorUser = Depends(require_operator()),
) -> dict[str, Any]:
    effective_status = _effective_status_expression()
    type_counts = (
        session.query(LicenseKey.license_type, effective_status, func.count(LicenseKey.id))
        .group_by(LicenseKey.license_type, effective_status)
        .all()
    )
    yesterday = _now() - timedelta(days=1)
    recent_total = (
        session.query(func.count(VerificationLog.id))
        .filter(VerificationLog.verified_at >= yesterday)
        .scalar()
        or 0
    )
    recent_success = (
        session.query(func.count(VerificationLog.id))
        .filter(VerificationLog.verified_at >= yesterday, VerificationLog.success.is_(True))
        .scalar()
        or 0
    )
    return {
        "total_keys": session.query(func.count(LicenseKey.id)).scalar() or 0,
        "by_type_and_status": [
            {"type": license_type, "status": status_value, "count": count}
            for license_type, status_value, count in type_counts
        ],
        "recent_verifications": {
            "total": recent_total,
            "successful": recent_success,
            "failed": recent_total - recent_success,
        },
        "operators": session.query(func.count(OperatorUser.id)).scalar() or 0,
    }


@app.get("/api/admin/audit-logs", response_model=PagedAuditLogsResponse)
def list_audit_logs(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(
        default=settings.key_list_default_page_size,
        ge=1,
        le=settings.key_list_max_page_size,
    ),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    session: Session = Depends(get_db),
    _: OperatorUser = Depends(require_operator()),
) -> PagedAuditLogsResponse:
    query = session.query(OperatorAuditLog)
    if action:
        query = query.filter(OperatorAuditLog.action == action)
    if entity_type:
        query = query.filter(OperatorAuditLog.entity_type == entity_type)
    total = query.count()
    items = (
        query.order_by(OperatorAuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return PagedAuditLogsResponse(
        items=[_audit_to_response(session, item) for item in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@app.post("/v1/verify", response_model=VerificationResponse)
def verify_license(
    payload: VerificationRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> VerificationResponse:
    enforce_rate_limit(
        request,
        RateLimitConfig(
            settings.verify_rate_limit_max_requests,
            settings.verify_rate_limit_window_seconds,
        ),
        resource="license verification",
    )
    return _verify_license_record(session, payload, request)


@app.get("/{path_name:path}", response_model=None)
def serve_spa(path_name: str) -> FileResponse | dict[str, str]:
    del path_name
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "License server API", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
