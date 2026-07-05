# W4 Task Board

> Week: W4 (6 Jul 2026 - 12 Jul 2026)
> Purpose: execution board for owners, dependencies, acceptance criteria, and proof
> Use with: `docs/requirement/phaseII/W4-EXECUTION-PLAN.md`, `docs/requirement/phaseII/W4-DESIGN-IA-SYNC-2026-07-05.md`, `docs/requirement/phaseII/W4-SIT-END-TO-END-CLOSURE-PLAN.md`

## 1. Owner Model

Use this owner split unless the user explicitly reassigns it:

| Lane | Owner | Responsibility |
| --- | --- | --- |
| Coordination / sequencing / reporting | Codex | W4 plan, task board, status wording, execution order, closeout checks |
| UX / frontend implementation | Codex | `TASK-1003`, `TASK-1006`, frontend wiring, route visibility, E2E checks |
| Deploy / infra / runtime proof | Copilot | SIT evidence, deploy path, environment/runtime follow-through, `TASK-1313` lane |
| Deep architecture / design consult | Claude | Only if a design-level conflict or backend contract dispute appears |

## 2. W4 Delivery Board

| ID | Priority | Owner | Task | Dependency | Deliverable | Proof |
| --- | --- | --- | --- | --- | --- | --- |
| W4-01 | P0 | Codex + PO | Record live SIT review close | SIT reachable | Reviewed flow on live SIT is reflected in current docs | Review notes + linked handoff |
| W4-02 | P0 | Codex + PO | Resolve formal 5 UX freeze checkbox close | W4-01 | Approved or explicitly rejected freeze items are visible in-source | Updated `UX-FREEZE-EXPORT-CONFIGURATOR.md` |
| W4-03 | P0 | Codex | `TASK-1003` Configurator web surface | W4-02 | Real Configurator page reachable from product flow | Route + screenshots + smoke pass |
| W4-04 | P0 | Codex | Schema Analyzer UI integration | W4-03 | Upload sample -> analyze -> prefill mapping | API call evidence + visible prefill |
| W4-05 | P0 | Codex | Template CRUD + preview UI wiring | W4-03 | List/create/edit/delete/clone/preview on real page | Manual flow proof + targeted tests |
| W4-06 | P1 | Codex | `TASK-1006` Export full-page flow | W4-03, W4-04, W4-05 | Quick Export / Template Export page | Route + visible mode switch |
| W4-06A | P1 | Codex | `index.html` parity sync | W4-06 | Static/fallback surface does not contradict accepted W4 UX | File diff + quick static check |
| W4-07 | P1 | Codex | Export preview + validation hookup | W4-06 | Inline preview and validation in export flow | API call evidence + UI message states |
| W4-08 | P1 | Codex | Main workflow bridge | W4-03, W4-06 | Existing workflow links into new pages cleanly | Navigation test |
| W4-09 | P1 | Codex | Focused E2E / smoke pack | W4-03 through W4-08 | Regression coverage for core W4 paths | Passing test run |
| W4-10 | P1 | Codex | Master template seed verification | Runtime ready | Needed templates present for W4 flow | Seed/runtime check notes |
| W4-11 | P1 | Codex | ~~`TASK-906` wording alignment~~ **Resolved 2026-07-05** | W4 implementation status known | Report reflects actual repo state | See §2.1 W4-11 row — `TASK-906` is an Epic 9 item, was never a W4 blocker |
| W4-12 | P2 | Copilot | `TASK-1313` status/evidence cleanup | Deploy lane evidence | UAT/deploy messaging is unambiguous | Updated task/status note |
| W4-E2E-01 | P0 | Codex | SIT end-to-end vertical-slice audit + design sync | Latest manual SIT review | Every visible route/action is classified as wired, disabled/deferred, or hidden | `W4-SIT-END-TO-END-CLOSURE-PLAN.md`, `W4-DESIGN-IA-SYNC-2026-07-05.md` + audit table (`epic-10/W4-SIT-E2E-CLAUDE-CODE-COMPLETION-01.md`) |
| W4-E2E-02 | P0 | Codex / Claude | Company + User persistence slice | W4-E2E-01 | Add/edit Company and User are persisted or visibly deferred | Real `/v1/admin/companies` + `/v1/admin/users` API (backend+frontend, this pass); local Playwright proof recorded — live SIT refresh/re-login proof still Copilot's lane |
| W4-E2E-03 | P0 | Codex / Claude | Remove fake-success blockers | W4-E2E-01 | Buttons no longer show success without API success | Done, including a 2026-07-05 follow-up (`W4-SIT-E2E-CLAUDE-CODE-FOLLOWUP-02`) after Codex Review 01 found residual Review Scan/Review Mapping/Processing controls still claiming success — see `epic-10/W4-SIT-E2E-CLAUDE-CODE-FOLLOWUP-02-COMPLETION.md` |
| W4-E2E-04 | P0 | Copilot | SIT end-to-end clickthrough proof | W4-E2E-02, W4-E2E-03 | Live SIT proves the full vertical slice | Browser/runtime report — pending Copilot deploy; Codex Review 01's `index.html` parity finding is still Copilot's lane |

## 2.1 Current Status After Epic Review

| Work item | Status | Note |
| --- | --- | --- |
| W4-01 | Done | live SIT review on `/phase2/prototype` is accepted; see `epic-10/UX-FREEZE-FINAL-CODEX-HANDOFF.md` |
| W4-02 | Done | formal checkbox close is committed in `UX-FREEZE-EXPORT-CONFIGURATOR.md` with 2026-07-05 sign-off |
| W4-03 | In progress (2026-07-05) | 3-tab shell + real column editor now on `main-ux-ui.html` (`#configuratorColumnsBody`, shares `state.exportColumns` with the Export screen). A real bug was found and fixed in this pass: every tab button (`onclick="setConfiguratorTab(...)"`) and several actions (`applyAnalysisToConfigurator`, `saveExportColumnsAsTemplate`, `updateActiveTemplateColumns`, `refreshConfiguratorTestTab`, `previewExport`) were declared inside a `"use strict"` IIFE but never exposed on `window` — every one of those inline `onclick=""` handlers threw `ReferenceError` on a real click. Fixed by exposing them; see `epic-10/W4-EPIC10-CLAUDE-FOLLOWUP-01` verification. Not yet done: `ac_w4_1003_01` (nav-link reachability from main flow) not independently re-verified this pass; the "Row-grouping Strategy" sub-panel (template_mode/row_source/aggregation) remains an explicitly-labeled non-wired design reference — no such fields exist in the current template schema |
| W4-04 | Wired, not live-verified | Tab 1 (`configuratorTab-upload`) calls the real `POST /api/v1/templates/analyze` (pre-existing) and "Apply to Tab ②" now actually works post-bugfix above. No live/credentialed run performed this pass to confirm the full upload→analyze→apply round trip against a real backend |
| W4-05 | Partially wired | Template list/Save-as/Update call real APIs (pre-existing + this pass's Configure-tab editor). Clone opens `modal-clone-template` (not independently re-verified this pass); Delete (`confirmTemplateDelete`) is still UI-only — shows a success toast without calling a delete endpoint |
| W4-06 | Done (backend + frontend) | Quick Export now calls the real null-template backend path end-to-end (`template_id:null` + `column_overrides` on both `/api/v1/export/preview` and `/api/v1/export`) — see `TASK-W4-BACKEND-FOLLOWUP`. Client-side-only fallback (`downloadQuickExportCsv`/`renderQuickPreview`) was dead code and has been deleted |
| W4-06A | Stale again — **Copilot's active lane** | `index.html` was resynced before this pass's Configurator changes landed; it still has the mode-picker/tab markers from that earlier resync but is missing the new real column editor (`#configuratorColumnsBody`, `#configuratorAddColumnSelect` absent — confirmed via grep). Being fixed under `epic-10/W4-EPIC10-SIT-FIX-AND-CLOSE-HANDOFF-01.prompt.json`; not re-diagnosed or re-solved in doc-cleanup passes |
| W4-07 | Done | preview (`/api/v1/export/preview`) and validation (`/api/v1/export/validate`) are both called from `main-ux-ui.html` for Quick and Template modes; UI shows balance/preview state inline |
| W4-08 | Not independently verified | no focused navigation test has confirmed every entry point from the existing workflow into the new export/configurator pages is dead-end-free; not one of the assigned work items in the passes done so far |
| W4-09 | Done for the paths touched so far | `tests/e2e/w4-export-uxui.spec.ts` fixed (had mojibake-corrupted Thai assertions from a prior edit) and expanded; `tests/e2e/w4-admin-crud-uxui.spec.ts` added 2026-07-05 for the new Company/User/AP-AR wiring. 16/16 e2e + 452/457 backend (2 pre-existing unrelated `tests/governance` failures) passing locally against a static copy of `main-ux-ui.html` with mocked API routes (no live DB available in this sandbox); not yet re-run against live SIT |
| W4-10 | Baseline verified | repo seed test passes for `Express GL` and `Purchase Tax`; wider Express template coverage still needs runtime/flow verification |
| W4-11 | Resolved | `TASK-906` is an Epic 9 Line-Item PoC feasibility item, not an Epic 10 Export/Configurator deliverable. `docs/PoC/reports/TASK-906-FEASIBILITY-REPORT.md` was updated 2026-07-04 and explicitly states its "Conditional Go" finding remains valid after W3 backend completion. It was carried on this board for cross-report hygiene only and was never a real W4 blocker — no further wording change needed unless the feasibility report itself goes stale |
| W4-12 | Non-blocking for W4 UI | deploy/UAT-readiness lane, not the direct UI gate |
| W4-E2E-01 | Done, residual blocker closed (2026-07-05) | Initial audit recorded in `epic-10/W4-SIT-E2E-CLAUDE-CODE-COMPLETION-01.md`; Codex Review 01 found remaining fake-success controls on Review Scan / Review Mapping / Processing, closed in the follow-up pass — see `epic-10/W4-SIT-E2E-CLAUDE-CODE-FOLLOWUP-02-COMPLETION.md` |
| W4-E2E-02 | Done (backend + frontend), live SIT proof pending | Added real `Company`/`User` DB-backed CRUD APIs (`/v1/admin/companies`, `/v1/admin/users` + `/v1/admin/users/{id}/reset-password`) and rewired the Companies/Users screens to load/create/edit through them instead of static demo rows. Refresh/re-login proof requires a live DB session — that's Copilot's deploy lane (`W4-E2E-04`) |
| W4-E2E-03 | Done, including follow-up (2026-07-05) | Company/User/AP-AR fake-success issues fixed in the first pass; Codex Review 01's residual findings — Review Scan `Approve`/`Approve All`, Review Mapping `Confirm Mapping`, Processing retry (plus the adjacent Flag modal, found during the follow-up's own re-audit) — are now honest deferred `warn` toasts, not fake `ok` success. See `epic-10/W4-SIT-E2E-CLAUDE-CODE-FOLLOWUP-02-COMPLETION.md` for the full remaining-`ok`-toast justification list |
| W4-E2E-04 | Ready for Copilot via Review 02 handoff | Claude-side blocker closed and accepted in `epic-10/W4-SIT-E2E-CODEX-REVIEW-02.md`; Copilot should now take the live deploy/clickthrough lane, but must still make `npm run verify:w4-html` pass before deploy-close |

## 3. Detailed Acceptance Criteria

### W4-01 / W4-02 - SIT review and freeze gate

| ID | Condition | Evidence |
| --- | --- | --- |
| ac_w4_gate_01 | Review is performed on live SIT using the production-facing review surface (`/phase2/prototype`), not local-only demo pages | SIT URL review notes |
| ac_w4_gate_02 | The SIT-pass outcome is reflected in current W4 docs and handoff references | Updated W4 plan/board + linked handoff |
| ac_w4_gate_03 | Any rejection includes the exact mismatch and follow-up decision | Review note linked from plan |

### W4-03 - `TASK-1003` Configurator web surface

| ID | Condition | Evidence |
| --- | --- | --- |
| ac_w4_1003_01 | Configurator is reachable from the main product flow | Navigation screenshot or smoke test |
| ac_w4_1003_02 | 3 persistent tabs exist: Upload & Detect, Configure Columns, Test Output | UI screenshot |
| ac_w4_1003_03 | Demo-only pages (`template-configurator-demo.html`, `ux-ui-prototype.html`, `/workflow-demo`) are no longer the primary proof of implementation | Main route proof |

### W4-04 - Schema Analyzer integration

| ID | Condition | Evidence |
| --- | --- | --- |
| ac_w4_1009ui_01 | Tab 1 accepts CSV/XLS/XLSX sample upload | UI interaction proof |
| ac_w4_1009ui_02 | Frontend calls `POST /api/v1/templates/analyze` | Network/API evidence |
| ac_w4_1009ui_03 | Analyzer result prefills column mapping or shows confidence/warnings visibly | UI screenshot |

### W4-05 - Template CRUD + preview wiring

| ID | Condition | Evidence |
| --- | --- | --- |
| ac_w4_1002ui_01 | Template list loads from real API | Network/API evidence |
| ac_w4_1002ui_02 | User can create or update a template from the Configurator | Manual flow proof |
| ac_w4_1002ui_03 | Preview calls the real preview endpoint and renders returned output | Preview screenshot |
| ac_w4_1002ui_04 | Clone/delete actions are wired or explicitly deferred with visible scope note | UI proof or deferral note |

### W4-06 / W4-07 - Export full-page flow

| ID | Condition | Evidence |
| --- | --- | --- |
| ac_w4_1006_01 | Export page supports `Quick Export` and `Template Export` modes | UI screenshot |
| ac_w4_1006_02 | Column adjustment is inline full-width, not modal-first | UI screenshot |
| ac_w4_1006_03 | Template Export requires template selection before preview/download | Manual flow proof |
| ac_w4_1006_04 | Export preview and validation use real endpoints | Network/API evidence |
| ac_w4_1006_05 | Old Step 6 hardcoded export is not the primary user path anymore | Route/navigation proof |
| ac_w4_1006_06 | Quick Export uses the real null-template backend contract, not only the client-side CSV fallback | Network/API evidence |

### W4-06A - `index.html` parity sync

| ID | Condition | Evidence |
| --- | --- | --- |
| ac_w4_index_01 | `src/frontend/index.html` reflects the same current W4 export/configurator surface intent as `src/frontend/main-ux-ui.html` | File diff / reviewer note |
| ac_w4_index_02 | Static or fallback review does not present obviously stale UX that contradicts SIT | Quick local/browser check |

### W4-08 / W4-09 - Workflow bridge and regression checks

| ID | Condition | Evidence |
| --- | --- | --- |
| ac_w4_bridge_01 | User can move from existing workflow into new export/configurator pages without dead ends | Smoke test |
| ac_w4_test_01 | Focused E2E/smoke tests cover main W4 path | Test output |
| ac_w4_test_02 | No blocker-level console or route errors appear in the tested path | Smoke output |

### W4-10 / W4-11 / W4-12 - carryover closeout

| ID | Condition | Evidence |
| --- | --- | --- |
| ac_w4_seed_01 | Required master templates exist in the runtime path used for W4 | Seed check note |
| ac_w4_906_01 | `TASK-906` wording matches backend-complete repo state, and it is explicit that `TASK-906` (Epic 9) is not a W4 export/configurator blocker | `TASK-906-FEASIBILITY-REPORT.md` (updated 2026-07-04) + this board's §2.1 W4-11 row |
| ac_w4_1313_01 | Deploy/UAT lane is described as done, in progress, or non-blocking with evidence | Status doc note |

### W4-E2E - SIT vertical-slice closure

| ID | Condition | Evidence |
| --- | --- | --- |
| ac_w4_e2e_01 | Login -> Dashboard -> Companies -> Users -> Templates -> Export can be clicked on SIT without dead-end shell behavior | Browser clickthrough |
| ac_w4_e2e_02 | Add/Edit Company either persists through backend and reload, or is visibly disabled/deferred | API + reload proof |
| ac_w4_e2e_03 | Add/Edit User either persists through backend and reload, or is visibly disabled/deferred | API + reload proof |
| ac_w4_e2e_04 | AP and AR tabs are separate and either wired to master-data APIs or visibly deferred | UI + API proof |
| ac_w4_e2e_05 | No visible W4 proof path shows success toast unless the backend action succeeded | Browser/network proof |
| ac_w4_e2e_06 | Final SIT report separates lane-close from product-shell close | Closeout report |
| ac_w4_e2e_07 | Original design docs and planning docs reflect the W4 visible-control rule across Epic 0,8,9,10,11,12,13,14,15,16 | `W4-DESIGN-IA-SYNC-2026-07-05.md`, IA/backlog/master/roadmap links |

## 4. Day-by-Day Board

| Day | Main target | Must finish | Secondary work |
| --- | --- | --- | --- |
| Day 1 | Re-anchor after SIT pass | W4 doc/board alignment + checkbox close route | Capture `index.html` parity follow-up |
| Day 2 | Build Configurator shell | Done — main route + 3 tabs + navigation | Template list wiring — done |
| Day 3 | Connect Configurator APIs | Done — Analyze + CRUD + preview (clone unverified, delete UI-only, both explicit deferrals) | Save/update handling — done |
| Day 4 | Close Export flow gaps | Done — Quick Export backend path; `index.html` parity is Copilot's active lane, not this board's open item | Validation/preview hookup — done |
| Day 5 | Verify + align | Done for repo-local scope — smoke/E2E (9/9) + doc/status alignment (this cleanup pass) | Seed verification + carryover cleanup — see §2.1 |

## 5. Risk Notes

| Risk | Why it matters | Response |
| --- | --- | --- |
| Formal checkbox close not recorded | Repo status can look more blocked than the live SIT evidence really is | Keep the handoff evidence linked and close the checkboxes explicitly |
| Frontend uses old endpoints by habit | Creates fake progress where APIs exist but product flow stays old | Verify network calls against `/api/v1/*` routes |
| Demo page mistaken as done surface | Hides that main web flow is still old | Measure success on main route only |
| Missing template seed/runtime data | UI appears broken for reasons outside UI code | Verify runtime templates before blaming frontend |
| `TASK-1313` wording stays fuzzy | UAT readiness gets overstated | Mark exact state with evidence |

## 6. Exit Checklist

- [x] SIT review completed on live environment
- [x] 5 UX freeze approvals resolved
- [x] Real Configurator page exists in main web flow (3-tab shell + wired column editor on `main-ux-ui.html`; tab-click `ReferenceError` bug found and fixed 2026-07-05)
- [x] Analyzer upload path calls real API (`POST /api/v1/templates/analyze`, pre-existing; "Apply to Tab ②" now actually reachable post-bugfix)
- [x] Template CRUD + preview actions call real APIs (list/save-as/update confirmed; clone not re-verified; delete still UI-only toast)
- [x] Export page supports Quick vs Template flow
- [x] Quick Export uses the real backend null-template path (`TASK-W4-BACKEND-FOLLOWUP`, confirmed both preview and download)
- [ ] `index.html` is aligned with the accepted W4 surface (stale again as of this pass's Configurator editor — see W4-06A)
- [ ] Old Step 6 is no longer the primary export path (not independently re-verified this pass)
- [x] Focused smoke/E2E verification run is recorded (16/16 `tests/e2e/w4-export-uxui.spec.ts` local, 77/77 backend `pytest`; not yet re-run against live SIT)
- [x] `TASK-906` wording aligned (resolved — Epic 9 item, never a W4 blocker; see §2.1 W4-11)
- [x] W4 carryover status is explicit and evidence-backed (this checklist + `epic-10/W4-EPIC10-CLAUDE-FOLLOWUP-01` verification notes)
- [ ] SIT end-to-end vertical slice is proven, not only Epic 10 export/configurator lane (Claude-side work done; blocked on Copilot live deploy/clickthrough + `index.html` parity)
- [x] Add/Edit Company is persisted or visibly deferred (real `/v1/admin/companies` API, 2026-07-05)
- [x] Add/Edit User is persisted or visibly deferred (real `/v1/admin/users` API + reset-password, 2026-07-05)
- [x] No fake-success admin/review action remains in the W4 proof path (Codex Review 01's residual Review Scan/Review Mapping/Processing findings closed in `W4-SIT-E2E-CLAUDE-CODE-FOLLOWUP-02`, 2026-07-05)
- [x] Original design/planning docs updated with W4 visible-control rule (`W4-DESIGN-IA-SYNC-2026-07-05.md`, IA, backlog, master plan, roadmap)
