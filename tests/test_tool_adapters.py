from pathlib import Path

from app.core.config import settings
from app.services import tool_adapters


def test_sqlfluff_file_groups_route_sql_and_plsql(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "schema.sql").write_text("select 1;\n", encoding="utf-8")
    (repo / "package.pkb").write_text("create package body demo as end;\n", encoding="utf-8")
    (repo / "proc.pls").write_text("create procedure demo is begin null; end;\n", encoding="utf-8")

    groups = tool_adapters._sqlfluff_file_groups(repo)  # noqa: SLF001

    assert set(groups["ansi"]) == {"schema.sql"}
    assert set(groups["oracle"]) == {"package.pkb", "proc.pls"}


def test_cloudformation_template_detection_is_specific(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "stack.yaml").write_text(
        "AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n",
        encoding="utf-8",
    )
    (repo / "k8s.yaml").write_text(
        "apiVersion: v1\nkind: Service\nmetadata:\n  name: app\n",
        encoding="utf-8",
    )
    (repo / "nested.template").write_text("Resources: {}\n", encoding="utf-8")

    templates = tool_adapters._matching_cloudformation_templates(repo)  # noqa: SLF001

    assert "stack.yaml" in templates
    assert "nested.template" in templates
    assert "k8s.yaml" not in templates


def test_runtime_capabilities_include_new_iac_tools(monkeypatch) -> None:
    original_which = tool_adapters.shutil.which

    def fake_which(tool_name: str) -> str | None:
        if tool_name in {"tflint", "cfn-lint"}:
            return f"/usr/local/bin/{tool_name}"
        return original_which(tool_name)

    monkeypatch.setattr(tool_adapters.shutil, "which", fake_which)

    capabilities = tool_adapters.get_runtime_tool_capabilities()

    assert capabilities["tflint"] is True
    assert capabilities["cfn-lint"] is True


def test_build_tool_adapters_disabled_by_default(monkeypatch, tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "gradlew").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    (repo / "sample.csproj").write_text("<Project></Project>\n", encoding="utf-8")

    monkeypatch.setattr(settings, "enable_repo_build_tool_adapters", False)

    android = tool_adapters._run_android_lint(1, repo)  # noqa: SLF001
    dotnet = tool_adapters._run_dotnet_analyzers(1, repo)  # noqa: SLF001

    assert android.status.value == "skipped"
    assert dotnet.status.value == "skipped"
    assert "disabled by default" in (android.error or "")
    assert "disabled by default" in (dotnet.error or "")
