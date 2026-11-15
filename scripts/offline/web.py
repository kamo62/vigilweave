"""Same-origin frontend serving for the offline launcher only."""

import os
from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.staticfiles import StaticFiles


class SPAFiles(StaticFiles):
    """Support browser-route refresh without hiding missing assets or API errors."""

    async def get_response(self, path, scope):
        if path.split("/", 1)[0] in {"api", "health", "ready", "openapi.json"}:
            raise HTTPException(404)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if (
                exc.status_code != 404
                or Path(path).suffix
                or scope["method"] not in {"GET", "HEAD"}
            ):
                raise
            return await super().get_response("index.html", scope)


def create_app():
    """Configure the bundled scanner profile before loading the existing API."""
    from app.services import config_loader

    config_loader.CONFIG_PATH = Path(os.environ["VIGILWEAVE_OFFLINE_TOOL_CONFIG"])
    config_loader.clear_tool_config_cache()
    from app.main import app

    frontend = Path(__file__).resolve().parents[2] / "frontend/dist"
    app.mount("/", SPAFiles(directory=frontend, html=True), name="offline-frontend")
    return app
