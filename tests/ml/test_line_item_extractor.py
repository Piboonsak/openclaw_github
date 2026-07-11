"""Tests for the line-item extraction stage (Epic 9 / W5-EXPORT-LINEITEM-REALDATA-04).

Covers the reusable extractor call (with provider fallback) and the pipeline's
non-blocking contract: a line-item failure must never fail the pipeline or the
header result.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from src.backend.ml import line_item_extractor, llm_router
from src.backend.pipeline import orchestrator


class _FakeResponse:
    def __init__(self, text: str) -> None:
        self.text = text
        self.input_tokens = 100
        self.output_tokens = 50
        self.raw = {}


class _FakeProvider:
    def __init__(self, text: str | None = None, error: Exception | None = None) -> None:
        self._text = text
        self._error = error

    def call(self, *, model, system_prompt, user_prompt, image_paths=None):
        if self._error is not None:
            raise self._error
        return _FakeResponse(self._text or "")


_CANNED = json.dumps(
    {
        "document_total": "1000",
        "currency": "THB",
        "line_items": [
            {
                "product_name": "ท่อ PVC",
                "qty": "10",
                "unit": "เส้น",
                "unit_price": "80",
                "line_amount": "800",
                "line_type": "part_or_material",
                "line_type_confidence": "0.9",
                "stock_candidate": True,
                "confidence_reasons": [],
            }
        ],
        "notes": [],
    }
)


def _patch_provider(monkeypatch, provider) -> None:
    monkeypatch.setattr(llm_router, "load_llm_keys", lambda: None)
    monkeypatch.setattr(llm_router, "_image_input_enabled", lambda: False)
    monkeypatch.setattr(llm_router, "_provider_order", lambda *a, **k: ["openrouter"])
    monkeypatch.setattr(llm_router, "_build_provider", lambda name: (provider, ""))
    monkeypatch.setattr(
        llm_router, "_normalize_model_for_provider", lambda model, prov: model or "m"
    )


def test_extract_line_items_parses_response(monkeypatch):
    _patch_provider(monkeypatch, _FakeProvider(text=_CANNED))
    result = line_item_extractor.extract_line_items(
        image_path="/tmp/x.pdf",
        ocr_text="ท่อ PVC 10 เส้น",
        metadata={"invoice_number": "INV-1"},
    )
    assert len(result["line_items"]) == 1
    assert result["line_items"][0]["product_name"] == "ท่อ PVC"


def test_extract_line_items_raises_when_all_providers_fail(monkeypatch):
    _patch_provider(monkeypatch, _FakeProvider(error=RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        line_item_extractor.extract_line_items(
            image_path="/tmp/x.pdf", ocr_text="", metadata={}
        )


def test_run_pipeline_line_item_failure_is_non_blocking(monkeypatch):
    """A failing line-item stage must leave the pipeline SUCCESS with header data
    intact and an empty line_items list — never FAILED."""
    monkeypatch.setattr(
        orchestrator, "run_ocr", lambda *a, **k: {"sha256": "x", "blocks": []}
    )
    monkeypatch.setattr(
        orchestrator,
        "run_extraction",
        lambda *a, **k: {
            "fields": {
                "invoice_number": "INV-1",
                "source_text": "ท่อ PVC",
                "net_amount": "1000",
            },
            "confidence_per_field": {},
            "meta": {},
        },
    )
    monkeypatch.setattr(
        orchestrator, "run_journal_router", lambda *a, **k: {"postings": []}
    )

    def _boom(**kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(orchestrator, "extract_line_items", _boom)

    ctx = asyncio.run(orchestrator.run_pipeline("/tmp/x.pdf", enable_stock=True))

    assert ctx.status == orchestrator.StageResult.SUCCESS
    assert ctx.line_item_output.get("error")
    assert ctx.extraction_output.get("line_items") == []
    # Header extraction survived.
    assert ctx.extraction_output["fields"]["invoice_number"] == "INV-1"
