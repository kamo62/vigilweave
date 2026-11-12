from pathlib import Path

from sqlmodel import Session

from app.models import ToolExecutionStatus
from app.services.config_loader import upsert_tenant_tool_override
from app.services.scanner import analyze_directory
from app.services.tool_adapters import ToolRunResult


def test_scanner_applies_tenant_semgrep_rule_overrides(
    tmp_path: Path, monkeypatch, api_client
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "app.py").write_text(
        "def run(user_input):\n    return eval(user_input)\n",
        encoding="utf-8",
    )

    from app.core.database import engine as active_engine

    with Session(active_engine) as session:
        upsert_tenant_tool_override(
            session,
            tenant_slug="acme",
            tool_id="semgrep",
            patch={"rules": {"config": ["p/python"], "exclude": ["tests/**"]}},
        )

    captured_semgrep_configs: list[dict[str, object]] = []

    def fake_run_tool(
        scan_id: int,
        repo_path: Path,
        tool: str,
        *,
        tool_config: dict[str, object] | None = None,
    ) -> ToolRunResult:
        del scan_id, repo_path
        if tool == "semgrep":
            captured_semgrep_configs.append(tool_config or {})
        return ToolRunResult(
            findings=[],
            summary=f"{tool} fixture",
            status=ToolExecutionStatus.COMPLETED,
        )

    monkeypatch.setattr("app.services.scanner.run_tool", fake_run_tool)

    with Session(active_engine) as session:
        analyze_directory(
            1,
            repo,
            "fast",
            [],
            include_quality_metrics=False,
            session=session,
            tenant_slug="acme",
        )

    assert captured_semgrep_configs
    assert captured_semgrep_configs[0].get("rules") == {
        "config": ["p/python"],
        "exclude": ["tests/**"],
    }


def test_scanner_runs_tenant_custom_tool_with_runner(
    tmp_path: Path, monkeypatch, api_client
) -> None:
    repo = tmp_path / "repo-custom-tool"
    repo.mkdir()
    (repo / "service.py").write_text("print('hello')\n", encoding="utf-8")

    from app.core.database import engine as active_engine

    with Session(active_engine) as session:
        upsert_tenant_tool_override(
            session,
            tenant_slug="acme",
            tool_id="semgrep-strict",
            patch={
                "enabled": True,
                "category": "security",
                "languages": ["python"],
                "runner": "semgrep",
                "rules": {"config": ["p/python"], "timeout": 30},
            },
        )

    captured_calls: list[tuple[str, dict[str, object]]] = []

    def fake_run_tool(
        scan_id: int,
        repo_path: Path,
        tool: str,
        *,
        tool_config: dict[str, object] | None = None,
    ) -> ToolRunResult:
        del scan_id, repo_path
        captured_calls.append((tool, dict(tool_config or {})))
        return ToolRunResult(
            findings=[],
            summary=f"{tool} fixture",
            status=ToolExecutionStatus.COMPLETED,
        )

    monkeypatch.setattr("app.services.scanner.run_tool", fake_run_tool)

    with Session(active_engine) as session:
        analyze_directory(
            2,
            repo,
            "comprehensive",
            [],
            include_quality_metrics=False,
            session=session,
            tenant_slug="acme",
        )

    tools_run = {tool for tool, _ in captured_calls}
    assert "semgrep-strict" in tools_run
    custom_call = next(config for tool, config in captured_calls if tool == "semgrep-strict")
    assert custom_call.get("runner") == "semgrep"
    assert custom_call.get("rules") == {"config": ["p/python"], "timeout": 30}
