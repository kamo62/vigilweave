"""Models for IDE-oriented analysis requests."""

from sqlmodel import Field, SQLModel

from app.models.file_metrics import FileMetricsPublic
from app.models.finding import FindingPublic
from app.models.scan import ScanPublic, ScanType


class IdeFile(SQLModel):
    """File payload sent from an IDE client."""

    path: str
    content: str


class IdeAnalyzeRequest(SQLModel):
    """Ad hoc analysis request for IDE extensions."""

    repo: str | None = None
    branch: str | None = None
    scan_type: ScanType = ScanType.FAST
    include_quality_metrics: bool = True
    persist_scan: bool = False
    files: list[IdeFile] = Field(default_factory=list)
    tools: list[str] | None = None


class IdeAnalyzeResponse(SQLModel):
    """Analysis response consumable by editor extensions."""

    scan: ScanPublic | None = None
    findings: list[FindingPublic] = Field(default_factory=list)
    files: list[FileMetricsPublic] = Field(default_factory=list)
    severities: dict[str, int] = Field(default_factory=dict)
