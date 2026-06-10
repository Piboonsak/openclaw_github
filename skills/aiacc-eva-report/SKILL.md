---
name: aiacc-eva-report
description: "Generate AI Accounting evaluation reports from expectations.filled.jsonl with combined and per-company outputs."
scope: ai-accounting-copilot
version: 2026-06-10
---

# Skill: AIACC Eva Report

## Purpose
Generate evaluation reports for extracted accounting fields against answer keys in `private_data/poc/*/expectations.filled.jsonl`.

## When to Use This Skill
- When you need a normalized answer key JSON from expectations.
- When you need a full evaluation report across all companies.
- When you need a report for one company only.
- When you need HTML and JSON artifacts for auditable benchmark output.

## Supported Commands
- `/aiacc-eva-report -jsonanswer`
- `/aiacc-eva-report -full-report`
- `/aiacc-eva-report -comp-report <comp id>/<comp name>`

## Compared Fields
- `net_amount` (Net Amount)
- `total_amount` (Gross Amount)
- `vat_amount` (VAT 7%)
- `wht_amount` (WHT Amount)
- `buyer_tax_id`
- `seller_tax_id`
- `invoice_number`
- `invoice_date`

## Implementation Command
Use:
```powershell
python scripts/eva_report.py <option>
```

Examples:
```powershell
python scripts/eva_report.py -jsonanswer
python scripts/eva_report.py -full-report
python scripts/eva_report.py -comp-report 1/Comp_1
```

## Step-by-Step Workflows

### 1) Build Answer Key JSON
1. Run `python scripts/eva_report.py -jsonanswer`.
2. Collect output path from line `OUT_JSON|...`.
3. Verify `SUMMARY|companies=<n>|documents=<n>`.

### 2) Build Full Report (All Companies)
1. Ensure backend API is running on `http://127.0.0.1:8000`.
2. Run `python scripts/eva_report.py -full-report`.
3. Collect output paths from `OUT_HTML|...` and `OUT_JSON|...`.

### 3) Build Single Company Report
1. Ensure backend API is running on `http://127.0.0.1:8000`.
2. Run `python scripts/eva_report.py -comp-report <comp>`.
3. `<comp>` supports examples: `1`, `Comp_1`, `1/Comp_1`.

## Live Evaluation Requirement
For `-full-report` and `-comp-report`, backend API must be running at:
- `http://127.0.0.1:8000/api/process`

## Outputs
Written under:
- `tmp/benchmark/eva_report/`

Artifacts:
- JSON answer key (`-jsonanswer`)
- HTML + JSON evaluation report (`-full-report`, `-comp-report`)

## Guardrails
- Use only rows from `expectations.filled.jsonl` that are PDF and not excluded.
- Never mutate expectations source file.
- Keep report generation read-only except output artifacts in `tmp/benchmark/eva_report`.

## Output Checklist
- Answer-key JSON generated for `-jsonanswer`.
- HTML report generated for live modes.
- JSON summary report generated for live modes.
- Per-field accuracy includes all 8 required fields.
- Output location is under `tmp/benchmark/eva_report`.
