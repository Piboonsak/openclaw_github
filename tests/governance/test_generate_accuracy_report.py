from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_generate_accuracy_report_main(tmp_path):
    module = importlib.import_module("generate_accuracy_report")

    expectations = {
        "documents": {
            "doc1.pdf": {
                "invoice_number": "INV-001",
                "invoice_date": "2026-06-07",
                "supplier_name": "Vendor A",
                "amounts": {"gross_amount": 1070.0},
                "expected_journal": {
                    "postings": [
                        {"account_code": "5040"},
                        {"account_code": "1154"},
                        {"account_code": "2195"},
                    ]
                },
            }
        }
    }
    exp_path = tmp_path / "expectations.json"
    exp_path.write_text(json.dumps(expectations), encoding="utf-8")

    out_path = tmp_path / "accuracy_report.json"
    rc = module.main(["--expectations", str(exp_path), "--out", str(out_path)])
    assert rc == 0
    assert out_path.exists()

    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert "summary" in report
    assert "gate_passed" in report
