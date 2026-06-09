import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.backend.services.rule_engine import (
    run_journal_router,
    validate_required_fields,
)


class TestValidation(unittest.TestCase):
    def test_validate_required_fields_reports_missing(self):
        result = validate_required_fields(
            {"invoice_number": "INV-1"}, ["invoice_number", "total_amount"]
        )
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
            self.assertEqual(
                round(output["totals"]["debit"], 2),
                round(output["totals"]["credit"], 2),
            )

            artifact = Path(tmp) / "cache" / "xyz987" / "journal_output.json"
            self.assertTrue(artifact.exists())

            cached = run_journal_router(
                extraction_output,
                cache_root=Path(tmp) / "cache",
                rules_root=Path(tmp) / "rules",
            )
            self.assertTrue(cached["cache_hit"])

    def test_fallback_uses_document_vat_when_present(self):
        with TemporaryDirectory() as tmp:
            extraction_output = {
                "sha256": "doc125326",
                "fields": {
                    "invoice_number": "03062026125326",
                    "total_amount": "5703.10",
                    "vat_amount": "373.10",
                },
            }

            output = run_journal_router(
                extraction_output,
                cache_root=Path(tmp) / "cache",
                rules_root=Path(tmp) / "rules",
            )

            expense_line = next(
                p for p in output["postings"] if p["line_type"] == "expense"
            )
            vat_line = next(p for p in output["postings"] if p["line_type"] == "vat")
            ap_line = next(p for p in output["postings"] if p["line_type"] == "ap")

            self.assertEqual(round(expense_line["debit"], 2), 5330.00)
            self.assertEqual(round(vat_line["debit"], 2), 373.10)
            self.assertEqual(round(ap_line["credit"], 2), 5703.10)
            self.assertTrue(output["is_balanced"])

    def test_fallback_exclusive_doc_keeps_net_vat_gross(self):
        with TemporaryDirectory() as tmp:
            extraction_output = {
                "sha256": "doc130550",
                "fields": {
                    "invoice_number": "03062026130550",
                    "net_amount": "4900.00",
                    "vat_amount": "343.00",
                    "total_amount": "5243.00",
                },
            }

            output = run_journal_router(
                extraction_output,
                cache_root=Path(tmp) / "cache",
                rules_root=Path(tmp) / "rules",
            )

            expense_line = next(
                p for p in output["postings"] if p["line_type"] == "expense"
            )
            vat_line = next(p for p in output["postings"] if p["line_type"] == "vat")
            ap_line = next(p for p in output["postings"] if p["line_type"] == "ap")

            self.assertEqual(round(expense_line["debit"], 2), 4900.00)
            self.assertEqual(round(vat_line["debit"], 2), 343.00)
            self.assertEqual(round(ap_line["credit"], 2), 5243.00)
            self.assertTrue(output["is_balanced"])

    def test_fallback_total_only_uses_inclusive_vat_formula(self):
        with TemporaryDirectory() as tmp:
            extraction_output = {
                "sha256": "doc_total_only",
                "fields": {
                    "invoice_number": "INV-TOTAL-ONLY",
                    "total_amount": "5703.10",
                },
            }

            output = run_journal_router(
                extraction_output,
                cache_root=Path(tmp) / "cache",
                rules_root=Path(tmp) / "rules",
            )

            expense_line = next(
                p for p in output["postings"] if p["line_type"] == "expense"
            )
            vat_line = next(p for p in output["postings"] if p["line_type"] == "vat")
            ap_line = next(p for p in output["postings"] if p["line_type"] == "ap")

            self.assertEqual(round(vat_line["debit"], 2), 373.10)
            self.assertEqual(round(expense_line["debit"], 2), 5330.00)
            self.assertEqual(round(ap_line["credit"], 2), 5703.10)
            self.assertTrue(output["is_balanced"])


if __name__ == "__main__":
    unittest.main()
