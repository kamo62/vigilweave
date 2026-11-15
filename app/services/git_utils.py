"""Repository cloning helpers."""

import base64
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from app.core.config import settings
from app.core.git_refs import validate_branch, validate_commit
from app.core.network_security import ensure_safe_outbound_url, is_safe_repo_url


def _run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout_seconds: int | None = None,
    auth: tuple[str, str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    effective_timeout = (
        timeout_seconds if timeout_seconds is not None else settings.git_clone_timeout_seconds
    )
    env = {
        "PATH": os.defpath,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_ASKPASS": "/usr/bin/false",
        "LC_ALL": "C",
    }
    for name in ("SSL_CERT_FILE", "SSL_CERT_DIR"):
        if name in os.environ:
            env[name] = os.environ[name]
    config = [
        ("core.hooksPath", os.devnull),
        ("core.symlinks", "false"),
        ("credential.helper", ""),
        ("http.followRedirects", "false"),
        ("protocol.ext.allow", "never"),
    ]
    secrets = []
    if auth:
        url, username, password = auth
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
        config.append((f"http.{url}.extraheader", f"Authorization: Basic {encoded}"))
        secrets = [username, password, quote(username, safe=""), quote(password, safe=""), encoded]
    env["GIT_CONFIG_COUNT"] = str(len(config))
    for index, (key, value) in enumerate(config):
        env[f"GIT_CONFIG_KEY_{index}"] = key
        env[f"GIT_CONFIG_VALUE_{index}"] = value

    def redact(value: str | bytes | None) -> str | bytes | None:
        if value is None:
            return None
        binary = isinstance(value, bytes)
        if isinstance(value, bytes):
            text = value.decode("utf-8", errors="replace")
        else:
            text = value
        text = re.sub(r"(https?://)[^/@\s]+@", r"\1[redacted]@", text)
        for secret in secrets:
            if secret:
                text = text.replace(secret, "[redacted]")
        return text.encode() if binary else text

    try:
        return subprocess.run(
            args,
            cwd=cwd,
            check=True,
            capture_output=True,
            text=True,
            timeout=effective_timeout,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        raise subprocess.CalledProcessError(
            exc.returncode, args, output=redact(exc.stdout), stderr=redact(exc.stderr)
        ) from None
    except subprocess.TimeoutExpired as exc:
        raise subprocess.TimeoutExpired(
            args, exc.timeout, output=redact(exc.output), stderr=redact(exc.stderr)
        ) from None


def clone_repository(
    repo: str,
    branch: str | None = None,
    commit: str | None = None,
    *,
    timeout_seconds: int | None = None,
) -> Path:
    """Clone a repository into a temporary directory and return the path."""

    validate_branch(branch)
    validate_commit(commit)
    if not is_safe_repo_url(repo):
        raise ValueError(
            "Unsupported repository URL scheme. Only https:// and file:// are allowed."
        )
    if repo.startswith("https://"):
        ensure_safe_outbound_url(repo, allow_http=False)
    if repo.startswith("file://") and not settings.enable_file_repo_access:
        raise ValueError("Local file:// repository access is disabled")

    parsed = urlsplit(repo)
    if parsed.query or parsed.fragment:
        raise ValueError("Repository URL must not contain a query or fragment")
    repo_url = repo
    auth = None
    if repo.startswith("https://"):
        parsed = urlsplit(repo)
        repo_url = urlunsplit(parsed._replace(netloc=parsed.netloc.rsplit("@", 1)[-1]))
        if parsed.password is not None:
            auth = (repo_url, unquote(parsed.username or ""), unquote(parsed.password))
    if repo.startswith("file://"):
        repo_url = _resolve_local_repo_path(repo.removeprefix("file://"))
    destination = Path(tempfile.mkdtemp(prefix="vigilweave-"))
    try:
        clone_command = ["git", "clone"]
        if branch and not commit:
            clone_command.extend(["--branch", branch.removeprefix("refs/heads/"), "--depth", "1"])
        clone_command.extend(["--", repo_url, str(destination)])
        _run_git(clone_command, timeout_seconds=timeout_seconds, auth=auth)
        if commit:
            _run_git(
                ["git", "checkout", "--detach", commit, "--"],
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

    validate_branch(branch)
    command = [
        "git",
        "log",
        f"--max-count={max(1, limit)}",
        "--date=unix",
        "--pretty=format:%H%x09%an%x09%ae%x09%ad%x09%s",
    ]
    if branch:
        command.append(branch)
    command.append("--")
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
