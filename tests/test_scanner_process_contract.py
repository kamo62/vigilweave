import json
import subprocess
from pathlib import Path

from app.services import tool_adapters as adapters


def test_process_environment_and_version_are_isolated(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setenv("SYNTHETIC_SECRET", "private")
    monkeypatch.setenv("HOME", str(tmp_path))

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        assert "SYNTHETIC_SECRET" not in kwargs["env"]
        assert kwargs["env"]["HOME"] != str(tmp_path)
        assert kwargs["cwd"] == kwargs["env"]["HOME"]
        return subprocess.CompletedProcess(command, 0, "[]", "")

    monkeypatch.setattr(adapters.subprocess, "run", fake_run)
    monkeypatch.setattr(adapters.shutil, "which", lambda name: "/bin/" + name)
    assert adapters._run_ruff(1, tmp_path).status.value == "completed"
    assert len(calls) == 2


def test_hostile_configs_and_option_like_filenames(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "-danger.sql").write_text("select 1")
    (repo / "--config.sql").write_text("select 1")
    (repo / "nested").mkdir()
    (repo / "nested" / ".sqlfluff").write_text("[sqlfluff]\ntemplater = dbt")
    (repo / "nested" / "inside.sql").write_text("select 1")
    (repo / ".sqlfluff").write_text("[sqlfluff]\ntemplater = dbt")
    (repo / ".cfnlintrc").write_text("append_rules: [evil]")
    (repo / ".tflint.hcl").write_text('plugin "evil" { enabled = true }')
    (repo / ".checkov.yml").write_text("external-checks-dir: evil")
    (repo / "-stack.template").write_text("Resources: {}")
    (repo / "main.tf").write_text("terraform {}")
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if "--version" in command:
            return subprocess.CompletedProcess(command, 0, "v1", "")
        if command[0].endswith("tflint"):
            plugin_dir = Path(kwargs["env"]["TFLINT_PLUGIN_DIR"])
            assert plugin_dir.is_absolute() and plugin_dir.is_dir()
            assert not plugin_dir.is_relative_to(repo)
            assert not list(plugin_dir.iterdir())
        if command[0].endswith("sqlfluff"):
            output = "[]"
        elif command[0].endswith("checkov"):
            output = json.dumps({"results": {"failed_checks": []}})
        else:
            output = json.dumps(
                {
                    "version": "2.1.0",
                    "runs": [{"tool": {"driver": {"name": "stub"}}, "results": []}],
                }
            )
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setattr(adapters.subprocess, "run", fake_run)
    monkeypatch.setattr(adapters.shutil, "which", lambda name: "/bin/" + name)
    for name in ("sqlfluff", "cfn-lint", "tflint", "checkov"):
        assert adapters.run_tool(1, repo, name).status.value == "completed"
    scans = {Path(c[0][0]).name: c for c in calls if "--version" not in c[0]}
    assert "--ignore-local-config" in scans["sqlfluff"][0]
    assert scans["sqlfluff"][0][scans["sqlfluff"][0].index("--library-path") + 1] == "none"
    assert str(repo / "-danger.sql") in scans["sqlfluff"][0]
    assert str(repo / "--config.sql") in scans["sqlfluff"][0]
    assert str(repo / "nested" / "inside.sql") in scans["sqlfluff"][0]
    assert str(repo / "-stack.template") in scans["cfn-lint"][0]
    assert scans["cfn-lint"][1]["cwd"] != repo
    assert "--config" in scans["tflint"][0]
    assert "--config-file" in scans["checkov"][0]


def test_matching_does_not_follow_file_symlinks_outside_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    outside = tmp_path / "outside.sql"
    outside.write_text("select 1")
    (repo / "link.sql").symlink_to(outside)
    assert adapters._sqlfluff_file_groups(repo) == {}


def test_every_adapter_uses_clean_launcher_and_preserves_findings(monkeypatch, tmp_path):
    from app.core.config import settings

    repo = tmp_path / "repo"
    repo.mkdir()
    for name in ("x.sql", "x.tf", "x.template", "x.swift", "x.kt", "x.js", "x.csproj", "gradlew"):
        (repo / name).write_text("Resources: {}")
    monkeypatch.setattr(settings, "enable_repo_build_tool_adapters", True)
    monkeypatch.setattr(adapters.shutil, "which", lambda name: "/bin/" + name)
    calls = []
    sarif = json.dumps(
        {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "stub"}}, "results": []}]}
    )

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        assert kwargs["env"]["HOME"] != str(repo)
        assert "SYNTHETIC_SECRET" not in kwargs["env"]
        assert kwargs["cwd"] != repo or Path(command[0]).name in {"eslint", "gradlew", "dotnet"}
        if "--config-file" in command:
            assert Path(command[command.index("--config-file") + 1]).read_text() == "{}\n"
        if "--config" in command:
            contents = Path(command[command.index("--config") + 1]).read_text()
            assert contents == ("{}\n" if Path(command[0]).name == "swiftlint" else "")
        for option in ("--report-path", "--output", "--file"):
            if option in command and command[command.index(option) + 1].endswith(".sarif"):
                Path(command[command.index(option) + 1]).write_text(sarif)
        for arg in command:
            if arg.startswith("sarif:"):
                Path(arg[6:]).write_text(sarif)
            if arg.startswith("/p:ErrorLog="):
                Path(arg.split("=", 1)[1].split(";", 1)[0]).write_text(sarif)
        name = Path(command[0]).name
        if name == "gradlew":
            (repo / "lint-results.xml").write_text("<issues/>")
        if "--version" in command or command[1:] == ["version"]:
            output = "v1"
        elif name == "bandit":
            output = '{"results": []}'
        elif name == "semgrep":
            output = '{"results": []}'
        elif name == "checkov":
            output = '{"results": {"failed_checks": []}}'
        elif name == "sqlfluff":
            output = json.dumps(
                [
                    {
                        "filepath": str(repo / "x.sql"),
                        "violations": [{"code": "L001", "description": "synthetic"}],
                    }
                ]
            )
        elif name in {"tflint", "cfn-lint"}:
            output = sarif
        else:
            output = "[]"
        return subprocess.CompletedProcess(command, 0, output, "")

    monkeypatch.setenv("SYNTHETIC_SECRET", "private")
    monkeypatch.setattr(adapters.subprocess, "run", fake_run)
    tools = (
        "gitleaks",
        "semgrep",
        "bandit",
        "ruff",
        "eslint",
        "checkov",
        "tflint",
        "cfn-lint",
        "trivy",
        "sqlfluff",
        "swiftlint",
        "detekt",
        "android-lint",
        "dotnet-analyzers",
        "grype",
    )
    for name in tools:
        result = adapters.run_tool(1, repo, name)
        assert result.status.value == "completed", (name, result.error)
        if name == "sqlfluff":
            assert result.findings[0].file_path == "x.sql"
    launched = {Path(command[0]).name for command, _ in calls}
    assert set(tools) - {"android-lint", "dotnet-analyzers"} <= launched
    assert {"gradlew", "dotnet"} <= launched
    for name in launched - {"gradlew"}:
        assert any(
            Path(c[0]).name == name and ("--version" in c or c[1:] == ["version"]) for c, _ in calls
        )


def test_real_launcher_excludes_environment_and_sets_temporary_cwd(monkeypatch, tmp_path):
    import sys

    monkeypatch.setenv("SYNTHETIC_SECRET", "sensitive")
    monkeypatch.setenv("HOME", str(tmp_path))
    code = (
        'import json,os; print(json.dumps([os.getenv("SYNTHETIC_SECRET"),'
        'os.getcwd(),os.environ["HOME"]]))'
    )
    completed = adapters._scanner_process(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False, timeout=10
    )
    secret, cwd, home = json.loads(completed.stdout)
    assert secret is None
    assert Path(cwd).resolve() == Path(home).resolve()
    assert home != str(tmp_path)
    assert not Path(home).exists()
