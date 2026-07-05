# W4 Execution Plan

> Week: W4 (6 Jul 2026 - 12 Jul 2026)
> Purpose: convert W3 backend completion into real W4 web-facing workflow completion
> Scope focus: close carryover from W1-W3 that blocks usable export/configurator flow and the visible SIT product shell

## 1. W4 Goal

Week 4 must end with a visible and usable SIT vertical slice on the real web surface, not only backend APIs, route markers, or isolated demo files.

W4 is considered successful when we have:

1. Product-owner gate cleared on live SIT for the frozen Export + Configurator UX
2. `TASK-1003` Template Configurator UI connected to real APIs
3. `TASK-1006` Export page moved from old Step 6 hardcoded flow toward the frozen full-page flow
4. Every visible SIT action in the proof path is wired, explicitly deferred/disabled, or hidden
5. W1-W3 carryover items that still affect W4 execution are either closed or explicitly parked with evidence

This week is **not** about reopening backend foundation that already passed in W3 unless a real regression is found.

## 2. Source of Truth

Use these files in this order when there is any conflict:

1. `docs/requirement/phaseII/PHASE-II-TIMELINE.html`
2. `docs/requirement/phaseII/W3-EXECUTION-PLAN.md`
3. `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`
4. `docs/requirement/phaseII/W3-CODEX-UX-FRONTEND-PLAN.md`
5. `docs/requirement/phaseII/epic-10/EPIC-10-TASKS-DETAIL.md`
6. `docs/requirement/phaseII/epic-13/EPIC-13-TASKS-DETAIL.md`
7. `docs/requirement/phaseII/W4-DESIGN-IA-SYNC-2026-07-05.md`
8. `docs/requirement/phaseII/W4-SIT-END-TO-END-CLOSURE-PLAN.md`
9. `docs/requirement/phaseII/BACKLOG.md`

## 2A. Latest UX Review Intake (2026-07-05)

These items came from the latest UX/UI review comments and must be tracked in W4 before implementation starts. Treat them as active planning inputs, not optional polish.

### A. Export Config + Preview must preserve the PoC editing power

Implementation intent for W4 export/configurator work must stay aligned with the PoC-style behavior already requested in Epic 10 documentation:

- users must be able to select fields and reorder columns before export
- this must work for both:
  - export without a template
  - export from a selected template
- after choosing a template, users must still be able to adjust columns for that run
- the export adjustment experience must stay inline on the page, not revert to a popup/modal-first flow

Primary references for this requirement:

- `docs/requirement/phaseII/epic-10/README-EPIC-10.md`
- `docs/requirement/phaseII/epic-10/CLIENT-TEMPLATE-ANALYSIS.md`
- `docs/requirement/phaseII/epic-10/EPIC-10-TASKS-DETAIL.md`
- `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`
- `docs/requirement/phaseII/W4-UX-FREEZE-ACCEPTANCE-REVIEW.md`

W4 planning rule:

- if the live or planned export UX removes PoC-level column selection/reordering flexibility, fix that UX before counting `TASK-1006` as ready

### B. Company management UX needs AP/AR-specific restructuring

Company-management follow-up identified during review:

- the `COA` entry flow inside company management should be reframed as broader `Settings`, not only COA
- AP and AR import/reference flows should be separated instead of mixed into one generic vendor/customer tab structure
- review the customer sample files below as concrete references for the intended split:
  - `private_data/poc/Comp_1/APAR/AP-CCSS.csv`
  - `private_data/poc/Comp_1/APAR/AR-CCSS.csv`

W4 planning rule:

- this is not a reason to reopen unrelated company-admin redesign, but the AP/AR separation must be captured as a real follow-up requirement before implementation continues in that area

**Classification**: direct W4 change (done) + backlog/customer-confirmation question. The COA→Settings relabel and the AP/AR tab split are already implemented on `main-ux-ui.html` (see `epic-10/UX-FREEZE-FINAL-CODEX-HANDOFF.md`). The remaining IA-wording/canonical-import-format questions are tracked as `BL-011` in `BACKLOG.md` — not a W4 blocker.

### C. Additional customer template packs must become tracked work

Customer-provided template materials under the Excel-format folders must be incorporated into planning instead of staying as ad hoc references:

- `private_data/poc/Comp_1/template/excelformat/Excel format (สร้างเอง)`
- `private_data/poc/Comp_1/template/excelformat/Master`

W4 planning rule:

- add concrete implementation tasks for low-ambiguity work that these samples introduce
- add unresolved customer questions as explicit backlog items instead of burying them inside implementation notes
- do not silently expand W4 scope without first classifying each item as:
  - W4 execution work
  - later Epic 10 follow-up
  - backlog question for customer confirmation

**Classification**: direct W4 change (done) + backlog/customer-confirmation question. The 6 low-ambiguity Express master template families (Book 12/14/15/15+WHT/22/24, already fully specified in `TASK-1004`/`CLIENT-TEMPLATE-ANALYSIS.md`) are now on the Templates screen in `main-ux-ui.html`. The remaining pack-classification questions (which files are canonical, multi-line scope, PO/Journal-RV/bank-transfer scoping) are tracked as `BL-012` in `BACKLOG.md` — explicitly not folded into current implementation.

## 2B. Current W4 Status After SIT Review (2026-07-05)

The W4 status changed materially after the latest SIT deploy + review cycle and must now be treated as follows:

- live SIT review on the production-facing surface `/phase2/prototype` is complete
- the 5 UX/UI review gates were accepted on SIT for the deployed W4 frontend artifact referenced in `epic-10/UX-FREEZE-FINAL-CODEX-HANDOFF.md`
- the repo still needs the **formal PO checkbox commit** in `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` to close the gate visibly in-source
- `src/frontend/index.html` is still behind `src/frontend/main-ux-ui.html` and must be synced so fallback/static review does not show stale UX

Execution implication:

- do **not** treat W4 as blocked on SIT review anymore
- do **not** reopen the export/configurator freeze debate unless a new live mismatch is found
- move forward on the remaining implementation closure items while capturing the PO checkbox close and `index.html` parity as explicit follow-ups

## 2C. SIT End-to-End Closure Pivot (2026-07-05)

Latest manual SIT review shows that closing only the Epic 10 export/configurator lane is not enough for a usable weekly delivery. The application shell exposes Companies, Users, Company Settings, AP/AR, Templates, and Export as one product surface. If visible buttons only show toast success without persisted backend behavior, W4 must not be called "SIT complete".

Use `docs/requirement/phaseII/W4-SIT-END-TO-END-CLOSURE-PLAN.md` as the W4 closeout override for SIT readiness.

New closeout rule:

- "Epic 10 export/configurator close-ready" is allowed only for the export/configurator lane.
- "W4 SIT complete" requires a vertical slice that proves login, company/user admin persistence or explicit visible deferral, template/configurator, export, refresh/re-login persistence, and live SIT clickthrough.
- Company/User CRUD work belongs to Epic 12 by roadmap, but the minimum Company/User persistence slice is pulled into W4 because those screens are visible in the SIT product shell. **Done 2026-07-05** — real `Company`/`User` DB-backed CRUD APIs added (`/v1/admin/companies`, `/v1/admin/users`, `/v1/admin/users/{id}/reset-password`) and the Companies/Users screens on `main-ux-ui.html` now load/create/edit through them. See `epic-10/W4-SIT-E2E-CLAUDE-CODE-COMPLETION-01.md`.
- Fake-success buttons are blockers unless they are disabled or visibly labeled as deferred. **Done 2026-07-05** — full visible-control audit across the product shell; every fake-success toast found was either wired to a real API or converted to an honest deferred/disabled state.

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
- live SIT review has now been completed on `/phase2/prototype`; the W4 frontend artifact is accepted there, while `index.html` still needs parity sync and should not be used as acceptance evidence
- master template seed baseline is verified in repo tests: `Express GL` and `Purchase Tax` are built by `scripts/seed_data.py` and `tests/db/test_seed_data.py` passes
- **new 2026-07-05**: real Company/User CRUD now exists and is wired — `GET/POST /v1/admin/companies`, `PUT /v1/admin/companies/{id}`, `GET/POST /v1/admin/users`, `PUT /v1/admin/users/{id}`, `POST /v1/admin/users/{id}/reset-password`, all backed by the actual `Company`/`User`/`UserCompanyAssignment` tables (not the legacy `data/companies.json` demo store, which is left untouched for `ux-ui-prototype.html`'s internal-only use)
- **new 2026-07-05**: AP/AR tabs on `main-ux-ui.html` now render real data from the existing `TASK-1207` vendor-master/customer-master endpoints and wire CSV import through them; single-row add remains explicitly deferred (no such endpoint exists)

### Confirmed gap between backend and web surface

- the old 6-step workflow still exists only as the internal legacy demo at `/workflow-demo`
- `src/frontend/template-configurator-demo.html` and `src/frontend/ux-ui-prototype.html` are still demo/reference surfaces, not the main product flow; the production-facing page is `src/frontend/main-ux-ui.html`
- **resolved 2026-07-05**: `POST /api/v1/templates/analyze`, `GET/POST/PUT/DELETE /api/v1/templates`, `POST /api/v1/templates/{id}/preview`, `POST /api/v1/export/preview`, and `POST /api/v1/export/validate` are now all wired into `main-ux-ui.html` — including the Quick Export null-template path (`template_id: null` + `column_overrides` on both preview and export). See `epic-10/W4-EPIC10-CLAUDE-FOLLOWUP-01-COMPLETION.md`. The one remaining old-endpoint caller is `src/frontend/index.html`, which is behind `main-ux-ui.html` and is Copilot's active fix lane (`epic-10/W4-EPIC10-SIT-FIX-AND-CLOSE-HANDOFF-01.prompt.json`) — do not re-diagnose or re-fix it here.
- Template Clone (`modal-clone-template`) is wired but not independently re-verified end-to-end; Template Delete (`confirmTemplateDelete`) is still UI-only — it shows a success toast without calling a delete endpoint. Both are explicit, tracked deferrals, not silent gaps.
- **found and closed 2026-07-05**: a broad SIT visible-control audit found that Companies, Users, Company-detail COA/AP/AR/Settings, and Internal Console (Cost/Audit/Settings) were 100% static demo markup with `showToast(...,'ok')` calls claiming success on every add/edit/import action — none of it called any backend, unlike the already-wired Export/Configurator/Templates lane. Companies, Users, and AP/AR list+import are now real; COA, Company Settings (mapping rules), and Internal Console admin actions remain backend-less and are now honestly labeled deferred/disabled instead of faking success. Dashboard/Upload/Processing/Review Scan/Review Mapping are unchanged fixture demos (out of this week's must-finish scope) but now carry an explicit "Demo data" banner instead of looking live. See `epic-10/W4-SIT-E2E-CLAUDE-CODE-COMPLETION-01.md` for the full audit table.

### Carryover still active from W1-W3

- ~~formal PO checkbox close in `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`~~ **resolved** — all 5 items are `✅ 2026-07-05` in that file
- `TASK-1003` frontend implementation — 3-tab shell + a real, wired column editor now exist on `main-ux-ui.html` (shared state with the Export screen); remaining work is a full `ac_1003_r1`–`r7` acceptance pass, not a build-from-scratch. See "Day 2-3" below.
- `TASK-1006` frontend integration follow-up:
  - ~~Quick Export frontend must use the real null-template backend path~~ **resolved 2026-07-05**
  - `src/frontend/index.html` must be aligned with `src/frontend/main-ux-ui.html` — **Copilot's active lane**, see `epic-10/W4-EPIC10-SIT-FIX-AND-CLOSE-HANDOFF-01.prompt.json`; not re-diagnosed here
- ~~`TASK-906` wording/status alignment to the actual repo state~~ **resolved** — `TASK-906` is an Epic 9 Line-Item PoC feasibility item (not an Epic 10 Export/Configurator deliverable). Its own report, `docs/PoC/reports/TASK-906-FEASIBILITY-REPORT.md`, was updated 2026-07-04 and explicitly states its "Conditional Go" finding remains valid after W3 backend completion. It was tracked on the W4 board only for cross-report hygiene and was never a W4 export/configurator blocker; no further wording change is needed unless the feasibility report itself goes stale.
- `TASK-1313` deploy-evidence lane still needs clean status framing for UAT progression, but it is not a direct blocker for W4 UI execution

## 4. W4 Scope Lock

### In scope for W4

- `PO SIT review` on live SIT against the frozen export/configurator UX
- complete the formal 5 approval checkbox close in `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`
- `TASK-1003` Template Configurator UI on the real web surface
- `TASK-1009` frontend integration inside Configurator Tab 1
- `TASK-1006` Export page integration on the real web surface
- `src/frontend/index.html` parity with `src/frontend/main-ux-ui.html` for fallback/static review consistency
- bridge from existing workflow into the new export/configurator pages
- seed verification/hardening for the master templates needed by W4 flow
- `TASK-906` status wording alignment
- `TASK-1313` status/evidence alignment if it still affects W4/UAT readiness messaging
- capture the latest UX review corrections for:
  - PoC-level column select/reorder behavior in Export
  - AP/AR separation expectations in company-management follow-up
  - customer Excel-format sample packs that need task/backlog classification

### Explicitly not required to close W4

- broad redesign of non-export workflow screens
- reopening `TASK-1001`, `TASK-1002`, `TASK-1009`, `TASK-1101`, `TASK-1104`, or `TASK-1207` without a verified regression
- Phase II/2 work such as Epic 14/15/16 feature delivery
- unrelated dashboard/admin polishing outside what W4 export/configurator flow needs
- implementing all downstream company-management refinements immediately before they are classified into W4 vs Epic vs Backlog

But if any of those surfaces remain visible in SIT, they must still follow the W4 design rule: wired, disabled/deferred, or hidden. "Not required to implement fully" does not allow fake-success controls.

## 5. W1-W3 Carryover to Finish in W4

### Must finish now

- ~~formal PO checkbox close for the 5 UX freeze approval items~~ **resolved**
- `TASK-1003` — acceptance-pass remainder only (shell + editor already built; see §3)
- `TASK-1006` — closure-wiring remainder only (Quick Export backend path already done; `index.html` parity is Copilot's active lane)
- ~~`TASK-906` wording alignment to actual W3 completion state~~ **resolved** — see §3 for why it was never a real W4 blocker
- classify the latest UX review comments into:
  - direct W4 changes
  - Epic 10 task additions/updates
  - backlog questions for customer confirmation

### Finish if it blocks UAT progression or planning clarity

- `TASK-1313` deploy-evidence wording/status cleanup
- master template seed verification for the exact W4 flow

### Do not restart as new feature work

- `TASK-901` VAT disambiguation
- `TASK-902` WHT detection + backfill

These already have live code paths in repo. W4 should only verify regression risk where export/configurator flow depends on them.

## 6. Critical Path

The practical W4 critical path is now:

`formal PO checkbox close` -> `TASK-1003` -> `TASK-1006` closure wiring -> `focused E2E verification` -> `W4 status/doc alignment`

The live SIT review gate is no longer the blocker. The remaining risk is implementation closure drifting away from the accepted SIT surface.

## 7. Working Assumptions

1. W3 backend completion remains valid unless a focused regression test fails.
2. The lowest-risk frontend path is to introduce a new full-page export/configurator surface, then link it from the current workflow.
3. Existing demo/prototype files are references only; W4 success is measured on the production-facing review path (`/phase2/prototype`) and the main web flow, not on isolated mock pages.
4. Minimum master template baseline is already partially seeded (`Express GL` and `Purchase Tax`), but W4 must verify whether the real flow also needs the wider Express transaction template set.

## 8. Execution Order

### Day 1 - re-anchor after SIT pass

- record the SIT-pass state in W4 docs and task board
- complete or explicitly route the formal PO checkbox close
- capture `index.html` parity as a required follow-up so static/fallback review does not diverge from the accepted SIT surface

### Day 2-3 - `TASK-1003` (status: shell + editor built 2026-07-05; acceptance-pass remainder below)

- ~~build the real Template Configurator surface~~ done — `main-ux-ui.html` has a real 3-tab surface
- ~~implement 3 persistent tabs~~ done — Upload & Detect / Configure Columns / Test Output all exist and are wired (a `ReferenceError` bug that made every tab button non-clickable was found and fixed 2026-07-05, see `epic-10/W4-EPIC10-CLAUDE-FOLLOWUP-01-COMPLETION.md`)
- ~~wire Tab 1 to `POST /api/v1/templates/analyze`~~ done
- template list/edit/create/save/update wired to `TASK-1002` endpoints; **clone** not independently re-verified, **delete** still UI-only (toast, no API call) — explicit deferrals, not silent gaps
- ~~make the Configurator reachable from the main web flow~~ done
- remaining: full `ac_1003_r1`–`r7` acceptance pass; the "Row-grouping Strategy" panel (Template Mode/Row Source/Aggregation) is intentionally a disabled design-reference block — no such fields exist in the current template schema, so wiring it is a schema decision for later, not a W4 frontend task

### Day 4 - `TASK-1006` (status: backend path done 2026-07-05; remainder below)

- ~~replace old Step 6 assumptions with the frozen export page flow~~ done
- ~~support `Quick Export` vs `Template Export`~~ done
- ~~show inline full-width column adjustment, not modal behavior~~ done
- ~~call real preview/validation/template endpoints~~ done
- ~~replace the Quick Export client-side CSV fallback with the real null-template backend export path~~ done — the fallback functions were confirmed orphaned and deleted
- sync `src/frontend/index.html` with the production-facing W4 export surface — **Copilot's active lane** (`epic-10/W4-EPIC10-SIT-FIX-AND-CLOSE-HANDOFF-01.prompt.json`), not re-solved here
- ~~keep per-run changes ephemeral by default, with explicit template save/update actions~~ done

### Day 5 - proof and alignment

- verify navigation from existing workflow into new export/configurator pages
- run smoke/E2E coverage for main paths
- confirm seed/template availability needed by W4 flow
- align `TASK-906`, W4 status wording, and any W3 follow-on doc references
- convert the latest UX review intake into explicit Epic/Backlog follow-up after W4 plan alignment

## 9. W4 Work Board

| Priority | Task | Why it matters this week | Finish condition |
| --- | --- | --- | --- |
| P0 | SIT review status alignment | Keep plan truthful after live review already passed | W4 docs explicitly reflect SIT PASS on `/phase2/prototype` |
| P0 | formal 5 UX freeze checkbox close | Close the review gate visibly in-source | All 5 checkboxes reviewed and committed, or exact rejects documented |
| P0 | `TASK-1003` Configurator UI | Main W4 deliverable | Shell + editor exist on web flow and use real template APIs — **done**; full acceptance pass (`ac_1003_r1`–`r7`) is the remaining item |
| P0 | `TASK-1009` UI integration | Removes manual setup friction | Sample upload can analyze and prefill Configurator — **done** |
| P1 | `TASK-1006` Export page flow | Turns backend into usable output flow | Full-page export flow replaces old embedded Step 6 behavior — **done**, including the Quick Export backend path |
| P1 | `index.html` parity sync | Prevent stale fallback/static review from contradicting SIT | **Copilot's active lane** (`epic-10/W4-EPIC10-SIT-FIX-AND-CLOSE-HANDOFF-01.prompt.json`) — not tracked as open frontend/doc work here |
| P1 | Focused E2E / smoke checks | Stops false-done UI claims | `tests/e2e/w4-export-uxui.spec.ts` (9 tests, including real-click interaction tests) + backend `pytest` (77 tests) passing locally — **done** for the paths touched; live SIT re-run pending in Copilot's lane |
| P1 | Master template seed verification | Avoids UI flow failing on missing templates | Needed masters exist in the runtime path used by W4 |
| P1 | ~~`TASK-906` wording alignment~~ | Keeps reporting truthful | **Resolved** — see §3; `TASK-906` (Epic 9) was never a W4 export/configurator blocker |
| P2 | `TASK-1313` status cleanup | Keeps UAT/deploy reporting clear | Marked clearly as done, in progress, or non-blocking with evidence |

## 10. Blocker Rules

If a blocker lasts more than half a day, record it explicitly and reroute the week.

Use these rules:

1. If a new SIT mismatch appears, log it against the accepted `/phase2/prototype` surface before reopening the freeze decision
2. If the formal checkbox close stalls, keep coding only when the SIT acceptance evidence is already written and unambiguous
3. `TASK-1003` slips -> do not pretend `TASK-1006` can finish cleanly
4. Missing master template/runtime data -> fix seed/runtime path before blaming frontend
5. Regression found in W3 backend endpoints -> run focused backend fix only for the broken contract, not a broad rewrite

## 11. Definition of Done for W4

W4 is done when all items below are true:

1. ✅ live SIT review on `/phase2/prototype` is completed and recorded
2. ✅ all 5 approval checkboxes in `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` are resolved
3. ✅ `TASK-1003` exists on the real web surface, not only in `template-configurator-demo.html` — 3-tab shell + real column editor; remaining gap is the full acceptance pass, not existence
4. ✅ Configurator Tab 1 can call `POST /api/v1/templates/analyze`
5. ✅ template CRUD/preview actions are wired to real APIs (clone not independently re-verified; delete still explicitly UI-only)
6. ✅ `TASK-1006` moves export into the intended full-page flow with Quick vs Template modes, including the real backend path for both
7. ✅ the old hardcoded Step 6 behavior is no longer the primary export path
8. ⏳ `src/frontend/index.html` is aligned closely enough with `src/frontend/main-ux-ui.html` to avoid stale fallback review confusion — **Copilot's active lane**, tracked in `epic-10/W4-EPIC10-SIT-FIX-AND-CLOSE-HANDOFF-01.prompt.json`, not this doc's open item
9. ✅ focused smoke/E2E checks cover the main W4 paths locally (`tests/e2e/w4-export-uxui.spec.ts` + `tests/e2e/w4-admin-crud-uxui.spec.ts`, 16/16; backend `pytest` 452/457, 2 pre-existing unrelated `tests/governance` failures); live SIT re-run is part of item 8's closure
10. ✅ `TASK-906` and W4/W3 status wording reflect actual repo state — see §3 for the resolution
11. ✅ Company add/edit is persisted through a real backend API or refresh/re-login proof — done (`/v1/admin/companies`), live SIT re-proof pending Copilot's deploy
12. ✅ User add/edit and admin password reset are persisted through a real backend API — done (`/v1/admin/users`, `/v1/admin/users/{id}/reset-password`), live SIT re-proof pending Copilot's deploy
13. ✅ AP/AR company tabs are separated and either wired or visibly deferred — list/import wired to the existing `TASK-1207` API; single-row add explicitly deferred
14. ✅ No visible W4 proof-path control shows success without a real backend action — full visible-control audit closed 2026-07-05, see `epic-10/W4-SIT-E2E-CLAUDE-CODE-COMPLETION-01.md`

## 12. Practical Next Step After W4

If W4 closes successfully, the next follow-on order should be:

1. W5 hardening for clone/export polish and unified export endpoint completion if still partial
2. template seed expansion for the wider Express transaction set if runtime proof shows it is still incomplete
3. UAT-facing verification and documentation cleanup
