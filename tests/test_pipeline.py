from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import src.backend.pipeline.orchestrator as orchestrator
from src.backend.pipeline.orchestrator import StageResult, run_pipeline


def test_run_pipeline_success_for_text_input(monkeypatch):
    with TemporaryDirectory() as tmp:
        sample = Path(tmp) / "doc.txt"
        sample.write_text(
            "invoice INV-123\ndate 2026-06-07\nvendor บริษัท ทดสอบ\ntotal 1070\n",
            encoding="utf-8",
        )

        ctx = asyncio.run(run_pipeline(str(sample)))
        assert ctx.status == StageResult.SUCCESS
        assert ctx.ocr_output
        assert ctx.extraction_output
        assert ctx.journal_output
        assert ctx.journal_output["is_balanced"] is True


def test_run_pipeline_backfills_missing_net_from_vat_and_total(monkeypatch):
    def fake_run_ocr(_image_path: str, **_kwargs) -> dict:
        return {"raw_text": "mock", "ocr_confidence": 0.95}

    def fake_run_extraction(_ocr_output: dict, **_kwargs) -> dict:
        return {
            "fields": {
                "source_text": "VAT 373.10 TOTAL 5703.10",
                "net_amount": "",
                "vat_amount": "373.10",
                "total_amount": "5703.10",
                "seller_tax_id": "0107544000043",
                "buyer_tax_id": "0125561025189",
            },
            "confidence_per_field": {
                "net_amount": 0.2,
                "vat_amount": 0.9,
                "total_amount": 0.9,
                "seller_tax_id": 0.9,
                "buyer_tax_id": 0.9,
            },
            "meta": {"ocr_confidence": 0.95},
        }

    def fake_cascade_repair(**_kwargs) -> dict:
        return {
            "fields": {},
            "confidence": {},
            "attempts": [],
            "unresolved_fields": [],
        }

    def fake_run_journal_router(
        _payload: dict, company_id: str | None = None, **_kwargs
    ) -> dict:
        return {"is_balanced": True, "company_id": company_id}

    monkeypatch.setattr(orchestrator, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(orchestrator, "run_extraction", fake_run_extraction)
    monkeypatch.setattr(orchestrator, "cascade_repair", fake_cascade_repair)
    monkeypatch.setattr(orchestrator, "run_journal_router", fake_run_journal_router)

    ctx = asyncio.run(run_pipeline("dummy.pdf"))
    assert ctx.status == StageResult.SUCCESS
    assert ctx.extraction_output["fields"]["net_amount"] == "5330.00"
    assert ctx.extraction_output["reconciliation"]["reconciled"] is True
    assert ctx.extraction_output["reconciliation_backfilled_fields"] == ["net_amount"]


def test_run_pipeline_emits_numeric_consistency_alerts(monkeypatch):
    def fake_run_ocr(_image_path: str, **_kwargs) -> dict:
        return {"raw_text": "mock", "ocr_confidence": 0.95}

    def fake_run_extraction(_ocr_output: dict, **_kwargs) -> dict:
        return {
            "fields": {
                "source_text": "mock",
                "net_amount": "1000.00",
                "vat_amount": "70.00",
                "total_amount": "1200.00",
                "wht_rate": "3",
                "wht_amount": "50.00",
                "amount_paid": "1000.00",
                "seller_tax_id": "0107544000043",
                "buyer_tax_id": "0125561025189",
            },
            "confidence_per_field": {
                "net_amount": 0.9,
                "vat_amount": 0.9,
                "total_amount": 0.9,
                "wht_amount": 0.9,
                "amount_paid": 0.9,
                "seller_tax_id": 0.9,
                "buyer_tax_id": 0.9,
            },
            "meta": {"ocr_confidence": 0.95},
        }

    def fake_cascade_repair(**_kwargs) -> dict:
        return {
            "fields": {},
            "confidence": {},
            "attempts": [],
            "unresolved_fields": [],
        }

    def fake_run_journal_router(
        _payload: dict, company_id: str | None = None, **_kwargs
    ) -> dict:
        return {"is_balanced": True, "company_id": company_id}

    monkeypatch.setattr(orchestrator, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(orchestrator, "run_extraction", fake_run_extraction)
    monkeypatch.setattr(orchestrator, "cascade_repair", fake_cascade_repair)
    monkeypatch.setattr(orchestrator, "run_journal_router", fake_run_journal_router)

    ctx = asyncio.run(run_pipeline("dummy.pdf"))
    assert ctx.status == StageResult.SUCCESS

    alerts = ctx.extraction_output["numeric_consistency_alerts"]
    by_field = {item["field"]: item for item in alerts}

    assert by_field["total_amount"]["recommended"] == "1070.00"
    assert by_field["wht_amount"]["recommended"] == "30.00"
    assert by_field["amount_paid"]["recommended"] == "1150.00"
