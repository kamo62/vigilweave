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


class _IncompleteReport(ValueError):
    def __init__(self, message: str, findings: list[Finding]):
        super().__init__(message)
        self.findings = findings


def _incomplete(tool: str, message: str, findings: list[Finding]) -> ToolRunResult:
    return ToolRunResult(
        findings=findings,
        summary=f"{tool} failed",
        status=ToolExecutionStatus.FAILED,
        error=redact_sensitive_text(message)[:4000],
    )


def get_runtime_tool_capabilities(repo_path: Path | None = None) -> dict[str, bool]:
    """Return whether each configured tool can execute in the current environment."""

    return {
        "gitleaks": shutil.which("gitleaks") is not None,
        "semgrep": shutil.which("semgrep") is not None,
        "bandit": shutil.which("bandit") is not None,
        "ruff": shutil.which("ruff") is not None,
        "eslint": settings.enable_repo_build_tool_adapters
        and _eslint_command(repo_path) is not None,
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

    repo_path = repo_path.resolve()
    runner_id = str((tool_config or {}).get("runner") or tool).strip().lower()
    runner = runners.get(runner_id)
    if runner is None:
        return ToolRunResult(
            findings=[],
            summary=f"{tool} is not implemented",
            status=ToolExecutionStatus.SKIPPED,
            error=f"No adapter exists for {runner_id}",
        )
    try:
        if runner_id == "semgrep":
            return _run_semgrep(scan_id, repo_path, tool_config)
        if runner_id == "checkov":
            return _run_checkov(scan_id, repo_path, tool_config)
        if runner_id == "sqlfluff":
            return _run_sqlfluff(scan_id, repo_path, tool_config)
        return runner(scan_id, repo_path)
    except _IncompleteReport as exc:
        return _incomplete(tool, str(exc), exc.findings)


def _run_gitleaks(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("gitleaks")
    if executable is None:
        return _skipped("gitleaks", "gitleaks binary is not installed")

    with tempfile.NamedTemporaryFile(suffix=".sarif") as report:
        completed = _scanner_process(
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
        command.append(f"--config={config}")
    for include in include_patterns:
        command.append(f"--include={include}")
    for exclude in exclude_patterns:
        command.append(f"--exclude={exclude}")
    if jobs and jobs > 0:
        command.extend(["--jobs", str(jobs)])
    if timeout and timeout > 0:
        command.extend(["--timeout", str(timeout)])
    command.append(str(repo_path))

    completed = _scanner_process(
        command,
        capture_output=True,
        text=True,
        check=False,
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

    completed = _scanner_process(
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

    completed = _scanner_process(
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
    if not settings.enable_repo_build_tool_adapters:
        return _skipped("eslint", "Repository code execution requires explicit opt-in")
    command = _eslint_command(repo_path)
    if command is None:
        return _skipped("eslint", "eslint is unavailable or the repository has no JS/TS files")

    files = _matching_files(repo_path, {".js", ".jsx", ".ts", ".tsx"})
    if not files:
        return _skipped("eslint", "No JavaScript or TypeScript files were found")

    completed = _scanner_process(
        [
            *command,
            "--format",
            "json",
            "--no-error-on-unmatched-pattern",
            "--",
            *(str((repo_path / f).resolve()) for f in files),
        ],
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
        command.append(f"--check={check}")
    for skip_check in skip_checks:
        command.append(f"--skip-check={skip_check}")
    for framework in frameworks:
        command.append(f"--framework={framework}")

    completed = _scanner_process(
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
        summary=f"checkov reported {len(findings)} findings; repository config ignored",
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([executable, "--version"]),
    )


def _run_tflint(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("tflint")
    if executable is None:
        return _skipped("tflint", "tflint is not installed")
    if not _matching_files(repo_path, {".tf"}) and not _matching_name_suffix(repo_path, ".tf.json"):
        return _skipped("tflint", "No Terraform files were found")

    completed = _scanner_process(
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
        summary=f"tflint reported {len(findings)} findings; repository config ignored",
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

    completed = _scanner_process(
        [
            executable,
            "--format",
            "sarif",
            "--non-zero-exit-code",
            "none",
            "--",
            *[str((repo_path / f).resolve()) for f in templates],
        ],
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
        summary=f"cfn-lint reported {len(findings)} findings; repository config ignored",
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([executable, "--version"]),
    )


def _run_trivy(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("trivy")
    if executable is None:
        return _skipped("trivy", "trivy is not installed")

    with tempfile.NamedTemporaryFile(suffix=".sarif") as report:
        completed = _scanner_process(
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
        command = [
            executable,
            "lint",
            "--ignore-local-config",
            "--library-path",
            "none",
            "--format",
            "json",
            f"--dialect={dialect}",
        ]
        if include_rules:
            command.append(f"--rules={','.join(include_rules)}")
        if exclude_rules:
            command.append(f"--exclude-rules={','.join(exclude_rules)}")
        command.extend(["--", *(str((repo_path / f).resolve()) for f in files)])
        completed = _scanner_process(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=settings.tool_execution_timeout_seconds,
        )
        if completed.returncode not in {0, 1, 65}:
            if dialect == "oracle":
                fallback = _scanner_process(
                    [
                        executable,
                        "lint",
                        "--ignore-local-config",
                        "--library-path",
                        "none",
                        "--format",
                        "json",
                        "--dialect",
                        "ansi",
                        "--",
                        *(str((repo_path / f).resolve()) for f in files),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=settings.tool_execution_timeout_seconds,
                )
                if fallback.returncode in {0, 1, 65}:
                    try:
                        findings.extend(
                            _parse_sqlfluff_json(
                                fallback.stdout, scan_id, dialect="ansi", repo_path=repo_path
                            )
                        )
                    except _IncompleteReport as exc:
                        raise _IncompleteReport(str(exc), findings + exc.findings) from exc
                    continue
            failed = _failed("sqlfluff", completed)
            failed.findings = findings
            return failed
        try:
            findings.extend(
                _parse_sqlfluff_json(
                    completed.stdout, scan_id, dialect=dialect, repo_path=repo_path
                )
            )
        except _IncompleteReport as exc:
            raise _IncompleteReport(str(exc), findings + exc.findings) from exc

    return ToolRunResult(
        findings=findings,
        summary=(
            f"sqlfluff reported {len(findings)} findings across {total_files} files; "
            "repository config ignored"
        ),
        status=ToolExecutionStatus.COMPLETED,
        version=_tool_version([executable, "--version"]),
    )


def _run_swiftlint(scan_id: int, repo_path: Path) -> ToolRunResult:
    executable = shutil.which("swiftlint")
    if executable is None:
        return _skipped("swiftlint", "swiftlint is not installed")
    if not _matching_files(repo_path, {".swift"}):
        return _skipped("swiftlint", "No Swift files were found")

    completed = _scanner_process(
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
        completed = _scanner_process(
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

    completed = _scanner_process(
        [str(gradlew), "lint"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=settings.tool_execution_timeout_seconds,
    )
    report_path = next(repo_path.rglob("lint-results*.xml"), None)
    if report_path is None:
        return _incomplete("android-lint", "android lint did not produce an XML report", [])
    findings = _parse_android_lint_xml(report_path, scan_id, repo_path)
    if completed.returncode != 0:
        return _incomplete(
            "android-lint", "android lint failed; report may be incomplete", findings
        )
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
        completed = _scanner_process(
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
        if completed.returncode != 0:
            findings = []
            try:
                findings = _parse_sarif(Path(report.name), scan_id, "dotnet-analyzers", "quality")
            except _IncompleteReport as exc:
                findings = exc.findings
            except ValueError, OSError:
                pass
            result = _failed("dotnet-analyzers", completed)
            result.findings = findings
            return result
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
        completed = _scanner_process(
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
        raise ValueError(f"{tool} did not produce a SARIF report")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return _parse_sarif_payload(payload, scan_id, tool, default_category)


def _parse_sarif_text(
    payload_text: str, scan_id: int, tool: str, default_category: str
) -> list[Finding]:
    if not payload_text.strip():
        raise ValueError(f"{tool} did not produce a SARIF report")
    payload = json.loads(payload_text)
    return _parse_sarif_payload(payload, scan_id, tool, default_category)


def _parse_sarif_payload(
    payload: dict[str, Any], scan_id: int, tool: str, default_category: str
) -> list[Finding]:
    if not isinstance(payload, dict) or payload.get("version") != "2.1.0":
        raise ValueError(f"{tool} produced invalid SARIF metadata")
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError(f"{tool} produced SARIF without runs")
    for run in runs:
        if not isinstance(run, dict) or not isinstance(run.get("tool"), dict):
            raise ValueError(f"{tool} produced an invalid SARIF run")
        driver = run["tool"].get("driver")
        if not isinstance(driver, dict) or not isinstance(driver.get("name"), str):
            raise ValueError(f"{tool} produced SARIF without a driver")
        if not isinstance(run.get("results"), list):
            raise ValueError(f"{tool} produced SARIF without results")
        invocations = run.get("invocations", [])
        rules = driver.get("rules", [])
        if not isinstance(invocations, list) or any(not isinstance(i, dict) for i in invocations):
            raise ValueError(f"{tool} produced invalid SARIF invocations")
        if not isinstance(rules, list) or any(
            not isinstance(r, dict) or not isinstance(r.get("id"), str) for r in rules
        ):
            raise ValueError(f"{tool} produced invalid SARIF rules")
        for rule in rules:
            for key in ("shortDescription", "fullDescription", "properties"):
                if key in rule and not isinstance(rule[key], dict):
                    raise ValueError(f"{tool} produced an invalid SARIF rule")
            for key in ("shortDescription", "fullDescription"):
                description = rule.get(key, {})
                if "text" in description and not isinstance(description["text"], str):
                    raise ValueError(f"{tool} produced an invalid SARIF rule description")
            tags = rule.get("properties", {}).get("tags", [])
            if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
                raise ValueError(f"{tool} produced invalid SARIF rule tags")
        for result in run["results"]:
            if not isinstance(result, dict):
                raise ValueError(f"{tool} produced an invalid SARIF result")
            for key in ("message", "properties"):
                if key in result and not isinstance(result[key], dict):
                    raise ValueError(f"{tool} produced an invalid SARIF result {key}")
            message = result.get("message")
            if not isinstance(message, dict) or not any(
                isinstance(message.get(key), str) and message[key] for key in ("text", "id")
            ):
                raise ValueError(f"{tool} produced SARIF without a result message")
            if any(key in message and not isinstance(message[key], str) for key in ("text", "id")):
                raise ValueError(f"{tool} produced an invalid SARIF message")
            if "ruleId" in result and not isinstance(result["ruleId"], str):
                raise ValueError(f"{tool} produced an invalid SARIF rule id")
            locations = result.get("locations", [])
            if not isinstance(locations, list):
                raise ValueError(f"{tool} produced invalid SARIF locations")
            for location in locations:
                if not isinstance(location, dict) or not isinstance(
                    location.get("physicalLocation", {}), dict
                ):
                    raise ValueError(f"{tool} produced an invalid SARIF location")
                physical = location.get("physicalLocation", {})
                if any(
                    not isinstance(physical.get(k, {}), dict)
                    for k in ("region", "artifactLocation")
                ):
                    raise ValueError(f"{tool} produced an invalid SARIF physical location")
                region = physical.get("region", {})
                if any(
                    key in region
                    and (not isinstance(region[key], int) or isinstance(region[key], bool))
                    for key in ("startLine", "startColumn")
                ):
                    raise ValueError(f"{tool} produced an invalid SARIF region")
                uri = physical.get("artifactLocation", {}).get("uri")
                if uri is not None and not isinstance(uri, str):
                    raise ValueError(f"{tool} produced an invalid SARIF artifact URI")
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
    if any(
        invocation.get("executionSuccessful") is False
        for run in runs
        for invocation in run.get("invocations", [])
    ):
        raise _IncompleteReport(f"{tool} reported an unsuccessful SARIF invocation", findings)
    return findings


def _parse_ruff_json(payload_text: str, scan_id: int) -> list[Finding]:
    if not payload_text.strip():
        raise ValueError("ruff did not produce a JSON report")
    payload = json.loads(payload_text)
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ValueError("ruff produced an invalid JSON report")
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
        raise ValueError("bandit did not produce a JSON report")
    payload = json.loads(payload_text)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("results"), list)
        or payload.get("errors")
    ):
        raise ValueError("bandit produced an invalid or incomplete report")
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
        raise ValueError("semgrep did not produce a JSON report")
    payload = json.loads(payload_text)
    if (
        not isinstance(payload, dict)
        or not isinstance(payload.get("results"), list)
        or payload.get("errors")
    ):
        raise ValueError("semgrep produced an invalid or incomplete report")
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
        raise ValueError("eslint did not produce a JSON report")
    payload = json.loads(payload_text)
    if not isinstance(payload, list):
        raise ValueError("eslint produced an invalid JSON report")
    findings: list[Finding] = []
    incomplete = False
    for file_report in payload:
        if (
            not isinstance(file_report, dict)
            or not isinstance(file_report.get("filePath"), str)
            or not isinstance(file_report.get("messages"), list)
            or any(
                not isinstance(m, dict) or not isinstance(m.get("message"), str)
                for m in file_report["messages"]
            )
        ):
            raise ValueError("eslint produced an invalid file report")
        incomplete |= bool(file_report.get("fatalErrorCount")) or any(
            m.get("fatal") is True for m in file_report["messages"]
        )
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
    if incomplete:
        raise _IncompleteReport(
            "eslint reported fatal parsing errors; analysis incomplete", findings
        )
    return findings


def _parse_checkov_json(payload_text: str, scan_id: int, repo_path: Path) -> list[Finding]:
    if not payload_text.strip():
        raise ValueError("checkov did not produce a JSON report")

    findings: list[Finding] = []
    incomplete = False
    for payload in _parse_json_documents(payload_text):
        documents = payload if isinstance(payload, list) else [payload]
        if not documents:
            raise ValueError("checkov produced an empty JSON report")
        for document in documents:
            if not isinstance(document, dict) or not isinstance(document.get("results"), dict):
                raise ValueError("checkov produced an invalid report")
            results = document["results"]
            if not isinstance(results.get("failed_checks"), list) or any(
                not isinstance(i, dict) for i in results["failed_checks"]
            ):
                raise ValueError("checkov produced invalid failed checks")
            if any(
                not isinstance(i.get("check_id"), str) or not isinstance(i.get("check_name"), str)
                for i in results["failed_checks"]
            ):
                raise ValueError("checkov produced an invalid failed check")
            summary = document.get("summary", {})
            if not isinstance(summary, dict):
                raise ValueError("checkov produced an invalid summary")
            incomplete |= bool(summary.get("parsing_errors")) or bool(results.get("parsing_errors"))
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
    if incomplete:
        raise _IncompleteReport("checkov reported parsing errors; analysis incomplete", findings)
    return findings


def _parse_sqlfluff_json(
    payload_text: str, scan_id: int, *, dialect: str, repo_path: Path | None = None
) -> list[Finding]:
    if not payload_text.strip():
        raise ValueError("sqlfluff did not produce a JSON report")
    payload = json.loads(payload_text)
    if not isinstance(payload, list):
        raise ValueError("sqlfluff produced an invalid JSON report")
    findings: list[Finding] = []
    incomplete = False
    for file_report in payload:
        if (
            not isinstance(file_report, dict)
            or not isinstance(file_report.get("filepath"), str)
            or not isinstance(file_report.get("violations"), list)
            or any(
                not isinstance(v, dict) or not isinstance(v.get("description"), str)
                for v in file_report["violations"]
            )
        ):
            raise ValueError("sqlfluff produced an invalid file report")
        incomplete |= any(v.get("code") in {"PRS", "TMP", "LXR"} for v in file_report["violations"])
        relative_path = file_report.get("filepath")
        if relative_path and repo_path and Path(relative_path).is_absolute():
            relative_path = _relative_path(repo_path, Path(relative_path))
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
    if incomplete:
        raise _IncompleteReport(
            "sqlfluff reported parsing, templating or lexing errors; analysis incomplete", findings
        )
    return findings


def _parse_swiftlint_json(payload_text: str, scan_id: int, repo_path: Path) -> list[Finding]:
    if not payload_text.strip():
        raise ValueError("swiftlint did not produce a JSON report")
    payload = json.loads(payload_text)
    if not isinstance(payload, list):
        raise ValueError("swiftlint produced an invalid JSON report")
    findings: list[Finding] = []
    for item in payload:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("file"), str)
            or not isinstance(item.get("reason"), str)
        ):
            raise ValueError("swiftlint produced an invalid finding")
        relative_path = _relative_path(repo_path, Path(item["file"]))
        severity = (
            FindingSeverity.MEDIUM if item.get("severity") == "error" else FindingSeverity.LOW
        )
        rule_id = item.get("rule_id")
        message = item["reason"]
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
    if root.tag != "issues" or any(child.tag != "issue" for child in root):
        raise ValueError("android lint produced an invalid XML report")
    for issue in root.findall("issue"):
        if (
            not issue.get("id")
            or not issue.get("message")
            or any(child.tag != "location" for child in issue)
        ):
            raise ValueError("android lint produced an invalid issue")
        location = issue.find("location")
        file_path = location.get("file") if location is not None else None
        line_text = location.get("line") if location is not None else None
        column_text = location.get("column") if location is not None else None
        line = int(line_text) if line_text else None
        column = int(column_text) if column_text else None
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
    if any(issue.get("id") in {"LintError", "LintErrorReported"} for issue in root):
        raise _IncompleteReport("android lint reported an analysis error", findings)
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


def _safe_repository_file(repo_path: Path, file_path: Path) -> bool:
    try:
        return (
            ".git" not in file_path.relative_to(repo_path).parts
            and file_path.is_file()
            and file_path.resolve().is_relative_to(repo_path.resolve())
        )
    except OSError, ValueError, RuntimeError:
        return False


def _scanner_process(
    command: list[str],
    *,
    cwd: Path | None = None,
    capture_output: bool,
    text: bool,
    check: bool,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    """Run a scanner with a private home and an explicit, credential-free environment."""
    tool = Path(command[0]).name
    with tempfile.TemporaryDirectory(prefix="vigilweave-scanner-") as work:
        work_path = Path(work)
        env = {
            "PATH": os.pathsep.join(
                p for p in os.environ.get("PATH", os.defpath).split(os.pathsep) if os.path.isabs(p)
            ),
            "HOME": work,
            "XDG_CONFIG_HOME": str(work_path / "config"),
            "XDG_CACHE_HOME": str(work_path / "cache"),
            "LANG": "C.UTF-8",
            "SEMGREP_SEND_METRICS": "off",
        }
        command = list(command)
        is_probe = "--version" in command or command[1:] == ["version"]
        if tool == "tflint":
            plugin_dir = work_path / "plugins"
            plugin_dir.mkdir()
            env["TFLINT_PLUGIN_DIR"] = str(plugin_dir)
        if not is_probe and tool == "tflint":
            config = work_path / "tflint.hcl"
            config.write_text("", encoding="utf-8")
            command.extend(["--config", str(config), "--chdir", str(Path(cwd or ".").resolve())])
            cwd = None
        elif not is_probe and tool == "swiftlint":
            config = work_path / "swiftlint.yml"
            config.write_text("{}\n", encoding="utf-8")
            command.extend(["--config", str(config)])
        elif not is_probe and tool == "checkov":
            config = work_path / "checkov.yaml"
            config.write_text("{}\n", encoding="utf-8")
            command.extend(["--config-file", str(config)])
        return subprocess.run(
            command,
            cwd=cwd or work,
            env=env,
            capture_output=capture_output,
            text=text,
            check=check,
            timeout=timeout,
        )


def _tool_version(command: list[str]) -> str | None:
    try:
        completed = _scanner_process(
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
        if not _safe_repository_file(repo_path, file_path):
            continue
        if file_path.suffix.lower() in suffixes:
            matches.append(str(file_path.relative_to(repo_path)))
    return matches


def _matching_name_suffix(repo_path: Path, file_name_suffix: str) -> list[str]:
    matches: list[str] = []
    for file_path in repo_path.rglob("*"):
        if not _safe_repository_file(repo_path, file_path):
            continue
        if file_path.name.lower().endswith(file_name_suffix):
            matches.append(str(file_path.relative_to(repo_path)))
    return matches


def _sqlfluff_file_groups(repo_path: Path) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}
    sql_suffixes = {".sql", ".psql"}
    plsql_suffixes = {".pls", ".pks", ".pkb", ".prc", ".fnc", ".trg", ".tpb", ".tps", ".sqlj"}

    for file_path in repo_path.rglob("*"):
        if not _safe_repository_file(repo_path, file_path):
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
        if not _safe_repository_file(repo_path, file_path):
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
