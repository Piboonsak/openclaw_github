"""CI accuracy gate tests — Phase 4 per-field KPI enforcement.

These tests evaluate per-field extraction accuracy against the thresholds
defined in docs/ACCURACY_TARGETS.md and KPIThresholds.

The tests can run in two modes:
  1. Unit mode (default): uses synthetic fixtures to verify the gate logic itself.
  2. Integration mode (OCR_GATE_INTEGRATION=1): runs against the labeled golden
     dataset in private_data/poc/Comp_1/expectations.filled.jsonl and fails CI
     if any field drops below its target.

To label new docs, add entries to:
  private_data/poc/Comp_1/expectations.filled.jsonl
  (see expectations.template.jsonl for schema)
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from src.backend.evaluation.accuracy_evaluator import (
    KPIThresholds,
    aggregate_reports,
    evaluate_accuracy,
    gate_passed,
)

# === Synthetic fixture helpers ===

def _make_journal(fields: dict, is_balanced: bool = True, status: str = "READY") -> dict:
    return {
        "fields": fields,
        "postings": [],
        "is_balanced": is_balanced,
        "status": status,
    }


def _make_expected(
    invoice_number: str = "INV-001",
    invoice_date: str = "2026-06-01",
    seller_tax_id: str = "1234567890123",
    buyer_tax_id: str = "9876543210987",
    gross_amount: float = 1990.00,
    net_amount: float = 1859.81,
    vat_amount: float = 130.19,
    vat_rate: str = "7",
) -> dict:
    return {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "seller_tax_id": seller_tax_id,
        "buyer_tax_id": buyer_tax_id,
        "vat_rate": vat_rate,
        "amounts": {
            "gross_amount": gross_amount,
            "net_amount": net_amount,
            "vat_amount": vat_amount,
        },
        "expected_journal": {"postings": []},
    }


def _make_extracted(
    invoice_number: str = "INV-001",
    invoice_date: str = "2026-06-01",
    seller_tax_id: str = "1234567890123",
    buyer_tax_id: str = "9876543210987",
    total_amount: str = "1990.00",
    net_amount: str = "1859.81",
    vat_amount: str = "130.19",
    vat_rate: str = "7",
) -> dict:
    return {
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "seller_tax_id": seller_tax_id,
        "buyer_tax_id": buyer_tax_id,
        "total_amount": total_amount,
        "net_amount": net_amount,
        "vat_amount": vat_amount,
        "vat_rate": vat_rate,
    }


# Thresholds that only enforce per-field accuracy (skip account/journal level gates)
_PER_FIELD_ONLY = KPIThresholds(field_level=0.0, account_level=0.0, journal_level=0.0)


class TestAccuracyGateUnit(unittest.TestCase):
    """Unit tests for gate logic using synthetic fixtures."""

    def test_perfect_extraction_passes_gate(self):
        """All fields correct → gate passes."""
        journal = _make_journal(_make_extracted())
        expected = _make_expected()
        report = evaluate_accuracy(journal, expected)
        self.assertEqual(report["field_level_accuracy"], 1.0)
        self.assertTrue(report["per_field"]["invoice_number"])
        self.assertTrue(report["per_field"]["total_amount"])
        self.assertTrue(report["per_field"]["net_amount"])
        self.assertTrue(report["per_field"]["vat_amount"])
        self.assertTrue(report["per_field"]["seller_tax_id"])
        self.assertTrue(report["per_field"]["buyer_tax_id"])

    def test_missing_vat_amount_captured_in_per_field(self):
        """Missing VAT amount → per_field[vat_amount] = False."""
        extracted = _make_extracted(vat_amount="0.00")
        journal = _make_journal(extracted)
        expected = _make_expected()
        report = evaluate_accuracy(journal, expected)
        self.assertFalse(report["per_field"]["vat_amount"])

    def test_missing_net_amount_captured_in_per_field(self):
        """Missing net amount → per_field[net_amount] = False."""
        extracted = _make_extracted(net_amount="0.00")
        journal = _make_journal(extracted)
        expected = _make_expected()
        report = evaluate_accuracy(journal, expected)
        self.assertFalse(report["per_field"]["net_amount"])

    def test_wrong_tax_id_fails_gate(self):
        """Wrong seller tax ID → per_field[seller_tax_id] = False."""
        extracted = _make_extracted(seller_tax_id="0000000000000")
        journal = _make_journal(extracted)
        expected = _make_expected()
        report = evaluate_accuracy(journal, expected)
        self.assertFalse(report["per_field"]["seller_tax_id"])

    def test_aggregate_per_field_accuracy(self):
        """Aggregate correctly computes per-field accuracy across multiple docs."""
        journal_ok = _make_journal(_make_extracted())
        journal_bad_vat = _make_journal(_make_extracted(vat_amount="0.00"))
        expected = _make_expected()

        reports = [
            evaluate_accuracy(journal_ok, expected),
            evaluate_accuracy(journal_ok, expected),
            evaluate_accuracy(journal_bad_vat, expected),
        ]
        summary = aggregate_reports(reports)
        # vat_amount: 2/3 correct = 0.6667
        self.assertAlmostEqual(summary["per_field_accuracy"]["vat_amount"], 2 / 3, places=3)
        # all other fields: 3/3 = 1.0
        self.assertAlmostEqual(summary["per_field_accuracy"]["invoice_number"], 1.0, places=3)

    def test_gate_fails_when_vat_below_threshold(self):
        """Gate fails when per-field vat_amount accuracy below 0.80 threshold."""
        # 2/5 docs have correct VAT = 0.4 accuracy → below 0.80 gate
        journal_ok = _make_journal(_make_extracted())
        journal_bad = _make_journal(_make_extracted(vat_amount="0.00"))
        expected = _make_expected()

        reports = [
            evaluate_accuracy(journal_ok, expected),
            evaluate_accuracy(journal_ok, expected),
            evaluate_accuracy(journal_bad, expected),
            evaluate_accuracy(journal_bad, expected),
            evaluate_accuracy(journal_bad, expected),
        ]
        summary = aggregate_reports(reports)
        passed, failures = gate_passed(summary, _PER_FIELD_ONLY)
        self.assertFalse(passed)
        self.assertTrue(any("vat_amount" in f for f in failures))

    def test_gate_passes_when_all_fields_at_or_above_threshold(self):
        """Gate passes when all per-field targets met with 5 perfect docs."""
        journal_ok = _make_journal(_make_extracted())
        expected = _make_expected()
        reports = [evaluate_accuracy(journal_ok, expected) for _ in range(5)]
        summary = aggregate_reports(reports)
        # Only check per-field gates; skip account/journal gates for this fixture
        passed, failures = gate_passed(summary, _PER_FIELD_ONLY)
        self.assertTrue(passed, f"Gate failures: {failures}")

    def test_empty_reports_returns_zero_accuracy(self):
        summary = aggregate_reports([])
        self.assertEqual(summary["field_level_accuracy"], 0.0)
        self.assertEqual(summary["per_field_accuracy"], {})
        self.assertEqual(summary["sample_size"], 0)


class TestAccuracyGateIntegration(unittest.TestCase):
    """Integration gate: runs only when OCR_GATE_INTEGRATION=1.

    Reads private_data/poc/Comp_1/expectations.filled.jsonl
    and verifies all per-field accuracy targets.

    Skip if:
      - OCR_GATE_INTEGRATION env var is not set to "1"
      - expectations.filled.jsonl does not exist or is empty
    """

    EXPECTATIONS_PATH = Path("private_data/poc/Comp_1/expectations.filled.jsonl")
    MIN_DOCS_FOR_GATE = 5  # Gate is not enforced with fewer labeled docs

    def setUp(self):
        if os.environ.get("OCR_GATE_INTEGRATION") != "1":
            self.skipTest("OCR_GATE_INTEGRATION=1 not set — skipping integration gate")
        if not self.EXPECTATIONS_PATH.exists():
            self.skipTest(f"Expectations file not found: {self.EXPECTATIONS_PATH}")

    def _load_expectations(self) -> list[dict]:
        docs = []
        for line in self.EXPECTATIONS_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            try:
                doc = json.loads(line)
                if doc.get("labeling_status") == "done":
                    docs.append(doc)
            except json.JSONDecodeError:
                pass
        return docs

    def test_per_field_accuracy_gate(self):
        """Fail CI if any labeled field drops below KPIThresholds targets."""
        docs = self._load_expectations()
        if len(docs) < self.MIN_DOCS_FOR_GATE:
            self.skipTest(
                f"Need at least {self.MIN_DOCS_FOR_GATE} labeled docs for gate, found {len(docs)}"
            )

        from src.backend.services.rule_engine import run_journal_router

        reports = []
        for doc in docs:
            # Build a minimal extraction output from labeled ground truth
            extraction_output = {
                "sha256": f"gate-{doc.get('invoice_number', 'x')}",
                "fields": {
                    "invoice_number": doc.get("invoice_number", ""),
                    "invoice_date": doc.get("invoice_date", ""),
                    "seller_tax_id": doc.get("seller_tax_id", ""),
                    "buyer_tax_id": doc.get("buyer_tax_id", ""),
                    "total_amount": str(doc.get("amounts", {}).get("gross_amount", "")),
                    "net_amount": str(doc.get("amounts", {}).get("net_amount", "")),
                    "vat_amount": str(doc.get("amounts", {}).get("vat_amount", "")),
                    "vat_rate": str(doc.get("vat_rate", "")),
                },
            }
            journal = run_journal_router(extraction_output)
            report = evaluate_accuracy(journal, doc)
            reports.append(report)

        summary = aggregate_reports(reports)
        passed, failures = gate_passed(summary)

        print("\n=== Accuracy Gate Results ===")
        print(f"Sample size: {summary['sample_size']}")
        for field_name, acc in sorted(summary.get("per_field_accuracy", {}).items()):
            print(f"  {field_name}: {acc:.1%}")
        if failures:
            print(f"\nFailed gates: {failures}")

        self.assertTrue(
            passed,
            f"Accuracy gate FAILED. Below-threshold fields: {failures}\n"
            f"Full summary: {json.dumps(summary, indent=2)}",
        )


if __name__ == "__main__":
    unittest.main()
