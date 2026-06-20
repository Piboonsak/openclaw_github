# Epic 14 — Line Item + Inventory Full

**Goal**: Full line item extraction (SKU, Qty, Unit Price, Line Amount) + inventory data preparation — ขยาย PoC (TASK-906) เป็น production-grade

## Documentation

- **[EPIC-14-TASKS-DETAIL.md](EPIC-14-TASKS-DETAIL.md)** — full design for all tasks with ACs, schemas, governance fields

## At a glance

| Aspect | Details |
|--------|---------|
| Lead | Backend Dev |
| Duration | 2-3 weeks |
| Status | Design |
| Critical path | **No** — Post-go-live CR, scope depends on TASK-906 PoC results |
| Week | Post-Go-Live |
| Phase | II/2 |

## Task overview

| Task | Title | Complexity | Status | Pain points closed |
|------|-------|-----------|--------|-------------------|
| TASK-1401 | Line item extraction (full) | L | New | PP-2, PP-3, PP-5, PP-11 |
| TASK-1402 | Line item DB schema + API endpoints | M | New | PP-2, PP-3, PP-4, PP-5 |
| TASK-1403 | Inventory data structure | M | New | PP-2, PP-3, PP-5 |
| TASK-1404 | Inventory export template | M | New | PP-2, PP-3, PP-5, PP-11 |

## Dependencies

- **Upstream**: Epic 9 TASK-906 (Line Item PoC — Go/No-Go determines scope), Epic 8 (DB + Celery), Epic 10 (Template Engine for export)
- **Downstream**: None (leaf epic)

## Execution order

```text
Post-Go-Live Week 1:  TASK-1401 — Line item extraction full (largest, LLM prompt engineering)
Post-Go-Live Week 1:  TASK-1402 — Line item DB schema + API (parallel with 1401)
Post-Go-Live Week 2:  TASK-1403 — Inventory data structure (needs 1402 for line item data)
Post-Go-Live Week 2-3: TASK-1404 — Inventory export template (needs 1403 + Template Engine)
```

## Definition of Done

1. Line items extracted with >=80% per-field accuracy for supported document formats
2. Line total reconciliation >=70% (sum of line amounts matches invoice total)
3. Multi-page invoices handled correctly
4. Line items stored in PostgreSQL with proper schema, API endpoints for CRUD + review
5. Inventory data aggregated across documents by product (qty, supplier, amount)
6. Inventory export generates correct format via template engine
7. All ACs pass with pytest tests

## Discussion Prompts

1. **TASK-906 Go/No-Go**: PoC results จะกำหนด scope ของ Epic นี้ — ถ้า Conditional (3/6 metrics pass) จะลด scope อย่างไร? เฉพาะ digital PDF only?
2. **LLM model selection**: PoC จะเปรียบเทียบ Gemini Flash vs Pro vs Claude Sonnet — cost vs accuracy tradeoff สำหรับ 10K-20K docs/month จะเลือกอย่างไร?
3. **Inventory aggregation logic**: aggregate by product name (fuzzy match?) หรือต้องมี product master data ก่อน? ลูกค้ามี SKU code standardized หรือยัง?
4. **Multi-page handling**: ถ้า invoice ข้ามหน้า — ส่ง full PDF ให้ LLM หรือ page-by-page แล้ว merge? Cost vs accuracy tradeoff?

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
