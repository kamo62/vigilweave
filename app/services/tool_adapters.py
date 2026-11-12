"""Actual CLI-backed tool adapters for repository scanning."""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from app.core.config import settings
from app.core.network_security import redact_sensitive_text
from app.models import Finding, FindingSeverity, ToolExecutionStatus


@dataclass(slots=True)
class ToolRunResult:
    """Result returned by a tool adapter."""

    findings: list[Finding]
    summary: str
    status: ToolExecutionStatus
    version: str | None = None
    error: str | None = None


def get_runtime_tool_capabilities(repo_path: Path | None = None) -> dict[str, bool]:
    """Return whether each configured tool can execute in the current environment."""

    return {
        "gitleaks": shutil.which("gitleaks") is not None,
        "semgrep": shutil.which("semgrep") is not None,
        "bandit": shutil.which("bandit") is not None,
        "ruff": shutil.which("ruff") is not None,
        "eslint": _eslint_command(repo_path) is not None,
        "checkov": shutil.which("checkov") is not None,
        "tflint": shutil.which("tflint") is not None,
        "cfn-lint": shutil.which("cfn-lint") is not None,
        "trivy": shutil.which("trivy") is not None,
        "sqlfluff": shutil.which("sqlfluff") is not None,
        "swiftlint": shutil.which("swiftlint") is not None,
        "detekt": shutil.which("detekt") is not None,
        "android-lint": (
            settings.enable_repo_build_tool_adapters
            and (_gradlew_path(repo_path) is not None if repo_path else False)
        ),
        "dotnet-analyzers": settings.enable_repo_build_tool_adapters
        and shutil.which("dotnet") is not None,
        "grype": shutil.which("grype") is not None,
    }


def run_tool(
    scan_id: int,
    repo_path: Path,
    tool: str,
    *,
    tool_config: dict[str, Any] | None = None,
) -> ToolRunResult:
    """Run a configured tool against a repository."""

    runners = {
        "gitleaks": _run_gitleaks,
        "semgrep": _run_semgrep,
        "bandit": _run_bandit,
        "ruff": _run_ruff,
        "eslint": _run_eslint,
        "checkov": _run_checkov,
        "tflint": _run_tflint,
        "cfn-lint": _run_cfn_lint,
        "trivy": _run_trivy,
        "sqlfluff": _run_sqlfluff,
        "swiftlint": _run_swiftlint,
        "detekt": _run_detekt,
        "android-lint": _run_android_lint,
        "dotnet-analyzers": _run_dotnet_analyzers,
        "grype": _run_grype,
    }

    runner_id = str((tool_config or {}).get("runner") or tool).strip().lower()
    runner = runners.get(runner_id)
    if runner is None:
        return ToolRunResult(
            findings=[],
            summary=f"{tool} is not implemented",
            status=ToolExecutionStatus.SKIPPED,
            error=f"No adapter exists for {runner_id}",
        )
    if runner_id == "semgrep":
        return _run_semgrep(scan_id, repo_path, tool_config)
    if runner_id == "checkov":
        return _run_checkov(scan_id, repo_path, tool_config)
    if runner_id == "sqlfluff":
        return _run_sqlfluff(scan_id, repo_path, tool_config)
    return runner(scan_id, repo_path)


def _run_gitleaks(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("gitleaks")
    if executable is None:
        return _skipped("gitleaks", "gitleaks binary is not installed")

    with tempfile.NamedTemporaryFile(suffix=".sarif") as report:
        completed = subprocess.run(
            [
                executable,
                "detect",
                "--source",
                str(repo_path),
                "--report-format",
                "sarif",
                "--report-path",
                report.name,
                "--no-banner",
                "--redact",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=settings.tool_execution_timeout_seconds,
        )
        if completed.returncode not in {0, 1}:
            return _failed("gitleaks", completed)
        findings = _parse_sarif(Path(report.name), scan_id, "gitleaks", "secret")
        return ToolRunResult(
            findings=findings,
            summary=f"gitleaks reported {len(findings)} findings",
            status=ToolExecutionStatus.COMPLETED,
            version=_tool_version([executable, "version"]),
        )


def _run_semgrep(
    scan_id: int, repo_path: Path, tool_config: dict[str, Any] | None = None
) -> ToolRunResult:
    executable = shutil.which("semgrep")
    if executable is None:
        return _skipped("semgrep", "semgrep is not installed")

    rule_config = _tool_rules(tool_config)
    configs = _as_string_list(rule_config.get("config"))
    if not configs:
        configs = ["p/default"]
    include_patterns = _as_string_list(rule_config.get("include"))
    exclude_patterns = _as_string_list(rule_config.get("exclude"))
    jobs = _as_int(rule_config.get("jobs"))
    timeout = _as_int(rule_config.get("timeout"))

    command = [executable, "scan", "--json"]
    for config in configs:
        command.extend(["--config", config])
    for include in include_patterns:
        command.extend(["--include", include])
    for exclude in exclude_patterns:
        command.extend(["--exclude", exclude])
    if jobs and jobs > 0:
        command.extend(["--jobs", str(jobs)])
    if timeout and timeout > 0:
        command.extend(["--timeout", str(timeout)])
    command.append(str(repo_path))

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env={
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "SEMGREP_SEND_METRICS": "off",
        },
        timeout=settings.tool_execution_timeout_seconds,
    )
    if completed.returncode not in {0, 1}:
        return _failed("semgrep", completed)
    findings = _parse_semgrep_json(completed.stdout, scan_id, repo_path)
    return ToolRunResult(
        findings=findings,
        summary=f"semgrep reported {len(findings)} findings",
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([executable, "--version"]),
    )


def _run_bandit(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("bandit")
    if executable is None:
        return _skipped("bandit", "bandit is not installed")

    completed = subprocess.run(
        [executable, "-r", str(repo_path), "-f", "json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=settings.tool_execution_timeout_seconds,
    )
    if completed.returncode not in {0, 1}:
        return _failed("bandit", completed)
    findings = _parse_bandit_json(completed.stdout, scan_id, repo_path)
    return ToolRunResult(
        findings=findings,
        summary=f"bandit reported {len(findings)} findings",
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([executable, "--version"]),
    )


def _run_ruff(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("ruff")
    if executable is None:
        return _skipped("ruff", "ruff is not installed")

    completed = subprocess.run(
        [executable, "check", str(repo_path), "--output-format", "json"],
        capture_output=True,
        text=True,
        check=False,
        timeout=settings.tool_execution_timeout_seconds,
    )
    if completed.returncode not in {0, 1}:
        return _failed("ruff", completed)
    findings = _parse_ruff_json(completed.stdout, scan_id)
    return ToolRunResult(
        findings=findings,
        summary=f"ruff reported {len(findings)} findings",
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([executable, "--version"]),
    )


def _run_eslint(scan_id: int, repo_path: Path) -> ToolRunResult:
    command = _eslint_command(repo_path)
    if command is None:
        return _skipped("eslint", "eslint is unavailable or the repository has no JS/TS files")

    files = _matching_files(repo_path, {".js", ".jsx", ".ts", ".tsx"})
    if not files:
        return _skipped("eslint", "No JavaScript or TypeScript files were found")

    completed = subprocess.run(
        [*command, "--format", "json", "--no-error-on-unmatched-pattern", *files],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=settings.tool_execution_timeout_seconds,
    )
    if completed.returncode not in {0, 1}:
        return _failed("eslint", completed)
    findings = _parse_eslint_json(completed.stdout, scan_id, repo_path)
    return ToolRunResult(
        findings=findings,
        summary=f"eslint reported {len(findings)} findings",
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([command[0], "--version"]),
    )


def _run_checkov(
    scan_id: int, repo_path: Path, tool_config: dict[str, Any] | None = None
) -> ToolRunResult:
    executable = shutil.which("checkov")
    if executable is None:
        return _skipped("checkov", "checkov is not installed")

    rule_config = _tool_rules(tool_config)
    checks = _as_string_list(rule_config.get("check"))
    skip_checks = _as_string_list(rule_config.get("skip_check"))
    frameworks = _as_string_list(rule_config.get("framework"))

    command = [executable, "-d", str(repo_path), "-o", "json", "--quiet"]
    for check in checks:
        command.extend(["--check", check])
    for skip_check in skip_checks:
        command.extend(["--skip-check", skip_check])
    for framework in frameworks:
        command.extend(["--framework", framework])

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        timeout=settings.tool_execution_timeout_seconds,
    )
    if completed.returncode not in {0, 1}:
        return _failed("checkov", completed)
    findings = _parse_checkov_json(completed.stdout, scan_id, repo_path)
    return ToolRunResult(
        findings=findings,
        summary=f"checkov reported {len(findings)} findings",
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([executable, "--version"]),
    )


def _run_tflint(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("tflint")
    if executable is None:
        return _skipped("tflint", "tflint is not installed")
    if not _matching_files(repo_path, {".tf"}) and not _matching_name_suffix(repo_path, ".tf.json"):
        return _skipped("tflint", "No Terraform files were found")

    completed = subprocess.run(
        [executable, "--recursive", "--format", "sarif"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=settings.tool_execution_timeout_seconds,
    )
    if completed.returncode not in {0, 2}:
        return _failed("tflint", completed)
    findings = _parse_sarif_text(completed.stdout, scan_id, "tflint", "iac")
    return ToolRunResult(
        findings=findings,
        summary=f"tflint reported {len(findings)} findings",
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([executable, "--version"]),
    )


def _run_cfn_lint(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("cfn-lint")
    if executable is None:
        return _skipped("cfn-lint", "cfn-lint is not installed")

    templates = _matching_cloudformation_templates(repo_path)
    if not templates:
        return _skipped("cfn-lint", "No CloudFormation templates were found")

    completed = subprocess.run(
        [executable, "--format", "sarif", "--non-zero-exit-code", "none", *templates],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=settings.tool_execution_timeout_seconds,
    )
    if completed.returncode != 0:
        return _failed("cfn-lint", completed)
    findings = _parse_sarif_text(completed.stdout, scan_id, "cfn-lint", "iac")
    return ToolRunResult(
        findings=findings,
        summary=f"cfn-lint reported {len(findings)} findings",
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([executable, "--version"]),
    )


def _run_trivy(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("trivy")
    if executable is None:
        return _skipped("trivy", "trivy is not installed")

    with tempfile.NamedTemporaryFile(suffix=".sarif") as report:
        completed = subprocess.run(
            [
                executable,
                "fs",
                "--quiet",
                "--format",
                "sarif",
                "--output",
                report.name,
                str(repo_path),
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=settings.tool_execution_timeout_seconds,
        )
        if completed.returncode not in {0, 1}:
            return _failed("trivy", completed)
        findings = _parse_sarif(Path(report.name), scan_id, "trivy", "container")
        return ToolRunResult(
            findings=findings,
            summary=f"trivy reported {len(findings)} findings",
            status=ToolExecutionStatus.COMPLETED,
            version=_tool_version([executable, "--version"]),
        )


def _run_sqlfluff(
    scan_id: int, repo_path: Path, tool_config: dict[str, Any] | None = None
) -> ToolRunResult:
    executable = shutil.which("sqlfluff")
    if executable is None:
        return _skipped("sqlfluff", "sqlfluff is not installed")

    rule_config = _tool_rules(tool_config)
    forced_dialect = _as_string(rule_config.get("dialect"))
    include_rules = _as_string_list(rule_config.get("rules"))
    exclude_rules = _as_string_list(rule_config.get("exclude_rules"))

    dialect_to_files = _sqlfluff_file_groups(repo_path)
    if forced_dialect:
        all_files = sorted({file for files in dialect_to_files.values() for file in files})
        dialect_to_files = {forced_dialect: all_files} if all_files else {}
    total_files = sum(len(files) for files in dialect_to_files.values())
    if total_files == 0:
        return _skipped("sqlfluff", "No SQL or PL/SQL files were found")

    findings: list[Finding] = []
    for dialect, files in dialect_to_files.items():
        command = [executable, "lint", "--format", "json", "--dialect", dialect]
        if include_rules:
            command.extend(["--rules", ",".join(include_rules)])
        if exclude_rules:
            command.extend(["--exclude-rules", ",".join(exclude_rules)])
        command.extend(files)
        completed = subprocess.run(
            command,
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=settings.tool_execution_timeout_seconds,
        )
        if completed.returncode not in {0, 1, 65}:
            if dialect == "oracle":
                fallback = subprocess.run(
                    [
                        executable,
                        "lint",
                        "--format",
                        "json",
                        "--dialect",
                        "ansi",
                        *files,
                    ],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=settings.tool_execution_timeout_seconds,
                )
                if fallback.returncode in {0, 1, 65}:
                    findings.extend(_parse_sqlfluff_json(fallback.stdout, scan_id, dialect="ansi"))
                    continue
            return _failed("sqlfluff", completed)
        findings.extend(_parse_sqlfluff_json(completed.stdout, scan_id, dialect=dialect))

    return ToolRunResult(
        findings=findings,
        summary=f"sqlfluff reported {len(findings)} findings across {total_files} files",
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([executable, "--version"]),
    )


def _run_swiftlint(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("swiftlint")
    if executable is None:
        return _skipped("swiftlint", "swiftlint is not installed")
    if not _matching_files(repo_path, {".swift"}):
        return _skipped("swiftlint", "No Swift files were found")

    completed = subprocess.run(
        [executable, "lint", "--quiet", "--reporter", "json", "--path", str(repo_path)],
        capture_output=True,
        text=True,
        check=False,
        timeout=settings.tool_execution_timeout_seconds,
    )
    if completed.returncode not in {0, 1, 2}:
        return _failed("swiftlint", completed)
    findings = _parse_swiftlint_json(completed.stdout, scan_id, repo_path)
    return ToolRunResult(
        findings=findings,
        summary=f"swiftlint reported {len(findings)} findings",
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([executable, "version"]),
    )


def _run_detekt(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("detekt")
    if executable is None:
        return _skipped("detekt", "detekt is not installed")
    if not _matching_files(repo_path, {".kt", ".kts"}):
        return _skipped("detekt", "No Kotlin files were found")

    with tempfile.NamedTemporaryFile(suffix=".sarif") as report:
        completed = subprocess.run(
            [
                executable,
                "--input",
                str(repo_path),
                "--report",
                f"sarif:{report.name}",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=settings.tool_execution_timeout_seconds,
        )
        if completed.returncode not in {0, 2}:
            return _failed("detekt", completed)
        findings = _parse_sarif(Path(report.name), scan_id, "detekt", "quality")
        return ToolRunResult(
            findings=findings,
            summary=f"detekt reported {len(findings)} findings",
            status=ToolExecutionStatus.COMPLETED,
            version=_tool_version([executable, "--version"]),
        )


def _run_android_lint(scan_id: int, repo_path: Path) -> ToolRunResult:
    if not settings.enable_repo_build_tool_adapters:
        return _skipped(
            "android-lint",
            "android-lint is disabled by default; "
            "set ENABLE_REPO_BUILD_TOOL_ADAPTERS=true to opt in",
        )

    gradlew = _gradlew_path(repo_path)
    if gradlew is None:
        return _skipped("android-lint", "Gradle wrapper is not available for Android lint")

    completed = subprocess.run(
        [str(gradlew), "lint"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=settings.tool_execution_timeout_seconds,
    )
    report_path = next(repo_path.rglob("lint-results*.xml"), None)
    if report_path is None:
        if completed.returncode == 0:
            return ToolRunResult(
                findings=[],
                summary="android lint completed without a report",
                status=ToolExecutionStatus.COMPLETED,
                version=None,
            )
        return _failed("android-lint", completed)
    findings = _parse_android_lint_xml(report_path, scan_id, repo_path)
    return ToolRunResult(
        findings=findings,
        summary=f"android lint reported {len(findings)} findings",
        status=ToolExecutionStatus.COMPLETED,
        version="gradle-wrapper",
    )


def _run_dotnet_analyzers(scan_id: int, repo_path: Path) -> ToolRunResult:
    if not settings.enable_repo_build_tool_adapters:
        return _skipped(
            "dotnet-analyzers",
            "dotnet-analyzers is disabled by default; "
            "set ENABLE_REPO_BUILD_TOOL_ADAPTERS=true to opt in",
        )

    executable = shutil.which("dotnet")
    target = _first_existing(sorted(repo_path.glob("*.sln")) + sorted(repo_path.rglob("*.csproj")))
    if executable is None or target is None:
        return _skipped(
            "dotnet-analyzers",
            "dotnet SDK or a solution/project file is not available",
        )

    with tempfile.NamedTemporaryFile(suffix=".sarif") as report:
        completed = subprocess.run(
            [
                executable,
                "build",
                str(target),
                f"/p:ErrorLog={report.name};format=sarif",
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=settings.tool_execution_timeout_seconds,
        )
        if completed.returncode not in {0, 1}:
            return _failed("dotnet-analyzers", completed)
        findings = _parse_sarif(Path(report.name), scan_id, "dotnet-analyzers", "quality")
        return ToolRunResult(
            findings=findings,
            summary=f".NET analyzers reported {len(findings)} findings",
            status=ToolExecutionStatus.COMPLETED,
            version=_tool_version([executable, "--version"]),
        )


def _run_grype(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("grype")
    if executable is None:
        return _skipped("grype", "grype is not installed")

    with tempfile.NamedTemporaryFile(suffix=".sarif") as report:
        completed = subprocess.run(
            [
                executable,
                f"dir:{repo_path}",
                "--output",
                "sarif",
                "--file",
                report.name,
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=settings.tool_execution_timeout_seconds,
        )
        if completed.returncode not in {0, 1}:
            return _failed("grype", completed)
        findings = _parse_sarif(Path(report.name), scan_id, "grype", "sca")
        return ToolRunResult(
            findings=findings,
            summary=f"grype reported {len(findings)} findings",
            status=ToolExecutionStatus.COMPLETED,
            version=_tool_version([executable, "version"]),
        )


def _parse_sarif(
    report_path: Path, scan_id: int, tool: str, default_category: str
) -> list[Finding]:
    if not report_path.exists() or report_path.stat().st_size == 0:
        return []
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return _parse_sarif_payload(payload, scan_id, tool, default_category)


def _parse_sarif_text(
    payload_text: str, scan_id: int, tool: str, default_category: str
) -> list[Finding]:
    if not payload_text.strip():
        return []
    payload = json.loads(payload_text)
    return _parse_sarif_payload(payload, scan_id, tool, default_category)


def _parse_sarif_payload(
    payload: dict[str, Any], scan_id: int, tool: str, default_category: str
) -> list[Finding]:
    findings: list[Finding] = []
    for run in payload.get("runs", []):
        rules = {
            rule.get("id"): rule
            for rule in run.get("tool", {}).get("driver", {}).get("rules", [])
            if rule.get("id")
        }
        for result in run.get("results", []):
            rule_id = result.get("ruleId")
            rule = rules.get(rule_id, {})
            location = ((result.get("locations") or [{}])[0]).get("physicalLocation", {})
            region = location.get("region", {})
            file_path = location.get("artifactLocation", {}).get("uri")
            message = result.get("message", {}).get("text") or rule_id or "Tool finding"
            title = (
                rule.get("shortDescription", {}).get("text")
                or rule.get("name")
                or rule_id
                or message
            )
            description = rule.get("fullDescription", {}).get("text") or message
            fingerprint = _sarif_fingerprint(
                tool,
                file_path,
                region.get("startLine"),
                rule_id,
                message,
                result,
            )
            findings.append(
                Finding(
                    scan_id=scan_id,
                    tool=tool,
                    scan_source="native",
                    severity=_severity_from_sarif(result, rule),
                    title=title,
                    message=message,
                    description=description,
                    category=_category_from_rule(rule, result, default_category),
                    file_path=file_path,
                    line=region.get("startLine"),
                    column=region.get("startColumn"),
                    rule_id=rule_id,
                    cwe_id=_find_tag(rule, "cwe"),
                    owasp_category=_find_tag(rule, "owasp"),
                    confidence=result.get("properties", {}).get("precision"),
                    fingerprint=fingerprint,
                    tool_metadata=result.get("properties"),
                )
            )
    return findings


def _parse_ruff_json(payload_text: str, scan_id: int) -> list[Finding]:
    if not payload_text.strip():
        return []
    payload = json.loads(payload_text)
    findings: list[Finding] = []
    for item in payload:
        code = item.get("code")
        filename = item.get("filename")
        location = item.get("location", {})
        message = item.get("message", code or "Ruff finding")
        category = "complexity" if code == "C901" else "style"
        severity = FindingSeverity.MEDIUM if category == "complexity" else FindingSeverity.LOW
        findings.append(
            Finding(
                scan_id=scan_id,
                tool="ruff",
                scan_source="native",
                severity=severity,
                title=code or "ruff",
                message=message,
                description=item.get("url"),
                category=category,
                file_path=filename,
                line=location.get("row"),
                column=location.get("column"),
                rule_id=code,
                fingerprint=_fingerprint("ruff", filename, location.get("row"), code, message),
            )
        )
    return findings


def _parse_bandit_json(payload_text: str, scan_id: int, repo_path: Path) -> list[Finding]:
    if not payload_text.strip():
        return []
    payload = json.loads(payload_text)
    findings: list[Finding] = []
    for item in payload.get("results", []):
        relative_path = _relative_path(repo_path, Path(item.get("filename", "")))
        rule_id = item.get("test_id")
        message = item.get("issue_text", rule_id or "Bandit finding")
        category = "secret" if rule_id in {"B105", "B106", "B107"} else "security"
        cwe = item.get("issue_cwe", {})
        findings.append(
            Finding(
                scan_id=scan_id,
                tool="bandit",
                scan_source="native",
                severity=_severity_from_label(item.get("issue_severity")),
                title=item.get("test_name") or rule_id or "bandit",
                message=message,
                description=item.get("more_info") or message,
                category=category,
                file_path=relative_path,
                line=item.get("line_number"),
                column=item.get("col_offset"),
                rule_id=rule_id,
                cwe_id=str(cwe.get("id")) if cwe.get("id") is not None else None,
                confidence=item.get("issue_confidence"),
                fingerprint=_fingerprint(
                    "bandit",
                    relative_path,
                    item.get("line_number"),
                    rule_id,
                    message,
                ),
                tool_metadata={
                    "confidence": item.get("issue_confidence"),
                    "more_info": item.get("more_info"),
                },
            )
        )
    return findings


def _parse_semgrep_json(payload_text: str, scan_id: int, repo_path: Path) -> list[Finding]:
    if not payload_text.strip():
        return []
    payload = json.loads(payload_text)
    findings: list[Finding] = []
    for item in payload.get("results", []):
        extra = item.get("extra", {})
        metadata = extra.get("metadata", {})
        path = _relative_path(repo_path, Path(item.get("path", "")))
        rule_id = item.get("check_id")
        message = extra.get("message", rule_id or "Semgrep finding")
        severity = _severity_from_label(extra.get("severity"))
        category = str(metadata.get("category", "security")).lower()
        findings.append(
            Finding(
                scan_id=scan_id,
                tool="semgrep",
                scan_source="native",
                severity=severity,
                title=rule_id or "semgrep",
                message=message,
                description=metadata.get("source-rule-url") or message,
                category=category,
                file_path=path,
                line=item.get("start", {}).get("line"),
                column=item.get("start", {}).get("col"),
                rule_id=rule_id,
                cwe_id=_extract_semgrep_cwe(metadata),
                owasp_category=_extract_first(metadata.get("owasp")),
                confidence=_extract_first(metadata.get("confidence")),
                fingerprint=_fingerprint(
                    "semgrep",
                    path,
                    item.get("start", {}).get("line"),
                    rule_id,
                    message,
                ),
                tool_metadata=metadata,
            )
        )
    return findings


def _parse_eslint_json(payload_text: str, scan_id: int, repo_path: Path) -> list[Finding]:
    if not payload_text.strip():
        return []
    payload = json.loads(payload_text)
    findings: list[Finding] = []
    for file_report in payload:
        absolute_path = Path(file_report.get("filePath", ""))
        relative_path = _relative_path(repo_path, absolute_path)
        for message in file_report.get("messages", []):
            severity = (
                FindingSeverity.MEDIUM if message.get("severity") == 2 else FindingSeverity.LOW
            )
            rule_id = message.get("ruleId")
            text = message.get("message", rule_id or "ESLint finding")
            findings.append(
                Finding(
                    scan_id=scan_id,
                    tool="eslint",
                    scan_source="native",
                    severity=severity,
                    title=rule_id or "eslint",
                    message=text,
                    description=text,
                    category="style",
                    file_path=relative_path,
                    line=message.get("line"),
                    column=message.get("column"),
                    rule_id=rule_id,
                    fingerprint=_fingerprint(
                        "eslint",
                        relative_path,
                        message.get("line"),
                        rule_id,
                        text,
                    ),
                )
            )
    return findings


def _parse_checkov_json(payload_text: str, scan_id: int, repo_path: Path) -> list[Finding]:
    if not payload_text.strip():
        return []

    findings: list[Finding] = []
    for payload in _parse_json_documents(payload_text):
        documents = payload if isinstance(payload, list) else [payload]
        for document in documents:
            if not isinstance(document, dict):
                continue
            check_type = str(document.get("check_type", "iac")).lower()
            results = document.get("results", {})
            for item in results.get("failed_checks", []):
                file_path = _checkov_file_path(item, repo_path)
                line = _checkov_line(item)
                rule_id = item.get("check_id")
                message = item.get("check_name", rule_id or "Checkov finding")
                findings.append(
                    Finding(
                        scan_id=scan_id,
                        tool="checkov",
                        scan_source="native",
                        severity=_checkov_severity(item),
                        title=message,
                        message=message,
                        description=item.get("guideline") or item.get("description") or message,
                        category=_checkov_category(check_type),
                        file_path=file_path,
                        line=line,
                        column=None,
                        rule_id=rule_id,
                        fingerprint=_fingerprint(
                            "checkov",
                            file_path,
                            line,
                            rule_id,
                            f"{message}:{item.get('resource')}",
                        ),
                        tool_metadata={
                            "resource": item.get("resource"),
                            "check_type": check_type,
                            "guideline": item.get("guideline"),
                        },
                    )
                )
    return findings


def _parse_sqlfluff_json(payload_text: str, scan_id: int, *, dialect: str) -> list[Finding]:
    if not payload_text.strip():
        return []
    payload = json.loads(payload_text)
    findings: list[Finding] = []
    for file_report in payload:
        relative_path = file_report.get("filepath")
        for violation in file_report.get("violations", []):
            code = violation.get("code")
            message = violation.get("description", code or "SQLFluff finding")
            findings.append(
                Finding(
                    scan_id=scan_id,
                    tool="sqlfluff",
                    scan_source="native",
                    severity=FindingSeverity.LOW,
                    title=code or "sqlfluff",
                    message=message,
                    description=message,
                    category="style",
                    file_path=relative_path,
                    line=violation.get("line_no"),
                    column=violation.get("line_pos"),
                    rule_id=code,
                    fingerprint=_fingerprint(
                        "sqlfluff",
                        relative_path,
                        violation.get("line_no"),
                        f"{dialect}:{code}",
                        message,
                    ),
                    tool_metadata={"dialect": dialect},
                )
            )
    return findings


def _parse_swiftlint_json(payload_text: str, scan_id: int, repo_path: Path) -> list[Finding]:
    if not payload_text.strip():
        return []
    payload = json.loads(payload_text)
    findings: list[Finding] = []
    for item in payload:
        relative_path = _relative_path(repo_path, Path(item.get("file")))
        severity = (
            FindingSeverity.MEDIUM if item.get("severity") == "error" else FindingSeverity.LOW
        )
        rule_id = item.get("rule_id")
        message = item.get("reason", rule_id or "SwiftLint finding")
        findings.append(
            Finding(
                scan_id=scan_id,
                tool="swiftlint",
                scan_source="native",
                severity=severity,
                title=rule_id or "swiftlint",
                message=message,
                description=message,
                category="style",
                file_path=relative_path,
                line=item.get("line"),
                column=item.get("character"),
                rule_id=rule_id,
                fingerprint=_fingerprint(
                    "swiftlint",
                    relative_path,
                    item.get("line"),
                    rule_id,
                    message,
                ),
            )
        )
    return findings


def _parse_android_lint_xml(report_path: Path, scan_id: int, repo_path: Path) -> list[Finding]:
    findings: list[Finding] = []
    root = ElementTree.parse(report_path).getroot()
    for issue in root.findall("issue"):
        location = issue.find("location")
        file_path = location.get("file") if location is not None else None
        line = int(location.get("line")) if location is not None and location.get("line") else None
        column = (
            int(location.get("column")) if location is not None and location.get("column") else None
        )
        relative_path = _relative_path(repo_path, Path(file_path)) if file_path else None
        rule_id = issue.get("id")
        message = issue.get("message", rule_id or "Android lint finding")
        findings.append(
            Finding(
                scan_id=scan_id,
                tool="android-lint",
                scan_source="native",
                severity=_severity_from_label(issue.get("severity")),
                title=rule_id or "android-lint",
                message=message,
                description=issue.get("summary") or message,
                category="style",
                file_path=relative_path,
                line=line,
                column=column,
                rule_id=rule_id,
                fingerprint=_fingerprint("android-lint", relative_path, line, rule_id, message),
            )
        )
    return findings


def _severity_from_sarif(result: dict[str, Any], rule: dict[str, Any]) -> FindingSeverity:
    properties = {**rule.get("properties", {}), **result.get("properties", {})}
    severity = properties.get("severity") or properties.get("security-severity")
    if severity is not None:
        return _severity_from_label(str(severity))
    level = str(result.get("level", "warning"))
    if level == "error":
        return FindingSeverity.HIGH
    if level == "warning":
        return FindingSeverity.MEDIUM
    if level == "note":
        return FindingSeverity.LOW
    return FindingSeverity.INFO


def _severity_from_label(label: str | None) -> FindingSeverity:
    normalized = (label or "").strip().lower()
    if normalized in {"critical", "blocker"}:
        return FindingSeverity.CRITICAL
    if normalized in {"high", "error", "major"}:
        return FindingSeverity.HIGH
    if normalized in {"medium", "moderate", "warning"}:
        return FindingSeverity.MEDIUM
    if normalized in {"low", "minor", "note", "style"}:
        return FindingSeverity.LOW
    try:
        numeric = float(normalized)
    except ValueError:
        return FindingSeverity.INFO
    if numeric >= 9:
        return FindingSeverity.CRITICAL
    if numeric >= 7:
        return FindingSeverity.HIGH
    if numeric >= 4:
        return FindingSeverity.MEDIUM
    if numeric > 0:
        return FindingSeverity.LOW
    return FindingSeverity.INFO


def _category_from_rule(rule: dict[str, Any], result: dict[str, Any], default_category: str) -> str:
    properties = {**rule.get("properties", {}), **result.get("properties", {})}
    for key in ("category", "issue_confidence", "kind"):
        value = properties.get(key)
        if isinstance(value, str):
            return value.lower()
    tag = _find_tag(rule, "security") or _find_tag(rule, "style") or _find_tag(rule, "owasp")
    return tag or default_category


def _find_tag(rule: dict[str, Any], prefix: str) -> str | None:
    for tag in rule.get("properties", {}).get("tags", []):
        if tag.lower().startswith(prefix):
            return tag
    return None


def _skipped(tool: str, reason: str) -> ToolRunResult:
    return ToolRunResult(
        findings=[],
        summary=f"{tool} skipped",
        status=ToolExecutionStatus.SKIPPED,
        error=reason,
    )


def _failed(tool: str, completed: subprocess.CompletedProcess[str]) -> ToolRunResult:
    stderr = completed.stderr.strip() or completed.stdout.strip() or f"{tool} failed"
    stderr = redact_sensitive_text(stderr)
    return ToolRunResult(
        findings=[],
        summary=f"{tool} failed",
        status=ToolExecutionStatus.FAILED,
        error=stderr[:4000],
    )


def _tool_version(command: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=settings.tool_execution_timeout_seconds,
        )
    except OSError:
        return None
    output = completed.stdout.strip() or completed.stderr.strip()
    return output.splitlines()[0] if output else None


def _fingerprint(
    tool: str,
    file_path: str | None,
    line: int | None,
    rule_id: str | None,
    message: str,
) -> str:
    digest = hashlib.sha1(
        f"{tool}:{file_path}:{line}:{rule_id}:{message}".encode("utf-8")
    ).hexdigest()
    return digest


def _sarif_fingerprint(
    tool: str,
    file_path: str | None,
    line: int | None,
    rule_id: str | None,
    message: str,
    result: dict[str, Any],
) -> str:
    partials = result.get("partialFingerprints") or result.get("fingerprints") or {}
    if partials:
        first = next(iter(partials.values()))
        if isinstance(first, str):
            return first
    return _fingerprint(tool, file_path, line, rule_id, message)


def _relative_path(repo_path: Path, file_path: Path) -> str:
    try:
        return str(file_path.relative_to(repo_path))
    except ValueError:
        return str(file_path)


def _matching_files(repo_path: Path, suffixes: set[str]) -> list[str]:
    matches: list[str] = []
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file() or ".git" in file_path.parts:
            continue
        if file_path.suffix.lower() in suffixes:
            matches.append(str(file_path.relative_to(repo_path)))
    return matches


def _matching_name_suffix(repo_path: Path, file_name_suffix: str) -> list[str]:
    matches: list[str] = []
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file() or ".git" in file_path.parts:
            continue
        if file_path.name.lower().endswith(file_name_suffix):
            matches.append(str(file_path.relative_to(repo_path)))
    return matches


def _sqlfluff_file_groups(repo_path: Path) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    sql_suffixes = {".sql", ".psql"}
    plsql_suffixes = {".pls", ".pks", ".pkb", ".prc", ".fnc", ".trg", ".tpb", ".tps", ".sqlj"}

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file() or ".git" in file_path.parts:
            continue
        suffix = file_path.suffix.lower()
        relative_path = str(file_path.relative_to(repo_path))
        if suffix in plsql_suffixes:
            groups.setdefault("oracle", []).append(relative_path)
            continue
        if suffix in sql_suffixes:
            groups.setdefault("ansi", []).append(relative_path)
            continue
        if file_path.name.lower().endswith(".plsql.sql"):
            groups.setdefault("oracle", []).append(relative_path)

    return groups


def _matching_cloudformation_templates(repo_path: Path) -> list[str]:
    matches: list[str] = []
    for file_path in repo_path.rglob("*"):
        if not file_path.is_file() or ".git" in file_path.parts:
            continue
        name = file_path.name.lower()
        suffix = file_path.suffix.lower()
        if name.endswith(".template"):
            matches.append(str(file_path.relative_to(repo_path)))
            continue
        if suffix not in {".yaml", ".yml", ".json"}:
            continue
        if _looks_like_cloudformation(file_path):
            matches.append(str(file_path.relative_to(repo_path)))
    return matches


def _looks_like_cloudformation(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")[:65536].lower()
    except OSError:
        return False
    if "awstemplateformatversion" in content or '"awstemplateformatversion"' in content:
        return True
    if "aws::" in content:
        return True
    if "transform:" in content and "aws::" in content:
        return True
    return False


def _tool_rules(tool_config: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(tool_config, dict):
        return {}
    raw_rules = tool_config.get("rules")
    if isinstance(raw_rules, dict):
        return raw_rules
    return {}


def _as_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None


def _eslint_command(repo_path: Path | None) -> list[str] | None:
    if repo_path is None:
        return ["eslint"] if shutil.which("eslint") else None

    local = repo_path / "node_modules" / ".bin" / "eslint"
    if local.exists():
        return [str(local)]
    if shutil.which("eslint"):
        return ["eslint"]
    return None


def _gradlew_path(repo_path: Path | None) -> Path | None:
    if repo_path is None:
        return None
    candidates = [repo_path / "gradlew", repo_path / "gradlew.bat"]
    return _first_existing(candidates)


def _first_existing(paths: list[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def _parse_json_documents(payload_text: str) -> list[Any]:
    decoder = json.JSONDecoder()
    documents: list[Any] = []
    index = 0
    length = len(payload_text)
    while index < length:
        while index < length and payload_text[index].isspace():
            index += 1
        if index >= length:
            break
        document, offset = decoder.raw_decode(payload_text, index)
        documents.append(document)
        index = offset
    return documents


def _extract_first(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        first = value[0]
        return str(first) if first is not None else None
    return None


def _extract_semgrep_cwe(metadata: dict[str, Any]) -> str | None:
    cwe = _extract_first(metadata.get("cwe"))
    if not cwe:
        return None
    return cwe.split(":", maxsplit=1)[0]


def _checkov_category(check_type: str) -> str:
    if check_type in {"dockerfile", "sca_image", "sca_package"}:
        return "container"
    if check_type == "secrets":
        return "secret"
    return "iac"


def _checkov_line(item: dict[str, Any]) -> int | None:
    line_range = item.get("file_line_range")
    if isinstance(line_range, list) and line_range:
        try:
            return int(line_range[0])
        except TypeError, ValueError:
            return None
    return None


def _checkov_file_path(item: dict[str, Any], repo_path: Path) -> str | None:
    for key in ("repo_file_path", "file_abs_path", "file_path"):
        raw_value = item.get(key)
        if not raw_value:
            continue
        path = Path(str(raw_value))
        if key == "file_path" and str(raw_value).startswith("/"):
            return str(raw_value).lstrip("/")
        return _relative_path(repo_path, path)
    return None


def _checkov_severity(item: dict[str, Any]) -> FindingSeverity:
    severity = item.get("severity")
    if severity:
        return _severity_from_label(str(severity))
    return FindingSeverity.MEDIUM
