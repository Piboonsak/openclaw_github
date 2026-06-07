"""In-process background job store for PoC async workflows."""

from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_JOBS_ROOT = REPO_ROOT / "rules" / "_jobs"
STAGE_LABELS = {
    1: "Uploading & validating files",
    2: "Extracting text from documents",
    3: "Analyzing COA structure",
    4: "Generating journal entry rules",
    5: "Validating & writing rule file",
}


class JobStore:
    def __init__(self, max_workers: int = 2) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="rulegen")
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        DEFAULT_JOBS_ROOT.mkdir(parents=True, exist_ok=True)

    def create_job(self, *, kind: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        job_id = f"gen_{uuid.uuid4().hex[:12]}"
        snapshot = {
            "job_id": job_id,
            "kind": kind,
            "status": "queued",
            "progress_pct": 0,
            "current_stage": 1,
            "stage_label": STAGE_LABELS[1],
            "estimated_seconds": 60,
            "meta": deepcopy(meta or {}),
            "stages": [
                {"stage": idx, "status": "pending", "duration_ms": None, "label": STAGE_LABELS[idx]}
                for idx in range(1, 6)
            ],
            "result": None,
            "error": None,
            "version": 1,
        }
        snapshot["stages"][0]["status"] = "queued"
        with self._lock:
            self._jobs[job_id] = snapshot
        return deepcopy(snapshot)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            snapshot = self._jobs.get(job_id)
            return deepcopy(snapshot) if snapshot else None

    def update_progress(
        self,
        job_id: str,
        *,
        stage: int,
        status: str,
        progress_pct: int,
        stage_label: str | None = None,
        duration_ms: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job["status"] = "processing" if status not in {"failed", "done"} else status
            job["current_stage"] = stage
            job["progress_pct"] = max(0, min(int(progress_pct), 100))
            job["stage_label"] = stage_label or STAGE_LABELS.get(stage, job.get("stage_label", ""))
            for stage_state in job["stages"]:
                if stage_state["stage"] == stage:
                    stage_state["status"] = status
                    if duration_ms is not None:
                        stage_state["duration_ms"] = duration_ms
                    if stage_label:
                        stage_state["label"] = stage_label
                elif stage_state["stage"] < stage and stage_state["status"] in {"pending", "queued", "running"}:
                    stage_state["status"] = "done"
                elif stage_state["stage"] > stage and stage_state["status"] == "pending":
                    continue
            if extra:
                job.setdefault("meta", {}).update(extra)
            job["version"] += 1

    def complete(self, job_id: str, result: dict[str, Any]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job["status"] = "done"
            job["progress_pct"] = 100
            job["current_stage"] = 5
            job["stage_label"] = STAGE_LABELS[5]
            for stage_state in job["stages"]:
                if stage_state["status"] in {"pending", "queued", "running"}:
                    stage_state["status"] = "done"
            job["result"] = deepcopy(result)
            job["version"] += 1

    def fail(self, job_id: str, error: str, *, stage: int | None = None) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job["status"] = "failed"
            job["error"] = error
            if stage is not None:
                job["current_stage"] = stage
            for stage_state in job["stages"]:
                if stage is not None and stage_state["stage"] == stage:
                    stage_state["status"] = "failed"
            job["version"] += 1

    def run_in_background(
        self,
        job_id: str,
        worker: Callable[..., dict[str, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        def runner() -> None:
            try:
                result = worker(*args, **kwargs)
            except Exception as exc:  # pragma: no cover - runtime safety net
                self.fail(job_id, str(exc))
                return
            self.complete(job_id, result)

        self._executor.submit(runner)


job_store = JobStore()
