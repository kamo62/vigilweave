"""Scan and tool execution models."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel

from app.models.file_metrics import FileMetricsPublic

if TYPE_CHECKING:
    from app.models.file_metrics import FileMetrics
    from app.models.finding import Finding


class ScanType(StrEnum):
    """Supported scan modes."""

    COMPREHENSIVE = "comprehensive"
    FAST = "fast"
    SECURITY_ONLY = "security-only"
    CUSTOM = "custom"


class ScanStatus(StrEnum):
    """Scan lifecycle states."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanAssignmentStatus(StrEnum):
    """How a scan is associated with project inventory."""

    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"


class ToolExecutionStatus(StrEnum):
    """Per-tool execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ScanBase(SQLModel):
    """Shared scan fields."""

    tenant_slug: str = Field(default="default", index=True)
    repo: str = Field(index=True)
    branch: str | None = None
    commit: str | None = None
    source: str = Field(default="native", index=True)
    scan_type: ScanType = Field(default=ScanType.COMPREHENSIVE, index=True)
    status: ScanStatus = Field(default=ScanStatus.QUEUED, index=True)
    include_quality_metrics: bool = True
    quality_gate_passed: bool | None = None
    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    info_findings: int = 0
    quality_score: float | None = None
    complexity_score: float | None = None
    maintainability_score: float | None = None
    style_score: float | None = None
    quality_grade: str | None = None
    technical_debt_minutes: int | None = None
    avg_cyclomatic_complexity: float | None = None
    max_cyclomatic_complexity: int | None = None
    maintainability_index: float | None = None
    duplication_percentage: float | None = None
    quality_issues: int = 0
    style_issues: int = 0
    complexity_issues: int = 0
    suppressed_findings: int = 0


class Scan(ScanBase, table=True):
    """Persisted scan."""

    __tablename__ = "scans"

    id: int | None = Field(default=None, primary_key=True)
    project_id: int | None = Field(
        default=None, foreign_key="projects.id", index=True, ondelete="SET NULL"
    )
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    scan_metadata: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))

    findings: list["Finding"] = Relationship(
        back_populates="scan", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    file_metrics: list["FileMetrics"] = Relationship(
        back_populates="scan", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    tool_executions: list["ToolExecution"] = Relationship(
        back_populates="scan", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class ToolExecutionBase(SQLModel):
    """Shared per-tool execution fields."""

    tool: str = Field(index=True)
    status: ToolExecutionStatus = Field(default=ToolExecutionStatus.PENDING, index=True)
    findings_count: int = 0
    stdout_summary: str | None = None
    stderr_summary: str | None = None
    version: str | None = None


class ToolExecution(ToolExecutionBase, table=True):
    """Persisted per-tool execution record."""

    __tablename__ = "tool_executions"

    id: int | None = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scans.id", index=True, ondelete="CASCADE")
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None

    scan: Optional["Scan"] = Relationship(back_populates="tool_executions")


class ScanCreate(SQLModel):
    """Scan creation payload."""

    repo: str
    project_key: str | None = None
    branch: str | None = None
    commit: str | None = None
    scan_type: ScanType = ScanType.COMPREHENSIVE
    tools: list[str] | None = None
    include_quality_metrics: bool = True


class ToolExecutionPublic(ToolExecutionBase):
    """Per-tool execution response."""

    id: int
    scan_id: int
    started_at: datetime
    completed_at: datetime | None = None


class ScanPublic(ScanBase):
    """Scan response payload."""

    id: int
    project_id: int | None = None
    project_key: str | None = None
    assignment_status: ScanAssignmentStatus = ScanAssignmentStatus.UNASSIGNED
    started_at: datetime
    completed_at: datetime | None = None
    scan_metadata: dict[str, Any] | None = None
    tool_executions: list[ToolExecutionPublic] = Field(default_factory=list)


class FindingStats(SQLModel):
    """Aggregate finding statistics."""

    total_findings: int = 0
    critical_findings: int = 0
    high_findings: int = 0
    medium_findings: int = 0
    low_findings: int = 0
    info_findings: int = 0
    by_category: dict[str, int] = {}
    by_tool: dict[str, int] = {}


class QualityMetricsResponse(SQLModel):
    """Quality summary response."""

    scan_id: int
    quality_score: float | None = None
    quality_grade: str | None = None
    complexity_score: float | None = None
    maintainability_score: float | None = None
    style_score: float | None = None
    avg_cyclomatic_complexity: float | None = None
    max_cyclomatic_complexity: int | None = None
    duplication_percentage: float | None = None
    maintainability_index: float | None = None
    technical_debt_minutes: int | None = None
    quality_issues: int = 0
    style_issues: int = 0
    complexity_issues: int = 0
    files: list[FileMetricsPublic] = Field(default_factory=list)


class RepositorySummary(SQLModel):
    """Repository-level summary for the dashboard."""

    repo: str
    scans: int
    latest_scan_id: int
    latest_status: ScanStatus
    quality_gate_passed: bool | None = None
    total_findings: int = 0
    quality_score: float | None = None
