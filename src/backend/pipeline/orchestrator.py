"""Epic 5 pipeline orchestrator skeleton (TASK-501/502/503)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any

from src.backend.ml.field_extractor import run_extraction
from src.backend.ml.ocr import run_ocr
from src.backend.services.rule_engine import run_journal_router


class StageResult(Enum):
    SUCCESS = auto()
    FAILED = auto()


@dataclass
class PipelineContext:
    source_file: str
    company_id: str | None = None
    ocr_output: dict[str, Any] = field(default_factory=dict)
    extraction_output: dict[str, Any] = field(default_factory=dict)
    journal_output: dict[str, Any] = field(default_factory=dict)
    status: StageResult = StageResult.SUCCESS
    error: str | None = None


async def run_pipeline(
    image_path: str, company_id: str | None = None
) -> PipelineContext:
    """Run OCR -> extraction -> journal routing pipeline."""
    ctx = PipelineContext(source_file=image_path, company_id=company_id)
    try:
        ctx.ocr_output = run_ocr(image_path)
        ctx.extraction_output = run_extraction(ctx.ocr_output)
        ctx.extraction_output["company_id"] = company_id
        ctx.journal_output = run_journal_router(
            ctx.extraction_output,
            company_id=company_id,
        )
    except Exception as exc:  # pragma: no cover - safety net for runtime failures
        ctx.status = StageResult.FAILED
        ctx.error = str(exc)
    return ctx


def select_model(ctx: PipelineContext) -> str:
    """Expose selected extraction model for diagnostics."""
    model = ctx.extraction_output.get("model") if ctx.extraction_output else None
    return str(model or "claude-haiku-4-5-20250514")
