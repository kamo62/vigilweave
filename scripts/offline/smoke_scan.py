"""Run real scanners through the API using only disposable synthetic local data."""

import os
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root))
    arch = {"arm64": "aarch64"}.get(platform.machine(), platform.machine())
    path = os.pathsep.join(
        [
            str(Path(sys.executable).parent),
            str(root / "vendor/bin" / arch),
            os.environ.get("PATH", os.defpath),
        ]
    )
    with tempfile.TemporaryDirectory(prefix="vigilweave-smoke-") as directory:
        state = Path(directory)
        os.environ.clear()
        os.environ.update(
            {
                "PATH": path,
                "HOME": directory,
                "LANG": "C.UTF-8",
                "ENVIRONMENT": "test",
                "SESSION_SECRET": secrets.token_hex(32),
                "SESSION_AUTH_PROVIDER": "local",
                "CELERY_TASK_ALWAYS_EAGER": "true",
                "ENABLE_FILE_REPO_ACCESS": "true",
                "HOST_REPO_ROOT": directory,
                "CONTAINER_REPO_ROOT": directory,
                "DATABASE_URL": f"sqlite:///{state / 'smoke.db'}",
                "RULEPACKS_PATH": str(state / "rulepacks"),
                "VIGILWEAVE_WEB_BASE_URL": "http://testserver",
                "VIGILWEAVE_OFFLINE_TOOL_CONFIG": str(state / "tools_config.yaml"),
            }
        )
        shutil.copyfile(root / "scripts/offline/tools_config.yaml", state / "tools_config.yaml")
        for tool in ["git", "gitleaks", "bandit", "ruff"]:
            if shutil.which(tool) is None:
                raise RuntimeError(f"Real scanner prerequisite is missing: {tool}")
        original_cwd = Path.cwd()
        os.chdir(state)
        try:
            from fastapi.testclient import TestClient

            from scripts.offline.web import create_app

            with TestClient(create_app()) as client:
                assert client.get("/setup").status_code == 200
                token = client.get("/api/v1/auth/csrf").json()["csrf_token"]
                client.headers["X-CSRF-Token"] = token
                setup = client.post(
                    "/api/v1/auth/local/setup",
                    json={
                        "email": "offline-smoke@example.com",
                        "name": "Synthetic Offline Admin",
                        "password": secrets.token_urlsafe(24),
                    },
                )
                assert setup.status_code == 201, setup.text
                for vulnerable in [True, False]:
                    repo = state / ("vulnerable" if vulnerable else "clean")
                    repo.mkdir()
                    content = 'def greet():\n    return "hello"\n'
                    if vulnerable:
                        content = (
                            "import os\nimport subprocess\n"
                            'subprocess.call("echo synthetic-example", shell=True)\n'
                            f'api_key = "{secrets.token_hex(24)}"\n'
                        )
                    (repo / "example.py").write_text(content)
                    for args in [
                        ["init", "-q"],
                        ["add", "."],
                        [
                            "-c",
                            "user.name=Synthetic Example",
                            "-c",
                            "user.email=offline@example.com",
                            "commit",
                            "-qm",
                            "Synthetic input",
                        ],
                    ]:
                        subprocess.run(
                            ["git", "-C", str(repo), *args], check=True, capture_output=True
                        )
                    response = client.post(
                        "/api/v1/scans/",
                        json={
                            "repo": repo.as_uri(),
                            "scan_type": "comprehensive",
                        },
                    )
                    assert response.status_code == 201, response.text
                    scan_id = response.json()["id"]
                    scan = client.get(f"/api/v1/scans/{scan_id}").json()
                    assert scan["status"] == "completed", scan.get("error_message")
                    executions = {item["tool"]: item for item in scan["tool_executions"]}
                    assert set(executions) == {"gitleaks", "bandit", "ruff"}, executions.keys()
                    for tool, execution in executions.items():
                        assert execution["status"] == "completed", (tool, execution["status"])
                        assert (execution["findings_count"] > 0) == vulnerable, (
                            tool,
                            execution["findings_count"],
                            vulnerable,
                        )
                    assert client.get(f"/api/v1/scans/{scan_id}/sarif").status_code == 200
                    print(
                        f"{'Vulnerable' if vulnerable else 'Clean'} synthetic repository: "
                        + ", ".join(
                            f"{tool}={item['findings_count']}"
                            for tool, item in sorted(executions.items())
                        )
                    )
            print("PASS: local authentication, UI routing, SQLite, real scans and SARIF")
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    main()
