from __future__ import annotations

from src.backend.evaluation.accuracy_evaluator import (
    KPIThresholds,
    aggregate_reports,
    evaluate_accuracy,
    gate_passed,
)


def test_evaluate_accuracy_and_gate_passed():
    journal_output = {
        "postings": [
            {"account_code": "5040", "credit": 0.0},
            {"account_code": "1154", "credit": 0.0},
            {"account_code": "2195", "credit": 10400.0},
        ],
        "status": "READY",
        "is_balanced": True,
    }
    expected_doc = {
        "invoice_number": "RRL202410-001",
        "invoice_date": "2024-10-15",
        "amounts": {"gross_amount": 10400.0},
        "expected_journal": {
            "postings": [
                {"account_code": "5040"},
                {"account_code": "1154"},
                {"account_code": "2195"},
            ]
        },
    }

    report = evaluate_accuracy(journal_output, expected_doc)
    summary = aggregate_reports([report])

    ok, failures = gate_passed(summary, KPIThresholds())
    assert ok is True
    assert failures == []


def test_gate_fails_when_summary_below_threshold():
    summary = {
        "field_level_accuracy": 0.5,
        "account_level_accuracy": 0.5,
        "journal_level_accuracy": 0.5,
        "rule_effectiveness": 0.5,
    }
    ok, failures = gate_passed(summary, KPIThresholds())
    assert ok is False
    assert len(failures) >= 1
