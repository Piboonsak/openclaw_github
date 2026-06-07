"""In-process job store for D6 rule generation endpoints."""

from __future__ import annotations

import asyncio
import traceback
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.backend.services.rule_generator import (
    approve_generated_rules,
    run_rule_generation_job,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
JOBS_ROOT = REPO_ROOT / "rules" / "_jobs"
JOBS_ROOT.mkdir(parents=True, exist_ok=True)

_STAGE_LABELS = {
    1: "Uploading & validating files",
    2: "Extracting text from documents",
    3: "Analyzing COA structure",
    4: "Generating journal entry rules",
    5: "Validating & writing rule file",
}


class RuleGenerationJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def _persist(self, job_id: str) -> None:
        payload = self._jobs.get(job_id)
        if not payload:
            return
        (JOBS_ROOT / f"{job_id}.json").write_text(
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
            job["status"] = "processing" if status not in {"failed", "done"} else status
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
            result = await asyncio.to_thread(
                run_rule_generation_job,
                job_id=job_id,
                company_id=request["company_id"],
                company_name=request["company_name"],
                tax_id=request.get("tax_id", ""),
                business_type=request["business_type"],
                coa_file=Path(request["coa_file_path"]),
                mapping_file=Path(request["mapping_file_path"]),
                provider=request.get("provider", "anthropic"),
                model=request.get("model", "claude-sonnet-4-6-20250601"),
                progress_callback=progress_cb,
            )
            await self.mark_done(job_id, result)
        except Exception as exc:  # pragma: no cover
            await self.mark_failed(job_id, exc)


RULE_GENERATION_JOBS = RuleGenerationJobStore()
