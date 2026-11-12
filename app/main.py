"""FastAPI application entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.auth_workos import router as auth_workos_router
from app.api.billing import router as billing_router
from app.api.ide import router as ide_router
from app.api.integrations import router as integrations_router
from app.api.policies import router as policies_router
from app.api.projects import router as projects_router
from app.api.repositories import router as repositories_router
from app.api.saas_admin import router as saas_admin_router
from app.api.scans import router as scans_router
from app.api.scm_connections import router as scm_connections_router
from app.api.system import router as system_router
from app.api.tool_configs import router as tool_configs_router
from app.api.webhooks import router as webhooks_router
from app.core.config import settings
from app.core.csrf import enforce_csrf_if_session, should_enforce_csrf
from app.core.database import init_db
from app.core.logging import setup_logging
from app.core.migrations import migrate_sqlite_database
from app.core.runtime_checks import readiness_report
from app.core.workos_session import session_secret_configured


def _validate_production_secrets() -> None:
    """Fail fast if critical secrets are missing outside dev/test."""
    if settings.environment in {"development", "test"}:
        return
    if not session_secret_configured():
        raise RuntimeError(
            "SESSION_SECRET or legacy WORKOS_SESSION_SECRET must be set in "
            "non-development environments. "
            "Sessions and SCM token encryption depend on this value."
        )
    if settings.license_key and settings.license_key.startswith("vw-ent-offline-"):
        if not settings.offline_license_secret:
            raise RuntimeError(
                "OFFLINE_LICENSE_SECRET must be set when validating offline enterprise licenses "
                "outside development/test environments."
            )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize application resources."""

    setup_logging()
    _validate_production_secrets()
    migrate_sqlite_database()
    init_db()
    yield


app = FastAPI(title="VigilWeave", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-VigilWeave-Tenant",
        "X-VigilWeave-Actor",
        "X-CSRF-Token",
        "X-Requested-With",
    ],
)


@app.get("/health")
def healthcheck() -> dict[str, str]:
    """Health endpoint."""

    return {"status": "ok"}


@app.get("/ready")
def readiness() -> JSONResponse:
    """Readiness endpoint that verifies core runtime dependencies."""

    report = readiness_report()
    status_code = 200 if report["status"] == "ok" else 503
    return JSONResponse(report, status_code=status_code)


@app.middleware("http")
async def enforce_request_size_limit(request: Request, call_next):
    """Reject oversized request bodies before they hit handlers."""

    content_length = request.headers.get("content-length")
    if request.method in {"POST", "PUT", "PATCH"} and content_length:
        try:
            if int(content_length) > settings.max_request_body_bytes:
                return JSONResponse(
                    {"detail": "Request body is too large"},
                    status_code=413,
                )
        except ValueError:
            pass
    return await call_next(request)


@app.middleware("http")
async def enforce_csrf_for_session_mutations(request: Request, call_next):
    """Apply CSRF validation globally for session-authenticated API mutations."""

    try:
        if should_enforce_csrf(request):
            enforce_csrf_if_session(request)
    except HTTPException as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    return await call_next(request)


app.include_router(scans_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix=settings.api_v1_prefix)
app.include_router(auth_workos_router, prefix=settings.api_v1_prefix)
app.include_router(billing_router, prefix=settings.api_v1_prefix)
app.include_router(policies_router, prefix=settings.api_v1_prefix)
app.include_router(integrations_router, prefix=settings.api_v1_prefix)
app.include_router(ide_router, prefix=settings.api_v1_prefix)
app.include_router(system_router, prefix=settings.api_v1_prefix)
app.include_router(repositories_router, prefix=settings.api_v1_prefix)
app.include_router(saas_admin_router, prefix=settings.api_v1_prefix)
app.include_router(tool_configs_router, prefix=settings.api_v1_prefix)
app.include_router(projects_router, prefix=settings.api_v1_prefix)
app.include_router(scm_connections_router, prefix=settings.api_v1_prefix)
app.include_router(webhooks_router, prefix=settings.api_v1_prefix)
