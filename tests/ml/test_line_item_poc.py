from __future__ import annotations

import json
from pathlib import Path

from scripts.line_item_poc import (
    FIELD_NAMES,
    aggregate_model_reports,
    build_ground_truth_template,
    choose_timed_review_docs,
    expected_line_total_for_doc,
    normalize_line_item_row,
    numeric_match,
    render_report,
    score_document,
    score_go_no_go,
    summarize_diversity,
)


def test_normalize_line_item_row_normalizes_text_unit_and_numbers():
    row = {
        "product_name": "  Premium  Cable  ",
        "qty": "2.000",
        "unit": "ชิ้น",
        "unit_price": "150.50",
        "line_amount": "301.00",
    }
    normalized = normalize_line_item_row(row)
    assert normalized["product_name"] == "premium cable"
    assert normalized["qty"] == 2.0
    assert normalized["unit"] == "piece"
    assert normalized["unit_price"] == 150.5
    assert normalized["line_amount"] == 301.0


def test_numeric_match_respects_tolerance():
    assert numeric_match(10.0, 10.0009, 0.001) is True
    assert numeric_match(10.0, 10.02, 0.01) is False


def test_score_document_flags_row_count_mismatch_and_reconciliation_failure():
    truth = [
        {
            "product_name": "Widget A",
            "qty": "1",
            "unit": "pcs",
            "unit_price": "100.00",
            "line_amount": "100.00",
        },
        {
            "product_name": "Widget B",
            "qty": "2",
            "unit": "pcs",
            "unit_price": "50.00",
            "line_amount": "100.00",
        },
    ]
    predicted = [
        {
            "product_name": "Widget A",
            "qty": "1",
            "unit": "piece",
            "unit_price": "100.00",
            "line_amount": "100.00",
        }
    ]
    report = score_document(truth, predicted, expected_total=200.0)
    assert report["row_count_match"] is False
    assert report["document_success"] is False
    assert report["reconciliation_pass"] is False


def test_score_document_scores_per_field_accuracy():
    truth = [
        {
            "product_name": "Widget A",
            "qty": "1",
            "unit": "pcs",
            "unit_price": "100.00",
            "line_amount": "100.00",
        }
    ]
    predicted = [
        {
            "product_name": "Widget A",
            "qty": "1.000",
            "unit": "ชิ้น",
            "unit_price": "100.00",
            "line_amount": "100.01",
        }
    ]
    report = score_document(truth, predicted, expected_total=100.0)
    assert report["row_count_match"] is True
    assert report["per_field_accuracy"]["product_name"] == 1.0
    assert report["per_field_accuracy"]["qty"] == 1.0
    assert report["per_field_accuracy"]["unit"] == 1.0
    assert report["per_field_accuracy"]["line_amount"] == 0.0
    assert report["document_success"] is False


def test_score_go_no_go_uses_all_six_metrics():
    summary = {
        "per_field_accuracy": {field: 0.85 for field in FIELD_NAMES},
        "document_success_rate": 0.60,
        "line_total_reconciliation_rate": 0.70,
        "cost_per_document_thb": 1.00,
        "processing_time_per_document_sec": 10.0,
        "manual_correction_time_min": 2.0,
    }
    decision = score_go_no_go(summary)
    assert decision["pass_count"] == 6
    assert decision["decision"] == "Go"


def test_summarize_diversity_counts_categories():
    docs = [
        {"diversity_tags": ["digital_pdf", "multi_page"]},
        {"diversity_tags": ["digital_pdf", "discount_or_wht"]},
    ]
    summary = summarize_diversity(docs)
    assert summary["category_count"] == 3
    assert summary["counts"]["digital_pdf"] == 2


def test_choose_timed_review_docs_prefers_uncovered_tags():
    docs = [
        {"doc_id": "a", "diversity_tags": ["digital_pdf"]},
        {"doc_id": "b", "diversity_tags": ["multi_page"]},
        {"doc_id": "c", "diversity_tags": ["discount_or_wht"]},
        {"doc_id": "d", "diversity_tags": ["gridline_table"]},
        {"doc_id": "e", "diversity_tags": ["text_only_layout"]},
        {"doc_id": "f", "diversity_tags": ["digital_pdf"]},
    ]
    selected = choose_timed_review_docs(docs, target=5)
    assert len(selected) == 5
    assert {doc["doc_id"] for doc in selected} >= {"a", "b", "c", "d", "e"}


def test_build_ground_truth_template_includes_model_timing_slots():
    manifest = {
        "documents": [
            {
                "doc_id": "comp1-0002",
                "selection_status": "core",
                "timed_review_eligible": True,
                "net_amount": "100.00",
                "total_amount": "100.00",
                "currency": "THB",
            }
        ]
    }
    template = build_ground_truth_template(manifest)
    doc = template["documents"][0]
    assert doc["label_status"] == "pending_bootstrap"
    assert doc["expected_line_total_amount"] == "100.00"
    assert doc["expected_gross_total_amount"] == "100.00"
    assert "google/gemini-2.5-flash" in doc["timed_review_measurements"]


def test_expected_line_total_prefers_net_amount_over_gross_total():
    doc = {
        "net_amount": "1400.00",
        "expected_total_amount": "1498.00",
        "total_amount": "1498.00",
    }
    assert expected_line_total_for_doc(doc) == 1400.0


def test_aggregate_model_reports_emits_all_six_metrics():
    documents = [
        {
            "doc_id": "comp1-0002",
            "elapsed_sec": 3.2,
            "cost_thb": 0.45,
            "manual_review_seconds": 90,
            "scoring": {
                "per_field_accuracy": {field: 1.0 for field in FIELD_NAMES},
                "document_success": True,
                "reconciliation_pass": True,
            },
        },
        {
            "doc_id": "comp1-0003",
            "elapsed_sec": 4.0,
            "cost_thb": 0.55,
            "manual_review_seconds": 120,
            "scoring": {
                "per_field_accuracy": {field: 0.8 for field in FIELD_NAMES},
                "document_success": False,
                "reconciliation_pass": True,
            },
        },
    ]
    summary = aggregate_model_reports(
        "google/gemini-2.5-flash",
        documents,
        timed_review_docs={"comp1-0002", "comp1-0003"},
    )
    assert summary["documents_tested"] == 2
    assert summary["timed_review_sample_size"] == 2
    assert "document_success_rate" in summary
    assert "cost_projection_thb" in summary


def test_render_report_outputs_model_table_and_decision():
    payload = {
        "generated_at": "2026-06-21T00:00:00+00:00",
        "manifest_summary": {
            "core_count": 20,
            "reserve_count": 5,
            "timed_review_count": 5,
            "diversity_coverage": {
                "counts": {"clear_scan": 8, "multi_page": 2},
            },
        },
        "per_model_summary": {
            "google/gemini-2.5-flash": {
                "model": "google/gemini-2.5-flash",
                "decision": "Go",
                "pass_count": 4,
                "document_success_rate": 0.7,
                "line_total_reconciliation_rate": 0.8,
                "cost_per_document_thb": 0.5,
                "processing_time_per_document_sec": 4.0,
                "manual_correction_time_min": 2.0,
                "cost_projection_thb": {
                    "10000_docs_month": 5000.0,
                    "20000_docs_month": 10000.0,
                },
            }
        },
        "recommendation": {
            "best_model": "google/gemini-2.5-flash",
            "decision": "Go",
            "rationale": "best overall",
        },
    }
    markdown = render_report(payload)
    assert "| Model | Decision | Pass |" in markdown
    assert "**Go**" in markdown
    assert "`google/gemini-2.5-flash`" in markdown
