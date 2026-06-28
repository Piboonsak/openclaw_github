# W3 Codex UX / Frontend Execution Plan

> Scope owner: Codex
> Date: 2026-06-28
> Repo: `YAHWAN-SHOP/ai-accounting-copilot`
> Branch: `dev`

This note keeps the W3 agent split explicit so Codex work does not collide with Claude Code backend work or GitHub Copilot SIT/deploy work.

## Ownership Boundary

| Lane | Owner | Scope | Codex action |
| --- | --- | --- | --- |
| Complex backend | Claude Code | TASK-1009 backend/API/tests, then TASK-1001 Template Engine | Consume API contracts after Claude reports green tests |
| UX/frontend | Codex | UX freeze, prototype/frontend flows, Playwright checks, frontend acceptance mapping | Own |
| Infra/deploy | GitHub Copilot | TASK-1306A SIT runtime, deploy/smoke scripts, control-plane alignment | Do not edit unless asked |

## Current Gate

Codex must not implement TASK-1003 or TASK-1006 UI until:

1. `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` has all 5 approval items checked and committed.
2. SIT runtime validation evidence is green for the export/template flow.
3. Claude Code reports TASK-1009 backend/API/tests are complete enough for frontend integration.

While the approval gate is pending, Codex can safely do:

1. Keep UX freeze wording internally consistent.
2. Prepare frontend task breakdown and acceptance mapping.
3. Review prototype feasibility without changing production behavior.
4. Prepare Playwright test scenarios as a checklist or draft only.
5. Keep the W3 customer-facing/decision reports current, especially TASK-906.

## Codex Task List

| Priority | Task | Status | Files / surface | Exit criteria |
| --- | --- | --- | --- | --- |
| P0 | UX freeze consistency check | Done | `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` | Gate count, task order, and wording are consistent |
| P0 | Frontend implementation map for TASK-1003/TASK-1006 | Ready after approval | `src/frontend/ux-ui-prototype.html`, `src/frontend/ux-ui-prototype.css`, `src/frontend/main.js`, or a new prototype page if lower risk | UI paths match frozen Screen A/B |
| P0 | Schema Analyzer UI handoff contract | Blocked by Claude TASK-1009 | Template Configurator Tab 1 | Upload result can prefill column mapping once API exists |
| P0 | TASK-906 interim feasibility report | Done | `docs/PoC/reports/TASK-906-FEASIBILITY-REPORT.md` | Report reflects available W3 artifacts without claiming final locked accuracy |
| P1 | Playwright scenario plan | Draftable now | `tests/e2e/*` | Scenarios cover Quick Export, Template Export, Configurator 3 tabs, and apply-to-configurator |
| P1 | Mobile/responsive pass | Out of current freeze, later | Prototype/frontend CSS | No overlap/overflow on key desktop/mobile widths |

## Week 3 Codex Work Board

| Work item | Can do now? | Blocker | Output |
| --- | --- | --- | --- |
| Finalize UX freeze approval wording | Yes | PO must approve checkboxes | `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` |
| Maintain Codex frontend plan | Yes | None | This file |
| TASK-906 interim feasibility report | Yes | Final locked ground truth still pending | `docs/PoC/reports/TASK-906-FEASIBILITY-REPORT.md` |
| Export/configurator UI implementation | No | PO approval + SIT evidence + backend API contract | `src/frontend/*` after gates pass |
| W3 Playwright implementation | No | UI implementation must exist first | `tests/e2e/w3-export-configurator.spec.ts` after gates pass |
| Mobile/responsive polish | No | UI implementation must exist first | CSS/frontend patch after gates pass |

Codex should use this order when gates clear:

1. Implement full-page Export shell with mode picker and inline adjustment panel.
2. Implement 3-tab Template Configurator shell and mocked analyzer result display.
3. Wire frontend to real TASK-1009/TASK-1001 endpoints once Claude backend is stable.
4. Add Playwright coverage and screenshots.

## Acceptance Mapping

### TASK-1003: Template Configurator UI

- `ac_1003_tabs`: 3 persistent tabs exist: Upload & Detect, กำหนด Columns, ทดสอบ Output.
- `ac_1003_detect`: Tab 1 uploads sample CSV/Excel and displays mapping confidence.
- `ac_1003_columns`: Tab 2 supports reorder, rename, show/hide, transform, encoding, and format.
- `ac_1003_roundtrip`: Tab 3 shows round-trip result and blocks save on column count/header mismatch.
- `ac_1003_manage_link`: Export page links to Template Configurator through "Manage Templates ->".

### TASK-1006: Export Full-Page Workflow

- `ac_1006_mode`: Step 1 selects documents and chooses Quick Export vs Template Export.
- `ac_1006_quick`: Quick Export has no template selection and no transforms; all fields preselected.
- `ac_1006_template`: Template Export requires template selection before column adjustment.
- `ac_1006_adjust_inline`: Column adjustment is inline full-width, not a modal.
- `ac_1006_persist_options`: Per-run changes are ephemeral by default, with Save as Company Template and Update Template options.
- `ac_1006_preview_download`: Preview and download work for CSV/XLSX once backend endpoints exist.

## Current Frontend Feasibility Notes

- `src/frontend/ux-ui-prototype.html` still uses a 6-step workflow where Step 6 is an embedded "Export Express GL" panel. TASK-1006 should move export into a full-page workflow, leaving the 6-step review flow as the upstream path.
- The current Step 6 has checkbox-based column toggles and hardcoded download buttons. It does not yet support Quick Export vs Template Export, inline per-run column adjustment, template selection, encoding selection, or save/update template actions.
- `src/frontend/template-configurator-demo.html` already demonstrates template list/edit behavior, drag/drop-ish column editing, rename, field picker, preview, and save actions. It is a useful source, but TASK-1003 needs a new 3-tab persistent setup structure rather than simply reusing the existing one-panel editor.
- Existing Playwright coverage only checks page health, static assets, stepper render, console errors, and screenshots. W3 needs a separate spec focused on export/configurator behavior.
- Because the frontend is currently HTML + vanilla JS, the lowest-risk implementation path is to add a new full-page export/configurator surface first, then link it from the existing Step 5/Step 6 area after product approval.

## Do Not Touch In Codex Lane

- `docker/**`, `scripts/deploy/**`, `.github/workflows/bwcacc-deploy-uat.yml`: Copilot TASK-1306A.
- `src/backend/auth/**`, `src/backend/ml/**`: forbidden by current task scope.
- `src/backend/services/schema_analyzer.py`, `src/backend/api/**`: Claude TASK-1009 unless explicitly reassigned.
- Real deploy, SSH mutation, or Openclaw workflow dispatch.

## Draft Playwright Scenarios

These are draft scenarios only until the UX freeze is approved and the frontend surface is implemented.

| Scenario | Route | Checks |
| --- | --- | --- |
| `export_mode_picker_visible` | `/prototype` or new export route | User can reach Export from post-review workflow; Step 1 shows Quick Export and Template Export choices |
| `quick_export_adjust_columns` | Export page | Quick path skips template selection, shows all fields selected, hides transform selector, keeps format and encoding controls visible |
| `template_export_select_template` | Export page | Template path requires a template, shows Manage Templates link, then opens inline column adjustment |
| `export_adjust_is_inline` | Export page | Column adjustment panel is in page flow, not a modal; Save as Company Template and Update Template actions are visible |
| `template_configurator_tabs` | Template Configurator | Upload & Detect, กำหนด Columns, and ทดสอบ Output tabs are visible and switchable |
| `schema_analyzer_apply_to_configurator` | Template Configurator | Mocked analysis response fills mapped columns with confidence badges |
| `round_trip_blocks_save` | Template Configurator | Column count/header mismatch blocks Save Template; encoding/date warnings do not block save |
| `desktop_mobile_no_overlap` | Export + Configurator | Key controls do not overlap at desktop and mobile widths |

Existing E2E baseline:

- `tests/e2e/demo-smoke.spec.ts` checks the current demo root page, stepper, CSS, and console errors.
- `tests/e2e/poc-smoke.spec.ts` checks `/health`, `/api/health`, `/prototype`, `/phase2`, `/phase2/timeline`, and `/phase2/prototype`.
- New W3 tests should be added as a separate spec after implementation, e.g. `tests/e2e/w3-export-configurator.spec.ts`.

## Next Codex Action After Approval

1. Patch the prototype/frontend for the frozen 2-path export page and 3-tab configurator.
2. Add focused Playwright checks for navigation and visible states.
3. Run frontend smoke/E2E locally and report gaps separately from backend/API blockers.
