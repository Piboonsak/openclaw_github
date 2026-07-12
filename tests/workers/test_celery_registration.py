"""Regression coverage for HR-07-02B: OCR processing tasks stayed PENDING forever.

Root cause: the celery worker is started with `-A
src.backend.workers.celery_app:celery_app`, which imports the app module but NOT
`tasks.py`. Task registration relied solely on `autodiscover_tasks`, which did
not import `src.backend.workers.tasks` at the worker's boot, so the worker ran
with `process_document` UNREGISTERED and silently discarded every incoming
message as an unknown task — leaving `AsyncResult` PENDING forever (uploads
enqueued, tasks never executed, no stage progress).

These tests would FAIL on the pre-fix code (empty `conf.include`, tasks not
registered when only the app module is imported) and PASS after wiring
`include=["src.backend.workers.tasks"]`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EXPECTED_TASKS = (
    "src.backend.workers.tasks.process_document",
    "src.backend.workers.tasks.extract_coa_pdf",
)


def test_celery_app_includes_tasks_module() -> None:
    """The app must explicitly `include` the tasks module so the worker (which
    imports only the app) registers the tasks. Fails on the old empty-include."""
    from src.backend.workers.celery_app import celery_app

    include = list(celery_app.conf.include or ())
    assert "src.backend.workers.tasks" in include, include


def test_worker_boot_registers_tasks_in_isolation() -> None:
    """Replicate the worker exactly: a fresh process that imports ONLY the app
    module (as `-A ...celery_app:celery_app` does) and runs the loader's default-
    module import must end up with the document/COA tasks registered. On the
    pre-fix code this subprocess ends with the tasks UNREGISTERED (the bug)."""
    code = (
        "from src.backend.workers.celery_app import celery_app\n"
        "celery_app.loader.import_default_modules()\n"
        "names = set(celery_app.tasks)\n"
        "missing = [t for t in %r if t not in names]\n"
        "assert not missing, 'UNREGISTERED: %%s' %% missing\n"
        "print('REGISTERED_OK')\n" % (_EXPECTED_TASKS,)
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"worker-boot task registration failed:\nSTDOUT={result.stdout}\n"
        f"STDERR={result.stderr}"
    )
    assert "REGISTERED_OK" in result.stdout


def test_settings_honours_celery_env_vars(monkeypatch) -> None:
    """settings must read CELERY_BROKER_URL / CELERY_RESULT_BACKEND from env.

    Previously it did not, so celery_app.py's getattr(settings, "CELERY_*")
    always fell back to REDIS_URL and the env's configured broker/result-backend
    (e.g. a separate result DB) were silently ignored."""
    from config.settings import settings

    monkeypatch.setenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")
    try:
        settings.reload()
        assert settings.CELERY_BROKER_URL == "redis://redis:6379/0"
        assert settings.CELERY_RESULT_BACKEND == "redis://redis:6379/1"
    finally:
        monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
        monkeypatch.delenv("CELERY_RESULT_BACKEND", raising=False)
        settings.reload()
