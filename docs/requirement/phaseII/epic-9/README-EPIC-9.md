# Epic 9 — Extraction Accuracy + Line Item PoC

**Goal**: ยกระดับ accuracy จาก PoC feedback + พิสูจน์ feasibility ของ line item extraction

## Documentation

- **[EPIC-9-TASKS-DETAIL.md](EPIC-9-TASKS-DETAIL.md)** — full design for all tasks with ACs, schemas, governance fields

## At a glance

| Aspect | Details |
|--------|---------|
| Lead | ML / Backend Dev |
| Duration | 1.5 weeks (W1-W2) |
| Status | Partial (TASK-905 Done) |
| Critical path | No (parallel with Epic 8), but TASK-906 informs Phase II/2 scope + pricing |
| Week | W1-W2 |

## Task overview

| Task | Title | Complexity | Status | Pain points closed |
|------|-------|-----------|--------|-------------------|
| TASK-906 | Line Item Extraction PoC — Black Box Clear | M | New | PP-2, PP-3, PP-5, PP-11 |
| TASK-901 | VAT disambiguation — arithmetic-first | L | New | PP-2, PP-3, PP-5, PP-10, PP-11 |
| TASK-902 | WHT detection + backfill solver | M | New | PP-2, PP-3, PP-5, PP-11 |
| TASK-903 | OCR gridline removal | M | New | PP-2, PP-3, PP-5, PP-8 |
| TASK-905 | Vendor branch extraction | S | **Done** | -- |

## Dependencies

- **Upstream**: None (parallel with Epic 8, uses existing PoC pipeline)
- **Downstream**: Epic 14 (Line Item Full) — TASK-906 go/no-go determines Epic 14 scope + pricing

## Execution order

```text
W1 Day 1-3:  TASK-906 — Line Item PoC (FIRST PRIORITY, 20-30 docs, 3 models)
W1 Day 3-5:  TASK-901 — VAT disambiguation (start parallel, largest accuracy task)
W2 Day 1-2:  TASK-901 — VAT disambiguation (continue, test corpus validation)
W2 Day 2-3:  TASK-902 — WHT detection + backfill solver
W2 Day 4-5:  TASK-903 — OCR gridline removal (OpenCV preprocessing)
TASK-905:    Already done — no work needed
```

## Definition of Done

1. TASK-906 feasibility report (3-5 pages) delivered with go/no-go recommendation, tested on 20+ diverse documents across 3 LLM models
2. VAT disambiguation accuracy measurably improved on test corpus — 4 combinations tested per document, best-fit selected by arithmetic match
3. WHT rates (1%, 2%, 3%, 5%, 10%) detected correctly, backfill works when partial data, `has_wht` flag and `wht_form` (PND3/PND53) accurate
4. OCR gridline removal improves accuracy measurably, feature flag works, digital PDF text layer still used when available
5. All accuracy improvements have before/after metrics on the same test corpus
6. All ACs pass with pytest tests

## Discussion Prompts

1. **TASK-906 document sourcing**: ต้องการ 20-30 documents จากลูกค้าก่อน W1. ถ้าได้ไม่ครบตาม diversity checklist (8 categories), ลด scope เป็น 15 docs ครอบคลุมกี่ categories ถึงจะ statistically meaningful?
2. **VAT arithmetic tolerance**: TASK-901 picks best-fit from 4 combinations. What rounding tolerance is acceptable? (Thai tax rounding: สตางค์ปัดทิ้ง vs ปัดขึ้น)
3. **WHT form detection**: TASK-902 adds PND3/PND53 detection. Does the client need PND1/PND2 as well, or just PND3 (individual) and PND53 (corporate)?
4. **OCR gridline removal risk**: TASK-903 uses OpenCV morphological operations. Risk of accidentally removing text that looks like lines (e.g., underscores, minus signs). Should we keep original OCR result as fallback and compare?
5. **Line Item PoC cost threshold**: TASK-906 uses <=1.50 THB/doc as go threshold. At 20K docs/month = 30K THB/month. Is this acceptable to the client or should we lower the threshold?
6. **Test corpus versioning**: Accuracy improvements need before/after comparison. Should we formalize a test corpus (golden set) with ground-truth labels that persists across sprints?

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
