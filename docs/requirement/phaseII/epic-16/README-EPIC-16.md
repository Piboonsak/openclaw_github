# Epic 16 — Full Dashboard + Monitoring

**Goal**: Full KPI dashboard, Sentry error tracking, audit log viewer, budget alert notifications — production observability + operational tools

## Documentation

- **[EPIC-16-TASKS-DETAIL.md](EPIC-16-TASKS-DETAIL.md)** — full design for all tasks with ACs, schemas, governance fields

## At a glance

| Aspect | Details |
|--------|---------|
| Lead | Full-stack Dev |
| Duration | 1.5 weeks |
| Status | Design |
| Critical path | **No** — Post-go-live enhancement, MVP Dashboard (TASK-1202) covers go-live needs |
| Week | Post-Go-Live |
| Phase | II/2 |

## Task overview

| Task | Title | Complexity | Status | Pain points closed |
|------|-------|-----------|--------|-------------------|
| TASK-1601 | Full KPI Dashboard | M | New | PP-2, PP-3, PP-5, PP-17 |
| TASK-1602 | Sentry integration | M | New | PP-2, PP-3, PP-5, PP-16, PP-18 |
| TASK-1603 | Audit log viewer | M | New | PP-2, PP-3, PP-5, PP-17 |
| TASK-1604 | Budget alert notifications | S | New | PP-2, PP-3, PP-5, PP-16 |

## Dependencies

- **Upstream**: Epic 8 (DB + Celery — for background workers), Epic 12 (TASK-1202 MVP Dashboard — extend, not replace), Epic 12 (TASK-1204 RBAC — admin-only access)
- **Downstream**: None (leaf epic)

## Execution order

```text
Post-Go-Live Day 1-3:  TASK-1602 — Sentry integration (highest ROI — error visibility immediately)
Post-Go-Live Day 2-4:  TASK-1601 — Full KPI Dashboard (extend MVP Dashboard)
Post-Go-Live Day 4-5:  TASK-1603 — Audit log viewer (search + filter + export)
Post-Go-Live Day 5-6:  TASK-1604 — Budget alert notifications (LINE/email at 80% threshold)
```

## Definition of Done

1. KPI dashboard shows accuracy trends, throughput analytics, cost analytics with real data
2. Sentry captures errors with structured context, performance traces visible, alert rules fire on critical errors
3. Audit log viewer supports search + filter (by user, action, entity, date range), CSV export works
4. Budget alerts fire at 80% monthly LLM spend threshold, cooldown prevents spam (max 1/day/company)
5. All dashboards/viewers are admin-only (RBAC-gated)
6. All ACs pass with pytest tests

## Discussion Prompts

1. **Sentry pricing**: Sentry free tier (5K errors/month, 10K performance transactions) เพียงพอสำหรับ MVP ไหม? หรือต้อง Team plan?
2. **LLM budget tracking**: ปัจจุบัน track cost อย่างไร? ต้อง log ทุก LLM call (model, tokens, cost) ลง DB ก่อนถึงจะ build budget alerts ได้ — มี table/logging รองรับหรือยัง?
3. **Dashboard tech**: MVP Dashboard (TASK-1202) ใช้ vanilla JS + Chart.js หรือ React? Full KPI Dashboard ควรใช้เทคโนโลยีเดียวกัน
4. **Audit log retention**: เก็บ audit logs นานเท่าไร? ลูกค้าบัญชีอาจต้องเก็บ 5 ปีตามกฎหมาย — ต้อง archive strategy ไหม?
5. **Alert channels**: LINE notification เป็น primary — ต้อง email ด้วยไหม? Email infra ยังไม่มี setup ใน Epic 13

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
