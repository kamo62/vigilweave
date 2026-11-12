"""Celery application configuration."""

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "vigilweave",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.scan_tasks"],
)
celery_app.conf.update(
    task_always_eager=settings.celery_task_always_eager,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Resource isolation: prevent runaway scans from starving workers
    task_time_limit=1800,  # Hard kill after 30 minutes
    task_soft_time_limit=1500,  # Raise SoftTimeLimitExceeded after 25 minutes
    worker_max_tasks_per_child=50,  # Recycle workers to prevent memory leaks
    worker_max_memory_per_child=2_000_000,  # 2 GB max memory per worker process (KB)
)
