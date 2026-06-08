# KPI Gates (TASK-510)

## Purpose

This document defines minimum quality thresholds for Epic 5 pipeline output before merge.

## Thresholds

- Field-level accuracy: >= 0.85
- Account-level accuracy: >= 0.80
- Journal-level accuracy: >= 0.75
- Rule effectiveness: >= 0.70 (advisory)

## Decision Rules

- PASS: All three hard thresholds (field/account/journal) are met.
- REVIEW: Any threshold falls below target but above 0.70.
- BLOCK: Any hard threshold falls below 0.70.

## CI Integration

- Workflow: `.github/workflows/agent_gate.yml`
- Script: `python scripts/check_kpi_gate.py --report evaluation/metrics/accuracy_report.json`
- Report source: `evaluation/metrics/accuracy_report.json`

## Notes

- Small sample bootstrap may fluctuate. Use trend over 3 runs for release decisions.
- This gate is strict for Epic 5 and Epic 6 (`require_accuracy_report: true`).
