"""Unit tests for the amount reconciliation engine.

Anchored on the four documents reported during live testing (2026-06-09):
- 03062026130649: WHT present, gross must be net + vat (before WHT deduction)
- 03062026130532: amounts do not reconcile -> must NOT reconcile
- 03062026130707: correct net/gross, no VAT line -> derived VAT consistent
- 03062026130738: VAT-exclusive layout, net 17,950 + vat 1,256.50 = gross 19,206.50
"""

import unittest

from src.backend.ml.amount_reconciler import (
    apply_amount_confidence,
    classify_vat_layout,
    reconcile_amounts,
)


class TestVatLayoutClassifier(unittest.TestCase):
    def test_exclusive_layout_net_plus_vat(self):
        # 03062026130738: บวก VAT (exclusive)
        layout, derived = classify_vat_layout(net=17950.0, vat=1256.50, total=None)
        self.assertEqual(layout, "exclusive")
        self.assertAlmostEqual(derived["gross"], 19206.50, places=2)

    def test_inclusive_layout_total_minus_vat(self):
        layout, derived = classify_vat_layout(net=None, vat=1256.50, total=19206.50)
        self.assertEqual(layout, "inclusive")
        self.assertAlmostEqual(derived["net"], 17950.0, places=2)

    def test_only_total_assumes_inclusive(self):
        layout, derived = classify_vat_layout(net=None, vat=None, total=107.0, rate=7.0)
        self.assertEqual(layout, "inclusive")
        self.assertAlmostEqual(derived["net"], 100.0, places=1)
        self.assertAlmostEqual(derived["vat"], 7.0, places=1)

    def test_only_net_assumes_exclusive(self):
        layout, derived = classify_vat_layout(net=100.0, vat=None, total=None, rate=7.0)
        self.assertEqual(layout, "exclusive")
        self.assertAlmostEqual(derived["vat"], 7.0, places=1)
        self.assertAlmostEqual(derived["gross"], 107.0, places=1)


class TestReconcileAmounts(unittest.TestCase):
    def test_doc_130738_exclusive_reconciles(self):
        fields = {
            "net_amount": "17950.00",
            "vat_amount": "1256.50",
            "total_amount": "19206.50",
            "vat_rate": "7",
        }
        result = reconcile_amounts(fields)
        self.assertTrue(result["reconciled"])
        self.assertEqual(result["layout"], "exclusive")
        self.assertEqual(result["checks"]["total"], "ok")
        self.assertEqual(result["checks"]["vat"], "ok")

    def test_doc_130649_gross_before_wht(self):
        # gross = net + vat (2,057,692.31); WHT is a separate deduction
        fields = {
            "net_amount": "1922142.35",
            "vat_amount": "134549.96",
            "total_amount": "2056692.31",
            "wht_amount": "57692.31",
            "vat_rate": "7",
        }
        result = reconcile_amounts(fields)
        # net + vat should equal gross (within tolerance); not net+vat-wht
        self.assertAlmostEqual(result["derived"]["gross"], 2056692.31, places=0)

    def test_doc_130532_does_not_reconcile(self):
        # Net 496.00 but Gross 530.72 with no consistent VAT -> must fail
        fields = {
            "net_amount": "496.00",
            "vat_amount": "0.00",
            "total_amount": "530.72",
            "vat_rate": "7",
        }
        result = reconcile_amounts(fields)
        self.assertFalse(result["reconciled"])

    def test_wht_strict_check_fails_on_mismatch(self):
        fields = {
            "net_amount": "1000.00",
            "vat_amount": "70.00",
            "total_amount": "1070.00",
            "wht_amount": "99.99",  # not 3% of 1000 (=30)
            "wht_rate": "3",
            "vat_rate": "7",
        }
        result = reconcile_amounts(fields)
        self.assertEqual(result["checks"]["wht"], "fail")
        self.assertFalse(result["reconciled"])

    def test_wht_strict_check_passes_on_net_base(self):
        fields = {
            "net_amount": "1000.00",
            "vat_amount": "70.00",
            "total_amount": "1070.00",
            "wht_amount": "30.00",  # 3% of net 1000
            "wht_rate": "3",
            "vat_rate": "7",
        }
        result = reconcile_amounts(fields)
        self.assertEqual(result["checks"]["wht"], "ok")
        self.assertTrue(result["reconciled"])

    def test_total_is_paid_autocorrect(self):
        # Printed total is the post-WHT paid amount
        fields = {
            "net_amount": "1000.00",
            "vat_amount": "70.00",
            "total_amount": "1040.00",  # = net + vat - wht(30)
            "wht_amount": "30.00",
            "wht_rate": "3",
            "vat_rate": "7",
        }
        result = reconcile_amounts(fields)
        self.assertTrue(result["total_is_paid"])
        self.assertEqual(result["corrected"]["total_amount"], "1070.00")


class TestApplyAmountConfidence(unittest.TestCase):
    def test_failed_total_caps_amount_confidence(self):
        fields = {
            "net_amount": "496.00",
            "vat_amount": "0.00",
            "total_amount": "530.72",
        }
        confidence = {"net_amount": 0.9, "vat_amount": 0.9, "total_amount": 0.9}
        recon = reconcile_amounts(fields)
        apply_amount_confidence(fields, confidence, recon)
        self.assertLessEqual(confidence["total_amount"], 0.55)
        self.assertLessEqual(confidence["net_amount"], 0.45)

    def test_reconciled_keeps_high_confidence(self):
        fields = {
            "net_amount": "17950.00",
            "vat_amount": "1256.50",
            "total_amount": "19206.50",
        }
        confidence = {"net_amount": 0.9, "vat_amount": 0.9, "total_amount": 0.9}
        recon = reconcile_amounts(fields)
        apply_amount_confidence(fields, confidence, recon)
        self.assertEqual(confidence["net_amount"], 0.9)
        self.assertEqual(confidence["vat_amount"], 0.9)


if __name__ == "__main__":
    unittest.main()
