"""Celery task entrypoints for scans."""

from app.core import database as database_module
from app.core.celery_app import celery_app
from app.core.database import Session
from app.services.scanner import execute_scan


@celery_app.task(name="vigilweave.run_scan")
def run_scan(scan_id: int) -> None:
    """Execute a scan in a worker context."""

    with Session(database_module.engine) as session:
        execute_scan(session, scan_id)
