# TASK-906 Feasibility Report

> Status: Interim W3 feasibility readout  
> Updated: 2026-06-28  
> Decision level: Conditional, not final Go/No-Go  
> Scope note: This report uses available PoC artifacts and review outputs. It does not claim final locked accuracy because human-verified ground truth and timed review measurements are still pending.

## Executive decision

TASK-906 is feasible enough to continue into a controlled Epic 14 design, but not enough to approve full production line-item automation without review gates.

Recommended decision: **Conditional Go**

Reason:

- Vision extraction produced usable line-item rows across Comp_3 samples and multiple non-overlapping batches.
- The cheapest successful primary candidate, `google/gemini-2.5-flash-lite`, processed the 10-doc backup-matrix sample at very low cost and acceptable speed.
- Same-company product master / alias history materially improves row confidence and reduces review burden.
- Reconciliation and final accuracy remain inconclusive because the available Comp_3 matrix lacks locked expected net/gross/line-item ground truth.

## Evidence used

| Artifact | What it proves | Limitation |
| --- | --- | --- |
| `TASK-906-VISION-MODEL-BACKUP-MATRIX.md` | Model backup candidates were compared on the same 10-PDF Comp_3 sample | Smoke test only, not full accuracy evaluation |
| `TASK-906-MODEL-MATRIX-GEMINI25-FLASH-LITE.html` | Gemini 2.5 Flash Lite extracted rows from 10 docs with low total cost and ~5 sec/doc | No expected net values, so reconciliation stayed review-only |
| `TASK-906-LINE-ITEM-FOLDER-REVIEW-V3-COMP3-BATCH2-MASTER.html` | 50-doc Comp_3 master-simulated run produced 200 rows with confidence bands and product matching | Master/alias simulation is not yet production DB-backed |
| `EPIC-9-TASKS-DETAIL.md` evidence block | Captures lessons from Comp_1/Comp_3 scans and carry-forward design choices | Still needs final locked evaluation loop |

## Model feasibility

Backup matrix sample: Comp_3, 10 PDFs, seed 910, max 4 pages, max file 25 MB.

| Rank | Model | Result | Rows | Green / Amber / Red | Cost THB | Avg sec/doc | Readout |
| ---: | --- | --- | ---: | --- | ---: | ---: | --- |
| 1 | `google/gemini-2.5-flash-lite` | PASS | 28 | 4 / 24 / 0 | 0.1525 | 5.10 | Primary candidate |
| 2 | `openai/gpt-4.1-nano` | PASS | 28 | 4 / 24 / 0 | 0.2503 | 4.66 | First non-Gemini backup |
| 3 | `google/gemini-3.1-flash-lite` | PASS | 28 | 4 / 24 / 0 | 1.8818 | 3.32 | Same-family fallback, watch cost |
| 4 | `openai/gpt-4o-mini` | PASS | 28 | 4 / 24 / 0 | 13.4590 | 6.48 | Works, too expensive for normal fallback |
| 5-7 | Qwen / Mistral candidates | FAIL | 0 | 0 / 0 / 0 | 0.0000 | < 1.00 | Provider/image pipeline unavailable in this smoke path |

Recommendation:

- Primary: `google/gemini-2.5-flash-lite`
- Backup 1: `openai/gpt-4.1-nano`
- Backup 2: `google/gemini-3.1-flash-lite`
- Do not use `gpt-4o-mini` as default fallback unless quality need outweighs cost.
- Re-test Qwen/Mistral only after a separate image-render adapter exists.

## Product/master matching feasibility

The strongest W3 finding is that line-item extraction alone is not enough. The useful product workflow is extraction plus same-company matching.

In `TASK-906-LINE-ITEM-FOLDER-REVIEW-V3-COMP3-BATCH2-MASTER.html`:

- Documents: 50
- Rows: 200
- Green rows: 156
- Amber rows: 42
- Red rows: 2
- Stock candidates: 179
- Total cost: THB 0.8652
- Avg seconds/doc: 6.40
- Line type distribution: `stock_item: 137`, `part_or_material: 42`, `labor: 19`, `unknown: 2`

Interpretation:

- Green rows increase when product alias/master evidence exists.
- Amber rows are still expected for new or fuzzy product descriptions.
- Red rows mostly represent non-standard business events such as deposit/receipt-style lines and should route to review, not fail the document.
- Same-company master must be used. Cross-company product matching remains risky because each company has a different item domain.

## Go/No-Go metric status

| Metric | Go threshold | Interim status | Reason |
| --- | --- | --- | --- |
| Per-field accuracy | >= 80% for product, qty, unit price, line amount, unit | Pending | No locked human-verified line-item ground truth yet |
| Document success | >= 70% docs need no major correction | Pending | Review actions not timed/locked |
| Line total reconciliation | >= 75% reconcile to net/expected amount | Inconclusive | Expected net/gross missing in Comp_3 matrix |
| Cost per document | <= THB 1.50/doc | Pass for tested primary | Gemini 2.5 Flash Lite sample cost is far below threshold |
| Processing time | <= 30 sec/doc | Pass for tested primary | 5.10-6.40 sec/doc in current samples |
| Manual correction time | <= 60 sec/doc | Pending | Timed review measurements not filled |

Interim score: 2 pass, 3 pending, 1 inconclusive. This is why the report recommends **Conditional Go**, not final Go.

## Recommended Epic 14 shape

Proceed only as a review-first workflow:

1. Run line-item extraction as an optional sub-stage after header OCR/extraction.
2. Never block header review/export if line-item extraction fails.
3. Store extracted line rows separately from accounting header data.
4. Match against same-company product master and confirmed aliases.
5. Show green/amber/red confidence per row in review UI.
6. Let users confirm existing stock item, create product candidate, mark non-stock/labor/service, or reject row.
7. Persist human confirmations as aliases/history first; dedup/merge product master in a background workflow.
8. Keep provider routing configurable. Do not hardcode the business workflow to a single model.

## What remains before final Go/No-Go

1. Lock a 20-doc core set with human-verified line items.
2. Run the same locked set across the selected primary and backup models.
3. Fill timed review measurements for the marked review samples.
4. Compute all 6 metrics numerically.
5. Decide supported formats if the result remains Conditional.
6. Re-render this report as a final decision with Go / Conditional / No-Go and downstream Epic 14 scope.

## Current decision for planning

Use TASK-906 as a **Conditional Go planning input** for Phase II/2:

- Include product master / alias history in the design.
- Do not sell or commit to full autonomous stock import yet.
- Keep line items behind human review and feature flag / company-level `enable_stock`.
- Pricing and timeline for Epic 14 should remain conditional until locked accuracy and timed review results are available.
