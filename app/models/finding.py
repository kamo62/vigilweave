"""Finding model definitions."""

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, Column, String
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.scan import Scan


class FindingSeverity(StrEnum):
    """Canonical finding severity values."""

    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


class ReviewStatus(StrEnum):
    """Triage status for a finding."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    FALSE_POSITIVE = "false_positive"
    FIXED = "fixed"
    WONT_FIX = "wont_fix"


class FindingBase(SQLModel):
    """Shared finding fields."""

    tool: str = Field(index=True)
    identifier: str | None = Field(default=None, index=True)
    scan_source: str = Field(default="native", index=True)
    severity: FindingSeverity = Field(index=True)
    title: str
    message: str
    description: str | None = None
    category: str = Field(index=True)
    file_path: str | None = None
    line: int | None = None
    column: int | None = None
    rule_id: str | None = None
    cwe_id: str | None = None
    owasp_category: str | None = None
    confidence: str | None = None
    fingerprint: str = Field(index=True)
    is_suppressed: bool = Field(default=False, index=True)
    suppression_reason: str | None = None
    waiver_id: int | None = Field(default=None, foreign_key="waivers.id", index=True)
    review_status: str = Field(
        default="open",
        sa_column=Column(String, default="open", index=True),
    )
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class Finding(FindingBase, table=True):
    """Persisted finding."""

    __tablename__ = "findings"

    id: int | None = Field(default=None, primary_key=True)
    scan_id: int = Field(foreign_key="scans.id", index=True, ondelete="CASCADE")
    tool_metadata: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON))

    scan: Optional["Scan"] = Relationship(back_populates="findings")

    def to_dict(self) -> dict[str, Any]:
        """Return a safe JSON representation."""

        return {
            "id": self.id,
            "scan_id": self.scan_id,
            "tool": self.tool,
            "identifier": self.identifier,
            "scan_source": self.scan_source,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "description": self.description,
            "category": self.category,
            "file_path": self.file_path,
            "line": self.line,
            "column": self.column,
            "rule_id": self.rule_id,
            "cwe_id": self.cwe_id,
            "owasp_category": self.owasp_category,
            "confidence": self.confidence,
            "fingerprint": self.fingerprint,
            "is_suppressed": self.is_suppressed,
            "suppression_reason": self.suppression_reason,
            "waiver_id": self.waiver_id,
            "review_status": self.review_status,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "tool_metadata": self.tool_metadata,
        }


class FindingPublic(FindingBase):
    """Finding response schema."""

    id: int
    scan_id: int
    tool_metadata: dict[str, Any] | None = None
    review_status: str = "open"
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class FindingTriageRequest(SQLModel):
    """Payload for triaging a finding."""

    review_status: ReviewStatus
    comment: str | None = None
