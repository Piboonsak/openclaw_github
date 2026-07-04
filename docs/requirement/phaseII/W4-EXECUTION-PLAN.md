# W4 Execution Plan

> Week: W4 (6 Jul 2026 - 12 Jul 2026)
> Purpose: convert W3 backend completion into real W4 web-facing workflow completion
> Scope focus: close carryover from W1-W3 that blocks usable export/configurator flow on the web

## 1. W4 Goal

Week 4 must end with the export/configurator path visible and usable on the real web surface, not only available as backend APIs or isolated demo files.

W4 is considered successful when we have:

1. Product-owner gate cleared on live SIT for the frozen Export + Configurator UX
2. `TASK-1003` Template Configurator UI connected to real APIs
3. `TASK-1006` Export page moved from old Step 6 hardcoded flow toward the frozen full-page flow
4. W1-W3 carryover items that still affect W4 execution are either closed or explicitly parked with evidence

This week is **not** about reopening backend foundation that already passed in W3 unless a real regression is found.

## 2. Source of Truth

Use these files in this order when there is any conflict:

1. `docs/requirement/phaseII/PHASE-II-TIMELINE.html`
2. `docs/requirement/phaseII/W3-EXECUTION-PLAN.md`
3. `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`
4. `docs/requirement/phaseII/W3-CODEX-UX-FRONTEND-PLAN.md`
5. `docs/requirement/phaseII/epic-10/EPIC-10-TASKS-DETAIL.md`
6. `docs/requirement/phaseII/epic-13/EPIC-13-TASKS-DETAIL.md`
7. `docs/requirement/phaseII/BACKLOG.md`

## 3. Repo Reality Snapshot at W4 Start

### Interface deployment map

Use this mapping before any deploy/debug/review work so the wrong HTML surface is not used as evidence or wired to the wrong backend path.

| File | Role | Expected route / environment use | W4 rule |
| --- | --- | --- | --- |
| `src/frontend/ux-ui-prototype.html` | Legacy interactive workflow demo | backend route `/workflow-demo`; internal/local reference only | Do not use as primary W4 acceptance surface |
| `docs/requirement/phaseII/PHASE-II-PROTOTYPE.html` | Requirement/reference prototype | local doc/reference only | Use for UX freeze baseline, not runtime deploy proof |
| `src/frontend/main-ux-ui.html` | Production-facing review UI | backend route `/phase2/prototype`; `/prototype` redirects here | This is the main W4 SIT/UAT review surface |
| `src/frontend/index.html` | Static entry/fallback copy | plain frontend/static preview contexts | Keep aligned with `main-ux-ui.html`, but do not treat it as route proof by itself |

Deployment and review rule by environment:

- Local UX/reference review: `PHASE-II-PROTOTYPE.html` and `ux-ui-prototype.html`
- Local runtime-style review: `main-ux-ui.html` and `index.html`
- SIT/UAT review with backend wiring: `/phase2/prototype` backed by `main-ux-ui.html`
- Legacy demo access for comparison only: `/workflow-demo` backed by `ux-ui-prototype.html`

### Confirmed green in code/repo now

- `TASK-1009` Schema Analyzer backend/API exists and targeted tests pass
- `TASK-1001` Template engine backend exists
- `TASK-1002` Template CRUD + preview contract exists
- `TASK-1101` Purchase Tax template-based flow exists
- `TASK-1104` export preview + balance validation endpoints exist
- `TASK-1207` vendor/customer import exists
- production-facing review routes now resolve from the frontend/runtime surface: `/phase2`, `/phase2/timeline`, `/phase2/prototype`
- repo route aliases now separate review vs legacy demo clearly:
  - `/` -> `/phase2/prototype`
  - `/prototype` -> `/phase2/prototype`
  - `/workflow-demo` -> legacy `ux-ui-prototype.html`
- live SIT edge responds with `401` on `/`, `/phase2`, `/prototype`, `/api/health`, and `/api/health/ready`, which confirms a reachable auth-protected review surface but not completed credentialed review
- master template seed baseline is verified in repo tests: `Express GL` and `Purchase Tax` are built by `scripts/seed_data.py` and `tests/db/test_seed_data.py` passes

### Confirmed gap between backend and web surface

- the old 6-step workflow still exists only as the internal legacy demo at `/workflow-demo`
- current export UI still calls old endpoints such as `/api/export-excel`
- real W3 endpoints are not yet wired into the main web export/configurator flow:
  - `POST /api/v1/templates/analyze`
  - `GET/POST/PUT/DELETE /api/v1/templates`
  - `POST /api/v1/templates/{id}/preview`
  - `POST /api/v1/export/preview`
  - `POST /api/v1/export/validate`
- `src/frontend/template-configurator-demo.html` and `src/frontend/ux-ui-prototype.html` are still demo/reference surfaces, not the main product flow; the production-facing page is `src/frontend/main-ux-ui.html`

### Carryover still active from W1-W3

- `PO SIT review` + all 5 UX freeze approval checkboxes
- `TASK-1003` frontend implementation
- `TASK-1006` frontend integration
- `TASK-906` wording/status alignment to the actual repo state
- `TASK-1313` deploy-evidence lane still needs clean status framing for UAT progression, but it is not a direct blocker for W4 UI execution

## 4. W4 Scope Lock

### In scope for W4

- `PO SIT review` on live SIT against the frozen export/configurator UX
- complete all 5 approval checkboxes in `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`
- `TASK-1003` Template Configurator UI on the real web surface
- `TASK-1009` frontend integration inside Configurator Tab 1
- `TASK-1006` Export page integration on the real web surface
- bridge from existing workflow into the new export/configurator pages
- seed verification/hardening for the master templates needed by W4 flow
- `TASK-906` status wording alignment
- `TASK-1313` status/evidence alignment if it still affects W4/UAT readiness messaging

### Explicitly not required to close W4

- broad redesign of non-export workflow screens
- reopening `TASK-1001`, `TASK-1002`, `TASK-1009`, `TASK-1101`, `TASK-1104`, or `TASK-1207` without a verified regression
- Phase II/2 work such as Epic 14/15/16 feature delivery
- unrelated dashboard/admin polishing outside what W4 export/configurator flow needs

## 5. W1-W3 Carryover to Finish in W4

### Must finish now

- `PO SIT review`
- 5 UX freeze approval checkboxes
- `TASK-1003`
- `TASK-1006`
- `TASK-906` wording alignment to actual W3 completion state

### Finish if it blocks UAT progression or planning clarity

- `TASK-1313` deploy-evidence wording/status cleanup
- master template seed verification for the exact W4 flow

### Do not restart as new feature work

- `TASK-901` VAT disambiguation
- `TASK-902` WHT detection + backfill

These already have live code paths in repo. W4 should only verify regression risk where export/configurator flow depends on them.

## 6. Critical Path

The practical W4 critical path is:

`live SIT review` -> `5 UX freeze approvals` -> `TASK-1003` -> `TASK-1006` -> `focused E2E verification` -> `W4 status/doc alignment`

If the approval gate slips, the rest of W4 slips with it.

## 7. Working Assumptions

1. W3 backend completion remains valid unless a focused regression test fails.
2. The lowest-risk frontend path is to introduce a new full-page export/configurator surface, then link it from the current workflow.
3. Existing demo/prototype files are references only; W4 success is measured on the production-facing review path (`/phase2/prototype`) and the main web flow, not on isolated mock pages.
4. Minimum master template baseline is already partially seeded (`Express GL` and `Purchase Tax`), but W4 must verify whether the real flow also needs the wider Express transaction template set.

## 8. Execution Order

### Day 1 - unblock the week

- run live SIT review against frozen Screen A / Screen B behavior
- complete or explicitly fail the 5 approval checkboxes
- if any checkbox fails, log the exact mismatch and patch the frozen spec before implementation continues

### Day 2-3 - `TASK-1003`

- build the real Template Configurator surface
- implement 3 persistent tabs:
  - Upload & Detect
  - Configure Columns
  - Test Output
- wire Tab 1 to `POST /api/v1/templates/analyze`
- wire template list/edit/create/delete/clone/preview actions to `TASK-1002` endpoints
- make the Configurator reachable from the main web flow

### Day 4 - `TASK-1006`

- replace old Step 6 assumptions with the frozen export page flow
- support `Quick Export` vs `Template Export`
- show inline full-width column adjustment, not modal behavior
- call real preview/validation/template endpoints
- keep per-run changes ephemeral by default, with explicit template save/update actions

### Day 5 - proof and alignment

- verify navigation from existing workflow into new export/configurator pages
- run smoke/E2E coverage for main paths
- confirm seed/template availability needed by W4 flow
- align `TASK-906`, W4 status wording, and any W3 follow-on doc references

## 9. W4 Work Board

| Priority | Task | Why it matters this week | Finish condition |
| --- | --- | --- | --- |
| P0 | `PO SIT review` | Unlocks all W4 frontend work | Live SIT review completed against frozen UX |
| P0 | `5 UX freeze approvals` | Real gate for `TASK-1003/1006` | All 5 checkboxes reviewed and committed, or exact rejects documented |
| P0 | `TASK-1003` Configurator UI | Main W4 deliverable | Real page exists on web flow and uses real template APIs |
| P0 | `TASK-1009` UI integration | Removes manual setup friction | Sample upload can analyze and prefill Configurator |
| P1 | `TASK-1006` Export page flow | Turns backend into usable output flow | Full-page export flow replaces old embedded Step 6 behavior |
| P1 | Focused E2E / smoke checks | Stops false-done UI claims | Main export/configurator paths verified locally |
| P1 | Master template seed verification | Avoids UI flow failing on missing templates | Needed masters exist in the runtime path used by W4 |
| P1 | `TASK-906` wording alignment | Keeps reporting truthful | Report/timeline wording matches repo reality |
| P2 | `TASK-1313` status cleanup | Keeps UAT/deploy reporting clear | Marked clearly as done, in progress, or non-blocking with evidence |

## 10. Blocker Rules

If a blocker lasts more than half a day, record it explicitly and reroute the week.

Use these rules:

1. SIT review not available -> stop UI implementation start and escalate immediately
2. Any freeze checkbox fails -> patch the frozen spec or narrow W4 scope before coding further
3. `TASK-1003` slips -> do not pretend `TASK-1006` can finish cleanly
4. Missing master template/runtime data -> fix seed/runtime path before blaming frontend
5. Regression found in W3 backend endpoints -> run focused backend fix only for the broken contract, not a broad rewrite

## 11. Definition of Done for W4

W4 is done when all items below are true:

1. `PO SIT review` is completed against live SIT
2. all 5 approval checkboxes in `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` are resolved
3. `TASK-1003` exists on the real web surface, not only in `template-configurator-demo.html`
4. Configurator Tab 1 can call `POST /api/v1/templates/analyze`
5. template CRUD/preview actions are wired to real APIs
6. `TASK-1006` moves export into the intended full-page flow with Quick vs Template modes
7. the old hardcoded Step 6 behavior is no longer the primary export path
8. focused smoke/E2E checks cover the main W4 paths
9. `TASK-906` and W4/W3 status wording reflect actual repo state

## 12. Practical Next Step After W4

If W4 closes successfully, the next follow-on order should be:

1. W5 hardening for clone/export polish and unified export endpoint completion if still partial
2. template seed expansion for the wider Express transaction set if runtime proof shows it is still incomplete
3. UAT-facing verification and documentation cleanup
