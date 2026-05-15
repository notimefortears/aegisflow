"""Celery application configuration."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "aegisflow",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=settings.worker_max_tasks_per_child,
    task_routes={
        "execute_workflow": {"queue": "workflows"},
    },
    task_default_queue="workflows",
)
