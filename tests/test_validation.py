import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.backend.services.rule_engine import (
    run_journal_router,
    validate_required_fields,
)


class TestValidation(unittest.TestCase):
    def test_validate_required_fields_reports_missing(self):
        result = validate_required_fields({"invoice_number": "INV-1"}, ["invoice_number", "total_amount"])
        self.assertEqual(result["missing_fields"], ["total_amount"])
        self.assertFalse(result["is_valid"])

    def test_run_journal_router_outputs_balanced_entries(self):
        with TemporaryDirectory() as tmp:
            extraction_output = {
                "sha256": "xyz987",
                "fields": {
                    "invoice_number": "INV-001",
                    "invoice_date": "2026-06-07",
                    "vendor_name": "Vendor A",
                    "total_amount": "1070",
                },
            }

            output = run_journal_router(
                extraction_output,
                cache_root=Path(tmp) / "cache",
                rules_root=Path(tmp) / "rules",
            )

            self.assertTrue(output["is_balanced"])
            self.assertEqual(output["status"], "READY")
            self.assertEqual(round(output["totals"]["debit"], 2), round(output["totals"]["credit"], 2))

            artifact = Path(tmp) / "cache" / "xyz987" / "journal_output.json"
            self.assertTrue(artifact.exists())

            cached = run_journal_router(
                extraction_output,
                cache_root=Path(tmp) / "cache",
                rules_root=Path(tmp) / "rules",
            )
            self.assertTrue(cached["cache_hit"])


if __name__ == "__main__":
    unittest.main()
