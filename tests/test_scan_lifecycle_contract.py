"""Contracts for durable scan ownership, using independent database sessions."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

from sqlmodel import Session, SQLModel, create_engine

from app.models import FindingSeverity, Scan, ScanStatus


def test_simultaneous_claims_have_one_owner(tmp_path):
    from app.services.scan_lifecycle import claim_scan

    engine = create_engine(
        f"sqlite:///{tmp_path / 'claims.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        scan = Scan(repo="https://example.com/repo")
        session.add(scan)
        session.commit()
        scan_id = scan.id
    barrier = Barrier(2)

    def claim():
        with Session(engine) as session:
            barrier.wait()
            return claim_scan(session, scan_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sum(token is not None for token in results) == 1


def test_fresh_heartbeat_is_not_reaped(tmp_path):
    from app.services.scan_lifecycle import claim_scan, heartbeat_scan, reap_stale_scans

    engine = create_engine(
        f"sqlite:///{tmp_path / 'heartbeat.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        scan = Scan(repo="https://example.com/repo")
        session.add(scan)
        session.commit()
        token = claim_scan(session, scan.id)
        assert heartbeat_scan(session, scan.id, token)
        assert reap_stale_scans(session, datetime.now(UTC) - timedelta(seconds=1)) == []
        session.refresh(scan)
        assert scan.status == ScanStatus.RUNNING


def test_worker_loses_lease_before_results(tmp_path, monkeypatch):
    from app.models import Finding
    from app.services import scanner
    from app.services.scan_lifecycle import reap_stale_scans

    engine = create_engine(
        f"sqlite:///{tmp_path / 'lost.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        scan = Scan(repo="https://example.com/repo")
        session.add(scan)
        session.commit()
        scan_id = scan.id
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    monkeypatch.setattr(scanner, "resolve_clone_url", lambda *a, **k: "synthetic")
    monkeypatch.setattr(scanner, "clone_repository", lambda *a: checkout)
    updates = []
    monkeypatch.setattr(scanner, "notify_terminal", lambda *a, **k: updates.append(a))

    def analysis(*args, **kwargs):
        with Session(engine) as other:
            assert reap_stale_scans(other, datetime.now(UTC) + timedelta(seconds=1))
        return (
            [
                Finding(
                    scan_id=scan_id,
                    tool="synthetic",
                    title="test",
                    message="test",
                    category="security",
                    severity=FindingSeverity.HIGH,
                    fingerprint="synthetic",
                )
            ],
            [],
            [],
            {},
        )

    monkeypatch.setattr(scanner, "analyze_directory", analysis)
    with Session(engine) as session:
        scanner.execute_scan(session, scan_id)
        assert session.get(Scan, scan_id).status == ScanStatus.FAILED
        assert not session.query(Finding).all()
    assert updates == []


def test_finalisation_failure_rolls_back_results_retains_diagnostics(tmp_path, monkeypatch):
    import pytest

    from app.models import Finding, ToolExecution, ToolExecutionStatus
    from app.services import scanner

    engine = create_engine(
        f"sqlite:///{tmp_path / 'rollback.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        scan = Scan(repo="https://example.com/repo")
        session.add(scan)
        session.commit()
        scan_id = scan.id
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    monkeypatch.setattr(scanner, "resolve_clone_url", lambda *a, **k: "synthetic")
    monkeypatch.setattr(scanner, "clone_repository", lambda *a: checkout)
    monkeypatch.setattr(scanner, "notify_terminal", lambda *a, **k: None)
    monkeypatch.setattr(
        scanner,
        "analyze_directory",
        lambda *a, **k: (
            [
                Finding(
                    scan_id=scan_id,
                    tool="synthetic",
                    title="test",
                    message="test",
                    category="security",
                    severity=FindingSeverity.HIGH,
                    fingerprint="synthetic",
                )
            ],
            [ToolExecution(scan_id=scan_id, tool="synthetic", status=ToolExecutionStatus.FAILED)],
            [],
            {},
        ),
    )
    monkeypatch.setattr(
        scanner, "finalize_scan", lambda *a, **k: (_ for _ in ()).throw(ValueError("policy failed"))
    )
    with Session(engine) as session:
        with pytest.raises(ValueError, match="policy failed"):
            scanner.execute_scan(session, scan_id)
        assert session.get(Scan, scan_id).status == ScanStatus.FAILED
        assert not session.query(Finding).all()
        assert len(session.query(ToolExecution).all()) == 1


def test_broker_failure_marks_created_scan_failed(api_client, bootstrap_api_key, monkeypatch):
    from app.core.config import settings
    from app.tasks.scan_tasks import run_scan

    headers = bootstrap_api_key()
    monkeypatch.setattr(settings, "celery_task_always_eager", False)
    monkeypatch.setattr(
        run_scan, "delay", lambda *_: (_ for _ in ()).throw(ConnectionError("broker unavailable"))
    )
    response = api_client.post(
        "/api/v1/scans/", json={"repo": "https://example.com/repo"}, headers=headers
    )
    assert response.status_code == 201
    assert response.json()["status"] == "failed"
    assert "broker unavailable" in response.json()["scan_metadata"]["error"]


def test_reaper_does_not_overwrite_refreshed_heartbeat(tmp_path, monkeypatch):
    from sqlalchemy import event

    from app.services.scan_lifecycle import claim_scan, heartbeat_scan, reap_stale_scans

    engine = create_engine(
        f"sqlite:///{tmp_path / 'race.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        scan = Scan(repo="https://example.com/repo")
        session.add(scan)
        session.commit()
        scan_id = scan.id
        token = claim_scan(session, scan_id)
    reached = Barrier(2)
    resume = Barrier(2)

    @event.listens_for(engine, "before_cursor_execute")
    def pause_read(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE") and "completed_at" in statement:
            reached.wait(timeout=5)
            resume.wait(timeout=5)

    def reap():
        with Session(engine) as session:
            return reap_stale_scans(session, datetime.now(UTC) + timedelta(seconds=10))

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(reap)
        reached.wait()
        with Session(engine) as session:
            assert heartbeat_scan(session, scan_id, token)
        resume.wait()
        assert future.result() == []


def test_startup_maintenance_recovers_stale_scan(tmp_path, monkeypatch):
    from sqlalchemy import update

    from app.core import database
    from app.services.scan_lifecycle import claim_scan, maintain_scans

    engine = create_engine(
        f"sqlite:///{tmp_path / 'startup.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)
    with Session(engine) as session:
        scan = Scan(repo="https://example.com/repo")
        session.add(scan)
        session.commit()
        scan_id = scan.id
        claim_scan(session, scan_id)
        session.execute(
            update(Scan)
            .where(Scan.id == scan_id)
            .values(lifecycle_heartbeat_at=datetime.now(UTC) - timedelta(hours=1))
        )
        session.commit()
    maintain_scans()
    with Session(engine) as session:
        scan = session.get(Scan, scan_id)
        assert scan.status == ScanStatus.FAILED
        assert "heartbeat expired" in scan.scan_metadata["error"]


def test_in_process_migration_keeps_existing_loggers(tmp_path, monkeypatch):
    import logging

    from app.core import database

    engine = create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    monkeypatch.setattr(database, "engine", engine)
    logger = logging.getLogger("vigilweave.lifecycle.test")
    logger.disabled = False
    database.init_db()
    assert not logger.disabled


def test_broker_failure_notifies_only_queued_terminal_winner(tmp_path, monkeypatch):
    from app.core.config import settings
    from app.services import scan_lifecycle
    from app.tasks.scan_tasks import run_scan

    engine = create_engine(f"sqlite:///{tmp_path / 'broker.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(settings, "celery_task_always_eager", False)
    monkeypatch.setattr(
        run_scan, "delay", lambda *_: (_ for _ in ()).throw(ConnectionError("offline"))
    )
    notified = []
    monkeypatch.setattr(scan_lifecycle, "notify_terminal", lambda *args: notified.append(args))
    with Session(engine) as session:
        scan = Scan(repo="https://example.com/repo")
        session.add(scan)
        session.commit()
        scan_lifecycle.dispatch_scan(session, scan.id)
        session.refresh(scan)
        assert scan.status == ScanStatus.FAILED
        assert notified and notified[0][2] == scan.lifecycle_token


def test_duplicate_execute_runs_analysis_once(tmp_path, monkeypatch):
    from threading import Event

    from app.services import scanner

    engine = create_engine(
        f"sqlite:///{tmp_path / 'execute.db'}", connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        scan = Scan(repo="https://example.com/repo")
        session.add(scan)
        session.commit()
        scan_id = scan.id
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    entered, release = Event(), Event()
    calls = []
    monkeypatch.setattr(scanner, "resolve_clone_url", lambda *a, **k: "synthetic")
    monkeypatch.setattr(scanner, "clone_repository", lambda *a: checkout)
    monkeypatch.setattr(scanner, "notify_terminal", lambda *a, **k: None)

    def analysis(*args, **kwargs):
        calls.append(1)
        entered.set()
        assert release.wait(5)
        return [], [], [], {}

    monkeypatch.setattr(scanner, "analyze_directory", analysis)

    def execute():
        with Session(engine) as session:
            scanner.execute_scan(session, scan_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(execute)
        assert entered.wait(5)
        second = pool.submit(execute)
        second.result(timeout=5)
        release.set()
        first.result(timeout=5)
    assert len(calls) == 1
    with Session(engine) as session:
        assert session.get(Scan, scan_id).status == ScanStatus.COMPLETED


def test_lifespan_serves_while_initial_recovery_is_busy(monkeypatch):
    import asyncio
    from threading import Event

    from app import main
    from app.services import scan_lifecycle

    entered, release = Event(), Event()

    def recover():
        entered.set()
        release.wait(2)

    for name in (
        "setup_logging",
        "_validate_production_secrets",
        "migrate_sqlite_database",
        "init_db",
    ):
        monkeypatch.setattr(main, name, lambda: None)
    monkeypatch.setattr(scan_lifecycle, "maintain_scans", recover)
    monkeypatch.setattr(scan_lifecycle, "resubmit_queued_scans", lambda: None)

    async def scenario():
        context = main.lifespan(main.app)
        started = False
        try:
            await asyncio.wait_for(context.__aenter__(), timeout=0.5)
            started = True
            assert await asyncio.to_thread(entered.wait, 1)
        finally:
            release.set()
            if started:
                await context.__aexit__(None, None, None)

    asyncio.run(scenario())
