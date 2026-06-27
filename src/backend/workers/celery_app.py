"""Celery application configuration for backend worker processes."""

from __future__ import annotations

from celery import Celery

from config.settings import settings


settings.reload()
_broker_url = getattr(settings, "CELERY_BROKER_URL", settings.REDIS_URL)
_result_backend = getattr(settings, "CELERY_RESULT_BACKEND", _broker_url)

celery_app = Celery(
    "ai_accounting_copilot",
    broker=_broker_url,
    backend=_result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_time_limit=180,
    task_soft_time_limit=120,
    timezone="Asia/Bangkok",
    enable_utc=False,
    task_track_started=True,
    task_always_eager=(
        str(getattr(settings, "CELERY_TASK_ALWAYS_EAGER", "false")).lower()
        == "true"
    ),
)

celery_app.autodiscover_tasks(["src.backend.workers"])
