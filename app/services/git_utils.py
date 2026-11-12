"""Repository cloning helpers."""

import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import unquote

from app.core.config import settings
from app.core.network_security import ensure_safe_outbound_url, is_safe_repo_url


def _run_git(
    args: list[str], *, cwd: Path | None = None, timeout_seconds: int | None = None
) -> subprocess.CompletedProcess[str]:
    effective_timeout = (
        timeout_seconds if timeout_seconds is not None else settings.git_clone_timeout_seconds
    )
    return subprocess.run(
        args,
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        timeout=effective_timeout,
    )


def clone_repository(
    repo: str,
    branch: str | None = None,
    commit: str | None = None,
    *,
    timeout_seconds: int | None = None,
) -> Path:
    """Clone a repository into a temporary directory and return the path."""

    if not is_safe_repo_url(repo):
        raise ValueError(
            "Unsupported repository URL scheme. Only https:// and file:// are allowed."
        )
    if repo.startswith("https://"):
        ensure_safe_outbound_url(repo, allow_http=False)
    if repo.startswith("file://") and not settings.enable_file_repo_access:
        raise ValueError("Local file:// repository access is disabled")

    destination = Path(tempfile.mkdtemp(prefix="vigilweave-"))
    repo_url = repo
    if repo.startswith("file://"):
        repo_url = _resolve_local_repo_path(repo.removeprefix("file://"))
    try:
        clone_command = ["git", "clone"]
        if branch and not commit:
            clone_command.extend(["--branch", branch, "--depth", "1"])
        clone_command.extend([repo_url, str(destination)])
        _run_git(clone_command, timeout_seconds=timeout_seconds)
        if commit:
            _run_git(
                ["git", "checkout", commit],
                cwd=destination,
                timeout_seconds=timeout_seconds,
            )
        return destination
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise


def _resolve_local_repo_path(raw_path: str) -> str:
    """Resolve a local repo path, with optional host-to-container remapping."""

    host_root = settings.host_repo_root
    if not host_root:
        raise ValueError("HOST_REPO_ROOT must be configured for local file:// repository access")

    local_path = Path(unquote(raw_path)).expanduser()
    if local_path.exists():
        return _validated_local_repo_path(local_path, allowed_root=Path(host_root).expanduser())

    try:
        relative_path = local_path.resolve().relative_to(Path(host_root).expanduser().resolve())
    except ValueError:
        raise ValueError(
            "Local repository path is outside the configured host repository root"
        ) from None

    mapped = Path(settings.container_repo_root).expanduser() / relative_path
    return _validated_local_repo_path(
        mapped, allowed_root=Path(settings.container_repo_root).expanduser()
    )


def _validated_local_repo_path(path: Path, *, allowed_root: Path) -> str:
    """Return a validated local repository path constrained to an allowlisted root."""

    candidate = path.resolve(strict=False)
    root = allowed_root.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "Local repository path is outside the configured host repository root"
        ) from exc
    return str(candidate)


def git_history(
    repo_path: Path,
    *,
    branch: str | None = None,
    limit: int = 50,
    timeout_seconds: int | None = None,
) -> list[dict[str, str]]:
    """Return commit history for a local repository clone."""

    command = [
        "git",
        "log",
        f"--max-count={max(1, limit)}",
        "--date=unix",
        "--pretty=format:%H%x09%an%x09%ae%x09%ad%x09%s",
    ]
    if branch:
        command.append(branch)
    result = _run_git(
        command,
        cwd=repo_path,
        timeout_seconds=timeout_seconds or settings.git_blame_timeout_seconds,
    )
    history: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 4)
        if len(parts) != 5:
            continue
        history.append(
            {
                "commit": parts[0],
                "author": parts[1],
                "author_email": parts[2],
                "authored_at_unix": parts[3],
                "summary": parts[4],
            }
        )
    return history


def git_blame_line(
    repo_path: Path, file_path: str, line: int, *, timeout_seconds: int | None = None
) -> dict[str, str]:
    """Return git blame data for one file line."""

    command = [
        "git",
        "blame",
        "-L",
        f"{line},{line}",
        "--line-porcelain",
        "--",
        file_path,
    ]
    result = _run_git(
        command,
        cwd=repo_path,
        timeout_seconds=timeout_seconds or settings.git_blame_timeout_seconds,
    )
    parsed: dict[str, str] = {}
    first = result.stdout.splitlines()[0].split()
    parsed["commit"] = first[0]
    for raw in result.stdout.splitlines()[1:]:
        if raw.startswith("author "):
            parsed["author"] = raw.removeprefix("author ").strip()
        elif raw.startswith("author-mail "):
            parsed["author_email"] = raw.removeprefix("author-mail ").strip("<> ")
        elif raw.startswith("author-time "):
            parsed["authored_at_unix"] = raw.removeprefix("author-time ").strip()
        elif raw.startswith("summary "):
            parsed["summary"] = raw.removeprefix("summary ").strip()
        if raw.startswith("\t"):
            break
    return parsed
