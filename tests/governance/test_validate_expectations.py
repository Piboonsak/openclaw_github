from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_validate_jsonl_passes_for_valid_rows(tmp_path):
    module = importlib.import_module("validate_expectations")
    data = [
        {
            "document_id": "DOC-1",
            "invoice_number": "INV-1",
            "invoice_date": "2026-06-07",
            "vendor_name": "Vendor",
            "total_amount": "1000",
        }
    ]
    path = tmp_path / "expectations.filled.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in data), encoding="utf-8")

    errors = module.validate_jsonl(path)
    assert errors == []


def test_validate_jsonl_fails_for_missing_key(tmp_path):
    module = importlib.import_module("validate_expectations")
    path = tmp_path / "expectations.filled.jsonl"
    path.write_text(json.dumps({"document_id": "DOC-1"}), encoding="utf-8")

    errors = module.validate_jsonl(path)
    assert errors
