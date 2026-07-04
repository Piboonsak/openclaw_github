# W4 Task Board

> Week: W4 (6 Jul 2026 - 12 Jul 2026)
> Purpose: execution board for owners, dependencies, acceptance criteria, and proof
> Use with: `docs/requirement/phaseII/W4-EXECUTION-PLAN.md`

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
| W4-01 | P0 | Codex + PO | Live SIT review | SIT reachable | Reviewed flow on live SIT | Review notes + checkbox outcome |
| W4-02 | P0 | Codex + PO | Resolve 5 UX freeze approvals | W4-01 | Approved or explicitly rejected freeze items | Updated `UX-FREEZE-EXPORT-CONFIGURATOR.md` |
| W4-03 | P0 | Codex | `TASK-1003` Configurator web surface | W4-02 | Real Configurator page reachable from product flow | Route + screenshots + smoke pass |
| W4-04 | P0 | Codex | Schema Analyzer UI integration | W4-03 | Upload sample -> analyze -> prefill mapping | API call evidence + visible prefill |
| W4-05 | P0 | Codex | Template CRUD + preview UI wiring | W4-03 | List/create/edit/delete/clone/preview on real page | Manual flow proof + targeted tests |
| W4-06 | P1 | Codex | `TASK-1006` Export full-page flow | W4-03, W4-04, W4-05 | Quick Export / Template Export page | Route + visible mode switch |
| W4-07 | P1 | Codex | Export preview + validation hookup | W4-06 | Inline preview and validation in export flow | API call evidence + UI message states |
| W4-08 | P1 | Codex | Main workflow bridge | W4-03, W4-06 | Existing workflow links into new pages cleanly | Navigation test |
| W4-09 | P1 | Codex | Focused E2E / smoke pack | W4-03 through W4-08 | Regression coverage for core W4 paths | Passing test run |
| W4-10 | P1 | Codex | Master template seed verification | Runtime ready | Needed templates present for W4 flow | Seed/runtime check notes |
| W4-11 | P1 | Codex | `TASK-906` wording alignment | W4 implementation status known | Report reflects actual repo state | Doc diff |
| W4-12 | P2 | Copilot | `TASK-1313` status/evidence cleanup | Deploy lane evidence | UAT/deploy messaging is unambiguous | Updated task/status note |

## 2.1 Current Status After Epic Review

| Work item | Status | Note |
| --- | --- | --- |
| W4-01 | In progress | live SIT edge is reachable and auth-protected (`401` without credentials), but credentialed PO review is still pending |
| W4-02 | Pending | all 5 approval items are still unchecked in repo |
| W4-03 | Blocked by approval gate | proceed only after W4-02 is resolved |
| W4-04 | Blocked by approval gate | API exists, but frontend integration should follow the same gate |
| W4-05 | Blocked by approval gate | template APIs exist; main web flow wiring is still pending |
| W4-06 | Blocked by approval gate | export flow work is still anchored to the old Step 6 behavior in the legacy workflow demo, not yet the new full-page W4 path |
| W4-09 | Ready after UI work starts | smoke/E2E should follow the new surfaces, not the old demo path |
| W4-10 | Baseline verified | repo seed test passes for `Express GL` and `Purchase Tax`; wider Express template coverage still needs runtime/flow verification |
| W4-12 | Non-blocking for W4 UI | deploy/UAT-readiness lane, not the direct UI gate |

## 3. Detailed Acceptance Criteria

### W4-01 / W4-02 - SIT review and freeze gate

| ID | Condition | Evidence |
| --- | --- | --- |
| ac_w4_gate_01 | Review is performed on live SIT using the production-facing review surface (`/phase2/prototype`), not local-only demo pages | SIT URL review notes |
| ac_w4_gate_02 | All 5 freeze items are marked approved or rejected explicitly | Updated checkbox section |
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
| ac_w4_906_01 | `TASK-906` wording matches backend-complete repo state | Doc diff |
| ac_w4_1313_01 | Deploy/UAT lane is described as done, in progress, or non-blocking with evidence | Status doc note |

## 4. Day-by-Day Board

| Day | Main target | Must finish | Secondary work |
| --- | --- | --- | --- |
| Day 1 | Clear gate | SIT review + 5 checkbox resolution | Capture exact mismatches if any |
| Day 2 | Build Configurator shell | Main route + 3 tabs + navigation | Start template list wiring |
| Day 3 | Connect Configurator APIs | Analyze + CRUD + preview | Save/update/clone handling |
| Day 4 | Build Export page | Quick/Template modes + inline adjust | Validation/preview hookup |
| Day 5 | Verify + align | Smoke/E2E + doc/status alignment | Seed verification + carryover cleanup |

## 5. Risk Notes

| Risk | Why it matters | Response |
| --- | --- | --- |
| Gate not truly approved | W4 UI can drift from agreed UX again | Do not start coding before checkbox resolution |
| Frontend uses old endpoints by habit | Creates fake progress where APIs exist but product flow stays old | Verify network calls against `/api/v1/*` routes |
| Demo page mistaken as done surface | Hides that main web flow is still old | Measure success on main route only |
| Missing template seed/runtime data | UI appears broken for reasons outside UI code | Verify runtime templates before blaming frontend |
| `TASK-1313` wording stays fuzzy | UAT readiness gets overstated | Mark exact state with evidence |

## 6. Exit Checklist

- [ ] SIT review completed on live environment
- [ ] 5 UX freeze approvals resolved
- [ ] Real Configurator page exists in main web flow
- [ ] Analyzer upload path calls real API
- [ ] Template CRUD + preview actions call real APIs
- [ ] Export page supports Quick vs Template flow
- [ ] Old Step 6 is no longer the primary export path
- [ ] Focused smoke/E2E verification run is recorded
- [ ] `TASK-906` wording aligned
- [ ] W4 carryover status is explicit and evidence-backed
