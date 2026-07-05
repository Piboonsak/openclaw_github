# UX Freeze — Final Status & Codex Continuation Handoff

> **Purpose**: Close out the UX-freeze review/implementation lane and hand the remaining `TASK-1003`/`TASK-1006` work to Codex (owner per `W4-TASK-BOARD.md` §1 Owner Model).
> **Written by**: Claude (Opus 4.8) · **Date**: 2026-07-05
> **Source docs**: `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`, `docs/requirement/phaseII/W4-UX-FREEZE-ACCEPTANCE-REVIEW.md`, `docs/requirement/phaseII/W4-EXECUTION-PLAN.md`, `docs/requirement/phaseII/W4-TASK-BOARD.md`

---

## 1. UX Freeze — final resolution

`docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` §9 lists 5 approval items. Acceptance review (`W4-UX-FREEZE-ACCEPTANCE-REVIEW.md`, 2026-07-04) resolved all 5:

| # | Approval item | Result | Resolution |
| --- | --- | --- | --- |
| 1 | Two paths: Quick Export (all fields, no transforms) / Template Export | Resolved | Quick Export format+encoding are **user-selectable, default `.xlsx`/UTF-8** — the "xlsx" in the checkbox text is a default, not a lock. |
| 2 | Step ① mode picker (Quick vs Template) | PASS as specified | No change needed. |
| 3 | Column adjust panel **inline, not modal**, per-run, Save/Update | Resolved | Inline supersedes the old modal. Canonical encoding enum fixed: API `utf-8`/`utf-8-sig`/`cp874` ↔ UI `UTF-8`/`UTF-8 BOM`/`TIS-620`. |
| 4 | Configurator 3-tab persistent setup | PASS as specified | No change needed (not yet built — see §3 below). |
| 5 | Schema Analyzer (`TASK-1009`) promoted ahead of 1001/1003/1006 | PASS | Backend already green per W4 plan. |

**Rewritten acceptance criteria** for `TASK-1003` (`ac_1003_r1`–`r7`) and `TASK-1006` (`ac_1006_r1`–`r8`) are in `W4-UX-FREEZE-ACCEPTANCE-REVIEW.md` §3–§4 — these supersede the stale pre-freeze criteria in `EPIC-10-TASKS-DETAIL.md`.

**Outstanding formality**: the 5 `☐` checkboxes in `UX-FREEZE-EXPORT-CONFIGURATOR.md` §9 are still unchecked in the file — per that doc's own rule, only the product owner marks them `✅` with a date. This handoff and the acceptance review together are the evidence; the checkbox commit itself was intentionally left for the product owner to do explicitly, not auto-applied by an agent.

## 1.1 SIT UX/UI review update (2026-07-05)

SIT deploy and runtime verification have now been completed via Openclaw control-plane workflow (`Deploy ai-accounting-copilot SIT`). The production-facing review surface `/phase2/prototype` is live with the W4 frontend artifact (`aa044c3`), and the reviewer-confirmed UX/UI scope below is accepted on SIT.

### 5 UX/UI gate status for Codex

| Gate | Scope | SIT result |
| --- | --- | --- |
| Gate 1 | Export menu (mode picker + inline flow) | **PASS** |
| Gate 2 | Template master cards | **PASS** |
| Gate 3 | Template by company (company template path in export flow) | **PASS** |
| Gate 4 | Company setting AP/AR separation | **PASS** |
| Gate 5 | Production review surface alignment on `/phase2/prototype` | **PASS** |

**Codex instruction from this review:** treat all 5 UX/UI gates as passed for W4 SIT review. Continue only with non-UI closure items and follow-up backend/flow wiring tasks.

---

## 2. What Claude already implemented (this pass, on `main-ux-ui.html`)

Ticket: `CLAUDE-W4-UXUI-IMPLEMENT.prompt.json`. All changes are on the production-facing surface (`src/frontend/main-ux-ui.html`, route `/phase2/prototype`), frontend-only (`src/frontend/**`, `tests/e2e/**`).

### UX-EXPORT-01 — done

- Export screen (`#s-export`) rebuilt as one full-page flow: Select Docs → **Mode picker** (`#exportModeQuickCard` / `#exportModeTemplateCard`, `setExportMode()`) → Template+format/encoding → **inline** Adjust Columns (`#exportColumnsBody`, reorder/rename/transform/show-hide/add-column) → inline Preview (`#exportPreviewInline`) → Download.
- Modal-first behavior retired: `#modal-export-preview` deleted entirely.
- The old "W4 Live Export Bridge" scaffold (real API-bound elements previously mis-parked on the **Processing** screen by an earlier pass) was moved onto the actual Export screen where the live-bound ids (`exportTemplateSelect`, `exportFormatSelect`, `exportEncodingSelect`) now belong.
- Quick Export downloads a real client-side UTF-8 CSV (`downloadQuickExportCsv()`) built from the adjusted column list — **no backend call**, because backend support for `template_id: null` + `column_overrides` (freeze doc §7) does not exist yet. This is the main open backend gap — see §3.
- Template Export keeps the exact proven request contracts (`previewExport()` / `downloadExportFile()`, already verified live against SIT in `TASK-1313`), just re-targeted to render into the inline container instead of a modal. Added real `Save as Company Template` (`POST /api/v1/templates`) and `Update Template` (`PUT /api/v1/templates/{id}`) actions.

### UX-COMPANY-01 — done

- Companies list entry relabeled from bare `COA` → `⚙️ ตั้งค่า` (reflects that the destination covers COA + AP + AR + Settings).
- Company detail: single generic vendor tab split into `AP · ผู้จำหน่าย` (existing, relabeled) and a new `AR · ลูกค้า` tab (customer master, mirrors AP structure, shaped from `private_data/poc/Comp_1/APAR/AP-CCSS.csv` / `AR-CCSS.csv`), each with its own import modal.

### UX-TEMPLATE-01 — done, narrowly scoped

- Added the 6 Express master template cards (Book 12 / 14 / 15 / 15+WHT / 22 / 24) to the Templates screen — these are already fully specified in `TASK-1004` / `CLIENT-TEMPLATE-ANALYSIS.md`. Deliberately excluded everything in the "New Scope" bucket of `TEMPLATE-COVERAGE-ASSESSMENT-2026-07-04.md` (PO/RR, multi-line, master-data imports, bank movements, Journal-RV) — those need a CR decision first, not UI work.

### Verification performed

- All 3 inline `<script>` blocks pass `node --check` (no syntax errors).
- 96 element IDs in the file, zero duplicates.
- Local static-file-server + Playwright pass (mode picker, reorder/rename/toggle, AP/AR tab switch, 8 template cards, no `modal-export-preview`) — 8/8 checks, backend-independent.
- New permanent spec `tests/e2e/w4-export-uxui.spec.ts` (5 no-login-required checks, same convention as `poc-smoke.spec.ts`) — passes locally against a static copy; will run for real once deployed to `POC_URL`/`DEMO_URL`.
- **Not done**: no re-run against live `sit.yahwan.biz` — these changes are only in the local working tree and haven't gone through the CI/CD deploy pipeline (`Piboonsak/Openclaw/.github/workflows/deploy-ai-accounting-copilot-sit.yml`). That is Copilot's deploy lane per the Owner Model, not something this pass triggered.

---

## 3. What's left for Codex

1. ~~**Deploy frontend to SIT + confirm UX/UI review scope**~~ **DONE 2026-07-05**. SIT review accepted the W4 UX/UI scope (all 5 gates PASS).
2. ~~**Backend: `column_overrides` + `template_id: null` support**~~ **DONE 2026-07-05** (`TASK-W4-BACKEND-FOLLOWUP`). `POST /api/v1/export/preview` now supports null-template Quick Export contract.
3. ~~**Wire Quick Export frontend to real backend path**~~ **DONE 2026-07-05**. `previewExport()`/`downloadExportFile()` now call the real endpoints for both modes; the client-side CSV fallback (`downloadQuickExportCsv`/`renderQuickPreview`) was dead code and has been deleted (see `W4-EPIC10-CLAUDE-FOLLOWUP-01`).
4. ~~**Template Configurator 3-tab rebuild**~~ **IN PROGRESS, real progress 2026-07-05** — 3-tab shell + a genuinely wired column editor (shared `state.exportColumns` with the Export screen) now exist on `main-ux-ui.html`, not a single-page builder. A real bug was found and fixed in the same pass: every Configurator tab button and several actions were declared inside a `"use strict"` IIFE and never exposed on `window`, so every inline `onclick=""` threw `ReferenceError` on a real click — the whole 3-tab surface was non-functional despite looking wired. Fixed; see `W4-TASK-BOARD.md` row W4-03 and `W4-EPIC10-CLAUDE-FOLLOWUP-01` verification. Still open: full `ac_1003_r1`–`r7` acceptance pass, and `index.html` needs re-resyncing (it predates this Configurator change).
5. **PO checkbox sign-off**: product owner to mark 5 freeze checkboxes (`☐` → `✅`) in `UX-FREEZE-EXPORT-CONFIGURATOR.md` §9 with date as formal close. *(Note: `W4-TASK-BOARD.md` §2.1 W4-02 already reports this as done with a 2026-07-05 date — reconcile which is authoritative before treating this as still open.)*
6. **AP/AR backend follow-up**: AR (customer) tab remains UI-only demo data; backend customer-master API/import parser is still needed for production behavior.

## 4. File map for Codex

| File | Role |
| --- | --- |
| `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` | Frozen design source of truth (§9 = pending PO checkboxes) |
| `docs/requirement/phaseII/W4-UX-FREEZE-ACCEPTANCE-REVIEW.md` | Rewritten acceptance criteria for TASK-1003/1006 |
| `src/frontend/main-ux-ui.html` | Production-facing surface — this pass's implementation target |
| `tests/e2e/w4-export-uxui.spec.ts` | New static regression coverage for this pass |
| `tests/e2e/sit-clickthrough.spec.ts` | Live SIT click-through harness — re-run after deploy |

---

*Created: 2026-07-05*
*Author: Claude Opus 4.8*
