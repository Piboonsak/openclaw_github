# W5-CLAUDE-EXPORT-LINEITEM-HARDENING-05 — Completion Report

## Doc ID
- **Task:** `docs/requirement/phaseII/W5-CLAUDE-EXPORT-LINEITEM-HARDENING-05.prompt.json`
- **Tracking tag:** `W5-EXPORT-LINEITEM-HARDENING-05`. **Branch:** `dev`.
- **Hardening pass on:** commit `3a87116` (W5-12 / W5-EXPORT-LINEITEM-REALDATA-04). Scope limited to the two Codex review findings; no W5-12 redesign.

## Commit SHA
- Single commit on `dev` carrying the patch + tests + this report (governance Action Lock blocks docs-only commits). Tag: `W5-EXPORT-LINEITEM-HARDENING-05`. Resolve the hash: `git log --grep W5-EXPORT-LINEITEM-HARDENING-05 -1 --format=%H`.

## Findings closed
- **W5-12-F1 (HIGH):** the live export path switched to backend data on any caller-provided `company_id` **without** enforcing company access → a caller could read another company's reviewed documents.
- **W5-12-F2 (MEDIUM):** reprocessing replaced line items but **not** prior journal vouchers; document detail and export read `journal_vouchers[0]`, so a reprocessed document could surface/export a **stale** earlier voucher.

## Access-control patch (F1)
- `src/backend/api/export_preview.py`: `_resolve_export_rows` now takes `current_user` and, when a `company_id` is present, calls `await ensure_company_access(db, current_user, company_id)` **before** building any rows — reusing the repo's existing scoping helper (admins/sys_admin see all; staff must be assigned via `user_company_assignments`, else HTTP 403). Both `POST /v1/export/preview` and `POST /v1/export` now bind `current_user` (previously the unused `_current_user`) and pass it through.
- No new auth model introduced; the sample_data (Template Configurator) path is unchanged and still needs no company scope.

## Voucher / reprocess patch (F2)
- Chose **replace-on-reprocess** (the most conservative repo-aligned fix): prior vouchers and their journal lines are cleared before the fresh voucher is written, so `journal_vouchers[0]` in both `GET /v1/documents/{id}` detail and `build_export_records()` is always the authoritative one — stale rows cannot leak.
- New repo method `clear_vouchers(document_id)` on the `DocumentRepository` protocol + `SqlAlchemyDocumentRepository` (deletes `JournalLine` for the document's vouchers, then the `JournalVoucher` rows — explicit two-step so it is backend-agnostic, not reliant on ORM cascade accident).
- `services/document_workflow.py::apply_pipeline_result` (async `/v1/documents/{id}/process` path) calls `repo.clear_vouchers(document.id)` right after the new `Extraction` and before adding the new voucher.
- `workers/tasks.py::_run_and_persist_pipeline` (Celery sync path) does the same via `session.execute(delete(JournalLine).where(voucher_id.in_(...)))` + `delete(JournalVoucher).where(document_id==...)` before adding the new voucher. Line-item replace (from W5-12) is unchanged. Detail and export therefore agree on the authoritative voucher after reprocess.

## Tests run
- `python -m pytest tests/api/test_export_api.py tests/services/test_document_workflow.py tests/services/test_export_dataset.py tests/api/test_documents_api.py tests/workers/test_tasks.py -q` → **64 passed**.
- New focused tests:
  - `tests/api/test_export_api.py::test_live_export_denies_foreign_company_for_unassigned_staff` — a staff user (with `get_user_company_ids` → ∅) posting a foreign `company_id` gets **403** on both `/v1/export/preview` and `/v1/export`.
  - `tests/services/test_document_workflow.py::test_reprocess_replaces_voucher_no_stale_rows` — applying the pipeline twice leaves exactly **1** voucher + **3** lines, and `journal_vouchers[0]` is the fresh voucher (id differs from the first run).
- In-memory test repos (`tests/services/test_document_workflow.py`, `tests/api/test_documents_api.py`) gained `clear_vouchers` (and the workflow repo's `add_voucher` now attaches to the registered document) so `apply_pipeline_result` runs under the fakes.
- Existing W5-12 behavior verified intact: line-item persist/reprocess/confirm/edit, export dataset (header + confirmed line items), sample_data design-preview path, and header-only flow all still pass.
- Full app import OK; no frontend changes in this pass.

## Residual risks
- The real `SqlAlchemyDocumentRepository.clear_vouchers` relies on a valid Postgres session at runtime (unit tests exercise the in-memory fakes); it is plain SQLAlchemy `delete(...)` and is covered indirectly by the workflow-level reprocess test. Copilot's SIT proof should confirm a real reprocessed document shows/export the fresh voucher.
- Export access control depends on `ensure_company_access` / `user_company_assignments` being correctly populated for staff; admins/sys_admin intentionally bypass (existing product rule).
- No change to line-item product matching, OCR, or Stage C timeout handling (explicitly out of scope for this prompt).

## Next Copilot deploy/proof handoff
- Redeploy `dev` via Openclaw GitHub Actions (must run `alembic upgrade head` — migration 013 from W5-12 is still required). On SIT prove: (1) a staff user restricted to company A cannot preview/download company B's export (expect 403); (2) reprocess a document and confirm detail + exported rows reflect the latest voucher, not a stale one; (3) the W5-12 happy path (line-item review/confirm/export for `enable_stock=true`, header-only export) still works.
