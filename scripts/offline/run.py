"""Launch an isolated, loopback-only local development instance."""

import argparse
import os
import platform
import secrets
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    parser.add_argument("--repos", type=Path, default=root / "repositories")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--state", type=Path, default=root / ".offline-state")
    parser.add_argument(
        "--all-features", action="store_true", help="Enable the existing development licence bypass"
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if not (root / "frontend/dist/index.html").is_file():
        parser.error("frontend/dist is missing; use the prepared offline ZIP")
    if not shutil.which("git"):
        parser.error("Git must already be installed")

    os.umask(0o077)
    args.repos = args.repos.expanduser().resolve()
    args.repos.mkdir(parents=True, exist_ok=True)
    args.state = args.state.expanduser().resolve()
    args.state.mkdir(parents=True, exist_ok=True, mode=0o700)
    secret_path = args.state / "session-secret"
    try:
        with secret_path.open("x", encoding="utf-8") as handle:
            handle.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    secret = secret_path.read_text(encoding="utf-8").strip()
    if len(secret) < 64:
        parser.error(f"Invalid local session secret: {secret_path}")
    config_path = args.state / "tools_config.yaml"
    if not config_path.exists():
        shutil.copyfile(root / "scripts/offline/tools_config.yaml", config_path)
    arch = {"arm64": "aarch64"}.get(platform.machine(), platform.machine())
    env = {
        "HOME": str(Path.home()),
        "PATH": os.pathsep.join(
            [str(Path(sys.executable).parent), str(root / "vendor/bin" / arch), "/usr/bin", "/bin"]
        ),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "ENVIRONMENT": "development",
        "DATABASE_URL": f"sqlite:///{args.state / 'vigilweave.db'}",
        "CELERY_TASK_ALWAYS_EAGER": "true",
        "SESSION_AUTH_PROVIDER": "local",
        "SESSION_SECRET": secret,
        "API_KEYS_ENABLED": "true",
        "LICENSE_TESTING_MODE": str(args.all_features).lower(),
        "SAAS_ENABLED": "false",
        "ENABLE_REPO_BUILD_TOOL_ADAPTERS": "false",
        "ENABLE_FILE_REPO_ACCESS": "true",
        "HOST_REPO_ROOT": str(args.repos),
        "CONTAINER_REPO_ROOT": str(args.repos),
        "RULEPACKS_PATH": str(args.state / "rulepacks"),
        "VIGILWEAVE_WEB_BASE_URL": f"http://127.0.0.1:{args.port}",
        "VIGILWEAVE_API_BASE_URL": f"http://127.0.0.1:{args.port}",
        "VIGILWEAVE_OFFLINE_TOOL_CONFIG": str(config_path),
        "AZURE_MARKETPLACE_ONBOARDING_ENABLED": "false",
    }
    # Settings reads .env from cwd, so use the private state directory, not the checkout.
    if (args.state / ".env").exists():
        parser.error(
            "Remove .env from the offline state directory; this launcher owns its settings"
        )
    print(f"Open http://127.0.0.1:{args.port}/setup", flush=True)
    print(f"Repository root: {args.repos}; private state: {args.state}", flush=True)
    return subprocess.call(
        [
            sys.executable,
            "-I",
            "-m",
            "uvicorn",
            "scripts.offline.web:create_app",
            "--factory",
            "--app-dir",
            str(root),
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
        ],
        cwd=args.state,
        env=env,
    )


if __name__ == "__main__":
    raise SystemExit(main())
