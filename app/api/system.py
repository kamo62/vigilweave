"""System-level endpoints."""

from fastapi import APIRouter, Depends
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlmodel import Session, select

from app.core.config import settings
from app.core.database import get_session
from app.core.licensing import get_license
from app.core.metrics import snapshot_metrics
from app.core.runtime_checks import readiness_report
from app.core.security import (
    anonymous_bootstrap_enabled,
    bootstrap_registration_required,
    maybe_get_principal,
    require_scope,
)
from app.core.workos_session import workos_auth_configured
from app.models import (
    CapabilityResponse,
    Scan,
    SystemMetricsResponse,
    ToolExecution,
    ToolTelemetryRow,
)
from app.services.github_app import github_app_configured
from app.services.tool_adapters import get_runtime_tool_capabilities

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
def get_system_health() -> dict[str, object]:
    """Return dependency-aware system health details."""

    return readiness_report()


@router.get("/capabilities", response_model=CapabilityResponse)
def get_capabilities(
    session: Session = Depends(get_session),
    principal=Depends(maybe_get_principal),
) -> CapabilityResponse:
    """Return the current server capability contract."""

    license_info = get_license(principal.tenant_slug if principal else None)
    distribution_mode = settings.resolved_distribution_mode()
    enterprise_tooling_available = distribution_mode != "community"
    tooling_profiles = {
        "base": [
            "gitleaks",
            "semgrep",
            "bandit",
            "ruff",
            "eslint",
            "checkov",
            "tflint",
            "cfn-lint",
            "trivy",
            "sqlfluff",
        ],
        "host_only": [],
    }
    if enterprise_tooling_available:
        tooling_profiles["enterprise"] = [
            "gitleaks",
            "semgrep",
            "bandit",
            "ruff",
            "eslint",
            "checkov",
            "tflint",
            "cfn-lint",
            "trivy",
            "sqlfluff",
            "swiftlint",
            "detekt",
            "android-lint",
            "dotnet-analyzers",
        ]

    host_requirements = {
        "tflint": "Bundled in the base linux/arm64 image for Terraform linting.",
        "cfn-lint": "Bundled in the base linux/arm64 image for CloudFormation linting.",
    }
    if enterprise_tooling_available:
        host_requirements.update(
            {
                "swiftlint": "Bundled in the enterprise linux/arm64 image.",
                "android-lint": (
                    "Disabled by default for safety. Set ENABLE_REPO_BUILD_TOOL_ADAPTERS=true "
                    "to opt in. Requires a Gradle wrapper in the repository; the enterprise "
                    "image bundles Java, Android SDK cmdline tools, and Detekt."
                ),
                "dotnet-analyzers": (
                    "Disabled by default for safety. Set ENABLE_REPO_BUILD_TOOL_ADAPTERS=true "
                    "to opt in. Requires a .sln or .csproj in the repository; the enterprise "
                    "image bundles the .NET SDK."
                ),
            }
        )

    return CapabilityResponse(
        version="2.0.0",
        authentication={
            "api_keys": settings.resolved_api_keys_enabled(),
            "anonymous_bootstrap": anonymous_bootstrap_enabled(session),
            "bootstrap_registration_required": bootstrap_registration_required(session),
            "tenant_headers": True,
            "auth_mode": settings.resolved_auth_mode(),
            "session_auth_provider": settings.resolved_session_auth_provider(),
            "saas_enabled": settings.saas_enabled,
            "workos_configured": workos_auth_configured(),
        },
        scan_types=["comprehensive", "fast", "security-only", "custom"],
        integrations={
            "azure_devops": True,
            "azure_marketplace_extension": True,
            "github_app": github_app_configured() and bool(settings.github_webhook_secret),
            "prisma_cloud": True,
            "sonarqube": True,
        },
        ide={"vscode": True, "analyze_endpoint": True},
        tooling=get_runtime_tool_capabilities(),
        languages=[
            "python",
            "javascript",
            "typescript",
            "go",
            "terraform",
            "cloudformation",
            "yaml",
            "dockerfile",
            "sql",
            "plsql",
            "swift",
            "kotlin",
            "java",
            "xml",
            "csharp",
            "php",
            "ruby",
            "rust",
        ],
        runtime={
            "profile": settings.toolchain_profile,
            "platforms": ["linux/arm64"],
            "distribution_mode": distribution_mode,
            "commercial_activation_enabled": settings.commercial_activation_enabled(),
            "enterprise_image_available": enterprise_tooling_available,
        },
        tooling_profiles=tooling_profiles,
        license={
            "tier": license_info.tier.value,
            "features": sorted(f.value for f in license_info.features),
            "organization": license_info.organization,
        },
        host_requirements=host_requirements,
    )


@router.get("/metrics/prometheus")
def get_prometheus_metrics(principal=Depends(require_scope("admin"))) -> str:
    """Return metrics in Prometheus exposition format for scraping."""

    from fastapi.responses import PlainTextResponse

    del principal
    snapshot = snapshot_metrics()
    uptime_block = (
        "# HELP vigilweave_uptime_seconds Seconds since process start\n"
        "# TYPE vigilweave_uptime_seconds gauge\n"
        f"vigilweave_uptime_seconds {snapshot['uptime_seconds']}\n"
    )
    return PlainTextResponse(
        uptime_block + generate_latest().decode("utf-8"),
        media_type=CONTENT_TYPE_LATEST,
    )


@router.get("/metrics", response_model=SystemMetricsResponse)
def get_system_metrics(principal=Depends(require_scope("admin"))) -> SystemMetricsResponse:
    """Return process-level metric counters and timers."""

    del principal
    snapshot = snapshot_metrics()
    started_at = snapshot["started_at"]
    if isinstance(started_at, str):
        from datetime import datetime

        started_at = datetime.fromisoformat(started_at)
    return SystemMetricsResponse(
        started_at=started_at,
        uptime_seconds=float(snapshot["uptime_seconds"]),
        counters={key: int(value) for key, value in snapshot["counters"].items()},
        timers={
            key: {
                "count": int(values["count"]),
                "avg": float(values["avg"]),
                "max": float(values["max"]),
                "sum": float(values["sum"]),
            }
            for key, values in snapshot["timers"].items()
        },
    )


@router.get("/tool-telemetry", response_model=list[ToolTelemetryRow])
def get_tool_telemetry(
    session: Session = Depends(get_session),
    principal=Depends(require_scope("scan:read")),
) -> list[ToolTelemetryRow]:
    """Return tenant-scoped aggregated per-tool execution telemetry."""

    rows = list(
        session.exec(
            select(ToolExecution, Scan).where(
                ToolExecution.scan_id == Scan.id,
                Scan.tenant_slug == principal.tenant_slug,
            )
        ).all()
    )

    aggregates: dict[str, dict[str, float | int]] = {}
    for execution, scan in rows:
        del scan
        bucket = aggregates.setdefault(
            execution.tool,
            {
                "total_runs": 0,
                "completed_runs": 0,
                "failed_runs": 0,
                "skipped_runs": 0,
                "findings_sum": 0.0,
                "duration_sum": 0.0,
                "duration_count": 0,
            },
        )
        bucket["total_runs"] = int(bucket["total_runs"]) + 1
        bucket["findings_sum"] = float(bucket["findings_sum"]) + execution.findings_count
        status = str(execution.status)
        if status == "completed":
            bucket["completed_runs"] = int(bucket["completed_runs"]) + 1
        elif status == "failed":
            bucket["failed_runs"] = int(bucket["failed_runs"]) + 1
        elif status == "skipped":
            bucket["skipped_runs"] = int(bucket["skipped_runs"]) + 1

        if execution.started_at and execution.completed_at:
            duration = (execution.completed_at - execution.started_at).total_seconds()
            if duration >= 0:
                bucket["duration_sum"] = float(bucket["duration_sum"]) + duration
                bucket["duration_count"] = int(bucket["duration_count"]) + 1

    response: list[ToolTelemetryRow] = []
    for tool in sorted(aggregates):
        aggregate = aggregates[tool]
        total_runs = int(aggregate["total_runs"])
        duration_count = int(aggregate["duration_count"])
        avg_duration = float(aggregate["duration_sum"]) / duration_count if duration_count else None
        response.append(
            ToolTelemetryRow(
                tool=tool,
                total_runs=total_runs,
                completed_runs=int(aggregate["completed_runs"]),
                failed_runs=int(aggregate["failed_runs"]),
                skipped_runs=int(aggregate["skipped_runs"]),
                avg_findings=round(float(aggregate["findings_sum"]) / max(total_runs, 1), 2),
                avg_duration_seconds=round(avg_duration, 3) if avg_duration is not None else None,
            )
        )
    return response
