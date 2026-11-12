"""File metrics model definitions."""

from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.scan import Scan


class FileMetricsBase(SQLModel):
    """Shared file metrics fields."""

    file_path: str = Field(index=True)
    language: str = Field(index=True)
    lines_of_code: int = 0
    cyclomatic_complexity: int = 1
    maintainability_index: float = 100.0
    duplication_percentage: float = 0.0
    line_coverage: float | None = None
    linting_errors: int = 0
    linting_warnings: int = 0
    style_violations: int = 0
    technical_debt_minutes: int = 0


class FileMetrics(FileMetricsBase, table=True):
    """Persisted file-level quality metrics."""

    __tablename__ = "file_metrics"

    id: int | None = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scans.id", index=True, ondelete="CASCADE")

    scan: Optional["Scan"] = Relationship(back_populates="file_metrics")


class FileMetricsPublic(FileMetricsBase):
    """File metrics response schema."""

    id: int
    scan_id: int
