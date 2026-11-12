"""Repository history and blame response models."""

from datetime import datetime

from sqlmodel import SQLModel

from app.models.scan import ScanStatus


class RepositoryHistoryPoint(SQLModel):
    """Single point in repository scan history."""

    scan_id: int
    started_at: datetime
    completed_at: datetime | None = None
    status: ScanStatus
    total_findings: int
    critical_findings: int
    high_findings: int
    medium_findings: int
    low_findings: int
    info_findings: int
    quality_score: float | None = None
    quality_gate_passed: bool | None = None


class RepositoryHistoryResponse(SQLModel):
    """Repository scan history response."""

    repo: str
    total_scans: int
    points: list[RepositoryHistoryPoint]


class RepositoryBlameRequest(SQLModel):
    """Request payload for git blame lookup."""

    repo: str
    file_path: str
    line: int
    branch: str | None = None
    commit: str | None = None


class RepositoryBlameResponse(SQLModel):
    """Single-line git blame response."""

    repo: str
    file_path: str
    line: int
    commit: str
    author: str
    author_email: str
    authored_at_unix: int
    summary: str
