# Epic 11 — Purchase Tax Report Integration

**Goal**: ย้าย Purchase Tax Report จาก hardcoded format เป็น template-based (ใช้ template engine จาก Epic 10)

## Documentation

- **[EPIC-11-TASKS-DETAIL.md](EPIC-11-TASKS-DETAIL.md)** — full design for all tasks with ACs, schemas, governance fields

## At a glance

| Aspect | Details |
|--------|---------|
| Lead | Backend Dev |
| Duration | 0.5 weeks (W3) |
| Status | Done for W3 backend scope |
| Critical path | No — depends on Epic 10 TASK-1001 (template engine), can run parallel in W3 |
| Week | W3 |

## Task overview

| Task | Title | Complexity | Status | Pain points closed |
|------|-------|-----------|--------|-------------------|
| TASK-1101 | Purchase Tax Report -> template-based | M | Done (`a693d06`) | PP-2, PP-3, PP-5, PP-11 |
| TASK-1104 | Preview + balance validation | S | Done (`fd7e11c`) | PP-2, PP-3, PP-5, PP-9 |

## Dependencies

- **Upstream**: Epic 10 TASK-1001 (template engine backend must exist), Epic 8 `TASK-801A` / `TASK-801B` (schema + DB integration for document data)
- **Downstream**: Epic 12 (Export screen uses unified export endpoint)

## Execution order

```text
W3 Day 3-4:  TASK-1101 — Purchase Tax Report -> template-based (done: a693d06)
W3 Day 5:    TASK-1104 — Preview + balance validation (done: fd7e11c)
```

## Definition of Done

1. Purchase Tax Report generates identical output via template engine as the current hardcoded implementation
2. Old endpoint `/api/export-purchase-tax-report` redirects to new unified endpoint with backward compatibility
3. Thai formatting and VAT bucket splitting logic preserved in template-based rendering
4. Preview endpoint returns first 5-10 rows as JSON table data
5. Balance validation detects unbalanced vouchers (Sum(Dr) != Sum(Cr)) and blocks export with clear error message
6. All ACs pass with pytest tests

## Discussion Prompts

1. **Backward compatibility period**: Old endpoint `/api/export-purchase-tax-report` redirects to new -- how long do we keep the redirect? W5 cutover or keep through go-live?
2. **VAT bucket splitting**: The current 240-line function has complex VAT bucket splitting logic -- should this be a template-level feature (configurable) or hardcoded in the purchase tax template's rendering logic?
3. **Balance validation scope**: Should balance validation apply to all export types (GL + Tax) or only GL export? Tax reports may not have Dr/Cr balancing.

---

*Created: 2026-06-15*
*Updated: 2026-06-29 - TASK-1101 and TASK-1104 completed in W3 backend lane*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
