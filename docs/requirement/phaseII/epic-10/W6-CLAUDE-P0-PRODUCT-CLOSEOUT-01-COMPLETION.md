# W6-CLAUDE-P0-PRODUCT-CLOSEOUT-01 — Completion Report

> Task: `TASK-W6-CLAUDE-P0-PRODUCT-CLOSEOUT-01`
> Tracking tag: `W6-CLAUDE-P0-PRODUCT-CLOSEOUT-01`
> Branch: `dev`
> Date: 2026-07-19
> Source of truth: `docs/requirement/phaseII/W5-HUMAN-REVIEW-REGRESSION-ISSUES-07.md` (HR-17 addendum),
> `docs/requirement/phaseII/W6-CLOSEOUT-DECISION-BUNDLE-2026-07-19.md`, `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`.

## Summary

All five repo-owned W6 P0 work items are implemented (product behavior patched, not just analyzed),
kept aligned to the frozen production-facing UI, covered by focused regression tests, and mirrored into
the static `index.html` fallback for parity.

Key discovery during scoping: **much of the backend was already capable** — `/v1/export` and
`/v1/export/preview` already accepted `document_ids`; the `Document` model already had all four party
columns; line items already carried a `status`; and the export/CSV writer already had Excel-safe date
logic. Most gaps were frontend wiring plus small backend schema/column additions. Two items required
genuinely new backend surface (master-data soft-delete endpoints, and the `template_mode` column +
granularity wiring), per the product owner's decision to go deeper than honest-disabled.

## Work items

### W6-C1-01 — Export document selection (HR-17-05)  ✅ Done
- Added per-row checkboxes, a **Select All / Clear** header checkbox (with indeterminate state), and a
  live **"เลือก N จาก M เอกสาร · ฿total"** summary to the Export document table.
- Selection state (`state.exportSelectedDocIds`) now feeds `document_ids` into both `/v1/export/preview`
  and `/v1/export`. Empty-selection is blocked with a clear toast.
- Backend already filtered by `document_ids`; the frontend previously always sent only `company_id`, so
  every export dumped all `mapping_confirmed` docs.
- Files: `src/frontend/main-ux-ui.html` (`renderExportDocuments`, `getSelectedExportDocIds`,
  `toggleExportSelectAll`, `previewExport`, `downloadExportFile`).
- Tests: `tests/services/test_export_dataset.py::TestDocumentIdSelection` — a fake session that honors the
  `Document.id IN (...)` WHERE clause proves a subset selection exports only the selected docs (would fail
  if the `document_ids` filter were removed).

### W6-C1-02 — Review Scan party fields + line-item decisions (HR-17-02, HR-17-04)  ✅ Done
- **Party fields (HR-17-02):** Review Scan now shows **seller name + seller tax ID + buyer name + buyer
  tax ID** together; not-extracted party fields are flagged `⚠ ไม่พบข้อมูล` instead of being silently
  omitted. `seller_tax_id` and `buyer_name` were added to `DocumentResponse`, `DocumentFieldsUpdateRequest`,
  and the editable allow-list so corrections persist (with `FieldCorrection` audit rows).
- **Line-item decisions (HR-17-04):** per-line **confirm / reject / unconfirm** controls added to each
  line-item row via a new `POST /v1/documents/{id}/line-items/{line_item_id}/decision` endpoint. The
  button for the current status is disabled so the active state is obvious.
- **Approve includes line items:** `approve_document` now confirms still-pending line items on
  Approve / Approve All (rejected items stay rejected); toasts state this explicitly.
- Files: `src/backend/api/schemas/document_schemas.py`, `src/backend/api/documents.py`,
  `src/backend/services/document_workflow.py`, `src/frontend/main-ux-ui.html`.
- Tests: `tests/services/test_document_workflow.py` — `test_per_line_confirm_reject_unconfirm_decision`,
  `test_line_item_decision_rejects_unknown_decision_and_id`,
  `test_approve_confirms_pending_line_items_but_keeps_rejected`,
  `test_seller_tax_id_and_buyer_name_are_editable`.

### W6-C1-03 — Master-data tab consistency + soft-delete (HR-17-07)  ✅ Done
- **Backend soft-delete/deactivate** (product-owner asked to go beyond honest-disabled):
  `DELETE /v1/companies/{id}/vendor-master/{code}`, `.../customer-master/{code}`,
  `.../product-master/{code}` — each sets `is_active=False` (row + history preserved). New services
  `deactivate_master_entry`, `deactivate_product_master_entry`.
- **Frontend normalization:** AP Vendor and AR Customer tabs gained a **search box** (backed by the
  existing `q` param) and a **count**; all of COA/AP/AR/Product now expose consistent search + count +
  a per-row **🗑 ปิด (deactivate)** action.
- **Removed fake-click controls:** the AP/AR "+ เพิ่ม" buttons that only fired a "not supported" toast are
  replaced with honestly-disabled buttons labeled `+ เพิ่ม… (ใช้ CSV)` (single-row add remains via CSV
  import upsert; deferred with a precise label).
- Files: `src/backend/services/master_data_import.py`, `src/backend/services/product_master_import.py`,
  `src/backend/api/master_import.py`, `src/backend/api/product_master.py`, `src/frontend/main-ux-ui.html`.
- Tests: `tests/services/test_master_data_import.py::TestMasterDeactivate`,
  `tests/services/test_product_master_import.py::TestDeactivateProduct`.

### W6-C1-04 — Template Configurator modes + manual fallback (HR-17-08, HR-17-09)  ✅ Done
End-to-end wiring per the product owner's request (DB → backend → frontend, tied to line items):
- **DB schema:** new `export_templates.template_mode` column (migration `014_add_template_mode.py`),
  default `flat_document`.
- **Backend granularity mapping:** `flat_document → document`, `flatten_row → line_item` (the line-item
  export mode), `grouped_summary → journal` (GL posting). `_granularity_for()` prefers the template's
  explicit mode over the column heuristic; both `/v1/export` and `/v1/export/preview` honor it.
- **Schemas:** `template_mode` added to `TemplateCreate`/`TemplateUpdate`/`TemplateResponse` (pattern-
  validated) and persisted on create/update/clone.
- **Frontend:** the three previously-disabled UI-only buttons (Flat Document / Flatten Row / Grouped
  Summary) are now live, drive `state.templateMode`, show a per-mode hint, are saved on the template,
  and adopt the selected template's / analyzer's suggested mode. Removed the unwired "Row-grouping
  Strategy / Row Source / Document Number Strategy" placeholder block.
- **Manual fallback (HR-17-09):** the manual column editor (Configurator Tab ② — add/edit columns,
  source fields, transforms, encoding/format, save/update) is present and reachable; it now carries the
  wired mode selector, aligned with the UX freeze.
- Files: `src/backend/db/models.py`, `alembic/versions/014_add_template_mode.py`,
  `src/backend/api/schemas/template_schemas.py`, `src/backend/api/templates.py`,
  `src/backend/api/export_preview.py`, `src/frontend/main-ux-ui.html`.
- Tests: `tests/api/test_export_api.py::TestTemplateModeGranularity` — each mode maps to the expected
  granularity, mode overrides column detection, and missing mode falls back to detection.

### W6-C1-05 — Upload company match, Excel-safe dates, test quality (HR-17-01, HR-17-06, HR-17-10)  ✅ Done
- **Upload company match (HR-17-01):** the Processing table now shows a per-document
  `✓ เลขผู้เสียภาษีตรงกับบริษัท` / `⚠ …ไม่ตรง…` hint right after processing. The pipeline `tax_id_match`
  gate was widened to match the company against **either** the buyer (AP) **or** seller (AR) tax ID, so
  the hint is correct for both purchase and sales documents; a missing party id stays "unknown".
- **Excel-safe dates (HR-17-06):** the CSV/XLSX writer already wrapped date columns as Excel text, but
  only when `data_type == "date"` — and the UI saves every column as `"string"`, so dates leaked through
  and Excel mangled them (e.g. `01/05/69 → 1 May 2069`). Added `_is_date_column()` which also detects a
  Thai-date **transform** or a known date **source field**, so the Excel-safe path now fires for real
  templates. XLSX remains available as the customer-safe default format.
- **Test-quality gate (HR-17-10):** every item above ships at least one regression that fails on the
  observed human issue (see per-item Tests).
- Files: `src/backend/pipeline/orchestrator.py`, `src/backend/services/template_engine.py`,
  `src/frontend/main-ux-ui.html`.
- Tests: `tests/services/test_template_engine.py` —
  `test_date_column_wrapped_when_typed_as_string_but_has_date_transform`,
  `test_date_source_field_wrapped_even_without_transform`.

### HR-17-03 (P1) — Golden line-item sample tag
Per HR-17-03, `03062026131708.pdf` / invoice **`IV260225-056`** is recorded here as the **golden positive
line-item sample** (strong correct extraction that displayed a low 69% confidence — a calibration-display
issue, not an extraction error). Confidence-display calibration vs. extraction correctness is left as
tracked P1 follow-up (`W6-P1-01`); this report tags the sample as required.

## Tests run

- Full backend suite: **613 passed, 3 skipped, 2 failed** in ~2m05s.
  - The 2 failures are **pre-existing and unrelated**:
    `tests/governance/test_validate_expectations.py::test_validate_jsonl_passes_for_valid_rows` and
    `…::test_validate_jsonl_fails_for_missing_key` call `validate_expectations.validate_jsonl`, which the
    module renamed to `validate_row` — a stale test, in code this task did not touch.
- Targeted runs (all green): `test_export_dataset.py`, `test_document_workflow.py`,
  `test_master_data_import.py`, `test_product_master_import.py`, `test_template_engine.py`,
  `test_export_api.py`, `test_templates.py`, `test_pipeline.py`.
- Frontend: all inline `<script>` blocks in `main-ux-ui.html` pass `node --check`; `index.html` is
  byte-identical to `main-ux-ui.html` (parity verified with `diff -q`).

## UI alignment / scope compliance

- Layout, tabs, and table styling stay aligned with `main-ux-ui.html` / `index.html`; no product-shell
  redesign, no modal-first replacement of the full-page export flow.
- No customer-facing fake-click controls remain: the master-data "+ เพิ่ม" toasts are now honestly
  disabled with precise labels; the template-mode buttons are wired (not UI-only).
- No auth/RBAC weakening; company scoping on export/live paths is unchanged. No SIT/VPS edits; no deploy
  workflows added to this repo.

## Residual risk & explicit deferrals

- **Migration must be applied on SIT/UAT.** `014_add_template_mode.py` adds `export_templates.template_mode`
  with a `server_default`, so existing rows backfill to `flat_document`; the deploy must run `alembic upgrade`
  before the new template-mode path is exercised. Existing templates keep current behavior until re-saved.
- **Single-row master add** (COA/AP/AR/Product) remains CSV-import-only; honestly disabled with a label.
  Full per-row create endpoints are a follow-up.
- **COA delete** is intentionally not added — accounts are referenced by mapping rules; "delete where
  backend permits" applies to vendor/customer/product masters only.
- **HR-17-03 confidence-display calibration** deferred to `W6-P1-01` (golden sample tagged above).
- **Live SIT proof** (clicking through the real UI, PostgreSQL/Redis/MinIO evidence) is owned by the
  Copilot SIT-proof lane (`W6-COPILOT-SIT-PROOF-02`) after this merges — required before customer-review
  sign-off on 2026-07-30.

## Changed files

Backend: `src/backend/api/documents.py`, `src/backend/api/export_preview.py`,
`src/backend/api/master_import.py`, `src/backend/api/product_master.py`, `src/backend/api/templates.py`,
`src/backend/api/schemas/document_schemas.py`, `src/backend/api/schemas/template_schemas.py`,
`src/backend/db/models.py`, `src/backend/pipeline/orchestrator.py`,
`src/backend/services/document_workflow.py`, `src/backend/services/master_data_import.py`,
`src/backend/services/product_master_import.py`, `src/backend/services/template_engine.py`,
`alembic/versions/014_add_template_mode.py`.

Frontend: `src/frontend/main-ux-ui.html`, `src/frontend/index.html` (parity mirror).

Tests: `tests/services/test_export_dataset.py`, `tests/services/test_document_workflow.py`,
`tests/services/test_master_data_import.py`, `tests/services/test_product_master_import.py`,
`tests/services/test_template_engine.py`, `tests/api/test_export_api.py`.
