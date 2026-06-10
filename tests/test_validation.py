import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.validation.rules import (
    InvalidChartOfAccountsError,
    UnbalancedEntryError,
    compile_rules,
    post_journal_entry,
    route_journal,
    validate_required_fields,
)


class TestValidation(unittest.TestCase):
    def _prepare_company_rules(self, base_dir: Path) -> Path:
        repo_root = Path(__file__).resolve().parents[1]
        source_rule = repo_root / "docs" / "PoC" / "Comp_1" / "rule_coa.yaml"
        target_rule = base_dir / "rules" / "Comp_1" / "rule_coa.yaml"
        target_rule.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_rule, target_rule)
        return target_rule

    def test_validate_required_fields_reports_missing(self):
        result = validate_required_fields(
            {"invoice_number": "INV-1"}, ["invoice_number", "total_amount"]
        )
        self.assertEqual(result["missing_fields"], ["total_amount"])
        self.assertFalse(result["is_valid"])

    def test_compile_rules_loads_company_yaml(self):
        with TemporaryDirectory() as tmp:
            yaml_path = self._prepare_company_rules(Path(tmp))
            compiled = compile_rules(yaml_path)
            self.assertEqual(compiled.company_id, "Comp_1")
            self.assertGreater(len(compiled.chart_of_accounts), 0)
            self.assertGreater(len(compiled.journal_rules), 0)

    def test_purchase_route_and_post_balanced(self):
        with TemporaryDirectory() as tmp:
            yaml_path = self._prepare_company_rules(Path(tmp))
            compiled = compile_rules(yaml_path)
            extraction = {
                "sha256": "purchase001",
                "fields": {
                    "document_type": "Purchase Order",
                    "source_document": "P/O",
                    "payment_method": "credit",
                    "has_vat": True,
                    "vat_type": "normal",
                    "invoice_date": "2026-06-07",
                    "invoice_number": "PO-001",
                    "gross_amount": 1070.0,
                    "net_amount": 1000.0,
                    "vat_amount": 70.0,
                },
            }
            output = post_journal_entry(extraction, compiled)
            self.assertTrue(output["is_balanced"])
            self.assertEqual(output["status"], "READY")
            self.assertEqual(output["rule_id"], "RRL-PURCHASE-SUPPLIES")
            self.assertEqual(output["express_gl"]["book_code"], "AP")

    def test_sale_route_and_post_balanced(self):
        with TemporaryDirectory() as tmp:
            yaml_path = self._prepare_company_rules(Path(tmp))
            compiled = compile_rules(yaml_path)
            extraction = {
                "sha256": "sale001",
                "fields": {
                    "document_type": "Invoice",
                    "has_vat": True,
                    "vat_type": "deferred",
                    "payment_method": "wire",
                    "source_document": "invoice",
                    "invoice_number": "AR-001",
                    "invoice_date": "2026-06-08",
                    "gross_amount": 2140.0,
                    "net_amount": 2000.0,
                    "vat_amount": 140.0,
                },
            }
            output = post_journal_entry(extraction, compiled)
            self.assertTrue(output["is_balanced"])
            self.assertEqual(output["rule_id"], "RRL-SALE-CREDIT")
            self.assertEqual(output["express_gl"]["book_code"], "AR")

    def test_receipt_route_and_post_balanced_with_wht(self):
        with TemporaryDirectory() as tmp:
            yaml_path = self._prepare_company_rules(Path(tmp))
            compiled = compile_rules(yaml_path)
            extraction = {
                "sha256": "receipt001",
                "fields": {
                    "document_type": "Receipt",
                    "has_vat": True,
                    "has_wht": True,
                    "vat_type": "recognize",
                    "invoice_number": "RV-001",
                    "invoice_date": "2026-06-09",
                    "net_received": 2000.00,
                    "wht_amount": 57.69,
                    "receivable_amount": 2057.69,
                    "vat_amount": 134.62,
                },
            }

            output = post_journal_entry(extraction, compiled)
            self.assertTrue(output["is_balanced"])
            self.assertEqual(output["rule_id"], "RRL-RECEIVE-PAYMENT")
            self.assertEqual(output["express_gl"]["book_code"], "RV")

    def test_payment_route_flags_variable_account_for_review(self):
        with TemporaryDirectory() as tmp:
            yaml_path = self._prepare_company_rules(Path(tmp))
            compiled = compile_rules(yaml_path)
            extraction = {
                "sha256": "payment001",
                "fields": {
                    "document_type": "Bill",
                    "payment_method": "cash",
                    "has_vat": True,
                    "vat_type": "normal",
                    "invoice_number": "PV-001",
                    "net_amount": 1000.0,
                    "vat_amount": 70.0,
                    "payment_amount": 1070.0,
                    "wht_amount": 0.0,
                    "seller_type": "corporate",
                    "source_text": "ค่าไฟสำนักงาน",
                },
            }

            routed = route_journal(extraction, compiled)
            self.assertEqual(routed["rule_id"], "RRL-EXPENSE-CASH")
            self.assertIn("needs_human_account_pick", routed.get("flags", []))

            with self.assertRaises(InvalidChartOfAccountsError):
                post_journal_entry(extraction, compiled)

    def test_multi_line_wht_tolerance_balance(self):
        with TemporaryDirectory() as tmp:
            yaml_path = self._prepare_company_rules(Path(tmp))
            compiled = compile_rules(yaml_path)
            extraction = {
                "sha256": "receipt-rounding-001",
                "fields": {
                    "document_type": "Receipt",
                    "has_vat": True,
                    "has_wht": True,
                    "vat_type": "recognize",
                    "invoice_number": "RV-RND-001",
                    "net_received": 999.99,
                    "wht_amount": 30.00,
                    "receivable_amount": 1029.99,
                    "vat_amount": 70.00,
                },
            }
            output = post_journal_entry(extraction, compiled)
            self.assertTrue(output["is_balanced"])

    def test_unbalanced_entry_raises_exception(self):
        with TemporaryDirectory() as tmp:
            yaml_path = self._prepare_company_rules(Path(tmp))
            compiled = compile_rules(yaml_path)
            extraction = {
                "sha256": "receipt-unbalanced-001",
                "fields": {
                    "document_type": "Receipt",
                    "has_vat": True,
                    "has_wht": True,
                    "vat_type": "recognize",
                    "invoice_number": "RV-BAD-001",
                    "net_received": 2000.00,
                    "wht_amount": 57.69,
                    "receivable_amount": 2055.00,
                    "vat_amount": 134.62,
                },
            }

            with self.assertRaises(UnbalancedEntryError):
                post_journal_entry(extraction, compiled)


if __name__ == "__main__":
    unittest.main()
