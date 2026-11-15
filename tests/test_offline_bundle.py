"""Offline packaging boundaries do not depend on native scanner stubs."""

from pathlib import Path

from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.testclient import TestClient

from scripts.offline.build_bundle import included_source
from scripts.offline.web import SPAFiles


def test_offline_source_filter_retains_source_and_rejects_private_build_material():
    for name in [
        ".gitignore",
        "LICENSE",
        "app/main.py",
        "frontend/package.json",
        "app/tasks/scan_tasks.py",
    ]:
        assert included_source(Path(name)), name
    for name in [
        "Tasks.md",
        "docs/HANDOFF.md",
        "docs/PRD.md",
        "app/AGENTS.md",
        ".env",
        "data/private.db",
        "DO-NOT-RUN/code.py",
        "frontend/node_modules/pkg/index.js",
        "frontend/public/assets/stitch/prd.html",
        "Dockerfile",
        "frontend/Dockerfile",
        "scripts/docker-entrypoint.sh",
        "frontend/.env.local",
        "app/__pycache__/main.pyc",
    ]:
        assert not included_source(Path(name)), name


def test_offline_spa_refresh_keeps_api_and_missing_asset_errors(tmp_path):
    (tmp_path / "index.html").write_text("<html>synthetic offline UI</html>")
    (tmp_path / "asset.js").write_text("// synthetic asset")
    app = Starlette(routes=[Mount("/", app=SPAFiles(directory=tmp_path, html=True))])
    with TestClient(app) as client:
        assert client.get("/projects/example").text == "<html>synthetic offline UI</html>"
        assert client.get("/asset.js").text == "// synthetic asset"
        for path in ["/api/v1/missing", "/api", "/health", "/ready", "/missing.js"]:
            assert client.get(path).status_code == 404, path
        assert client.post("/projects/example").status_code == 405
