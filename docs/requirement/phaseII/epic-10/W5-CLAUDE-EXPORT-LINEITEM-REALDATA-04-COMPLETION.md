# W5-CLAUDE-EXPORT-LINEITEM-REALDATA-04 — Completion Report

- **Task:** `docs/requirement/phaseII/W5-CLAUDE-EXPORT-LINEITEM-REALDATA-04.prompt.json`
- **Board:** W5-12 (P0). **Tracking tag:** `W5-EXPORT-LINEITEM-REALDATA-04`. **Branch:** `dev`.
- **Follows:** W5-02 Processing UX (commit `5836bd6`). Codex gave the go-ahead to implement the line-item scan path.

## Summary
Wired the Epic 9 line-item scan end-to-end and replaced the demo/`sample_data`-driven live Export with real reviewed/mapped document data:
`enable_stock=true` → Processing runs a **non-blocking** line-item extraction sub-stage → line items are **persisted** in a new table → **human-confirmed** in Review Scan → **included in Export**; live Export now builds rows from real documents on the backend and shows an honest empty state when none are ready.

## List of removed / isolated demo-static export sources
- **Frontend `fallbackSampleData` + `fallbackVouchers`** (the "Metro Electric / INV-2605 / Green Supply" fixtures in `src/frontend/main-ux-ui.html` + `index.html`) — **deleted**. `getEffectiveSampleData()` no longer injects them (returns real `analysisSampleData` or `[]`); `getEffectiveVouchers()` no longer falls back to fixtures.
- **Export screen "per-document selection not wired" disclosure** — replaced with a **real read-only list** of the selected company's `mapping_confirmed` documents (`GET /companies/{id}/documents?status=mapping_confirmed`) + an honest empty state ("ยังไม่มีเอกสารที่พร้อม export …"), no fake rows.
- Live Export preview/download/validate no longer send fixture `sample_data`; they send `company_id` and let the backend build rows.

## Backend live-export endpoint/service contract
- **New service** `src/backend/services/export_dataset.py::build_export_records(db, company_id, *, document_ids=None, statuses=None, include_line_items=False)` → flat `list[dict]` records keyed by the `TemplateEngine` `source_field` names (invoice_number, invoice_date, seller_name, seller_tax_id, net/vat/wht/total_amount, document_type, account_code, description, voucher_no, debit, credit, company_name/…). One row per journal line; when `include_line_items` **and** the company has `enable_stock`, one extra row per **confirmed** `DocumentLineItem` carrying product fields (product_name, product_unit, product_unit_price, qty, line_amount). Default document set = `mapping_confirmed` + `exported`.
- **Endpoints** `POST /v1/export/preview` and `POST /v1/export` (`src/backend/api/export_preview.py`) gained optional `company_id`, `document_ids`, `include_line_items`. When `company_id` is present → live rows from `build_export_records`; otherwise `sample_data` (kept only for the Template Configurator design-time preview). `TemplateEngine` / CSV+XLSX writers / template columns are unchanged and reused.
- **New line-item review API** on the documents router: `PUT /v1/documents/{id}/line-items` (save edits) and `POST /v1/documents/{id}/line-items/confirm` (confirm) → both return `DocumentDetailResponse` (now including `line_items`).

## Line-item storage choice and why
- **New table `document_line_items`** (`DocumentLineItem` model + migration `alembic/versions/013_add_document_line_items.py`, `down_revision=012`, single head). Columns: `document_id` FK→documents CASCADE, `line_order`, `product_name`, `qty`, `unit`, `unit_price`, `line_amount`, `confidence`, `line_type`, `matched_product_code`, `status` (`LineItemStatus`: pending/confirmed/rejected), timestamps.
- **Why a table (not a JSON blob):** per-row human review needs individual edit + confirm status, and export must **join confirmed rows** — both are clean with a real table and awkward inside `Extraction.extraction_json`. Matches the task's "prefer a proper `document_line_items` table" and "not fake/local-only". (User-confirmed decision.)

## How `enable_stock=true` changes Processing
- `run_pipeline(..., enable_stock=bool)` runs a **non-blocking** `line_item` sub-stage after header extraction, before journal mapping (`src/backend/pipeline/orchestrator.py`). It reuses the Epic 9 PoC prompts (relocated to `src/backend/ml/line_item_prompts.py`; `scripts/line_item_prompts.py` now re-exports it) via a new `src/backend/ml/line_item_extractor.py` that calls the vision LLM through the shared `llm_router` provider selection / model resolution / cost logging.
- `enable_stock` is read from `Company.settings.enable_stock` in both real callers — the Celery task (`workers/tasks.py`, company already loaded) and the sync `POST /v1/documents/{id}/process` (`api/documents.py`).
- The stage is wrapped in its own `try/except` that only writes `ctx.line_item_output`; a line-item failure never sets `ctx.status`/blocks header persistence or journal routing.
- Emits a `line_item` progress stage → flows to `GET /v1/tasks/{id}` → the W5-02 Processing tracker shows it (as a status label + advances the stage-weighted bar; the 3-column glyph tracker stays stable for all companies).
- Extracted rows persist as `status="pending"`; Review Scan shows an editable line-item table + Save/Confirm; only **confirmed** rows are exported.

## How header-only companies remain unaffected
- When `enable_stock` is false the pipeline never runs the line-item stage, `line_items` stays empty, the Review Scan line-item card stays hidden, the Processing tracker never shows a `line_item` label, and Export omits product rows. Header-only Upload→Process→Review→Mapping→Export is unchanged. Idempotent reprocess clears prior line items so re-runs don't duplicate.

## Tests run
- **pytest (218 passed):** `tests/api` (incl. `test_documents_api.py` process + new line-item repo methods, `test_export_api.py` sample_data path preserved), `tests/services` (new `test_export_dataset.py`; `test_document_workflow.py` line-item persist/reprocess/confirm/edit + header-only), `tests/workers` (`test_tasks.py` updated for the DELETE-replace), `tests/ml/test_line_item_extractor.py` (extractor happy/fallback + **pipeline non-blocking** on line-item failure).
- **Playwright e2e (36 passed):** new `tests/e2e/w5-export-lineitem-uxui.spec.ts` (Export lists real ready docs + sends `company_id`; honest empty state; Review Scan line-item render + confirm) plus regressions `w4-export`, `w4-routine-ops`, `w4-product-shell-followup-22`, `w5-processing-poc-parity` (percent assertion made weight-agnostic after adding the `line_item` stage).
- **Migration:** `alembic heads` → single head `013`; `012 -> 013` chain clean.
- **HTML parity:** `node scripts/verify-w4-html-integrity.mjs` → VERIFY_OK; `index.html == main-ux-ui.html` (0 diff).
- Local e2e note: the static test root must expose `auth.js` at `/static/auth.js` (serving `src/frontend` flat 404s it and hangs `login()`).

## Commit SHA and tag
- Single commit on `dev` carrying implementation + tests + this report (governance Action Lock blocks docs-only commits). Tag: `W5-EXPORT-LINEITEM-REALDATA-04`. Resolve the hash: `git log --grep W5-EXPORT-LINEITEM-REALDATA-04 -1 --format=%H`.
- **No deploy by Claude** — Copilot deploys `dev` via Openclaw GitHub Actions and runs the SIT proof (`W5-COPILOT-E2E-SIT-PROOF-03`). The deploy must run `alembic upgrade head` for migration 013.

## Known residual risks
- **Product matching** (`matched_product_code`) is stored but not yet populated — best-effort ProductMaster matching is deferred (task marks matching accuracy out of scope); the column is forward-compat.
- **Per-line confidence** is only the model-returned `line_type_confidence`; low-confidence rows are surfaced (warn badge) for human review, no runtime scoring.
- **Line-item extraction adds one vision-LLM call per document** when `enable_stock=true` (expected; non-blocking, cost-logged via `llm_router`).
- **Export granularity:** header/GL rows always; line-item rows only when `include_line_items` + `enable_stock`. Per-document checkbox selection deferred (user chose whole-company auto); the real ready-doc list is shown read-only.
- **Migration must be applied on deploy** — the new table is required before line-item processing/export works on SIT.

## Next Copilot proof required
On SIT, for an `enable_stock=true` company: Upload 2–3 real docs → Processing shows the `line_item` stage → Review Scan shows/edits/confirms line items → Confirm Mapping → Export lists the real documents and the downloaded CSV/XLSX includes confirmed line-item rows. Also verify a header-only (`enable_stock=false`) company still exports normally with no product rows.
