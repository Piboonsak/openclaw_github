"""Tests for TASK-1104 — balance validation and export preview helpers.

Covers:
  ac_1104_balanced    — balanced vouchers pass (valid=True)
  ac_1104_unbalanced  — unbalanced vouchers return valid=False with details
  ac_1104_tolerance   — rounding difference <= 0.01 THB is tolerated
  ac_1104_report      — unbalanced entry has voucher_no, total_debit, total_credit, difference
  ac_1104_preview     — preview uses render_preview() with max 10 rows (pure-Python path)
"""

from __future__ import annotations

import unittest

from src.backend.services.export_service import validate_balance
from src.backend.services.template_engine import ColumnDef
from src.backend.api.templates import render_preview


# ---------------------------------------------------------------------------
# ac_1104_balanced
# ---------------------------------------------------------------------------

class TestBalancedVouchers(unittest.TestCase):
    def _make(self, voucher_no, pairs):
        """pairs: list of (debit, credit)"""
        return {
            "voucher_no": voucher_no,
            "lines": [{"debit": d, "credit": c} for d, c in pairs],
        }

    def test_perfectly_balanced(self):
        v = self._make("AP001", [(10700.0, 0), (0, 10700.0)])
        result = validate_balance([v])
        self.assertTrue(result["valid"])
        self.assertEqual(result["unbalanced_vouchers"], [])

    def test_multiple_balanced_vouchers(self):
        vouchers = [
            self._make("AP001", [(5000, 0), (0, 5000)]),
            self._make("AP002", [(3000, 0), (0, 3000)]),
        ]
        result = validate_balance(vouchers)
        self.assertTrue(result["valid"])

    def test_empty_lines_treated_as_balanced(self):
        """A voucher with no lines has Dr=0 and Cr=0 → balanced."""
        result = validate_balance([{"voucher_no": "AP000", "lines": []}])
        self.assertTrue(result["valid"])

    def test_empty_voucher_list(self):
        result = validate_balance([])
        self.assertTrue(result["valid"])
        self.assertEqual(result["unbalanced_vouchers"], [])


# ---------------------------------------------------------------------------
# ac_1104_unbalanced
# ---------------------------------------------------------------------------

class TestUnbalancedVouchers(unittest.TestCase):
    def _make(self, voucher_no, pairs):
        return {
            "voucher_no": voucher_no,
            "lines": [{"debit": d, "credit": c} for d, c in pairs],
        }

    def test_single_unbalanced(self):
        v = self._make("AP003", [(10000.0, 0), (0, 9999.0)])
        result = validate_balance([v])
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["unbalanced_vouchers"]), 1)

    def test_mixed_balanced_and_unbalanced(self):
        vouchers = [
            self._make("AP001", [(5000, 0), (0, 5000)]),   # balanced
            self._make("AP002", [(5000, 0), (0, 4000)]),   # unbalanced
        ]
        result = validate_balance(vouchers)
        self.assertFalse(result["valid"])
        codes = [u["voucher_no"] for u in result["unbalanced_vouchers"]]
        self.assertIn("AP002", codes)
        self.assertNotIn("AP001", codes)

    def test_multiple_unbalanced(self):
        vouchers = [
            self._make("X1", [(100, 0), (0, 50)]),
            self._make("X2", [(200, 0), (0, 100)]),
        ]
        result = validate_balance(vouchers)
        self.assertEqual(len(result["unbalanced_vouchers"]), 2)


# ---------------------------------------------------------------------------
# ac_1104_tolerance
# ---------------------------------------------------------------------------

class TestBalanceTolerance(unittest.TestCase):
    def _make(self, voucher_no, dr, cr):
        return {"voucher_no": voucher_no, "lines": [{"debit": dr, "credit": cr}]}

    def test_exactly_at_tolerance_is_ok(self):
        # diff == 0.01 → should PASS (≤ tolerance)
        result = validate_balance([self._make("V1", 1000.00, 999.99)])
        self.assertTrue(result["valid"])

    def test_just_above_tolerance_fails(self):
        # diff == 0.02 → should FAIL (> tolerance)
        result = validate_balance([self._make("V1", 1000.00, 999.98)])
        self.assertFalse(result["valid"])

    def test_custom_tolerance(self):
        result = validate_balance([self._make("V1", 1000.00, 999.95)], tolerance=0.10)
        self.assertTrue(result["valid"])

    def test_zero_difference_always_ok(self):
        result = validate_balance([self._make("V1", 500.00, 500.00)])
        self.assertTrue(result["valid"])


# ---------------------------------------------------------------------------
# ac_1104_report
# ---------------------------------------------------------------------------

class TestValidationReport(unittest.TestCase):
    def test_unbalanced_report_fields(self):
        voucher = {
            "voucher_no": "AP999",
            "lines": [{"debit": 10000.0, "credit": 0}, {"debit": 0, "credit": 9500.0}],
        }
        result = validate_balance([voucher])
        u = result["unbalanced_vouchers"][0]
        self.assertEqual(u["voucher_no"],    "AP999")
        self.assertAlmostEqual(u["total_debit"],  10000.0)
        self.assertAlmostEqual(u["total_credit"],  9500.0)
        self.assertAlmostEqual(u["difference"],     500.0)

    def test_difference_rounded_to_2dp(self):
        voucher = {
            "voucher_no": "X1",
            "lines": [{"debit": 1.005, "credit": 1.0}],
        }
        result = validate_balance([voucher])
        # diff = 0.005 < 0.01 → valid; but if it were unbalanced, difference is 2dp
        # Force unbalanced: use diff > 0.01
        voucher2 = {"voucher_no": "X2", "lines": [{"debit": 100.123, "credit": 100.0}]}
        r2 = validate_balance([voucher2])
        if not r2["valid"]:
            diff = r2["unbalanced_vouchers"][0]["difference"]
            self.assertEqual(diff, round(diff, 2))

    def test_multi_line_totals_summed_correctly(self):
        voucher = {
            "voucher_no": "JV001",
            "lines": [
                {"debit": 5000.0, "credit": 0},
                {"debit": 350.0,  "credit": 0},
                {"debit": 0,      "credit": 5200.0},
            ],
        }
        result = validate_balance([voucher])
        u = result["unbalanced_vouchers"][0]
        self.assertAlmostEqual(u["total_debit"],  5350.0)
        self.assertAlmostEqual(u["total_credit"], 5200.0)
        self.assertAlmostEqual(u["difference"],    150.0)

    def test_missing_debit_credit_defaults_to_zero(self):
        voucher = {"voucher_no": "V1", "lines": [{"debit": 100}]}  # no credit key
        result = validate_balance([voucher])
        self.assertFalse(result["valid"])
        self.assertAlmostEqual(result["unbalanced_vouchers"][0]["total_credit"], 0.0)


# ---------------------------------------------------------------------------
# ac_1104_preview — pure-Python path (no DB, reuses render_preview)
# ---------------------------------------------------------------------------

class TestExportPreviewHelper(unittest.TestCase):
    def test_preview_caps_at_10_rows(self):
        cols = [ColumnDef(source_field="x", header_label="X")]
        data = [{"x": str(i)} for i in range(20)]
        result = render_preview(cols, data, max_rows=10)
        self.assertEqual(len(result.rows), 10)

    def test_preview_returns_correct_headers(self):
        cols = [
            ColumnDef("voucher_no",   "เลขที่"),
            ColumnDef("voucher_date", "วันที่", data_type="date", transform="thai_date_short"),
        ]
        result = render_preview(cols, [{"voucher_no": "V1", "voucher_date": "2026-06-01"}])
        self.assertEqual(result.headers, ["เลขที่", "วันที่"])

    def test_preview_empty_sample_data(self):
        cols = [ColumnDef("x", "X")]
        result = render_preview(cols, [])
        self.assertEqual(result.rows, [])
        self.assertEqual(result.headers, ["X"])


if __name__ == "__main__":
    unittest.main()
