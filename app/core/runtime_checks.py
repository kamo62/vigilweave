"""Runtime dependency and readiness checks."""

from __future__ import annotations

import logging
from typing import Any

import redis
from sqlalchemy import text
from sqlmodel import Session

from app.core.config import settings
from app.core.database import engine
from app.core.workos_session import session_secret_configured

logger = logging.getLogger(__name__)


def database_ready() -> bool:
    """Return whether the primary database is reachable."""

    try:
        with Session(engine) as session:
            session.exec(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


def redis_ready() -> bool:
    """Return whether Redis is reachable when required."""

    try:
        client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        return bool(client.ping())
    except Exception:  # noqa: BLE001
        if settings.environment in {"development", "test"}:
            logger.warning(
                "Redis is not reachable — returning OK because environment=%s",
                settings.environment,
            )
            return True
        return False


def readiness_report() -> dict[str, Any]:
    """Collect readiness details for liveness/readiness endpoints."""

    db_ok = database_ready()
    redis_ok = redis_ready()
    secrets_ready = session_secret_configured()
    return {
        "status": "ok" if db_ok and redis_ok and secrets_ready else "degraded",
        "database": db_ok,
        "redis": redis_ok,
        "session_secret": secrets_ready,
    }
