"""In-process job store for D6 rule generation endpoints."""

from __future__ import annotations

import asyncio
import json
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.settings import settings
from src.backend.services.rule_generator import (
    approve_generated_rules,
    run_rule_generation_job,
    save_edited_rules,
)


def _jobs_root() -> Path:
    settings.reload()
    root = settings.RULES_ROOT / "_jobs"
    root.mkdir(parents=True, exist_ok=True)
    return root


_STAGE_LABELS = {
    1: "Uploading & validating files",
    2: "Extracting text from documents",
    3: "Analyzing COA structure",
    4: "Generating journal entry rules",
    5: "Validating & writing rule file",
}
JOB_TIMEOUT_SECONDS = 420  # 2× measured wall-clock (206 s) for 246-account COA via auto provider


class RuleGenerationJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._restore_jobs_from_disk()

    def _restore_jobs_from_disk(self) -> None:
        """Restore persisted jobs so progress/result survives server restarts."""
        for path in _jobs_root().glob("gen_*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                # Ignore corrupted snapshots so one bad file does not block startup.
                continue

            job_id = str(payload.get("job_id") or path.stem)
            payload["job_id"] = job_id

            # In-flight jobs cannot resume automatically because worker threads
            # are gone after process restart; mark them recoverably failed.
            if payload.get("status") in {"queued", "processing"}:
                payload["status"] = "failed"
                payload["error"] = {
                    "message": "Job interrupted by server restart. Please rerun this job.",
                    "traceback": None,
                }
                payload["updated_at"] = datetime.now(UTC).isoformat()

            self._jobs[job_id] = payload

    def _persist(self, job_id: str) -> None:
        payload = self._jobs.get(job_id)
        if not payload:
            return
        (_jobs_root() / f"{job_id}.json").write_text(
            __import__("json").dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _snapshot_stages(self, current_stage: int) -> list[dict[str, Any]]:
        base = []
        for stage in range(1, 6):
            if stage < current_stage:
                status = "done"
            elif stage == current_stage:
                status = "running"
            else:
                status = "pending"
            base.append(
                {
                    "stage": stage,
                    "status": status,
                    "duration_ms": None,
                    "label": _STAGE_LABELS[stage],
                }
            )
        return base

    async def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with self._lock:
            job_id = f"gen_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
            job = {
                "job_id": job_id,
                "status": "queued",
                "progress_pct": 0,
                "current_stage": 1,
                "stage_label": _STAGE_LABELS[1],
                "stages": self._snapshot_stages(1),
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
                "estimated_seconds": 60,
                "request": payload,
                "result": None,
                "error": None,
                "approved": False,
            }
            self._jobs[job_id] = job
            self._persist(job_id)
            return job

    async def update_progress(
        self,
        job_id: str,
        *,
        progress_pct: int,
        stage: int,
        status: str,
        duration_ms: int | None = None,
    ) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            # Job lifecycle is controlled by mark_done/mark_failed.
            # Stage-level "done" means only the current stage is complete,
            # not the whole job.
            if status == "failed":
                job["status"] = "failed"
            elif job.get("status") != "done":
                job["status"] = "processing"
            job["progress_pct"] = max(0, min(100, int(progress_pct)))
            job["current_stage"] = stage
            job["stage_label"] = _STAGE_LABELS.get(stage, job.get("stage_label", ""))
            for stage_state in job["stages"]:
                if stage_state["stage"] == stage:
                    stage_state["status"] = status
                    if duration_ms is not None:
                        stage_state["duration_ms"] = duration_ms
                    stage_state["label"] = _STAGE_LABELS.get(
                        stage, stage_state.get("label", "")
                    )
                elif stage_state["stage"] < stage and stage_state["status"] in {
                    "queued",
                    "pending",
                    "running",
                }:
                    stage_state["status"] = "done"
            job["updated_at"] = datetime.now(UTC).isoformat()
            self._persist(job_id)

    async def mark_done(self, job_id: str, result: dict[str, Any]) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            job["status"] = "done"
            job["progress_pct"] = 100
            job["current_stage"] = 5
            job["stage_label"] = _STAGE_LABELS[5]
            job["result"] = result
            job["updated_at"] = datetime.now(UTC).isoformat()
            self._persist(job_id)

    async def mark_failed(self, job_id: str, exc: Exception) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            job["status"] = "failed"
            job["error"] = {
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
            job["updated_at"] = datetime.now(UTC).isoformat()
            self._persist(job_id)

    async def mark_approved(self, job_id: str) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            if job["status"] != "done":
                raise RuntimeError("Job is not complete")
            approve_generated_rules(job.get("result") or {})
            job["approved"] = True
            job["updated_at"] = datetime.now(UTC).isoformat()
            self._persist(job_id)

    async def save_rule_edits(
        self, job_id: str, edited_rules: list[dict[str, Any]]
    ) -> dict[str, Any]:
        async with self._lock:
            job = self._jobs[job_id]
            if job["status"] != "done":
                raise RuntimeError("Job is not complete")

            result = dict(job.get("result") or {})
            result["approved"] = bool(job.get("approved", False))
            updated_result = save_edited_rules(result, edited_rules)

            job["result"] = updated_result
            job["updated_at"] = datetime.now(UTC).isoformat()
            self._persist(job_id)
            return updated_result

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def run_job(self, job_id: str) -> None:
        job = await self.get_job(job_id)
        if not job:
            return

        request = dict(job["request"])
        loop = asyncio.get_running_loop()

        def _schedule_progress_update(kwargs: dict[str, Any]) -> None:
            task = self.update_progress(
                job_id,
                progress_pct=int(kwargs.get("progress_pct", 0)),
                stage=int(kwargs.get("stage", 1)),
                status=str(kwargs.get("status", "running")),
                duration_ms=int(kwargs["duration_ms"])
                if kwargs.get("duration_ms") is not None
                else None,
            )
            asyncio.create_task(task)

        def progress_cb(**kwargs: Any) -> None:
            # run_rule_generation_job executes in a worker thread; marshal updates back
            # onto the main event loop so create_task has a running loop context.
            loop.call_soon_threadsafe(_schedule_progress_update, dict(kwargs))

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    run_rule_generation_job,
                    job_id=job_id,
                    company_id=request["company_id"],
                    company_name=request["company_name"],
                    tax_id=request.get("tax_id", ""),
                    business_type=request["business_type"],
                    coa_file=Path(request["coa_file_path"]),
                    mapping_file=Path(request["mapping_file_path"]),
                    provider=request.get("provider", "auto"),
                    model=request.get("model", ""),
                    progress_callback=progress_cb,
                    rules_root=settings.RULES_ROOT,
                ),
                timeout=JOB_TIMEOUT_SECONDS,
            )
            await self.mark_done(job_id, result)
        except asyncio.TimeoutError as exc:  # pragma: no cover
            await self.mark_failed(
                job_id,
                RuntimeError(
                    f"Rule generation timed out after {JOB_TIMEOUT_SECONDS} seconds"
                ),
            )
        except Exception as exc:  # pragma: no cover
            await self.mark_failed(job_id, exc)


RULE_GENERATION_JOBS = RuleGenerationJobStore()
