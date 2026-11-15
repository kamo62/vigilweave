"""Synthetic regressions for Git transport and untrusted refs."""

import subprocess

import pytest
from pydantic import ValidationError

from app.models.ide import IdeAnalyzeRequest
from app.models.scan import ScanCreate
from app.services import git_utils


@pytest.mark.parametrize(
    "field,value",
    [
        ("branch", "--upload-pack=evil"),
        ("branch", "bad..name"),
        ("branch", "/main"),
        ("commit", "HEAD~1"),
        ("commit", "-abc"),
    ],
)
def test_request_refs_rejected(field, value):
    with pytest.raises(ValidationError):
        ScanCreate(repo="https://example.com/repo", **{field: value})


def test_ide_branch_rejected():
    with pytest.raises(ValidationError):
        IdeAnalyzeRequest(branch="--help")


def test_clone_keeps_credentials_out_of_command_and_config(monkeypatch):
    calls = []
    monkeypatch.setattr(git_utils, "ensure_safe_outbound_url", lambda *a, **k: None)
    monkeypatch.setenv("UNRELATED_SECRET", "do-not-forward")

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(subprocess, "run", run)
    path = git_utils.clone_repository(
        "https://user:pa%3Ass%40word@example.com/org/repo.git", branch="feature/test"
    )
    try:
        args, kwargs = calls[0]
        assert "pa%3Ass%40word" not in str(args)
        assert "user:" not in str(args)
        assert "https://example.com/org/repo.git" in args
        assert "UNRELATED_SECRET" not in kwargs["env"]
        assert kwargs["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
    finally:
        import shutil

        shutil.rmtree(path)


def test_clone_and_history_reject_bad_refs(monkeypatch, tmp_path):
    monkeypatch.setattr(git_utils, "ensure_safe_outbound_url", lambda *a, **k: None)
    with pytest.raises(ValueError):
        git_utils.clone_repository("https://example.com/repo", branch="--help")
    with pytest.raises(ValueError):
        git_utils.git_history(tmp_path, branch="--all")


def test_clone_redacts_credentials_from_git_failure(monkeypatch):
    monkeypatch.setattr(git_utils, "ensure_safe_outbound_url", lambda *a, **k: None)

    def run(args, **kwargs):
        raise subprocess.CalledProcessError(1, args, stderr="bad pa%3Ass%40word and pa:ss@word")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError) as error:
        git_utils.clone_repository("https://user:pa%3Ass%40word@example.com/org/repo.git")
    assert "pa%3Ass%40word" not in error.value.stderr
    assert "pa:ss@word" not in error.value.stderr


def test_clone_rejects_query_secrets(monkeypatch):
    monkeypatch.setattr(git_utils, "ensure_safe_outbound_url", lambda *a, **k: None)
    with pytest.raises(ValueError):
        git_utils.clone_repository("https://example.com/repo?token=secret")


def test_local_clone_history_and_detached_commit(tmp_path, monkeypatch):
    import shutil

    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(source)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "Tester"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "config", "user.email", "test@example.com"], check=True
    )
    (source / "file.txt").write_text("hello\n")
    outside = tmp_path / "private.txt"
    outside.write_text("synthetic host-only content\n")
    (source / "linked.txt").symlink_to(outside)
    subprocess.run(["git", "-C", str(source), "add", "file.txt", "linked.txt"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "commit", "-m", "first"], check=True, capture_output=True
    )
    sha = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    monkeypatch.setattr(git_utils.settings, "enable_file_repo_access", True)
    monkeypatch.setattr(git_utils.settings, "host_repo_root", str(tmp_path))
    clone = git_utils.clone_repository(source.as_uri(), branch="refs/heads/main", commit=sha[:10])
    try:
        assert not (clone / "linked.txt").is_symlink()
        assert "synthetic host-only content" not in (clone / "linked.txt").read_text()
        assert git_utils.git_history(clone, branch="refs/heads/main")[0]["commit"] == sha
        assert git_utils.git_blame_line(clone, "file.txt", 1)["commit"] == sha
    finally:
        shutil.rmtree(clone)


@pytest.mark.parametrize(
    "url",
    [
        "https://x-access-token:tok%40en@github.com/org/repo.git",
        "https://pat:tok%40en@dev.azure.com/org/project/_git/repo",
        "https://user:tok%40en@gitlab.example.com/nested/group/repo.git",
        "https://user:tok%40en@bitbucket.org/workspace/repo.git",
    ],
)
def test_auth_header_scoped_to_repository(monkeypatch, url):
    import base64
    import shutil

    calls = []
    monkeypatch.setattr(git_utils, "ensure_safe_outbound_url", lambda *a, **k: None)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda args, **kw: calls.append((args, kw)) or subprocess.CompletedProcess(args, 0, "", ""),
    )
    clone = git_utils.clone_repository(url)
    try:
        args, kwargs = calls[0]
        clean = args[-2]
        env = kwargs["env"]
        items = {
            env[f"GIT_CONFIG_KEY_{i}"]: env[f"GIT_CONFIG_VALUE_{i}"]
            for i in range(int(env["GIT_CONFIG_COUNT"]))
        }
        assert f"http.{clean}.extraheader" in items
        assert (
            base64.b64decode(items[f"http.{clean}.extraheader"].split()[-1])
            .decode()
            .endswith(":tok@en")
        )
        assert items["http.followRedirects"] == "false"
    finally:
        shutil.rmtree(clone)


def test_timeout_redacts_captured_output(monkeypatch):
    monkeypatch.setattr(git_utils, "ensure_safe_outbound_url", lambda *a, **k: None)

    def run(args, **kwargs):
        raise subprocess.TimeoutExpired(args, 1, output=b"pa%3Ass%40word", stderr=b"pa:ss@word")

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(subprocess.TimeoutExpired) as error:
        git_utils.clone_repository("https://user:pa%3Ass%40word@example.com/org/repo.git")
    assert b"pa%3Ass%40word" not in error.value.output
    assert b"pa:ss@word" not in error.value.stderr


def test_scan_api_rejects_invalid_ref(api_client, bootstrap_api_key):
    headers = bootstrap_api_key()
    response = api_client.post(
        "/api/v1/scans/",
        headers=headers,
        json={"repo": "https://example.com/org/repo.git", "branch": "--upload-pack=evil"},
    )
    assert response.status_code == 422


def test_full_branch_ref_cannot_hide_option():
    with pytest.raises(ValidationError):
        ScanCreate(repo="https://example.com/repo", branch="refs/heads/--help")
