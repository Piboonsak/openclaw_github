# Epic 0 — UX Contract & Workflow Freeze

**Goal**: Lock the Phase II user workflow before deep DB design — especially batch, review, export, template, and mobile/navigation behavior.

## Documentation

- **[EPIC-0-TASKS-DETAIL.md](EPIC-0-TASKS-DETAIL.md)** — full design for all tasks with ACs, deliverables, and governance fields
- **[UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md)** — screen-by-screen action inventory with DB impact (TASK-001)
- **[WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md)** — frozen batch + document state machines (TASK-002)
- **[DB-IMPACT-CONTRACT.md](DB-IMPACT-CONTRACT.md)** — entity decision matrix + proposed schema deltas (TASK-003)
- **[API-ROUTE-CONTRACT.md](API-ROUTE-CONTRACT.md)** — MVP route + payload contract (TASK-005)
- **[EPIC-8-HANDOFF-CHECKLIST.md](EPIC-8-HANDOFF-CHECKLIST.md)** — gate checklist before DB implementation (TASK-006)

## At a glance

| Aspect | Details |
|--------|---------|
| Lead | Product / UX + Backend Dev |
| Duration | 2-4 days (W0 / before W1 DB integration) |
| Status | **Completed** — TASK-001~006 complete |
| Critical path | **Yes** — prevents DB rework in Epic 8, 10, 12 |
| Week | W0 / W1 Day 0 |

## Task overview

| Task | Title | Complexity | Status | Pain points closed |
|------|-------|-----------|--------|-------------------|
| TASK-001 | PoC UX click audit + interaction inventory | S | **Done** | PP-2, PP-3, PP-5 |
| TASK-002 | MVP workflow state machine freeze | M | **Done** | PP-2, PP-3, PP-10 |
| TASK-003 | DB impact contract for workflow entities | M | **Done** | PP-2, PP-3, PP-5, PP-11 |
| TASK-004 | Prototype interaction patch scope | M | **Done** | PP-3, PP-5, PP-8 |
| TASK-005 | API / route contract for Phase II screens | M | **Done** | PP-2, PP-3, PP-4 |
| TASK-006 | Epic 8 handoff checklist + sign-off | S | **Done** | PP-5, PP-8, PP-16 |

## Dependencies

- **Upstream**: Current Phase II prototype, `MENU-TREE-IA.html`, existing DB schema in `src/backend/db/models.py`
- **Downstream**: Epic 8 (DB integration), Epic 10 (Template Engine), Epic 12 (Admin UI), Epic 13 (smoke tests)

## Execution order

```text
W0 Day 1 AM:  TASK-001 — PoC UX click audit + interaction inventory
W0 Day 1 PM:  TASK-002 — Workflow state machine freeze
W0 Day 2 AM:  TASK-003 — DB impact contract
W0 Day 2 PM:  TASK-004 — Prototype interaction patch scope
W0 Day 3:     TASK-005 — API / route contract
W0 Day 3-4:   TASK-006 — Epic 8 handoff checklist + sign-off
```

## Definition of Done

1. Every visible Phase II prototype action is classified as `MVP`, `mock-only`, `disable`, or `Phase II/2`.
2. Main workflow state machine is frozen: Upload -> Processing -> Review Scan -> Review Mapping -> Export.
3. Batch-level and document-level states are defined with allowed transitions and role guards.
4. DB impact list is approved before changing ORM models: Batch, review, correction, export, template versioning.
5. Prototype patch scope is limited to UX blockers only, especially mobile navigation and dead primary CTAs.
6. API / route contract lists payloads needed by Epic 8, Epic 10, and Epic 12.
7. Epic 8 handoff is renumbered and annotated as `TASK-801A` (schema) and `TASK-801B` (pipeline).

## Discussion Prompts

1. **Epic naming**: Use `Epic 0` as the pre-foundation gate, not `Epic 8-0`, because it gates multiple downstream epics.
2. **Mobile scope**: Is Phase II/1 desktop-first only, or must tablet/mobile navigation work for real users?
3. **Dead buttons**: Should non-MVP actions be disabled/hidden in prototype, or left visible with labels as future scope?
4. **Batch semantics**: Is a batch always one upload session, or can users add documents to an existing batch?
5. **Review ownership**: Do we need per-user assignment and locking during review, or is first-pass MVP shared queue enough?
6. **Audit granularity**: Should every field edit be auditable, or only final approve/confirm/export actions?

---

*Created: 2026-06-20*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
