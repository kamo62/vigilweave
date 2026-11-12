"""Helpers for IDE-oriented ad hoc analysis."""

import shutil
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath

from sqlmodel import Session

from app.models import (
    FileMetricsPublic,
    Finding,
    FindingPublic,
    IdeAnalyzeRequest,
    IdeAnalyzeResponse,
    Scan,
    ScanPublic,
    ScanStatus,
)
from app.services.policy_engine import apply_waivers
from app.services.scanner import analyze_directory, finalize_scan


def run_ide_analysis(
    session: Session, payload: IdeAnalyzeRequest, *, tenant_slug: str, actor: str
) -> IdeAnalyzeResponse:
    """Run analysis for an IDE client and optionally persist the resulting scan."""

    workspace = Path(tempfile.mkdtemp(prefix="vigilweave-ide-"))
    workspace_root = workspace.resolve()
    try:
        for file in payload.files:
            destination = _safe_workspace_path(workspace_root, file.path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(file.content, encoding="utf-8")

        if payload.persist_scan:
            scan = Scan(
                tenant_slug=tenant_slug,
                repo=payload.repo or "ide://workspace",
                branch=payload.branch,
                source="ide",
                scan_type=payload.scan_type,
                status=ScanStatus.RUNNING,
                include_quality_metrics=payload.include_quality_metrics,
                scan_metadata={"requested_tools": payload.tools or [], "mode": "ide"},
            )
            session.add(scan)
            session.commit()
            session.refresh(scan)

            findings, executions, metrics, languages = analyze_directory(
                scan.id,
                workspace,
                payload.scan_type,
                payload.tools or [],
                payload.include_quality_metrics,
                session=session,
                tenant_slug=scan.tenant_slug,
            )
            for execution in executions:
                session.add(execution)
            for finding in findings:
                session.add(finding)
            for metric in metrics:
                session.add(metric)
            session.commit()

            persisted = list(scan.findings)
            persisted, _ = apply_waivers(session, scan, persisted, actor=actor)
            for finding in persisted:
                session.add(finding)
            session.commit()

            finalize_scan(
                session,
                scan.id,
                languages,
                [execution.tool for execution in executions],
                metrics,
            )
            session.refresh(scan)
            return IdeAnalyzeResponse(
                scan=ScanPublic.model_validate(scan),
                findings=[FindingPublic.model_validate(item) for item in scan.findings],
                files=[FileMetricsPublic.model_validate(item) for item in scan.file_metrics],
                severities=_severity_counts(scan.findings),
            )

        findings, _, metrics, _ = analyze_directory(
            0,
            workspace,
            payload.scan_type,
            payload.tools or [],
            payload.include_quality_metrics,
            persist_ids=False,
            session=session,
            tenant_slug=tenant_slug,
        )
        for index, finding in enumerate(findings, start=1):
            finding.id = index
        for index, metric in enumerate(metrics, start=1):
            metric.id = index
        return IdeAnalyzeResponse(
            findings=[FindingPublic.model_validate(item) for item in findings],
            files=[FileMetricsPublic.model_validate(item) for item in metrics],
            severities=_severity_counts(findings),
        )
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


def _severity_counts(findings: list[Finding]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for finding in findings:
        counter[str(finding.severity)] += 1
    return dict(counter)


def _safe_workspace_path(workspace_root: Path, relative_path: str) -> Path:
    normalized = relative_path.replace("\\", "/").strip()
    candidate = PurePosixPath(normalized)
    if not normalized or candidate.is_absolute() or candidate.drive:
        raise ValueError("Invalid IDE file path")

    resolved = (workspace_root / Path(candidate)).resolve()
    try:
        resolved.relative_to(workspace_root)
    except ValueError as exc:
        raise ValueError("Invalid IDE file path") from exc
    return resolved
