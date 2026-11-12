"""Application settings."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "VigilWeave"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./vigilweave.db"
    redis_url: str = "redis://localhost:6379/0"
    celery_task_always_eager: bool = True
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
    ]
    max_critical_findings: int = 0
    max_high_findings: int = 5
    min_quality_score: float = 70.0
    max_parallel_tools: int = 4
    toolchain_profile: str = "base"
    rulepacks_path: str = "./data/rulepacks"
    github_webhook_secret: str | None = None
    github_app_id: str | None = None
    github_app_slug: str | None = None
    github_app_private_key: str | None = None
    github_api_url: str = "https://api.github.com"
    github_webhook_tenant: str = "default"
    github_default_scan_type: str = "fast"
    github_check_name: str = "VigilWeave Scan"
    vigilweave_web_base_url: str = "http://localhost:5173"
    vigilweave_api_base_url: str = "http://localhost:8000"
    azure_marketplace_onboarding_enabled: bool = True
    azure_webhook_tenant: str = "default"
    azure_default_scan_type: str = "fast"
    azure_webhook_secret: str | None = None
    playwright_chromium_executable_path: str | None = None
    license_key: str | None = None
    license_server_url: str = "https://license.vigilweave.com/v1/verify"
    license_verify_timeout_seconds: int = 5
    license_cache_ttl_hours: int = 24
    # Secret used to sign/verify Enterprise Offline license keys (HMAC-SHA256).
    # MUST be set to a random value in production. If unset, falls back to a
    # deterministic placeholder derived from the org name (NOT secure).
    offline_license_secret: str | None = None
    # Testing mode - bypasses license verification, grants all features
    license_testing_mode: bool = False
    host_repo_root: str | None = None
    container_repo_root: str = "/workspace"
    enable_file_repo_access: bool = False
    allow_private_scm_base_urls: bool = False

    # --- Timeout configuration ---
    tool_execution_timeout_seconds: int = 600
    git_clone_timeout_seconds: int = 120
    git_blame_timeout_seconds: int = 60
    external_api_timeout_seconds: float = 30.0
    github_api_timeout_seconds: float = 20.0
    azure_api_timeout_seconds: float = 20.0
    allow_http_outbound: bool = False
    max_request_body_bytes: int = 5 * 1024 * 1024
    webhook_max_request_body_bytes: int = 1 * 1024 * 1024
    enable_repo_build_tool_adapters: bool = False

    # --- Rate limiting ---
    rate_limit_pdf_max_requests: int = 10
    rate_limit_pdf_window_seconds: int = 60
    rate_limit_csv_max_requests: int = 30
    rate_limit_csv_window_seconds: int = 60
    rate_limit_auth_max_requests: int = 30
    rate_limit_auth_window_seconds: int = 300
    rate_limit_webhook_max_requests: int = 120
    rate_limit_webhook_window_seconds: int = 60
    rate_limit_cleanup_interval: int = 100

    # --- Pagination defaults ---
    default_scan_list_limit: int = 50
    max_scan_list_limit: int = 500
    default_findings_limit: int = 500
    max_findings_limit: int = 5000
    max_bulk_triage_ids: int = 1000
    default_audit_events_limit: int = 200
    max_audit_events_limit: int = 1000
    max_regex_pattern_length: int = 200

    # --- Observability ---
    metrics_max_keys: int = 10_000

    # --- Authentication ---
    # Legacy compatibility mode: api_key | workos | dual
    auth_mode: Literal["api_key", "workos", "dual"] | None = None

    # Session provider: none | local | workos
    session_auth_provider: Literal["none", "local", "workos"] = "local"
    api_keys_enabled: bool = True
    session_secret: str | None = None
    token_encryption_key: str | None = None

    # Distribution channel / edition packaging.
    # - community: public self-hosted build with commercial activation disabled
    # - commercial: private self-hosted build that can honor paid licensing
    # - saas: hosted VigilWeave cloud runtime
    distribution_mode: Literal["community", "commercial", "saas"] = "commercial"

    # WorkOS AuthKit configuration
    workos_api_key: str | None = None
    workos_client_id: str | None = None
    workos_redirect_uri: str = "http://localhost:8000/api/v1/auth/callback"
    workos_cookie_domain: str | None = None
    workos_session_secret: str | None = None
    workos_jwks_cache_seconds: int = 300

    # SaaS platform settings
    saas_enabled: bool = False
    saas_domain: str = "app.vigilweave.com"
    marketing_domain: str | None = None  # e.g. "https://vigilweave.com" — added to CORS
    saas_bootstrap_platform_admin_emails: list[str] = []
    saas_operator_emails: list[str] = []

    # Paddle billing
    paddle_environment: Literal["sandbox", "production"] = "sandbox"
    paddle_client_token: str | None = None
    paddle_api_key: str | None = None
    paddle_webhook_secret: str | None = None
    paddle_webhook_tolerance_seconds: int = 30
    paddle_price_id_pro: str | None = None
    paddle_price_id_enterprise: str | None = None
    paddle_price_id_self_hosted_pro: str | None = None
    paddle_price_id_self_hosted_enterprise: str | None = None
    license_server_api_base_url: str | None = None
    license_server_shared_secret: str | None = None

    @model_validator(mode="after")
    def include_runtime_allowed_origins(self) -> "Settings":
        """Keep CORS aligned with the configured frontend runtime."""

        origins = list(dict.fromkeys(self.allowed_origins))

        def add_origin(candidate: str | None) -> None:
            if not candidate:
                return
            parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
            if not parsed.scheme or not parsed.netloc:
                return
            origin = f"{parsed.scheme}://{parsed.netloc}"
            if origin not in origins:
                origins.append(origin)

        add_origin(self.vigilweave_web_base_url)
        add_origin(self.saas_domain)
        add_origin(self.marketing_domain)
        self.allowed_origins = origins
        return self

    def resolved_session_auth_provider(self) -> Literal["none", "local", "workos"]:
        """Return the effective browser-session auth provider."""

        if self.auth_mode == "api_key":
            return "none"
        if self.auth_mode in {"workos", "dual"}:
            return "workos"
        return self.session_auth_provider

    def resolved_api_keys_enabled(self) -> bool:
        """Return whether header-based API keys are active."""

        if self.auth_mode in {"api_key", "workos", "dual"}:
            return True
        return self.api_keys_enabled

    def resolved_auth_mode(self) -> str:
        """Return a user-facing auth mode string for capability responses."""

        provider = self.resolved_session_auth_provider()
        api_keys_enabled = self.resolved_api_keys_enabled()

        if provider == "none" and api_keys_enabled:
            return "api_key"
        if provider == "workos" and api_keys_enabled:
            return "dual" if not self.saas_enabled else "workos"
        return provider

    def resolved_distribution_mode(self) -> Literal["community", "commercial", "saas"]:
        """Return the effective runtime distribution mode."""

        if self.saas_enabled:
            return "saas"
        if self.distribution_mode == "saas":
            return "commercial"
        return self.distribution_mode

    def commercial_activation_enabled(self) -> bool:
        """Return whether billing/license activation flows are allowed."""

        return self.resolved_distribution_mode() != "community"

    def is_vigilweave_cloud(self) -> bool:
        """Return whether this runtime is the hosted VigilWeave cloud."""

        if not self.saas_enabled or self.resolved_session_auth_provider() != "workos":
            return False

        hosts: set[str] = set()

        def add_host(candidate: str | None) -> None:
            if not candidate:
                return
            parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
            if parsed.hostname:
                hosts.add(parsed.hostname.lower())

        add_host(self.vigilweave_web_base_url)
        add_host(self.vigilweave_api_base_url)
        add_host(self.saas_domain)
        add_host(self.marketing_domain)

        return any(host == "vigilweave.com" or host.endswith(".vigilweave.com") for host in hosts)

    def platform_admin_bootstrap_emails(self) -> set[str]:
        """Return normalized bootstrap emails for persistent platform admin seeding."""

        return {
            email.strip().lower()
            for email in [*self.saas_bootstrap_platform_admin_emails, *self.saas_operator_emails]
            if email.strip()
        }


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""

    return Settings()


settings = get_settings()
