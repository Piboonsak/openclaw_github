"""Generate TASK-510 accuracy report JSON from expectations and routed journals."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.backend.evaluation.accuracy_evaluator import (
    aggregate_reports,
    evaluate_accuracy,
    gate_passed,
    write_accuracy_report,
)
from src.backend.services.rule_engine import run_journal_router


def _build_extraction_from_expected(expected_doc: dict) -> dict:
    gross = expected_doc.get("amounts", {}).get("gross_amount", 0)
    return {
        "sha256": f"eval-{expected_doc.get('invoice_number', 'unknown')}",
        "fields": {
            "invoice_number": expected_doc.get("invoice_number", ""),
            "invoice_date": expected_doc.get("invoice_date", ""),
            "vendor_name": expected_doc.get("supplier_name", ""),
            "total_amount": str(gross),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Epic 5 accuracy report")
    parser.add_argument(
        "--expectations",
        default="tests/expectations.json",
        help="Path to expectations JSON",
    )
    parser.add_argument(
        "--out",
        default="evaluation/metrics/accuracy_report.json",
        help="Path to output report",
    )
    args = parser.parse_args(argv)

    expectations_path = Path(args.expectations)
    if not expectations_path.exists():
        print(f"ERROR: expectations file not found: {expectations_path}", file=sys.stderr)
        return 1

    payload = json.loads(expectations_path.read_text(encoding="utf-8"))
    documents = payload.get("documents", {})
    if not documents:
        print("ERROR: no documents found in expectations payload", file=sys.stderr)
        return 1

    reports = []
    per_document = []
    for doc_name, expected_doc in documents.items():
        extraction_output = _build_extraction_from_expected(expected_doc)
        journal = run_journal_router(extraction_output)
        report = evaluate_accuracy(journal, expected_doc)
        reports.append(report)
        per_document.append(
            {
                "document": doc_name,
                "report": report,
            }
        )

    summary = aggregate_reports(reports)
    passed, failures = gate_passed(summary)

    output_payload = {
        "summary": summary,
        "gate_passed": passed,
        "failures": failures,
        "documents": per_document,
    }
    out = write_accuracy_report(args.out, output_payload)
    print(f"OK: wrote {out}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
