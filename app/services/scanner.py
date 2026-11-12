"""Scan orchestration and actual tool execution."""

import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.core.metrics import increment_metric, observe_metric
from app.core.network_security import redact_sensitive_text
from app.models import (
    FileMetrics,
    Finding,
    FindingSeverity,
    Scan,
    ScanStatus,
    ToolExecution,
    ToolExecutionStatus,
)
from app.services.config_loader import (
    get_effective_tool_config,
    get_enabled_tools,
    get_tools_for_scan_type,
)
from app.services.git_utils import clone_repository
from app.services.github_app import complete_github_check_run
from app.services.language_detector import detect_languages
from app.services.policy_engine import apply_waivers, evaluate_scan_policy, matching_policy
from app.services.quality_analyzer import analyze_files
from app.services.scm_clone import resolve_clone_url, safe_clone_url_for_logs
from app.services.tool_adapters import ToolRunResult, run_tool


def execute_scan(session: Session, scan_id: int) -> None:
    """Run a scan and persist its outputs."""

    scan_start = perf_counter()
    increment_metric("scan_runs_total")
    scan = session.get(Scan, scan_id)
    if scan is None:
        raise ValueError(f"Scan {scan_id} not found")

    scan.status = ScanStatus.RUNNING
    scan.started_at = datetime.now(UTC)
    session.add(scan)
    session.commit()
    session.refresh(scan)

    repo_path: Path | None = None
    try:
        clone_url = resolve_clone_url(session, scan.repo, scan.scan_metadata)
        repo_path = clone_repository(clone_url, scan.branch, scan.commit)
        findings, executions, file_metrics, language_counts = analyze_directory(
            scan.id,
            repo_path,
            scan.scan_type,
            scan.scan_metadata.get("requested_tools") if scan.scan_metadata else [],
            scan.include_quality_metrics,
            session=session,
            tenant_slug=scan.tenant_slug,
        )
        for execution in executions:
            session.add(execution)
        for finding in findings:
            _attach_code_context(finding, repo_path)
            session.add(finding)
        for metric in file_metrics:
            session.add(metric)
        session.commit()
        persisted_findings = list(
            session.exec(select(Finding).where(Finding.scan_id == scan.id)).all()
        )
        persisted_findings, suppressed = apply_waivers(
            session, scan, persisted_findings, actor=scan.scan_metadata.get("actor", "system")
        )
        for finding in persisted_findings:
            session.add(finding)
        session.commit()
        finalize_scan(
            session,
            scan.id,
            language_counts,
            [execution.tool for execution in executions],
            file_metrics,
            suppressed_findings=suppressed,
        )
        increment_metric("scan_runs_completed_total")
    except Exception as exc:  # noqa: BLE001
        redacted_error = redact_sensitive_text(str(exc))
        safe_repo = safe_clone_url_for_logs(scan.repo)
        scan.status = ScanStatus.FAILED
        scan.completed_at = datetime.now(UTC)
        github_update = complete_github_check_run(scan, error_message=redacted_error)
        scan.scan_metadata = {
            **(scan.scan_metadata or {}),
            "error": redacted_error,
            "repo": safe_repo,
            **({"github_check": github_update} if github_update else {}),
        }
        session.add(scan)
        session.commit()
        increment_metric("scan_runs_failed_total")
        raise
    finally:
        observe_metric("scan_duration_seconds", perf_counter() - scan_start)
        if repo_path and repo_path.exists():
            shutil.rmtree(repo_path, ignore_errors=True)


def analyze_directory(
    scan_id: int,
    repo_path: Path,
    scan_type: str,
    requested_tools: list[str] | None,
    include_quality_metrics: bool,
    *,
    persist_ids: bool = True,
    session: Session | None = None,
    tenant_slug: str | None = None,
) -> tuple[list[Finding], list[ToolExecution], list[FileMetrics], dict[str, int]]:
    """Analyze a local directory using the shared scan pipeline."""

    language_counts = detect_languages(repo_path)
    synthetic_scan = Scan(
        id=scan_id if persist_ids else None,
        repo=str(repo_path),
        scan_type=scan_type,
        include_quality_metrics=include_quality_metrics,
        scan_metadata={"requested_tools": requested_tools or []},
    )
    effective_config = get_effective_tool_config(session, tenant_slug)
    tools, tool_definitions = _select_tools(synthetic_scan, language_counts, effective_config)
    findings, executions = _run_tools(
        scan_id,
        repo_path,
        language_counts,
        tools,
        tool_definitions,
    )
    deduped_findings = _deduplicate(findings)

    file_metrics: list[FileMetrics] = []
    quality_findings: list[Finding] = []
    if include_quality_metrics:
        file_metrics, quality_findings = analyze_files(repo_path, scan_id)
        deduped_findings.extend(_deduplicate(quality_findings))

    if not persist_ids:
        for finding in deduped_findings:
            finding.scan_id = 0
        for execution in executions:
            execution.scan_id = 0
        for metric in file_metrics:
            metric.scan_id = 0

    return _deduplicate(deduped_findings), executions, file_metrics, language_counts


def _select_tools(
    scan: Scan,
    language_counts: dict[str, int],
    tool_config: dict[str, Any],
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    enabled_tools = get_enabled_tools(tool_config)
    selected = scan.scan_metadata.get("requested_tools") if scan.scan_metadata else None
    if scan.scan_type == "custom" and selected:
        return [tool for tool in selected if tool in enabled_tools], enabled_tools

    requested = get_tools_for_scan_type(scan.scan_type, tool_config)
    if requested:
        return [
            tool for tool in requested if _supports_languages(enabled_tools[tool], language_counts)
        ], enabled_tools

    return [
        tool
        for tool, config in enabled_tools.items()
        if _supports_languages(config, language_counts)
    ], enabled_tools


def _supports_languages(tool_config: dict[str, Any], language_counts: dict[str, int]) -> bool:
    languages = tool_config.get("languages", [])
    return "all" in languages or any(language in language_counts for language in languages)


def _run_tools(
    scan_id: int,
    repo_path: Path,
    language_counts: dict[str, int],
    tools: list[str],
    tool_definitions: dict[str, dict[str, Any]],
) -> tuple[list[Finding], list[ToolExecution]]:
    findings: list[Finding] = []
    executions: list[ToolExecution] = []

    increment_metric("scan_tools_scheduled_total", value=len(tools))
    max_workers = min(settings.max_parallel_tools, max(len(tools), 1))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        submitted_at: dict[Any, datetime] = {}
        submitted_perf: dict[Any, float] = {}
        future_map = {
            executor.submit(
                _execute_single_tool,
                scan_id,
                repo_path,
                language_counts,
                tool,
                tool_definitions.get(tool, {}),
            ): tool
            for tool in tools
        }
        for future in future_map:
            submitted_at[future] = datetime.now(UTC)
            submitted_perf[future] = perf_counter()
        for future in as_completed(future_map):
            tool = future_map[future]
            execution = ToolExecution(
                scan_id=scan_id,
                tool=tool,
                started_at=submitted_at.get(future, datetime.now(UTC)),
            )
            try:
                result = future.result()
                execution.status = result.status
                execution.version = result.version
                execution.findings_count = len(result.findings)
                execution.stdout_summary = result.summary
                execution.stderr_summary = result.error
                execution.completed_at = datetime.now(UTC)
                if result.status == ToolExecutionStatus.COMPLETED:
                    for finding in result.findings:
                        finding.tool = tool
                    findings.extend(result.findings)
                increment_metric(
                    "tool_runs_total", tags={"tool": tool, "status": str(execution.status)}
                )
            except Exception as exc:  # noqa: BLE001
                execution.status = ToolExecutionStatus.FAILED
                execution.stderr_summary = redact_sensitive_text(str(exc))
                execution.completed_at = datetime.now(UTC)
                increment_metric("tool_runs_total", tags={"tool": tool, "status": "failed"})
            started = submitted_perf.get(future)
            if started is not None:
                observe_metric(
                    "tool_duration_seconds",
                    perf_counter() - started,
                    tags={"tool": tool},
                )
            executions.append(execution)
    return findings, executions


def _execute_single_tool(
    scan_id: int,
    repo_path: Path,
    language_counts: dict[str, int],
    tool: str,
    tool_config: dict[str, Any],
) -> ToolRunResult:
    del language_counts
    return run_tool(scan_id, repo_path, tool, tool_config=tool_config)


def _deduplicate(findings: list[Finding]) -> list[Finding]:
    unique: dict[str, Finding] = {}
    for finding in findings:
        unique[finding.fingerprint] = finding
    return list(unique.values())


def finalize_scan(
    session: Session,
    scan_id: int,
    language_counts: dict[str, int],
    tools: list[str],
    file_metrics: list[FileMetrics],
    *,
    suppressed_findings: int = 0,
) -> None:
    """Persist aggregate scan rollups and policy evaluation."""

    scan = session.get(Scan, scan_id)
    if scan is None:
        return

    findings = session.exec(select(Finding).where(Finding.scan_id == scan_id)).all()
    active_findings = [finding for finding in findings if not finding.is_suppressed]
    scan.total_findings = len(active_findings)
    scan.suppressed_findings = suppressed_findings
    scan.critical_findings = sum(
        finding.severity == FindingSeverity.CRITICAL for finding in active_findings
    )
    scan.high_findings = sum(
        finding.severity == FindingSeverity.HIGH for finding in active_findings
    )
    scan.medium_findings = sum(
        finding.severity == FindingSeverity.MEDIUM for finding in active_findings
    )
    scan.low_findings = sum(finding.severity == FindingSeverity.LOW for finding in active_findings)
    scan.info_findings = sum(
        finding.severity == FindingSeverity.INFO for finding in active_findings
    )
    scan.quality_issues = sum(finding.category == "maintainability" for finding in active_findings)
    scan.style_issues = sum(finding.category == "style" for finding in active_findings)
    scan.complexity_issues = sum(finding.category == "complexity" for finding in active_findings)

    if file_metrics:
        complexity_values = [metric.cyclomatic_complexity for metric in file_metrics]
        maintainability_values = [metric.maintainability_index for metric in file_metrics]
        debt_values = [metric.technical_debt_minutes for metric in file_metrics]
        scan.avg_cyclomatic_complexity = round(sum(complexity_values) / len(complexity_values), 2)
        scan.max_cyclomatic_complexity = max(complexity_values)
        scan.maintainability_index = round(
            sum(maintainability_values) / len(maintainability_values), 2
        )
        scan.maintainability_score = scan.maintainability_index
        scan.complexity_score = round(max(0.0, 100.0 - (scan.avg_cyclomatic_complexity * 4)), 2)
        scan.style_score = round(max(0.0, 100.0 - (scan.style_issues * 2)), 2)
        scan.quality_score = round(
            (
                (scan.maintainability_score or 0.0)
                + (scan.complexity_score or 0.0)
                + (scan.style_score or 0.0)
            )
            / 3,
            2,
        )
        scan.duplication_percentage = 0.0
        scan.technical_debt_minutes = sum(debt_values)
        scan.quality_grade = _quality_grade(scan.quality_score or 0.0)
    else:
        scan.quality_score = None
        scan.quality_grade = None

    default_pass = (
        scan.critical_findings <= settings.max_critical_findings
        and scan.high_findings <= settings.max_high_findings
        and (scan.quality_score is None or scan.quality_score >= settings.min_quality_score)
    )
    policy = evaluate_scan_policy(
        scan, matching_policy(session, scan.tenant_slug, scan.repo, scan.branch)
    )
    scan.quality_gate_passed = default_pass and policy.passed
    scan.status = ScanStatus.COMPLETED
    scan.completed_at = datetime.now(UTC)
    scan.scan_metadata = {
        **(scan.scan_metadata or {}),
        "languages": language_counts,
        "tools_selected": tools,
        "policy": policy.model_dump(),
    }
    github_update = complete_github_check_run(scan)
    if github_update:
        scan.scan_metadata["github_check"] = github_update
    session.add(scan)
    session.commit()


_CODE_CONTEXT_LINES = 7  # lines before and after the issue line


def _attach_code_context(finding: Finding, repo_path: Path) -> None:
    """Read source lines around the finding and store in tool_metadata."""

    if not finding.file_path or not finding.line:
        return
    file_on_disk = Path(finding.file_path)
    if not file_on_disk.is_absolute():
        file_on_disk = repo_path / file_on_disk
    if not file_on_disk.is_file():
        return
    try:
        lines = file_on_disk.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    target = finding.line  # 1-based
    start = max(1, target - _CODE_CONTEXT_LINES)
    end = min(len(lines), target + _CODE_CONTEXT_LINES)
    snippet = [{"line": i, "text": lines[i - 1]} for i in range(start, end + 1)]
    meta = finding.tool_metadata or {}
    meta["code_context"] = {
        "start_line": start,
        "end_line": end,
        "issue_line": target,
        "lines": snippet,
    }
    finding.tool_metadata = meta


def _quality_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"
