"""System-level response models."""

from datetime import datetime

from sqlmodel import Field, SQLModel


class CapabilityResponse(SQLModel):
    """System capability contract."""

    version: str
    authentication: dict[str, bool | str] = Field(default_factory=dict)
    scan_types: list[str] = Field(default_factory=list)
    integrations: dict[str, bool] = Field(default_factory=dict)
    ide: dict[str, bool] = Field(default_factory=dict)
    tooling: dict[str, bool] = Field(default_factory=dict)
    languages: list[str] = Field(default_factory=list)
    runtime: dict[str, object] = Field(default_factory=dict)
    tooling_profiles: dict[str, list[str]] = Field(default_factory=dict)
    host_requirements: dict[str, str] = Field(default_factory=dict)
    license: dict[str, object] = Field(default_factory=dict)


class SystemMetricsResponse(SQLModel):
    """In-memory observability metrics snapshot."""

    started_at: datetime
    uptime_seconds: float
    counters: dict[str, int] = Field(default_factory=dict)
    timers: dict[str, dict[str, float | int]] = Field(default_factory=dict)


class ToolTelemetryRow(SQLModel):
    """Aggregated persisted tool telemetry."""

    tool: str
    total_runs: int
    completed_runs: int
    failed_runs: int
    skipped_runs: int
    avg_findings: float
    avg_duration_seconds: float | None = None
