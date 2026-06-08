"""API endpoint placeholders."""

import asyncio

from src.extraction.fields import extract_fields
from src.ocr.processor import process_document
from src.pipeline.orchestrator import run_pipeline
from src.validation.rules import validate_required_fields

try:
    from fastapi import FastAPI
except Exception:  # pragma: no cover
    FastAPI = None


if FastAPI is not None:
    app = FastAPI(title="AI Pre-Accounting Copilot")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.post("/process")
    def process(file_path: str) -> dict:
        text = process_document(file_path)
        fields = extract_fields(text)
        validation = validate_required_fields(fields, ["invoice_number", "invoice_date", "total_amount"])
        pipeline_ctx = asyncio.run(run_pipeline(file_path))
        return {
            "text": text,
            "fields": fields,
            "validation": validation,
            "extraction": pipeline_ctx.extraction_output,
            "journal": pipeline_ctx.journal_output,
            "pipeline_status": pipeline_ctx.status.name,
        }
else:
    app = None
