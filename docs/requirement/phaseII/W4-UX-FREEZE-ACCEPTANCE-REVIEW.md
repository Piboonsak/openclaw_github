# W4 UX-Freeze Acceptance Review — Export + Configurator

> Lane: UX / acceptance (no deploy/runtime work)
> Reviewer: Claude (Opus 4.8) · Date: 2026-07-04
> Source package: `UX-FREEZE-EXPORT-CONFIGURATOR.md`, `W4-EXECUTION-PLAN.md`, `W4-TASK-BOARD.md`,
> `TEMPLATE-COVERAGE-ASSESSMENT-2026-07-04.md`, `PHASE-II-PROTOTYPE.html` (reference),
> `src/frontend/main-ux-ui.html` (production-facing W4 surface)
> Purpose: close the approval gate for `TASK-1003` / `TASK-1006` and hand engineering unambiguous acceptance wording.

**Status legend**
- **PASS** — frozen design is clear, complete, implementable as-is; no product decision needed.
- **UNCLEAR** — a genuine ambiguity/internal contradiction in the frozen spec must be resolved before coding.
- **FAIL** — a conflicting artifact (reference / production / canonical task doc) blocks approval until reconciled.

---

## 1. Approval Checklist

| # | Approval item (freeze §9) | Status | Evidence | Exact clarification needed (if not PASS) |
|---|---------------------------|--------|----------|------------------------------------------|
| 1 | Export page has two paths: **Quick Export** (all fields, no transforms, xlsx) and **Template Export** (template-driven, full column adjust, csv/xlsx) | **UNCLEAR** | Freeze Decision 1 + Screen A + data contract §5 are complete. BUT approval text says Quick = "xlsx", while Decision 1 body says Quick Export format is user-selectable ("CSV หรือ Excel … เลือกได้เหมือนกัน. Default: Excel"). Two-path also absent from prototype + `main-ux-ui.html`. | **Resolve format-lock:** Quick Export format+encoding are **user-selectable, default `.xlsx` / UTF-8** (not xlsx-locked). Adopt this wording; the "xlsx" in the checkbox = default only. |
| 2 | Export Step ① shows **mode picker** (Quick vs Template) after document selection | **PASS** | Screen A specifies exact placement, two cards, and card copy. Implementable without further decision. | — (surface not yet built; that is TASK-1006 implementation, not a spec gap) |
| 3 | Column adjust panel is **inline full-width** on Export page (**not modal**), per-run by default, with optional Save/Update Template | **UNCLEAR** | Freeze Decision 2 is explicit (inline, not modal, ephemeral). BUT (a) production surface forces a **modal** (`main-ux-ui.html:2930` `modal-export-preview`), and (b) the **encoding identifier set is inconsistent** across docs (see M3). | **Confirm inline supersedes the modal** (remove modal-first behavior). **Canonicalize encoding enum** — API values `utf-8` / `utf-8-sig` / `cp874`, UI labels `UTF-8` / `UTF-8 BOM` / `TIS-620` (fixed mapping). |
| 4 | **Template Configurator 3-tab** (persistent setup only, separate page, via "Manage Templates →") | **PASS** | Freeze Decision 3 + Screen B fully specify the 3 tabs, contents, and round-trip rules. | — (Note: canonical `TASK-1003` in EPIC-10 is pre-freeze and must be superseded — see §3 and mismatch M4.) |
| 5 | **TASK-1009 Schema Analyzer** promoted ahead of TASK-1001/1003/1006 | **PASS** | W4 plan confirms `TASK-1009` backend + API exist and targeted tests pass ("Confirmed green in code/repo now"). Sequencing satisfied. | — (Frontend Tab-① wiring = W4-04, still pending implementation, not an approval gap.) |

**Gate outcome:** 3 PASS, 2 UNCLEAR, 0 FAIL. Items 1 and 3 are cleared by adopting the resolutions above (no product debate required — the freeze body already implies them; the checkbox text and a stale modal are the only conflicts). After adopting them, all 5 are approvable.

---

## 2. Mismatch List (frozen intent vs prototype / production / canonical docs)

| ID | Frozen intent | Conflicting artifact | Resolution |
|----|---------------|----------------------|------------|
| M1 | Screen A: two-path export + Step-① mode picker | Absent from `PHASE-II-PROTOTYPE.html` **and** `main-ux-ui.html` (single export flow only) | Build new per Screen A. **Do not treat the prototype export screen as the target.** |
| M2 | Decision 2: column/preview step is **inline full-width, not modal** | `main-ux-ui.html:2930` `modal-export-preview` ("กด Download ครั้งแรกจะเข้าหน้านี้ก่อนเสมอ…") | Replace modal-first flow with inline Step ③. Retire the modal as the primary path. |
| M3 | Encoding set | Freeze §5 contract: `utf-8` / `utf-8-sig` / `cp874`; freeze screens + `main-ux-ui.html`: `UTF-8` / `UTF-8 BOM` / `TIS-620`; `TASK-1001`: `utf-8` / `utf-8-bom` / `tis-620` | Adopt one canonical enum (API `utf-8`/`utf-8-sig`/`cp874`, UI `UTF-8`/`UTF-8 BOM`/`TIS-620`). Backend confirms stored value. |
| M4 | `TASK-1003` = 3-tab persistent Configurator on `main-ux-ui.html` | Canonical EPIC-10 `TASK-1003`: one-panel Manager in `ux-ui-prototype.html`, transform list missing new transforms, no Upload&Detect / round-trip. Its `ac_1003_*` would drive the OLD design. | Supersede with §3 acceptance wording below. |
| M5 | `TASK-1006` = full-page two-path flow | Canonical EPIC-10 `TASK-1006`: single "template selector dropdown on export screen," no mode picker, no inline-panel requirement. `ac_1006_*` lacks mode-switch + inline criteria. | Supersede with §4 acceptance wording below. |
| M6 | Quick Export format | Approval checkbox "xlsx" vs Decision 1 "selectable, default Excel" | Selectable; default `.xlsx` / UTF-8 (see item 1). |
| M7 | Round-trip Save gating | Tab ③ button "Save Template (ผ่านทุก check)" reads as "all checks pass"; §6 says only `column_count` + `header_match` block | Only `column_count` + `header_match` block Save; encoding/date/row are warning/info; no-sample → always saveable. |

---

## 3. Final Acceptance Wording — TASK-1003 (Template Configurator UI)

**Scope (supersedes EPIC-10 TASK-1003):** Build the Template Configurator as a **3-tab, persistent-setup page** on `src/frontend/main-ux-ui.html`, reachable via "Manage Templates →" (Export page) and the Admin menu, wired to real `TASK-1002` (CRUD/preview) and `TASK-1009` (analyze) APIs. Demo pages are reference only.

| ID | Acceptance condition |
|----|----------------------|
| ac_1003_r1 | Configurator is a **separate persistent page** (not the per-run export panel); reachable from Export "Manage Templates →" and Admin menu; edits here persist to DB. |
| ac_1003_r2 | Exactly **3 tabs in order**: ① Upload & Detect · ② กำหนด Columns (Configure) · ③ ทดสอบ Output (Test). |
| ac_1003_r3 | **Tab ①**: accepts `.csv/.xlsx/.xls`; calls `POST /api/v1/templates/analyze`; renders column-mapping table with confidence; columns `<80%` highlighted; `[Apply to Column Config → Tab ②]` prefills Tab ②; `[Skip]` allowed. |
| ac_1003_r4 | **Tab ②**: Available Fields / Selected Columns two-panel; drag-reorder (SortableJS OK); inline rename `header_label`; per-column transform selector including new transforms (`thai_date_short`, `thai_date_full`, `prefix:X`, `doc_number`, `pad_left`, `strip_dash`, `uppercase`); format / encoding / delimiter selectors. Persists via `POST`/`PUT /api/v1/templates`. |
| ac_1003_r5 | **Tab ③**: round-trip proof vs Tab-① sample; shows 5 checks; **Save blocked only when `column_count` OR `header_match` fail**; no sample uploaded → structural-only, **Save always allowed**; other checks are warning/info. |
| ac_1003_r6 | **Template Manager**: lists master + company templates grouped; Clone / Edit / Preview / Delete wired to `TASK-1002`; Preview calls `POST /api/v1/templates/{id}/preview` and renders returned rows. |
| ac_1003_r7 | Proof surface is the `/phase2/prototype` route backed by `main-ux-ui.html` — **not** `template-configurator-demo.html`, `ux-ui-prototype.html`, or `/workflow-demo`. |

---

## 4. Final Acceptance Wording — TASK-1006 (Export Page)

**Scope (supersedes EPIC-10 TASK-1006):** Replace the old step-6 / single-path export with the frozen **full-page two-path flow** on `src/frontend/main-ux-ui.html`, wired to `/api/v1/export`, `/api/v1/export/preview`, `/api/v1/export/validate`.

| ID | Acceptance condition |
|----|----------------------|
| ac_1006_r1 | **Step ①**: after document selection, page shows a **mode picker** with two cards — ⚡ Quick Export, 📋 Template Export. Selecting a card branches the flow. |
| ac_1006_r2 | **Quick Export path**: ① Docs+Mode → ② Adjust Columns (all fields pre-selected, no transform column) → ③ Preview → ④ Download. Format + encoding **user-selectable, default `.xlsx` / UTF-8**. Sends `template_id:null` + `column_overrides` to `POST /api/v1/export`. |
| ac_1006_r3 | **Template Export path**: ① Docs+Mode → ② Select Template → ③ Adjust Columns/Data → ④ Preview → ⑤ Download. **Template selection required before Preview/Download.** |
| ac_1006_r4 | **Step ③ column panel is INLINE full-width on the page — not a modal.** Per-run edits **ephemeral by default**; `[💾 Save as Company Template]` and `[↺ Update Template]` persist via `TASK-1002`; the saved template is **unchanged** when only per-run overrides are applied. |
| ac_1006_r5 | **Preview (Step ④)** calls `POST /api/v1/export/preview`; shows balance banner (Balanced / Unbalanced with delta + offending documents). |
| ac_1006_r6 | **Balance validation**: unbalanced vouchers block the normal download; only an explicit risk-acknowledged action (admin force-confirm) may proceed, listing affected vouchers. |
| ac_1006_r7 | **Download** uses `POST /api/v1/export` returning a file (`Content-Disposition: attachment`); template exports use filename pattern `express_{book}_{YYMM}.csv`. |
| ac_1006_r8 | Old modal-first export (`modal-export-preview`) and `/api/export-excel` are **no longer the primary path**. |

---

## 5. Implementation Guardrails

### Must stay fixed (do not vary — re-approval required to change)
- Two **independent** export paths + a Step-① **mode picker**.
- Step-③ column panel is **inline full-width, never a modal**.
- Per-run overrides are **ephemeral by default**; the saved template is untouched unless the user explicitly Saves/Updates.
- Configurator = **3 tabs, persistent, separate page**; Export Step ③ = **per-run tuning**. Do **not** merge the two surfaces.
- Round-trip **blocking checks limited to `column_count` + `header_match`**; no-sample → always saveable.
- **Real APIs only** (`/api/v1/templates*`, `/api/v1/export*`). Not `/api/export-excel`, not mock data.
- Proof surface = `/phase2/prototype` (`main-ux-ui.html`), never a demo page.
- **Encoding canonical enum** (fixed mapping): API `utf-8` / `utf-8-sig` / `cp874` ↔ UI `UTF-8` / `UTF-8 BOM` / `TIS-620`.
- Express date columns default to `thai_date_short` and are written as **text** (no Excel auto-reformat).

### May vary (engineering discretion)
- Component/drag-drop library (SortableJS acceptable), styling, spacing, iconography, microcopy.
- Whether "Adjust Columns" and "Preview" are two discrete steps or one inline scroll — **as long as** inline + not-modal + preview-before-download hold.
- Preview row count (5–10 rows is fine).
- Client- vs server-side rendering of the preview, as long as it renders the real preview-endpoint output.
- Ordering/grouping of the Available Fields categories.

---

## Appendix — Customer-safe product wording vs engineering notes

**Customer-safe (product owner / client language):**
- "Export now has two ways to get data out: a fast **Quick Export** to Excel, and a **Template Export** that formats data for Express / LoveBot / tax filing."
- "You adjust columns right on the export page before downloading; changes apply to that download only unless you choose to save them as a template."
- "Templates are set up once (upload a sample file, confirm the columns, test the output), then reused."

**Engineering-only (do not surface to customer):**
- Modal→inline migration, encoding-enum canonicalization, `/api/export-excel` retirement, `template_id:null` Quick-Export contract, stale EPIC-10 acceptance criteria being superseded, and the round-trip blocking-check subset.
