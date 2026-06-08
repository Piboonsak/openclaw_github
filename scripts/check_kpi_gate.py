"""Check TASK-510 KPI thresholds from evaluation/metrics/accuracy_report.json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from src.backend.evaluation.accuracy_evaluator import KPIThresholds, gate_passed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check KPI gate thresholds")
    parser.add_argument(
        "--report",
        default="evaluation/metrics/accuracy_report.json",
        help="Path to accuracy report JSON",
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"WARN: report not found at {report_path}, skip KPI gate check")
        return 0

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    summary = payload.get("summary", payload)

    passed, failures = gate_passed(summary, KPIThresholds())
    if passed:
        print("OK: KPI gate passed")
        return 0

    print(f"FAIL: KPI gate failed -> {', '.join(failures)}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
