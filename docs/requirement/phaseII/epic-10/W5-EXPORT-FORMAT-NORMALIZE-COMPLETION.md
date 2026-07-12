# W5-EXPORT-FORMAT-NORMALIZE — Completion Report

## Context
- **Trigger:** user found the live Export producing **one row per journal posting** (Dr expense / Dr VAT / Cr AP) for a single scanned document — the document-level net/vat/total repeated across 3 rows — instead of the customer's "บรรทัดเดียว" (one row per document) Express import format.
- **Grounded in real data (not assumptions):** the customer's own expected export formats under `private_data/poc/Comp_1/template/` (incl. `excelformat/Master/` — 14 canonical Express formats) and the AP/AR master (`AP-CCSS.csv` / `AR-CCSS.csv`) were analyzed to derive the exact row shapes and field mappings.
- **Tracking tag:** `W5-EXPORT-FORMAT-NORMALIZE`. **Branch:** `dev`. Scope decided with the user: do **A (granularity normalize) + B (AP/AR master join) together**.

## Format taxonomy (analysis of the customer's real templates)
The ~14 Express formats collapse to **3 granularity engines**; direction (purchase↔sale) and WHT/PO/dept are column/variant overlays, not new engines:

| Engine | Example formats | 1 row = | Amount col | Party | รหัสลงบัญชี |
| --- | --- | --- | --- | --- | --- |
| **document** (บรรทัดเดียว) | ซื้อสด/ซื้อเชื่อ/ค่าใช้จ่าย/ขายสด/ขายเชื่อ | one document | purchase=`net_amount`, sale=`total_amount` | vendor / customer | expense 536004 / revenue 410001 |
| **journal** (Express GL, Journal-RV) | 011 Journal-RV, Express GL | one posting | debit/credit | — | ผังบัญชี Dr/Cr |
| **line_item** (หลายบรรทัด) | ซื้อ/ขาย หลายบรรทัด | one confirmed line item | per-line | (header on each) | **รหัสสินค้า** |

Master-maintenance formats (007–014: add vendor/customer/product, receive-payment, bank withdraw/deposit/transfer) are **not** derived from scanned documents and are out of the document-export scope.

## A — Granularity normalization
`src/backend/services/export_dataset.py::build_export_records` was refactored from "always one row per posting (+ optionally appended line-item rows)" into a single-mode builder driven by a `granularity` parameter:
- **`document`** (default) — **one row per document**. Document-level net/vat/total on that row; `account_code`/`account_name`/`description` come from the **primary P&L posting** — the line tagged `amount_field == "net_amount"` (the expense line for a purchase / revenue line for a sale), never the VAT line (`vat_amount`) nor the AP/AR-control line (`total_amount`). Falls back to the first non-VAT/non-gross line, then the first line.
- **`journal`** — one row per posting (per-line debit/credit) — the prior behaviour, for real GL templates.
- **`line_item`** — one row per **confirmed** `DocumentLineItem`; falls back to a single document row when nothing is confirmed so the document is never silently dropped.

Granularity is auto-detected in `src/backend/api/export_preview.py::_detect_granularity` from the template's own columns — debit/credit source fields → `journal`; product/qty source fields (or the legacy `include_line_items` flag) → `line_item`; otherwise `document`. Both `POST /v1/export/preview` and `POST /v1/export` pass it through `_resolve_export_rows` → `build_export_records`. **No frontend change needed** — selecting a template yields the right row shape automatically.

## B — AP/AR master join
`VendorMaster` / `CustomerMaster` (columns: `vendor_code`/`vendor_name`/`gl_code`, `customer_code`/`customer_name`/`ar_flag`) carry **no tax id**, so the join is by **normalized name** (whitespace-insensitive, case-folded). For each document the seller is looked up as a vendor and the buyer as a customer; each record gains `vendor_code`, `vendor_name`, `vendor_gl_code`, `customer_code`, `customer_name` (blank when unmatched). Templates map `รหัสผู้จำหน่าย → vendor_code` and `รหัสลูกค้า → customer_code`. Each company's master is loaded once into a name-indexed dict (no per-document query).

## End-to-end proof (real "14 ซื้อเชื่อ บรรทัดเดียว" columns, the screenshot's Grabtaxi document)
A document with 3 postings (Dr expense 779.07 / Dr VAT 54.53 / Cr AP 833.60), rendered through the actual template column mapping:

```
วันที่|เลขที่เอกสาร|เลขที่ใบกำกับภาษี|จำนวนเงินก่อนภาษี|รหัสผู้จำหน่าย|ชื่อผู้จำหน่าย|รหัสลงบัญชี
2026-01-30|6905/100|GFAD20260130007921|779.07|5004|Grabtaxi (Thailand) Co.,Ltd.|536004
```
**One row** (was 3): `จำนวนเงินก่อนภาษี` = net 779.07 (single value, not repeated); `รหัสผู้จำหน่าย` = 5004 (vendor master join); `รหัสลงบัญชี` = 536004 (the `net_amount` posting — not VAT 1151 nor AP 2120-01).

## Tests run
- `tests/services/test_export_dataset.py` rewritten: document mode = one row/document with primary-posting account; journal mode = one row/posting; line_item mode = one row/confirmed item + fallback-to-document; `include_line_items` legacy flag maps to line_item; vendor & customer master name-join; unmatched party → blank code; empty when no documents.
- `python -m pytest tests/services tests/api/test_export_api.py tests/api/test_documents_api.py -q` → **222 passed**. Full app import OK. Single caller of `build_export_records` (the export endpoint) verified — no other call sites affected.

## Deferred (transparent scope)
- WHT-formula columns (มีหัก), PO-pull/RR numbers, department (แผนก) — the pipeline does not extract these fields yet.
- Master-maintenance formats 007–014 — not document-derived.
- Master join is **exact normalized-name** only; an OCR-drifted seller/buyer name will not match (blank party code). Fuzzy/alias matching is a follow-up; a tax-id column on the master would make the join exact but requires a schema change.

## Next steps / handoff
- No migration in this change (uses existing `vendor_master` / `customer_master`). For the join to populate on SIT, each company's AP/AR master must be imported (the existing `master_data_import` already parses the real `AP-CCSS.csv` / `AR-CCSS.csv` Express export shape).
- Claude does not deploy — Copilot redeploys `dev` via Openclaw and can verify live export now emits one row per document for a purchase/sale template and per-posting only for an Express-GL template.
