from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select

from app.core import database
from app.models import Finding, FindingSeverity, Scan, Waiver
from app.services import policy_engine, scanner


def finding(
    line=1, *, scan_id=1, fingerprint="a" * 40, message="issue", rule="R", category="security"
):
    return Finding(
        scan_id=scan_id,
        tool="synthetic",
        severity=FindingSeverity.HIGH,
        title="issue",
        message=message,
        category=category,
        file_path="app.py",
        line=line,
        rule_id=rule,
        fingerprint=fingerprint,
    )


def aggregate(monkeypatch, root, findings):
    monkeypatch.setattr(scanner, "detect_languages", lambda path: {})
    monkeypatch.setattr(scanner, "_select_tools", lambda *args: ([], {}))
    monkeypatch.setattr(scanner, "_run_tools", lambda *args: (findings, []))
    return scanner.analyze_directory(1, root, "custom", [], False)[0]


def test_identity_relocation_insertion_and_collisions(tmp_path, monkeypatch):
    first, second = tmp_path / "one", tmp_path / "two"
    first.mkdir()
    second.mkdir()
    (first / "app.py").write_text("issue\nrepeat\nrepeat\n")
    (second / "app.py").write_text("unrelated\nissue\nrepeat\nrepeat\n")

    def inputs(offset):
        return [
            finding(1 + offset, message="one"),
            finding(1 + offset, message="two"),
            finding(2 + offset),
            finding(3 + offset),
        ]

    a = aggregate(monkeypatch, first, inputs(0))
    b = aggregate(monkeypatch, second, inputs(1))
    assert len(a) == len(b) == 4
    assert {f.fingerprint for f in a} == {f.fingerprint for f in b}
    assert all(f.fingerprint.startswith("v1:") for f in a)
    assert str(first) not in str([f.tool_metadata for f in a])


def test_legacy_waiver_requires_scope_and_rule(api_client, tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text("issue\n")
    item = aggregate(monkeypatch, tmp_path, [finding()])[0]
    with Session(database.engine) as session:
        session.add(
            Waiver(
                tenant_slug="a",
                repo_pattern="repo",
                branch_pattern="main",
                rule_id="R",
                fingerprint="a" * 40,
                reason="legacy",
            )
        )
        session.commit()
        scan = Scan(tenant_slug="a", repo="repo", branch="main")
        assert policy_engine.apply_waivers(session, scan, [item])[1] == 1
        for changed in [
            Scan(tenant_slug="b", repo="repo", branch="main"),
            Scan(tenant_slug="a", repo="other", branch="main"),
            Scan(tenant_slug="a", repo="repo", branch="other"),
        ]:
            candidate = aggregate(monkeypatch, tmp_path, [finding()])[0]
            assert policy_engine.apply_waivers(session, changed, [candidate])[1] == 0
        candidate = aggregate(monkeypatch, tmp_path, [finding(rule="OTHER")])[0]
        assert policy_engine.apply_waivers(session, scan, [candidate])[1] == 0


def test_triage_previous_completed_scope_and_fixed_reopens(api_client, tmp_path, monkeypatch):
    from app.services.finding_identity import carry_triage

    now = datetime.now(UTC)
    with Session(database.engine) as session:
        previous = Scan(
            tenant_slug="a",
            project_id=17,
            repo="repo",
            branch="main",
            status="completed",
            completed_at=now - timedelta(minutes=1),
        )
        session.add(previous)
        session.flush()
        old = finding()
        old.scan_id = previous.id
        old.fingerprint = "v1:" + "b" * 64
        old.tool_metadata = {"identity_version": 1}
        old.review_status = "acknowledged"
        old.reviewed_by = "reviewer"
        old.is_suppressed = True
        session.add(old)
        session.commit()
        current = Scan(tenant_slug="a", project_id=17, repo="repo", branch="main")
        candidate = finding()
        candidate.fingerprint = old.fingerprint
        candidate.tool_metadata = {"identity_version": 1}
        carry_triage(session, current, [candidate])
        assert candidate.review_status == "acknowledged" and candidate.reviewed_by == "reviewer"
        assert not candidate.is_suppressed and candidate.waiver_id is None
        for scope in [
            Scan(tenant_slug="b", project_id=17, repo="repo", branch="main"),
            Scan(tenant_slug="a", project_id=None, repo="repo", branch="main"),
            Scan(tenant_slug="a", project_id=18, repo="repo", branch="main"),
            Scan(tenant_slug="a", project_id=17, repo="other", branch="main"),
            Scan(tenant_slug="a", project_id=17, repo="repo", branch="other"),
        ]:
            item = finding()
            item.fingerprint = old.fingerprint
            item.tool_metadata = {"identity_version": 1}
            carry_triage(session, scope, [item])
            assert item.review_status == "open"
        old.review_status = "fixed"
        session.add(old)
        session.commit()
        item = finding()
        item.fingerprint = old.fingerprint
        item.tool_metadata = {"identity_version": 1}
        carry_triage(session, current, [item])
        assert item.review_status == "open"


@pytest.mark.parametrize("category", ["complexity", "maintainability"])
def test_quality_file_wide_legacy_waiver(api_client, tmp_path, monkeypatch, category):
    (tmp_path / "app.py").write_text("def complex_function():\n    pass\n")
    original = (
        "quality:app.py:complexity:complex_function:1"
        if category == "complexity"
        else "quality:app.py:maintainability"
    )
    item = finding(fingerprint=original, category=category, rule=None)
    item.tool = "quality-analyzer"
    item = aggregate(monkeypatch, tmp_path, [item])[0]
    with Session(database.engine) as session:
        session.add(Waiver(fingerprint=f"quality:app.py:{category}", reason="old waiver"))
        session.commit()
        assert policy_engine.apply_waivers(session, Scan(repo="repo"), [item])[1] == 1


def test_execute_scan_persists_previous_decision(api_client, tmp_path, monkeypatch):
    from app.models import ToolExecutionStatus
    from app.services.finding_identity import assign_identities
    from app.services.tool_adapters import ToolRunResult

    previous_root = tmp_path / "previous"
    previous_root.mkdir()
    (previous_root / "app.py").write_text("issue\n")
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    (checkout / "app.py").write_text("unrelated\nissue\n")
    with Session(database.engine) as session:
        previous = Scan(
            tenant_slug="a",
            project_id=31,
            repo="repo",
            branch="main",
            status="completed",
            completed_at=datetime.now(UTC),
        )
        session.add(previous)
        session.flush()
        old = finding()
        old.scan_id = previous.id
        assign_identities(previous_root, [old])
        old.review_status = "wont_fix"
        old.reviewed_by = "reviewer"
        session.add(old)
        current = Scan(
            tenant_slug="a",
            project_id=31,
            repo="repo",
            branch="main",
            include_quality_metrics=False,
            scan_metadata={},
        )
        session.add(current)
        session.commit()
        current_id = current.id
        monkeypatch.setattr(scanner, "resolve_clone_url", lambda *args, **kwargs: "repo")
        monkeypatch.setattr(scanner, "clone_repository", lambda *args: checkout)
        monkeypatch.setattr(scanner, "detect_languages", lambda path: {})
        monkeypatch.setattr(scanner, "_select_tools", lambda *args: (["synthetic"], {}))
        monkeypatch.setattr(
            scanner,
            "run_tool",
            lambda scan_id, *args, **kwargs: ToolRunResult(
                findings=[finding(2, scan_id=scan_id)],
                summary="ok",
                status=ToolExecutionStatus.COMPLETED,
            ),
        )
        monkeypatch.setattr(scanner, "complete_github_check_run", lambda *args, **kwargs: None)
        scanner.execute_scan(session, current_id)
        result = session.exec(select(Finding).where(Finding.scan_id == current_id)).one()
        assert result.review_status == "wont_fix"
        assert result.reviewed_by == "reviewer"


def test_same_line_secrets_and_untrusted_paths(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text("two secrets on one line\n")
    one = finding(category="secret", message="secret detected")
    two = finding(category="secret", message="secret detected")
    one.tool_metadata = {"secret": "first synthetic secret"}
    two.tool_metadata = {"secret": "second synthetic secret"}
    results = aggregate(monkeypatch, tmp_path, [one, two])
    assert len({item.fingerprint for item in results}) == 2
    assert "first synthetic secret" not in str(results[0].tool_metadata)
    outside = tmp_path.parent / "outside-identity-source"
    outside.write_text("sensitive\n")
    (tmp_path / "link.py").symlink_to(outside)
    bad = finding()
    bad.file_path = "link.py"
    result = aggregate(monkeypatch, tmp_path, [bad])[0]
    assert result.fingerprint.startswith("unresolved:")
    assert "identity_version" not in result.tool_metadata
