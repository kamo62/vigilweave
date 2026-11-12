"""Database migration utilities for self-hosted upgrades."""

import logging
import os
import shutil
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def migrate_sqlite_database() -> None:
    """
    Auto-migrate from old codeguard.db to vigilweave.db on startup.

    This function checks if there's an existing database at the old location
    (codeguard.db) and copies it to the new location (vigilweave.db) if:
    1. The new database doesn't exist yet
    2. An old database exists in a known location

    This ensures existing self-hosted installations don't lose data when upgrading.
    """
    # Parse the current database URL to get the path
    db_url = settings.database_url

    if not db_url.startswith("sqlite:///"):
        # Not using SQLite, skip migration
        return

    # Extract the database file path from the URL
    new_db_path_str = db_url.replace("sqlite:///", "")
    new_db_path = Path(new_db_path_str)

    # If the new database already exists, nothing to do
    if new_db_path.exists():
        logger.debug("Database already exists at %s, skipping migration check", new_db_path)
        return

    # Ensure parent directory exists
    new_db_path.parent.mkdir(parents=True, exist_ok=True)

    # Look for old database files in various locations
    old_db_candidates = [
        # Old volume path (Docker)
        Path("/data/codeguard.db"),
        # Old relative path
        Path("./codeguard.db"),
        # Old absolute path
        Path(os.path.abspath("codeguard.db")),
    ]

    for old_db_path in old_db_candidates:
        if old_db_path.exists() and old_db_path.is_file():
            try:
                # Copy the old database to the new location
                shutil.copy2(old_db_path, new_db_path)
                logger.info(
                    "Successfully migrated database from %s to %s", old_db_path, new_db_path
                )

                # Also migrate the volume if in Docker
                if old_db_path == Path("/data/codeguard.db") and new_db_path == Path(
                    "/data/vigilweave.db"
                ):
                    logger.info(
                        "Database migrated from 'codeguard_data' volume to "
                        "'vigilweave_data' volume. Consider updating your "
                        "docker-compose.yml to use the new volume name."
                    )

                return
            except Exception as exc:
                logger.error(
                    "Failed to migrate database from %s to %s: %s", old_db_path, new_db_path, exc
                )
                # Continue to try next candidate

    # No old database found - this is a fresh install
    logger.debug("No existing database found for migration, starting fresh")
