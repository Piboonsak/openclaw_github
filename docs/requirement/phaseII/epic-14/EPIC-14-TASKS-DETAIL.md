# Epic 14 — Line Item + Inventory Full: Tasks Detail

> **Phase**: II/2 (Post-Go-Live, CR-based)
> **Prerequisite**: TASK-906 Line Item PoC — Go/No-Go determines scope
> **Created**: 2026-06-15

---

## TASK-1401: Line Item Extraction (Full)

**Owner**: Backend Dev
**Risk**: MEDIUM
**Duration**: ~4 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-11

### Purpose

ขยาย line item extraction จาก PoC (TASK-906) เป็น production-grade — ครอบคลุมทุก document format ที่ผ่าน Go threshold, handle multi-page invoices, reconcile line amounts กับ totals.

### What exists today

- TASK-906 PoC results: feasibility report, recommended model, accuracy metrics
- LLM pipeline (Stage C model router) supports Gemini/Claude
- Field extraction regex v29 for header fields
- OCR pipeline (PaddleOCR + Tesseract) working

### What to build

1. **LLM prompt engineering** for line item parsing:
   - Structured output schema (JSON array of line items)
   - Fields: product_name, quantity, unit, unit_price, discount, line_amount
   - Handle Thai + English product descriptions
2. **Post-processing pipeline**:
   - Validate: qty * unit_price - discount = line_amount per line
   - Reconcile: sum(line_amounts) = invoice total (from header)
   - Flag mismatches for manual review
3. **Multi-page invoice handling**:
   - Detect continuation pages
   - Merge line items across pages
   - Handle "carried forward" / "ยกไป" patterns
4. **Model selection** based on TASK-906 results:
   - Use recommended model from PoC feasibility report
   - Cost optimization: batch vs single-doc processing

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/ml/line_item_extractor.py` | Line item extraction logic |
| Create | `src/backend/ml/line_item_reconciler.py` | Amount validation + reconciliation |
| Modify | `src/backend/ml/field_extractor.py` | Integrate line item extraction into pipeline |
| Create | `src/backend/ml/prompts/line_item_prompt.py` | LLM prompt templates for line items |
| Create | `tests/ml/test_line_item_extractor.py` | Unit tests |
| Create | `tests/ml/test_line_item_reconciler.py` | Reconciliation tests |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1401_01 | Line items extracted with >=80% per-field accuracy | test_line_item_field_accuracy |
| ac_1401_02 | Line total reconciliation >=70% pass rate | test_line_item_reconciliation |
| ac_1401_03 | Multi-page invoices handled correctly | test_multi_page_extraction |
| ac_1401_04 | Mismatched amounts flagged for review | test_mismatch_flagging |
| ac_1401_05 | Thai + English product descriptions parsed | test_bilingual_product_names |

### Governance fields

```json
{
  "task_id": "TASK-1401",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/ml/**", "tests/ml/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1402: Line Item DB Schema + API Endpoints

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-4, PP-5

### Purpose

Persist line items in DB + provide API endpoints for CRUD and review UI. ต้องมี schema ที่รองรับ line item review workflow (manual correction).

### What exists today

- ORM models 15 tables (`src/backend/db/models.py`) — no line_items table yet
- Alembic migration infrastructure
- Document model exists (line items FK to document)
- FastAPI router patterns established

### What to build

1. **Database schema** — `line_items` table:
   - `id` (UUID PK)
   - `document_id` (FK → documents)
   - `line_order` (integer, position in document)
   - `product_name` (text)
   - `quantity` (decimal)
   - `unit` (varchar 50)
   - `unit_price` (decimal)
   - `discount` (decimal, default 0)
   - `line_amount` (decimal)
   - `confidence_score` (float, 0-1)
   - `is_reviewed` (boolean, default false)
   - `reviewed_by` (FK → users, nullable)
   - `created_at`, `updated_at` timestamps
2. **Alembic migration** for line_items table
3. **API endpoints**:
   - `GET /api/v1/documents/{id}/line-items` — list line items
   - `PUT /api/v1/line-items/{id}` — update single line item (review correction)
   - `POST /api/v1/documents/{id}/line-items/bulk` — bulk create (from extraction)
   - `PATCH /api/v1/line-items/{id}/review` — mark as reviewed

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/db/models.py` | Add LineItem model |
| Create | `alembic/versions/xxx_add_line_items.py` | Migration for line_items table |
| Create | `src/backend/api/line_items.py` | Line item API router |
| Modify | `src/backend/app/endpoints.py` | Register line_items router |
| Create | `tests/api/test_line_items.py` | API endpoint tests |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1402_01 | line_items table created via migration | test_migration_creates_table |
| ac_1402_02 | GET returns line items for a document | test_get_line_items |
| ac_1402_03 | PUT updates line item fields | test_update_line_item |
| ac_1402_04 | Bulk create stores extraction results | test_bulk_create_line_items |
| ac_1402_05 | Review endpoint marks as reviewed | test_mark_reviewed |

### Governance fields

```json
{
  "task_id": "TASK-1402",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/db/**", "src/backend/api/**", "alembic/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1403: Inventory Data Structure

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5

### Purpose

Aggregate line items across documents by product — เตรียมข้อมูลสำหรับ inventory report. ลูกค้าต้องรู้: สินค้าอะไร, ซื้อจากใคร, จำนวนเท่าไร, ยอดเท่าไร.

### What exists today

- Line item data from TASK-1401/1402 (extraction + DB storage)
- Document model has vendor/supplier info
- No inventory aggregation logic

### What to build

1. **Inventory data model**:
   - Aggregate by: product_name (normalized)
   - Group fields: total_qty, total_amount, supplier list, document references
   - Time-based: monthly, quarterly aggregation
2. **Aggregation service**:
   - Query line items across documents
   - Group by product (fuzzy name matching or exact)
   - Calculate totals (qty, amount)
   - Link to source documents + suppliers
3. **API endpoint**:
   - `GET /api/v1/inventory/summary?company_id=X&period=2026-06` — aggregated inventory data

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/services/inventory_service.py` | Inventory aggregation logic |
| Create | `src/backend/api/inventory.py` | Inventory API endpoints |
| Modify | `src/backend/app/endpoints.py` | Register inventory router |
| Create | `tests/services/test_inventory_service.py` | Aggregation tests |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1403_01 | Inventory aggregation groups by product | test_aggregate_by_product |
| ac_1403_02 | Total qty and amount calculated correctly | test_aggregation_totals |
| ac_1403_03 | Data linked to source documents | test_document_references |
| ac_1403_04 | Monthly period filter works | test_period_filter |
| ac_1403_05 | API returns aggregated data | test_inventory_summary_endpoint |

### Governance fields

```json
{
  "task_id": "TASK-1403",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/services/**", "src/backend/db/**", "src/backend/api/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1404: Inventory Export Template

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-11

### Purpose

Export inventory data ออก CSV/Excel ผ่าน template engine (Epic 10) — ใช้ pattern เดียวกับ Purchase Tax Report + Sales Tax Report.

### What exists today

- Template engine from Epic 10 (TASK-1001)
- Inventory aggregation from TASK-1403
- Export service with CSV/Excel support

### What to build

1. **Inventory report template definition**:
   - Columns: ลำดับ, ชื่อสินค้า, จำนวนรวม, หน่วย, มูลค่ารวม, ผู้ขาย, เอกสารอ้างอิง
   - Transforms: Thai formatting for numbers, dates
2. **Master template** seeded via Alembic migration
3. **Export endpoint**:
   - `POST /api/v1/export/inventory` — generate inventory report
   - Support CSV (UTF-8 BOM) and Excel formats
4. **Integration with template engine**:
   - Use template_id for customizable output
   - Same pattern as purchase/sales tax reports

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/services/export_service.py` | Add inventory export function |
| Create | `alembic/versions/xxx_seed_inventory_template.py` | Seed master inventory template |
| Create | `src/backend/api/export_inventory.py` | Export endpoint |
| Create | `tests/services/test_inventory_export.py` | Export tests |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1404_01 | Inventory export generates CSV with correct columns | test_inventory_csv_export |
| ac_1404_02 | Inventory export generates Excel with correct columns | test_inventory_excel_export |
| ac_1404_03 | Master template seeded via migration | test_inventory_template_seeded |
| ac_1404_04 | Thai number/date formatting correct | test_thai_formatting |
| ac_1404_05 | Template engine integration works | test_template_based_export |

### Governance fields

```json
{
  "task_id": "TASK-1404",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/services/**", "alembic/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
