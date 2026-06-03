"""API endpoint placeholders."""

from src.extraction.fields import extract_fields
from src.ocr.processor import process_document
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
        return {"text": text, "fields": fields, "validation": validation}
else:
    app = None
