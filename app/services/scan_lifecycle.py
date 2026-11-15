"""Database-backed scan leases, dispatch and recovery."""

import logging
import secrets
from datetime import UTC, datetime, timedelta
from threading import Event, Thread
from typing import cast

from kombu.exceptions import OperationalError
from sqlalchemy import Table, inspect, or_, update
from sqlalchemy.engine import CursorResult
from sqlmodel import Session, select

from app.core import database
from app.core.config import settings
from app.core.network_security import redact_sensitive_text
from app.models import Scan, ScanStatus
from app.services.scm_clone import safe_clone_url_for_logs

logger = logging.getLogger(__name__)
scan_table = cast(Table, inspect(Scan).local_table)
INTERRUPTED = "Scan interrupted: worker heartbeat expired"


def claim_scan(session: Session, scan_id: int) -> str | None:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    result = session.execute(
        update(scan_table)
        .where(scan_table.c.id == scan_id, scan_table.c.status == ScanStatus.QUEUED)
        .values(
            status=ScanStatus.RUNNING,
            started_at=now,
            lifecycle_token=token,
            lifecycle_heartbeat_at=now,
        )
    )
    session.commit()
    return token if cast(CursorResult, result).rowcount == 1 else None


def heartbeat_scan(session: Session, scan_id: int, token: str) -> bool:
    result = session.execute(
        update(scan_table)
        .where(
            scan_table.c.id == scan_id,
            scan_table.c.status == ScanStatus.RUNNING,
            scan_table.c.lifecycle_token == token,
        )
        .values(lifecycle_heartbeat_at=datetime.now(UTC))
    )
    session.commit()
    return cast(CursorResult, result).rowcount == 1


def lock_owned_scan(session: Session, scan_id: int, token: str) -> bool:
    """Acquire a row write lock; the caller must commit or roll back."""
    result = session.execute(
        update(scan_table)
        .where(
            scan_table.c.id == scan_id,
            scan_table.c.status == ScanStatus.RUNNING,
            scan_table.c.lifecycle_token == token,
        )
        .values(lifecycle_heartbeat_at=datetime.now(UTC))
    )
    return cast(CursorResult, result).rowcount == 1


def terminal_update(
    session: Session, scan_id: int, token: str, status: ScanStatus, error: str | None = None
) -> bool:
    if not lock_owned_scan(session, scan_id, token):
        session.rollback()
        return False
    session.expire_all()
    scan = session.get(Scan, scan_id)
    if scan is None:
        session.rollback()
        return False
    scan.status = status
    scan.completed_at = datetime.now(UTC)
    if error:
        scan.scan_metadata = {
            **(scan.scan_metadata or {}),
            "error": error,
            "repo": safe_clone_url_for_logs(scan.repo),
        }
    session.add(scan)
    session.commit()
    return True


def notify_terminal(
    session: Session, scan_id: int, token: str, status: ScanStatus, error: str | None = None
) -> None:
    from app.services.github_app import complete_github_check_run

    session.expire_all()
    scan = session.get(Scan, scan_id)
    if scan is None or scan.status != status or scan.lifecycle_token != token:
        session.rollback()
        return
    snapshot = Scan.model_validate(scan.model_dump())
    session.rollback()
    result = complete_github_check_run(snapshot, error_message=error)
    if not result:
        return
    current = session.get(Scan, scan_id)
    if current is None:
        session.rollback()
        return
    metadata = {**(current.scan_metadata or {}), "github_check": result}
    session.execute(
        update(scan_table)
        .where(
            scan_table.c.id == scan_id,
            scan_table.c.status == status,
            scan_table.c.lifecycle_token == token,
        )
        .values(scan_metadata=metadata)
    )
    session.commit()


def reap_stale_scans(session: Session, cutoff: datetime, limit: int = 100) -> list[tuple[int, str]]:
    candidates = session.exec(
        select(scan_table.c.id, scan_table.c.lifecycle_token, scan_table.c.lifecycle_heartbeat_at)
        .where(
            scan_table.c.status == ScanStatus.RUNNING,
            or_(
                scan_table.c.lifecycle_heartbeat_at.is_(None),
                scan_table.c.lifecycle_heartbeat_at < cutoff,
            ),
        )
        .limit(limit)
    ).all()
    session.rollback()
    winners = []
    for scan_id, token, heartbeat in candidates:
        recovery_token = secrets.token_urlsafe(32)
        predicate = scan_table.c.lifecycle_heartbeat_at == heartbeat
        result = session.execute(
            update(scan_table)
            .where(
                scan_table.c.id == scan_id,
                scan_table.c.status == ScanStatus.RUNNING,
                scan_table.c.lifecycle_token == token,
                predicate,
            )
            .values(
                status=ScanStatus.FAILED,
                lifecycle_token=recovery_token,
                completed_at=datetime.now(UTC),
            )
        )
        if cast(CursorResult, result).rowcount:
            scan = session.get(Scan, scan_id)
            assert scan is not None
            scan.scan_metadata = {**(scan.scan_metadata or {}), "error": INTERRUPTED}
            session.add(scan)
            winners.append((scan_id, recovery_token))
        session.commit()
    return winners


def dispatch_scan(session: Session, scan_id: int) -> None:
    if settings.celery_task_always_eager:
        from app.services.scanner import execute_scan

        try:
            execute_scan(session, scan_id)
        except Exception:
            session.rollback()
            scan = session.get(Scan, scan_id)
            if scan is None or scan.status != ScanStatus.FAILED:
                raise
        return
    from app.tasks.scan_tasks import run_scan

    try:
        run_scan.delay(scan_id)
    except (OperationalError, ConnectionError, OSError) as exc:
        session.rollback()
        scan = session.get(Scan, scan_id)
        if scan is None:
            raise
        metadata = {
            **(scan.scan_metadata or {}),
            "error": redact_sensitive_text(f"Scan dispatch failed: {exc}"),
        }
        token = secrets.token_urlsafe(32)
        result = session.execute(
            update(scan_table)
            .where(scan_table.c.id == scan_id, scan_table.c.status == ScanStatus.QUEUED)
            .values(
                status=ScanStatus.FAILED,
                completed_at=datetime.now(UTC),
                scan_metadata=metadata,
                lifecycle_token=token,
            )
        )
        session.commit()
        if cast(CursorResult, result).rowcount:
            logger.warning("Scan %s could not be dispatched", scan_id)
            notify_terminal(session, scan_id, token, ScanStatus.FAILED, metadata["error"])


def maintain_scans() -> None:
    with Session(database.engine) as session:
        cutoff = datetime.now(UTC) - timedelta(seconds=settings.scan_stale_after_seconds)
        winners = reap_stale_scans(session, cutoff, settings.scan_recovery_batch_size)
        for scan_id, token in winners:
            notify_terminal(session, scan_id, token, ScanStatus.FAILED, INTERRUPTED)


def resubmit_queued_scans() -> None:
    if settings.celery_task_always_eager:
        return
    with Session(database.engine) as session:
        ids = list(
            session.exec(
                select(scan_table.c.id)
                .where(scan_table.c.status == ScanStatus.QUEUED)
                .limit(settings.scan_recovery_batch_size)
            ).all()
        )
        session.rollback()
        for scan_id in ids:
            dispatch_scan(session, scan_id)


def heartbeat_worker(engine, scan_id: int, token: str, stop: Event) -> None:
    while not stop.wait(settings.scan_heartbeat_interval_seconds):
        try:
            with Session(engine) as session:
                if not heartbeat_scan(session, scan_id, token):
                    return
        except Exception:
            logger.exception("Scan %s heartbeat failed", scan_id)


def start_heartbeat(session: Session, scan_id: int, token: str) -> tuple[Event, Thread]:
    stop = Event()
    thread = Thread(
        target=heartbeat_worker, args=(session.get_bind(), scan_id, token, stop), daemon=True
    )
    thread.start()
    return stop, thread
