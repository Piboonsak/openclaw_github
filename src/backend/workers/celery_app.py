"""Celery application configuration for backend worker processes."""

from __future__ import annotations

from celery import Celery

from config.settings import settings


settings.reload()
_broker_url = getattr(settings, "CELERY_BROKER_URL", settings.REDIS_URL)
_result_backend = getattr(settings, "CELERY_RESULT_BACKEND", _broker_url)

# W5-CLAUDE-OCR-PENDING-STALL-FIX-08 (HR-07-02B): the worker is started with
# `-A src.backend.workers.celery_app:celery_app`, which imports THIS module but
# not `tasks.py`. Task registration relied solely on `autodiscover_tasks`, which
# was empirically NOT importing `src.backend.workers.tasks` at worker finalize —
# so the worker booted with `process_document` / `extract_coa_pdf` UNREGISTERED,
# silently discarded every incoming message as an unknown task, and left
# `AsyncResult` PENDING forever (uploads enqueued, tasks never ran). `include`
# makes Celery import the tasks module deterministically at startup — the
# canonical, reliable way to register tasks — so the worker actually executes
# them and the Processing screen sees queued/ocr/extract/mapping/failure states.
celery_app = Celery(
    "ai_accounting_copilot",
    broker=_broker_url,
    backend=_result_backend,
    include=["src.backend.workers.tasks"],
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
