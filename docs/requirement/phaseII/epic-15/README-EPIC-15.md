# Epic 15 — Sales Tax Report

**Goal**: รายงานภาษีขาย (Sales Tax Report) — template-based, same pattern as Purchase Tax Report (Epic 11)

## Documentation

- **[EPIC-15-TASKS-DETAIL.md](EPIC-15-TASKS-DETAIL.md)** — full design for all tasks with ACs, schemas, governance fields

## At a glance

| Aspect | Details |
|--------|---------|
| Lead | Full-stack Dev |
| Duration | 1 week |
| Status | Design |
| Critical path | **No** — Post-go-live CR, follows same pattern as Purchase Tax |
| Week | Post-Go-Live |
| Phase | II/2 |

## Task overview

| Task | Title | Complexity | Status | Pain points closed |
|------|-------|-----------|--------|-------------------|
| TASK-1501 | Sales Tax Report template definition | M | New | PP-2, PP-3, PP-5, PP-11 |
| TASK-1502 | Sales Tax Report rendering + master template seed | M | New | PP-2, PP-3, PP-5, PP-11 |

## Dependencies

- **Upstream**: Epic 10 (Template Engine — rendering infrastructure), Epic 11 (Purchase Tax Report — pattern reference), Epic 8 (DB + Alembic)
- **Downstream**: None (leaf epic)

## Execution order

```text
Post-Go-Live Day 1-2:  TASK-1501 — Sales Tax Report template definition (columns, fields, transforms)
Post-Go-Live Day 3-5:  TASK-1502 — Sales Tax Report rendering + master template seed (implement + migrate)
```

## Definition of Done

1. Sales tax report columns defined (matching Revenue Department format for ภาษีขาย)
2. Template renders correctly with Thai formatting (dates, currency, tax ID)
3. Master template seeded via Alembic migration
4. Export produces CSV/Excel output consistent with purchase tax report styling
5. All ACs pass with pytest tests

## Discussion Prompts

1. **Sales vs Purchase tax differences**: คอลัมน์ภาษีขายต่างจากภาษีซื้ออย่างไร? ต้องขอ sample format จากลูกค้าก่อน implement หรือใช้แบบ standard สรรพากร?
2. **Document types**: ภาษีขายใช้เอกสารอะไรเป็น input? ใบกำกับภาษีที่ออกเอง (sales invoice) หรือต้อง OCR เอกสารขาเข้าด้วย?
3. **Template reuse**: Purchase Tax template engine (TASK-1001) สามารถ reuse สำหรับ Sales Tax ได้ 100% หรือต้อง extend?

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
