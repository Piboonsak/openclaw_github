# W3 Execution Plan

> Week: W3 (29 Jun 2026 - 5 Jul 2026)
> Purpose: lock one execution plan for Week 3 before continuing implementation
> Scope focus: finish W3 critical path first, then continue follow-on work

## 1. W3 Goal

Week 3 must end with the Template export foundation usable enough to unblock the rest of Phase II.

W3 is considered successful when we have:

1. Template backend core working for the W3 path
2. Purchase Tax export moving off hardcoded flow onto template-based flow
3. W3 supporting foundation green enough to continue W4 without reopening core decisions
4. Deployment path no longer blocked by missing process or missing evidence

This week is **not** about finishing every export UI screen. W3 should close the backend and release path that everything else depends on.

## 2. Source of Truth

Use these files in this order when there is any conflict:

1. `docs/requirement/phaseII/PHASE-II-TIMELINE.html`
2. `docs/requirement/phaseII/PHASE-II-EPIC-ROADMAP.md`
3. `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`
4. `docs/requirement/phaseII/epic-10/README-EPIC-10.md`
5. `docs/requirement/phaseII/epic-10/EPIC-10-TASKS-DETAIL.md`
6. `docs/requirement/phaseII/epic-12/EPIC-12-TASKS-DETAIL.md`
7. `docs/requirement/phaseII/W3-CODEX-UX-FRONTEND-PLAN.md`

## 3. W3 Scope Lock

### In scope for W3

- `TASK-1009` Schema Analyzer backend/API/tests
- `TASK-1001` Template engine backend
- `TASK-1002` Minimal template CRUD/API contract needed by W3 flow
- `TASK-1101` Purchase Tax Report -> template-based
- `TASK-1104` Preview + balance validation if it is small enough after `TASK-1101`
- `TASK-906` Feasibility Report finalization for W3
- `TASK-1306` CI/CD implementation closeout
- `TASK-1313` Openclaw UAT deploy trigger and deploy evidence
- `TASK-1207` Vendor/Customer master import only as dependency support for template lookup

### Explicitly not required to close W3

- `TASK-1003` Full Template Configurator UI implementation
- `TASK-1006` Full Export page UX implementation
- `TASK-1013` Product Master import + matching
- `TASK-1208` LoveBot data CSV export
- Full W4/W5 polish, clone workflow, or broad admin UI work

## 4. Current Status Snapshot

### Green or mostly green now

- `TASK-1009` DONE - commit `b3b2757` - 54 tests
- `TASK-1001` DONE - commit `a350333` - 47 tests
- `TASK-1207` DONE - commit `868a1ee` - 3 tests
- `TASK-1002` DONE - commit `66c7419` - 17 tests
- `TASK-1101` DONE - commit `a693d06` - 22 tests
- `TASK-1104` DONE - commit `fd7e11c` - 18 tests
- `TASK-1306` is marked done in timeline docs
- `TASK-1306A` SIT runtime gate is complete with green control-plane evidence
- `TASK-906` has Go direction already; W3 needs the final report state aligned with current work

### Still blocking W3 completion

- Product owner review on live SIT is still required before frozen export UX work can start
- `TASK-1313` is still in progress and blocks clean UAT movement
- Export/UI work is still gated by `UX-FREEZE-EXPORT-CONFIGURATOR.md` approval review

### Approval-gated work

- `TASK-1003` can start only after product owner reviews the live SIT environment and completes the 5 approval checkboxes
- `TASK-1006` cannot start until `TASK-1003` and the same approval gate are completed
- The 5 approval checkboxes in `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` are treated as a real gate, not a documentation nicety

### Local verification

- `tests/services/test_schema_analyzer.py`
- `tests/api/test_schema_analyze_api.py`
- `tests/services/test_master_data_import.py`
- `tests/api/test_master_import_api.py`

Result after W3 backend completion: `413 passed`, with `2` pre-existing governance failures outside this docs-only scope

## 5. Critical Path

The W3 backend critical path is closed:

`TASK-1009` -> `TASK-1001` -> `TASK-1207` -> `TASK-1002` -> `TASK-1101` -> `TASK-1104`

The current remaining gate for W3 follow-on work is:

`live SIT review` -> `5 UX freeze approval checkboxes` -> `TASK-1003` -> `TASK-1006`

Everything else is support work.

If anything threatens W3, protect the critical path first and push non-critical items right.

## 6. Working Assumption

For W3 implementation, treat the existing 6 template files already analyzed in repo/private reference as the current baseline for column order, encoding, and format.

Real Express CSV samples from customer are still useful as QA evidence, but they should not keep reopening W3 backend implementation unless they reveal a real format mismatch.

## 7. Execution Order

### Lane split

- `Continue now`: backend/application work that does not require live SIT UX validation
- `Wait for approval`: frontend/export UX work that still requires product owner review on live SIT

### Continue now - immediate order

- Freeze W3 scope using this document
- Keep W3 backend completion status aligned across timeline and epic docs
- Keep `TASK-1313` and `TASK-906` wording aligned with current repo state
- Prepare product-owner SIT review against the frozen export/configurator spec

### Continue now - backend follow-on

- W3 backend critical path is already complete
- Do not reopen `TASK-1009`, `TASK-1001`, `TASK-1207`, `TASK-1002`, `TASK-1101`, or `TASK-1104` unless a real regression is found
- Keep source changes focused on blocked-lane prerequisites or follow-up reporting only

### Wait for approval

- Use the completed SIT environment and rollout evidence as the review baseline
- Product owner reviews SIT and ticks all 5 approval checkboxes in `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`
- Only then start `TASK-1003`
- Start `TASK-1006` only after `TASK-1003` is complete enough to support the intended flow

### By end of W3

- Lock `TASK-906` report wording to current reality
- Update timeline/status docs so they reflect what is actually done, not what was only planned

## 8. W3 Work Board

| Priority | Task | Why it matters this week | Finish condition |
| --- | --- | --- | --- |
| Done | `TASK-1009` Schema Analyzer | Removes setup friction and validates W3 direction | ✅ DONE - `b3b2757` - 54 tests |
| Done | `TASK-1001` Template engine backend | Main value path for export | ✅ DONE - `a350333` - 47 tests |
| Done | `TASK-1207` vendor/customer import | Supports template field lookup | ✅ DONE - `868a1ee` - 3 tests |
| Done | `TASK-1002` minimal template API | Supports downstream flow | ✅ DONE - `66c7419` - 17 tests |
| Done | `TASK-1101` Purchase Tax template-based | Makes W3 output visible and usable | ✅ DONE - `a693d06` - 22 tests |
| Done | `TASK-1104` preview/balance validation | Good risk control after `TASK-1101` | ✅ DONE - `fd7e11c` - 18 tests |
| P0 | `TASK-1313` deploy path | Needed to move work out of local/dev limbo | UAT path has evidence and no process blocker |
| P0 | `PO SIT review` | Unlocks frozen frontend/export work | All 5 freeze approval checkboxes are reviewed on live SIT |
| P1 | `TASK-906` final report | Needed for W3 close and Phase II/2 planning | Report and timeline wording aligned |
| Hold | `TASK-1003` Template Configurator UI | SIT and UX approval gate required | Start only after all 5 freeze checkboxes are approved |
| Hold | `TASK-1006` Export workflow UI | Depends on same gate plus `TASK-1003` | Start only after `TASK-1003` is unblocked |

## 9. Blocker Rules

If a task is blocked for more than half a day, do not let it silently eat the week.

Use these rules:

1. `TASK-1001` blocked -> stop everything non-critical and resolve it first
2. `TASK-1101` blocked by `TASK-1001` -> do not start UI detours
3. `TASK-1313` blocked by external workflow/control-plane dependency -> collect exact blocker and continue local/backend completion in parallel
4. Freeze approval not completed on live SIT -> do not spend W3 time on `TASK-1003` or `TASK-1006`
5. New requirement appears -> add to backlog or W4 unless it is required for `TASK-1001` or `TASK-1101`

## 10. Definition of Done for W3

W3 is done when all items below are true:

1. ✅ `TASK-1009` is green in code and tests
2. ✅ `TASK-1001` exists as real implementation, not stub
3. ✅ `TASK-1207` is committed or explicitly confirmed non-blocking for current W3 export path
4. ✅ `TASK-1002` provides the minimum template contract needed by downstream flow
5. ✅ `TASK-1101` uses template-based export path
6. ⏳ SIT rollout evidence is recorded and reusable for approval/UAT planning
7. ⏳ `TASK-1313` no longer blocks deploy progression with missing setup/evidence
8. ⏳ `TASK-906` report and W3 status docs are updated to the actual repo state
9. ⏳ Remaining UI work is clearly parked behind gate approval, not mixed into W3 completion

## 11. First Follow-On After W3

Only after W3 is closed should we move in this order:

1. `TASK-1003` Template Configurator UI
2. `TASK-1006` Export page flow
3. `TASK-1004` master template seed hardening if still incomplete
4. `TASK-1013` Product Master
5. `TASK-1208` LoveBot export

## 12. Practical Next Step

The W3 backend critical path is already closed.

Before touching any new W4/W5 scope, we should first verify:

- product owner has reviewed the live SIT environment
- all 5 approval checkboxes in `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` are completed
- `TASK-1313` evidence lane is aligned for UAT progression
- `TASK-906` wording is aligned to the current backend-complete repo state
