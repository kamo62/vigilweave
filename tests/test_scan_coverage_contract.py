import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session

from app.core import database
from app.models import Finding, FindingSeverity, Scan, ToolExecution, Waiver
from app.services import policy_engine, scanner
from app.services.quality_analyzer import analyze_files
from app.services.tool_adapters import (
    _parse_bandit_json,
    _parse_ruff_json,
    _parse_sarif_text,
    _parse_semgrep_json,
)


@pytest.mark.parametrize("payload", ["", "{}", '{"runs": []}', '{"runs": [{}]}'])
def test_invalid_sarif_is_not_a_clean_report(payload):
    with pytest.raises(ValueError):
        _parse_sarif_text(payload, 1, "synthetic", "security")


def test_valid_empty_sarif_is_clean():
    report = {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "test"}}, "results": []}]}
    assert _parse_sarif_text(json.dumps(report), 1, "synthetic", "security") == []


def test_no_completed_analyser_fails_gate(api_client):
    with Session(database.engine) as session:
        scan = Scan(repo="https://example.com/repo")
        session.add(scan)
        session.flush()
        session.add(ToolExecution(scan_id=scan.id, tool="synthetic", status="skipped"))
        session.commit()
        scanner.finalize_scan(session, scan.id, {}, ["synthetic"], [])
        session.refresh(scan)
        assert scan.quality_gate_passed is False
        assert scan.scan_metadata["coverage_reasons"]


@pytest.mark.parametrize(
    "endpoint,payload",
    [
        (
            "/api/v1/scans/",
            {"repo": "https://example.com/repo", "scan_type": "custom", "tools": ["unknown"]},
        ),
        ("/api/v1/ide/analyze", {"scan_type": "custom", "tools": [], "files": []}),
    ],
)
def test_invalid_custom_selection_is_rejected(api_client, endpoint, payload):
    response = api_client.post(endpoint, json=payload)
    assert response.status_code == 422


def test_quality_analysis_does_not_read_symlinks_outside_checkout(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("print('outside')\n")
    (repo / "linked.py").symlink_to(outside)
    metrics, _ = analyze_files(repo, 1)
    assert not metrics


def test_simple_functions_are_not_reported_as_one_complex_function(tmp_path):
    (tmp_path / "sample.py").write_text(
        "\n".join(
            f"def function_{i}(x):\n    if x:\n        return 1\n    return 0\n" for i in range(20)
        )
    )
    _, findings = analyze_files(tmp_path, 1)
    assert not [finding for finding in findings if finding.category == "complexity"]


@pytest.mark.parametrize(
    "tool,payload",
    [
        ("ruff", ""),
        ("ruff", "{}"),
        ("bandit", "{}"),
        ("bandit", '{"results": [], "errors": ["failed"]}'),
        ("semgrep", "{}"),
        ("semgrep", '{"results": [], "errors": [{"message": "failed"}]}'),
    ],
)
def test_invalid_json_reports_are_not_clean(tool, payload, tmp_path):
    with pytest.raises(ValueError):
        if tool == "ruff":
            _parse_ruff_json(payload, 1)
        elif tool == "bandit":
            _parse_bandit_json(payload, 1, tmp_path)
        else:
            _parse_semgrep_json(payload, 1, tmp_path)


def test_sqlite_waiver_expiry_is_compared_as_utc(api_client):
    with Session(database.engine) as session:
        session.add(Waiver(reason="synthetic", expires_at=datetime.now(UTC) + timedelta(days=1)))
        session.commit()
        session.expunge_all()
        scan = Scan(repo="https://example.com/repo")
        finding = Finding(
            scan_id=1,
            tool="synthetic",
            severity=FindingSeverity.LOW,
            title="synthetic",
            message="synthetic",
            category="security",
            fingerprint="x",
        )
        _, suppressed = policy_engine.apply_waivers(session, scan, [finding])
        assert suppressed == 1


def test_gate_metadata_includes_coverage_failure(api_client):
    with Session(database.engine) as session:
        scan = Scan(repo="https://example.com/repo")
        session.add(scan)
        session.flush()
        session.add(ToolExecution(scan_id=scan.id, tool="synthetic", status="skipped"))
        session.commit()
        scanner.finalize_scan(session, scan.id, {}, ["synthetic"], [])
        session.refresh(scan)
        assert scan.scan_metadata["policy"]["passed"] is scan.quality_gate_passed is False
        assert "No analyser completed successfully" in scan.scan_metadata["policy"]["reasons"]


def test_gate_metadata_uses_deployment_thresholds_without_profile(api_client, monkeypatch):
    monkeypatch.setattr(scanner, "matching_policy", lambda *args: None)
    monkeypatch.setattr(scanner.settings, "max_high_findings", 0)
    with Session(database.engine) as session:
        scan = Scan(repo="https://example.com/repo")
        session.add(scan)
        session.flush()
        session.add(ToolExecution(scan_id=scan.id, tool="synthetic", status="completed"))
        session.add(
            Finding(
                scan_id=scan.id,
                tool="synthetic",
                severity=FindingSeverity.HIGH,
                title="Finding",
                message="Finding",
                category="security",
                fingerprint="x",
            )
        )
        session.commit()
        scanner.finalize_scan(session, scan.id, {}, ["synthetic"], [])
        session.refresh(scan)
        assert scan.scan_metadata["policy"]["passed"] is scan.quality_gate_passed is False
        assert scan.scan_metadata["policy"]["reasons"]


def test_shared_aggregation_redacts_findings_and_retains_partial_results(tmp_path, monkeypatch):
    from app.models import ToolExecutionStatus
    from app.services.finding_identity import legacy_fingerprint_digest
    from app.services.tool_adapters import ToolRunResult

    (tmp_path / "app.py").write_text("\n" * 6 + "synthetic source\n")

    def fake_tool(scan_id, repo_path, tool, **kwargs):
        return ToolRunResult(
            findings=[
                Finding(
                    scan_id=scan_id,
                    tool=tool,
                    severity=FindingSeverity.HIGH,
                    title="token=synthetic-title",
                    message="password=synthetic-message; value synthetic-value",
                    description="Bearer synthetic.description",
                    category="security",
                    file_path="app.py",
                    line=7,
                    rule_id="RULE-1",
                    fingerprint="stable",
                    tool_metadata={
                        "secret": "synthetic-value",
                        "nested": ["token=synthetic-nested", "diagnostic"],
                    },
                )
            ],
            summary="partial",
            status=ToolExecutionStatus.FAILED,
        )

    monkeypatch.setattr(scanner, "run_tool", fake_tool)
    monkeypatch.setattr(scanner, "detect_languages", lambda path: {})
    monkeypatch.setattr(scanner, "_select_tools", lambda *args: (["synthetic"], {}))
    findings, executions, _, _ = scanner.analyze_directory(1, tmp_path, "custom", [], False)
    assert executions[0].status == ToolExecutionStatus.FAILED
    assert len(findings) == 1
    finding = findings[0]
    assert "synthetic-" not in finding.title + finding.message
    assert "synthetic.description" not in finding.description
    assert finding.tool_metadata == {
        "secret": "***",
        "nested": ["token=***", "diagnostic"],
        "identity_version": 1,
        "original_fingerprint_sha256": legacy_fingerprint_digest("stable"),
        "legacy_fingerprints": [legacy_fingerprint_digest("stable")],
    }
    assert (finding.file_path, finding.line, finding.rule_id) == (
        "app.py",
        7,
        "RULE-1",
    )
    assert finding.fingerprint.startswith("v1:")
