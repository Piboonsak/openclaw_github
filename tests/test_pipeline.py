from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from src.backend.pipeline.orchestrator import StageResult, run_pipeline


def test_run_pipeline_success_for_text_input(monkeypatch):
    with TemporaryDirectory() as tmp:
        sample = Path(tmp) / "doc.txt"
        sample.write_text(
            "invoice INV-123\n"
            "date 2026-06-07\n"
            "vendor บริษัท ทดสอบ\n"
            "total 1070\n",
            encoding="utf-8",
        )

        ctx = asyncio.run(run_pipeline(str(sample)))
        assert ctx.status == StageResult.SUCCESS
        assert ctx.ocr_output
        assert ctx.extraction_output
        assert ctx.journal_output
        assert ctx.journal_output["is_balanced"] is True
