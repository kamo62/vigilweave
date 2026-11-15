import json
import subprocess
from pathlib import Path

import pytest

from app.core.config import settings
from app.services import tool_adapters as a


@pytest.mark.parametrize(
    ("parser", "payload"),
    [
        ("eslint", "{}"),
        ("eslint", '[{"filePath":"x","messages":[null]}]'),
        ("checkov", "[]"),
        ("checkov", '{"results":{"failed_checks":[null]}}'),
        ("sqlfluff", "{}"),
        ("sqlfluff", '[{"filepath":"x","violations":[null]}]'),
        ("swiftlint", "{}"),
        ("swiftlint", "[null]"),
    ],
)
def test_invalid_json_reports_rejected(parser, payload, tmp_path):
    parse = {
        "eslint": lambda: a._parse_eslint_json(payload, 1, tmp_path),
        "checkov": lambda: a._parse_checkov_json(payload, 1, tmp_path),
        "sqlfluff": lambda: a._parse_sqlfluff_json(payload, 1, dialect="ansi"),
        "swiftlint": lambda: a._parse_swiftlint_json(payload, 1, tmp_path),
    }[parser]
    with pytest.raises((ValueError, TypeError)):
        parse()


@pytest.mark.parametrize("parser", ["eslint", "sqlfluff", "swiftlint"])
def test_empty_lists_are_valid(parser, tmp_path):
    parse = {
        "eslint": lambda: a._parse_eslint_json("[]", 1, tmp_path),
        "sqlfluff": lambda: a._parse_sqlfluff_json("[]", 1, dialect="ansi"),
        "swiftlint": lambda: a._parse_swiftlint_json("[]", 1, tmp_path),
    }[parser]
    assert parse() == []
    with pytest.raises(ValueError):
        {
            "eslint": lambda: a._parse_eslint_json("", 1, tmp_path),
            "sqlfluff": lambda: a._parse_sqlfluff_json("", 1, dialect="ansi"),
            "swiftlint": lambda: a._parse_swiftlint_json("", 1, tmp_path),
        }[parser]()


def test_checkov_empty_results_and_android_root(tmp_path):
    assert a._parse_checkov_json('{"results":{"failed_checks":[]}}', 1, tmp_path) == []
    report = tmp_path / "lint.xml"
    report.write_text("<issues/>")
    assert a._parse_android_lint_xml(report, 1, tmp_path) == []
    report.write_text("<wrong/>")
    with pytest.raises(ValueError):
        a._parse_android_lint_xml(report, 1, tmp_path)


@pytest.mark.parametrize("bad", [None, {"locations": [None]}, {"message": []}])
def test_sarif_rejects_malformed_results(bad):
    payload = {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "x"}}, "results": [bad]}]}
    with pytest.raises((ValueError, TypeError)):
        a._parse_sarif_payload(payload, 1, "x", "quality")


def test_partial_reports_and_build_failures_keep_findings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "enable_repo_build_tool_adapters", True)
    monkeypatch.setattr(a.shutil, "which", lambda name: "/bin/" + name)
    monkeypatch.setattr(a, "_tool_version", lambda command: "v")
    (tmp_path / "x.sql").write_text("select")
    (tmp_path / "x.js").write_text("x")
    (tmp_path / "x.csproj").write_text("<Project/>")
    (tmp_path / "gradlew").write_text("")
    sarif = {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "x"}}, "results": [{"message": {"text": "issue"}}]}],
    }

    def run(command, **kwargs):
        name = Path(command[0]).name
        if name == "sqlfluff":
            data = [
                {
                    "filepath": "x.sql",
                    "violations": [{"code": "PRS", "description": "parse failed"}],
                }
            ]
        elif name == "eslint":
            data = [
                {
                    "filePath": str(tmp_path / "x.js"),
                    "messages": [{"message": "parse failed", "fatal": True, "severity": 2}],
                }
            ]
        elif name == "dotnet":
            Path(
                next(x for x in command if x.startswith("/p:ErrorLog="))
                .split("=", 1)[1]
                .split(";", 1)[0]
            ).write_text(json.dumps(sarif))
            return subprocess.CompletedProcess(command, 1, "", "build failed")
        else:
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, 1, json.dumps(data), "")

    monkeypatch.setattr(a, "_scanner_process", run)
    for tool in ("sqlfluff", "eslint", "dotnet-analyzers"):
        result = a.run_tool(1, tmp_path, tool)
        assert result.status.value == "failed" and result.findings and result.error
    result = a.run_tool(1, tmp_path, "android-lint")
    assert result.status.value == "failed" and result.error


def test_checkov_partial_and_sarif_invocation_keep_findings(monkeypatch, tmp_path):
    monkeypatch.setattr(a.shutil, "which", lambda name: "/bin/" + name)
    checkov = {
        "results": {"failed_checks": [{"check_id": "CKV_X", "check_name": "issue"}]},
        "summary": {"parsing_errors": 1},
    }
    monkeypatch.setattr(
        a,
        "_scanner_process",
        lambda command, **kw: subprocess.CompletedProcess(command, 1, json.dumps(checkov), ""),
    )
    result = a.run_tool(1, tmp_path, "checkov")
    assert result.status.value == "failed" and len(result.findings) == 1
    assert "parsing errors" in result.error
    payload = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "x"}},
                "results": [{"message": {"text": "issue"}}],
                "invocations": [{"executionSuccessful": False}],
            }
        ],
    }
    with pytest.raises(ValueError) as error:
        a._parse_sarif_payload(payload, 1, "x", "quality")
    assert len(error.value.findings) == 1


def test_android_failed_build_keeps_report_findings(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "enable_repo_build_tool_adapters", True)
    (tmp_path / "gradlew").write_text("")
    (tmp_path / "lint-results.xml").write_text(
        '<issues><issue id="Example" message="issue" severity="Warning"/></issues>'
    )
    monkeypatch.setattr(
        a,
        "_scanner_process",
        lambda command, **kw: subprocess.CompletedProcess(command, 1, "", "failed"),
    )
    result = a.run_tool(1, tmp_path, "android-lint")
    assert result.status.value == "failed" and len(result.findings) == 1 and result.error
