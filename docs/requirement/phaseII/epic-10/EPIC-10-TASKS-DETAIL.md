# Epic 10 — Tasks Detail

> Template Engine + Configurator UI (W3-W5)
> Parent: [README-EPIC-10.md](README-EPIC-10.md)

---

## TASK-1001: Template engine backend

**Owner**: Backend Dev
**Risk**: MEDIUM
**Duration**: ~3 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-8

### Purpose

สร้าง core engine ที่ map source fields (extraction data, journal data, computed fields) ไปเป็น output columns ตาม template definition. รองรับ transforms, multiple output formats (CSV/Excel), และ multiple encodings (UTF-8, UTF-8 BOM, TIS-620 สำหรับ Express Accounting รุ่นเก่า).

### What exists today

- Export service (`src/backend/services/export_service.py`) ที่มี hardcoded GL Ledger + Purchase Tax Report format
- DB model `ExportTemplate` with JSONB `columns` field ใน `src/backend/db/models.py`
- Template Configurator demo HTML (`src/frontend/template-configurator-demo.html`) ที่แสดง field list ที่ต้อง support

### What to build

1. **Column mapping engine**: รับ template definition + document data -> render output rows
2. **Field resolver**: ดึง value จาก source_field (extraction fields, journal fields, computed fields)
3. **Transform pipeline**: apply transforms ตามลำดับ
   - `uppercase` -- แปลงเป็นตัวพิมพ์ใหญ่
   - `pad_left:5:0` -- pad ซ้ายด้วย "0" ให้ครบ 5 หลัก
   - `thai_date` -- แปลง date เป็นรูปแบบไทย (พ.ศ.)
   - `strip_dash` -- ลบเครื่องหมาย "-" ออก
   - `thai_date_short` -- **[NEW]** แปลง ISO date → `DD/MM/YY` (พ.ศ. 2 หลัก) เช่น `2026-05-01` → `01/05/69` *(critical: Express rejects YYYY format)*
   - `thai_date_full` -- **[NEW]** แปลง ISO date → `D/M/YYYY` (พ.ศ. 4 หลัก) เช่น `2026-05-01` → `1/5/2569`
   - `prefix:X` -- **[NEW]** เติม prefix string เช่น `prefix:OE` → `OE6905/100` (ใช้กับ WHT formula doc)
   - `doc_number:PATTERN` -- **[NEW]** สร้างเลขที่เอกสารตาม pattern เช่น `YYMM/NNN` หรือ `YYMM######`
4. **CSV writer**: configurable delimiter, encoding (utf-8, utf-8-bom, tis-620)
   - **Date-as-text fix** *(added 2026-06-15)*: date columns MUST be written as plain text strings to prevent Excel auto-format from converting `DD/MM/YY` → `DD/MM/YYYY`. Options: wrap in `=""value""` or ensure cells are quoted strings. See [CLIENT-TEMPLATE-ANALYSIS.md § 3](CLIENT-TEMPLATE-ANALYSIS.md#3-client-bug-report-date-format-issue).
5. **Excel writer**: xlsxwriter with header styling, number formatting
   - Date columns: set cell format to `@` (text) before writing date strings
6. **Missing field handling**: graceful fallback -- use `default_value` or empty string

**Column definition schema:**
```json
{
  "source_field": "voucher_date",
  "header_label": "Date",
  "data_type": "date",
  "format_pattern": "YYYY-MM-DD",
  "default_value": null,
  "transform": null
}
```

**Available source fields:**
- Extraction: `invoice_number`, `invoice_date`, `seller_name`, `seller_tax_id`, `buyer_name`, `buyer_tax_id`, `net_amount`, `vat_amount`, `wht_amount`, `total_amount`, `document_type`
- Journal: `voucher_no`, `voucher_date`, `book_code`, `account_code`, `debit`, `credit`, `description`
- Computed: `company_name`, `company_tax_id`, `export_date`
- **Express Transaction** *(added 2026-06-15 from client template analysis — see [CLIENT-TEMPLATE-ANALYSIS.md](CLIENT-TEMPLATE-ANALYSIS.md))*:
  - `row_sequence` — ลำดับ (auto-increment per export)
  - `document_number` — เลขที่เอกสาร (generated per book type: `YYMM/NNN` or `YYMM######`)
  - `tax_invoice_number` — เลขที่ใบกำกับภาษี (alias for `invoice_number`, from OCR)
  - `transaction_desc` — คำอธิบาย (free text, for expense templates)
  - `amount_before_tax` — จำนวนเงินก่อนภาษี (alias for `net_amount`, purchase templates)
  - `amount_including_tax` — จำนวนเงินรวมภาษี (alias for `total_amount`, sales templates)
  - `vendor_code` / `vendor_name` — รหัส/ชื่อผู้จำหน่าย (vendor master lookup)
  - `customer_code` / `customer_name` — รหัส/ชื่อลูกค้า (customer master lookup)
  - `posting_account_code` — รหัสลงบัญชี (account code for Express posting)
  - `formula_doc_number` — เลขที่เอกสาร(สูตร) (computed: prefix + document_number, for WHT templates)

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/services/template_engine.py` | Core mapping engine: TemplateEngine class with render(), apply_transform(), resolve_field(), write_csv(), write_excel() |
| Create | `tests/services/test_template_engine.py` | Unit tests for mapping, transforms, CSV/Excel output, missing fields |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1001_map | Template engine maps source fields to output columns in correct order | test_field_mapping_order |
| ac_1001_transform | All 8 transforms (uppercase, pad_left, thai_date, strip_dash, thai_date_short, thai_date_full, prefix, doc_number) produce correct output | test_transforms |
| ac_1001_date_text | CSV date columns written as text strings — opening in Excel preserves DD/MM/YY format | test_csv_date_as_text |
| ac_1001_express | Express transaction fields (row_sequence, document_number, vendor_code, customer_code, etc.) resolve correctly | test_express_fields |
| ac_1001_csv | CSV output uses correct encoding (utf-8, utf-8-bom, tis-620) and delimiter | test_csv_encoding |
| ac_1001_excel | Excel output has styled headers and formatted numbers | test_excel_output |
| ac_1001_missing | Missing source fields use default_value or empty string (no crash) | test_missing_field_graceful |
| ac_1001_multi | Engine renders multiple documents in correct row order | test_multi_document_render |

### Governance fields

```json
{
  "task_id": "TASK-1001",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/services/template_engine.py", "tests/services/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1002: Template CRUD + Clone API endpoints

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-8

### Purpose

REST API สำหรับจัดการ export templates -- CRUD operations, clone master -> company-specific, และ preview with sample data. เป็น API layer ที่ Configurator UI (TASK-1003) จะเรียกใช้.

### What exists today

- DB model `ExportTemplate` ใน `src/backend/db/models.py` มี fields: id, company_id, template_name, template_type, columns (JSONB), static_values (JSONB), file_format, encoding, is_master, cloned_from
- No API endpoints for template management yet

### What to build

1. **REST endpoints:**
   - `GET /api/v1/templates` -- list templates by company (query param: `company_id`), include master templates
   - `POST /api/v1/templates` -- create new template with column definitions
   - `GET /api/v1/templates/{id}` -- get template with full columns JSONB
   - `PUT /api/v1/templates/{id}` -- update columns, order, header names, transforms
   - `DELETE /api/v1/templates/{id}` -- soft delete (set `is_active=false` or `deleted_at`)
   - `POST /api/v1/templates/{id}/clone` -- clone master -> company (deep copy columns)
   - `POST /api/v1/templates/{id}/preview` -- preview with sample data (first 5 rows)
2. **Pydantic schemas:** request/response models for template CRUD
3. **FastAPI router:** mounted at `/api/v1/templates`

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/api/templates.py` | FastAPI router with CRUD + clone + preview endpoints |
| Create | `src/backend/api/schemas/template_schemas.py` | Pydantic request/response models |
| Modify | `src/backend/app/endpoints.py` | Mount template router |
| Create | `tests/api/test_templates.py` | Integration tests for all endpoints |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1002_list | GET /api/v1/templates returns templates filtered by company_id + masters | test_list_templates |
| ac_1002_create | POST /api/v1/templates creates template with valid columns JSONB | test_create_template |
| ac_1002_get | GET /api/v1/templates/{id} returns template with full columns | test_get_template |
| ac_1002_update | PUT /api/v1/templates/{id} updates columns order and header names | test_update_template |
| ac_1002_delete | DELETE /api/v1/templates/{id} soft-deletes (record still in DB) | test_soft_delete_template |
| ac_1002_clone | POST /api/v1/templates/{id}/clone creates deep copy with company_id set and cloned_from FK | test_clone_template |
| ac_1002_preview | POST /api/v1/templates/{id}/preview returns formatted sample data | test_preview_template |

### Governance fields

```json
{
  "task_id": "TASK-1002",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/api/**", "src/backend/db/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1003: Template Configurator UI

**Owner**: Full-stack Dev
**Risk**: LOW (UI already prototyped)
**Duration**: ~3 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-8

### Purpose

Integrate the existing Template Configurator demo HTML with real API endpoints. ให้ user สามารถ drag-drop reorder columns, เลือก fields จาก picker, rename headers inline, เลือก transform per column, และ preview ผลลัพธ์จริงจาก API.

### What exists today

- Template Configurator demo HTML (`src/frontend/template-configurator-demo.html`) with SortableJS drag-drop
- SortableJS library already referenced
- Demo มี Available Fields list, Selected Columns list, drag-drop handle, rename capability
- ไม่ได้เชื่อมต่อ API จริง -- ใช้ mock data

### What to build

1. **Template Manager tab** ใน `ux-ui-prototype.html`:
   - List master templates with [Clone to Company] button
   - List company-specific templates grouped by company
   - [Edit], [Preview], [Delete] buttons per template
   - [+ New Template] button
2. **Template Configurator (edit mode):**
   - Available Fields panel (checkbox picker, categorized: Extraction / Journal / Computed)
   - Selected Columns panel (drag-drop reorder with SortableJS)
   - Inline rename headers (contenteditable or modal input)
   - Transform selector per column (dropdown: none, uppercase, pad_left, thai_date, strip_dash)
   - Format/encoding selectors (CSV/Excel, UTF-8/UTF-8 BOM/TIS-620)
3. **Live preview panel**: fetch first 5 rows from POST /api/v1/templates/{id}/preview
4. **API integration**: connect all UI actions to TASK-1002 endpoints

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/frontend/ux-ui-prototype.html` | Add Template Manager tab + Configurator UI (integrate from demo) |
| Modify | `src/frontend/template-configurator-demo.html` | Reference only -- extract working patterns into prototype |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1003_dragdrop | Drag-drop reorders columns, new order persists after save | test_column_reorder (Playwright) |
| ac_1003_picker | Field picker adds/removes columns from Selected list | test_field_picker (Playwright) |
| ac_1003_rename | Inline rename updates header_label, saved via API | test_inline_rename (Playwright) |
| ac_1003_transform | Transform selector changes transform value per column | test_transform_selector (Playwright) |
| ac_1003_preview | Preview panel shows formatted data from API | test_preview_panel (Playwright) |
| ac_1003_list | Template Manager lists masters and company templates grouped correctly | test_template_list (Playwright) |

### Governance fields

```json
{
  "task_id": "TASK-1003",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/frontend/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1004: Master templates + seed migration

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5

### Purpose

Pre-install master templates ใน DB via Alembic migration เพื่อให้ users สามารถ clone ไปเป็น company-specific templates ได้ทันทีหลัง deploy. Master templates เป็นจุดเริ่มต้นที่ไม่ต้องสร้าง template จาก scratch.

### What exists today

- DB model `ExportTemplate` with `is_master` boolean and `company_id=NULL` for masters
- Alembic migration infrastructure set up (`alembic/versions/001_initial_schema.py`)
- Hardcoded column layouts in `export_service.py` (GL 8-col, Purchase Tax 12-col)

### What to build

1. **Express GL Master Template** -- 8 columns:
   - Voucher_No (source: voucher_no)
   - Date (source: voucher_date, format: YYYY-MM-DD)
   - Book_Code (source: book_code)
   - Account_Code (source: account_code, transform: pad_left:5:0)
   - Debit_Amount (source: debit, format: #,##0.00)
   - Credit_Amount (source: credit, format: #,##0.00)
   - Line_Description (source: description)
   - Target_Company_TaxID (source: buyer_tax_id, transform: strip_dash)

2. **Purchase Tax Report Master Template** -- 12 columns (Thai headers):
   - ลำดับ (source: row_number)
   - เลขที่ใบกำกับภาษี (source: invoice_number)
   - วันที่ (source: invoice_date, transform: thai_date)
   - ชื่อผู้ขาย (source: seller_name)
   - เลขประจำตัวผู้เสียภาษี (source: seller_tax_id)
   - สถานประกอบการ (source: seller_branch_code, transform: pad_left:5:0)
   - มูลค่าสินค้า/บริการ (source: net_amount, format: #,##0.00)
   - ภาษีมูลค่าเพิ่ม (source: vat_amount, format: #,##0.00)
   - มูลค่ารวมภาษี (source: total_amount, format: #,##0.00)
   - VAT Rate (source: vat_rate)
   - ประเภทเอกสาร (source: document_type)
   - หมายเหตุ (source: description)

3. **Express Transaction Master Templates** *(added 2026-06-15 — see [CLIENT-TEMPLATE-ANALYSIS.md § 7](CLIENT-TEMPLATE-ANALYSIS.md#7-new-master-templates-to-seed-task-1004-update))*:

   - **#3** Express ซื้อสด (Cash Purchase) — Book 12, 8 cols — amount_before_tax, vendor fields, DD/MM/YY
   - **#4** Express ซื้อเชื่อ (Credit Purchase) — Book 14, 8 cols — Same as #3, different doc series
   - **#5** Express ค่าใช้จ่ายอื่นๆ (Other Expenses) — Book 15, 9 cols — Adds description column
   - **#6** Express ค่าใช้จ่าย+WHT (Expenses+WHT 3%) — Book 15+WHT, 11 cols — Adds formula doc (OE prefix)
   - **#7** Express ขายสด (Cash Sales) — Book 22, 7 cols — amount_including_tax, customer fields
   - **#8** Express ขายเชื่อ (Credit Sales) — Book 24, 7 cols — Same as #7

   All use TIS-620 encoding, comma delimiter, Thai headers, `thai_date_short` transform for dates.

4. **Alembic seed migration**: insert master templates with `is_master=true`, `company_id=NULL`

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `alembic/versions/003_seed_master_templates.py` | Data migration: insert 2 master templates with column definitions |
| Modify | `src/backend/db/models.py` | Verify ExportTemplate model has all needed fields (no changes expected) |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1004_gl | Express GL master template exists in DB with 8 columns after migration | test_gl_master_exists |
| ac_1004_tax | Purchase Tax master template exists in DB with 12 columns after migration | test_tax_master_exists |
| ac_1004_express | 6 Express transaction master templates (#3-#8) seeded with correct column definitions | test_express_masters_exist |
| ac_1004_master | All 8 templates have is_master=true, company_id=NULL | test_master_flags |
| ac_1004_columns | Column definitions match spec (source_field, header_label, data_type, format_pattern, transform) | test_column_definitions |
| ac_1004_idempotent | Migration is idempotent (running twice doesn't create duplicates) | test_migration_idempotent |

### Governance fields

```json
{
  "task_id": "TASK-1004",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["alembic/**", "src/backend/db/**", "scripts/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1005: Clone workflow

**Owner**: Full-stack Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-8

### Purpose

End-to-end clone workflow: user คลิก [Clone to Company] บน master template -> เลือก company -> deep-copy columns JSONB -> เปิด Template Configurator ให้แก้ไขได้ทันที. Clone ต้องสร้าง independent copy ที่แก้ไขได้โดยไม่กระทบ master.

### What exists today

- Clone endpoint spec ใน TASK-1002 (POST /api/v1/templates/{id}/clone)
- Template Configurator UI ใน TASK-1003
- DB model supports `cloned_from` FK and `company_id`

### What to build

1. **Clone API logic** (backend part of TASK-1002 clone endpoint):
   - Deep-copy columns JSONB (not a reference, full independent copy)
   - Set `company_id` to target company
   - Set `cloned_from` FK to master template ID
   - Set `is_master=false`
   - Default template name: `"{company_name} {master_template_name}"`
2. **Clone UI workflow** (frontend):
   - [Clone to Company] button on master template card
   - Company selector dropdown (populated from GET /api/v1/companies)
   - Optional: custom template name input (pre-filled with default)
   - After clone success: redirect to Template Configurator with new template loaded
3. **Validation**:
   - Only master templates (is_master=true) can be cloned
   - Target company must exist
   - Prevent duplicate clone (same master + same company) -- or allow with warning

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/api/templates.py` | Clone endpoint implementation (deep copy logic) |
| Modify | `src/frontend/ux-ui-prototype.html` | Clone button + company selector + redirect to editor |
| Create | `tests/api/test_template_clone.py` | Clone workflow tests |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1005_deepcopy | Cloned template columns are independent copy (modify clone doesn't affect master) | test_clone_deep_copy |
| ac_1005_fk | Cloned template has cloned_from FK pointing to master, company_id set | test_clone_foreign_keys |
| ac_1005_name | Default name follows pattern "{company_name} {master_name}" | test_clone_default_name |
| ac_1005_redirect | After clone, UI opens Template Configurator with the new template | test_clone_redirect (Playwright) |
| ac_1005_master_only | Non-master templates cannot be cloned (400 error) | test_clone_non_master_rejected |

### Governance fields

```json
{
  "task_id": "TASK-1005",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/api/**", "src/backend/services/**", "src/frontend/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1006: Export screen integration

**Owner**: Full-stack Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-11

### Purpose

เชื่อมต่อ export screen กับ template engine -- user เลือก template จาก dropdown, preview formatted data, download CSV/Excel. รวม balance validation ที่ block export เมื่อ voucher ไม่ balance (Sum(Debit) != Sum(Credit)).

### What exists today

- Export tab ใน `ux-ui-prototype.html` with hardcoded export buttons
- Export service (`export_service.py`) with `create_gl_ledger()` and `create_purchase_tax_report()` functions
- Template engine (TASK-1001) and CRUD API (TASK-1002) will be ready

### What to build

1. **Template selector dropdown** on export screen:
   - Populate from GET /api/v1/templates (filtered by current company)
   - Show template name + column count + format type
2. **Preview before download**:
   - After selecting template + documents, show preview table (first 5 rows)
   - POST /api/v1/templates/{id}/preview with document_ids[]
3. **Download button**:
   - POST /api/v1/export with body: `{ template_id, document_ids[], format: "csv"|"xlsx" }`
   - Return file download (Content-Disposition: attachment)
4. **Balance validation**:
   - Before export, check Sum(Debit) = Sum(Credit) per voucher
   - If unbalanced: block export, show which vouchers are unbalanced with amounts
   - User must fix mapping before export
5. **Unified export endpoint**: replace old hardcoded export endpoints

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/services/export_service.py` | Refactor to use template engine, add balance validation |
| Modify | `src/backend/app/endpoints.py` | Add unified POST /api/v1/export endpoint |
| Modify | `src/frontend/ux-ui-prototype.html` | Template selector, preview table, download button on export tab |
| Create | `tests/services/test_export_integration.py` | Integration tests: template-based export, balance validation |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1006_selector | Template selector shows available templates for current company + masters | test_template_selector |
| ac_1006_preview | Preview shows first 5 rows formatted per template definition | test_export_preview |
| ac_1006_csv | Download CSV works with correct encoding and delimiter | test_csv_download |
| ac_1006_xlsx | Download Excel works with styled headers | test_xlsx_download |
| ac_1006_balance | Unbalanced vouchers block export with error listing affected vouchers | test_balance_validation_block |
| ac_1006_balanced | Balanced vouchers allow export without errors | test_balance_validation_pass |

### Governance fields

```json
{
  "task_id": "TASK-1006",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/services/**", "src/backend/api/**", "src/frontend/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1007: Composite description field (concat transform)

**Owner**: Backend Dev  
**Risk**: LOW  
**Duration**: ~1 day  
**Closes pain points**: PP-2, PP-3 (enhanced column flexibility)

### Purpose

ขยาย transform pipeline ให้รองรับการสร้าง composite field จากหลายฟิลด์ — เช่น concat `{seller_name} {expense_type}` เป็น description เดียว. ช่วยให้ user customize output columns โดยไม่ต้องพึ่ง single source field.

### What exists today

- Transform pipeline ใน `template_engine.py` (TASK-1001) รองรับ single-field transforms: `uppercase`, `pad_left`, `thai_date`, `strip_dash`, `thai_date_short`, `thai_date_full`, `prefix`, `doc_number`
- Column definition JSONB schema มี `source_field` (single string) และ `transform` (single string)
- ไม่มีกลไกสำหรับ composite/computed fields ที่ reference หลาย source fields

### What to build

**Option A: `concat` transform** (simpler):
- New transform syntax: `concat:field1,field2,...` with optional separator config
- Example: `"transform": "concat:seller_name,expense_type"` → "บริษัท ABC จำกัด ค่าเช่า"
- Separator: default space, configurable via `concat:field1,field2,|` (last param = separator)

**Option B: `computed_field` with template engine** (more flexible):
- Add `computed_field` key to column definition (alternative to `source_field`)
- Template syntax: `"{seller_name} | {expense_type}"` using Jinja2-like placeholders
- Field resolver replaces `{field_name}` with actual values at render time
- Example: `"computed_field": "{seller_name} | {expense_type}"` → "บริษัท ABC จำกัด | ค่าเช่า"

**Recommended**: Start with Option A (`concat` transform) for MVP simplicity. Add Option B later if needed.

**Implementation details:**
1. Extend `apply_transform()` in `template_engine.py` to handle `concat` prefix
2. Parse `concat:field1,field2` → list of field names + separator
3. Resolve each field via existing `resolve_field()` method
4. Join values with separator (default: space)
5. Apply any subsequent transforms to concatenated result (e.g., `concat:a,b|uppercase`)
6. Update column definition schema docs to document concat syntax

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/services/template_engine.py` | Add concat transform handler to apply_transform(), extend field resolver |
| Modify | `tests/services/test_template_engine.py` | Add test_concat_transform with 2-field, 3-field, custom separator cases |
| Modify | `docs/requirement/phaseII/epic-10/EPIC-10-TASKS-DETAIL.md` | Update TASK-1001 transform list to include concat |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1007_concat_basic | `concat:seller_name,expense_type` produces "SellerValue ExpenseValue" (space separator) | test_concat_basic |
| ac_1007_concat_custom_sep | `concat:seller_name,expense_type,\|` produces "SellerValue \| ExpenseValue" | test_concat_custom_separator |
| ac_1007_concat_three | `concat:field1,field2,field3` works with 3+ fields | test_concat_multiple_fields |
| ac_1007_missing | Missing field in concat list uses empty string (no crash) | test_concat_missing_field |
| ac_1007_chained | Concat result can be piped to other transforms (e.g., `concat:a,b\|uppercase`) | test_concat_chained_transform |

### Governance fields

```json
{
  "task_id": "TASK-1007",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/services/template_engine.py", "tests/services/**", "docs/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1008: Row filter by COA code (`template_row_filters`)

**Owner**: Backend Dev  
**Risk**: MEDIUM  
**Duration**: ~1-2 days  
**Closes pain points**: PP-2 (flexible export formats)

### Purpose

เพิ่มความสามารถในการกรอง (filter out) rows ที่ไม่ต้องการออกจาก CSV export ตาม Chart of Accounts code หรือเงื่อนไขอื่น. Use case: Express GL template ไม่ต้องการ VAT ซื้อ (1151) และเจ้าหนี้การค้า (2110) เพราะ Express จัดการเองอัตโนมัติ.

### What exists today

- Export pipeline ใน `template_engine.py` (TASK-1001) renders ทุก row ที่มีใน document data
- ไม่มีกลไกสำหรับ filter rows based on field values
- DB model `ExportTemplate` มี JSONB columns field แต่ไม่มี filters field
- AI COA mapping (TASK-401) maps extracted line items → account codes

### What to build

1. **Schema migration:**
   - Add `template_row_filters` JSONB column to `export_templates` table
   - Structure: `{ "exclude_account_codes": ["1151", "2110"], "exclude_book_types": [], "min_amount": null, "max_amount": null }`
   - Migration: `alembic/versions/004_add_template_row_filters.py`

2. **Filter application logic** in template engine:
   - Apply filters AFTER AI maps COA (account_code is available) but BEFORE CSV write
   - Filter logic: for each row, check if `account_code` in `exclude_account_codes` list → skip row if match
   - Support multiple filter types (extensible for future: book_types, amount ranges)
   - Filter applies per-template (different templates = different filter rules)

3. **UI support** (defer to TASK-1003 follow-up or separate task):
   - Template Configurator should show filter settings (checkboxes for common COA codes to exclude)
   - Pre-populate with Express-specific defaults (1151, 2110) for Express GL master template

4. **Seed data update:**
   - Update Express GL master template (TASK-1004 seed migration) to include default `template_row_filters`

**Open question to resolve before implementation:**
- **VAT input rows (1151)**: Confirm with customer whether these rows are still needed for Purchase Tax Report (รายงานภาษีซื้อ Book 12/14) even if removed from GL template
- **Impact**: If yes, may need conditional filtering logic or separate template instances
- **Decision**: BLOCK implementation until customer confirms (flag as prerequisite)

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `alembic/versions/004_add_template_row_filters.py` | Migration: add template_row_filters JSONB column, set default for Express GL master |
| Modify | `src/backend/db/models.py` | Add template_row_filters field to ExportTemplate model |
| Modify | `src/backend/services/template_engine.py` | Add apply_row_filters() method, call before write_csv()/write_excel() |
| Modify | `tests/services/test_template_engine.py` | Add test_row_filter_exclude_account, test_row_filter_empty (no filters) |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1008_schema | `template_row_filters` JSONB column exists on export_templates table | test_schema_migration |
| ac_1008_exclude_coa | Rows with account_code in exclude_account_codes list are filtered out | test_filter_exclude_coa |
| ac_1008_no_filter | When template_row_filters is null or empty, all rows pass through | test_no_filter_applied |
| ac_1008_multiple | Multiple exclude codes work (exclude 1151 AND 2110) | test_multiple_exclude_codes |
| ac_1008_seed | Express GL master template has default exclude filter for 1151, 2110 after seed migration | test_master_default_filter |
| ac_1008_preserve_order | Filtered rows don't affect row sequence numbering of remaining rows | test_filter_preserve_sequence |

### Governance fields

```json
{
  "task_id": "TASK-1008",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/services/template_engine.py", "src/backend/db/**", "alembic/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1009: Schema Analyzer — Auto-detect Template from Sample File

**Owner**: Full-stack Dev
**Risk**: MEDIUM (AI inference + file parsing)
**Duration**: ~3 days
**Closes pain points**: PP-2, PP-3 (UX — reduces template setup cognitive load)

### Purpose

แทนที่จะให้ user สร้าง template จาก scratch (ต้องเข้าใจ data type, transform ต่างๆ), user อัปโหลดไฟล์ CSV/Excel ที่เคย Export ออกมาจากระบบเดิม (Express GL, PEAK, ERP อื่น) แล้วระบบจะ:

1. วิเคราะห์ schema (column headers, data types)
1. Sample ข้อมูล (detect patterns เช่น pad_left, thai_date, TIS-620 encoding)
1. Match คอลัมน์ไปยัง LF internal fields พร้อม confidence score
1. Pre-fill Template Configurator โดยอัตโนมัติ

User เหลือแค่ตรวจสอบและกดบันทึก — ไม่ต้องรู้ว่า `pad_left:5:0` หรือ `thai_date_short` คืออะไร

### What exists today

- Prototype screen `s-schema-analyzer` (Screen 11C) ใน `docs/requirement/phaseII/PHASE-II-PROTOTYPE.html` (added 2026-06-24)
- Template Configurator screen (Screen 11) — รับ pre-filled columns ผ่าน state/query param
- Template engine (TASK-1001) — มี transform registry และ field registry

### What to build

**Backend API:**

1. `POST /api/v1/templates/analyze` — รับไฟล์ multipart upload
   - Input: CSV หรือ Excel file (.csv, .xlsx, .xls)
   - Output: `AnalysisResult` JSON (ดู schema ด้านล่าง)

2. **File parser module** (`src/backend/services/schema_analyzer.py`):
   - Detect encoding (chardet สำหรับ TIS-620 vs UTF-8)
   - Parse headers + sample rows (first 20 rows)
   - รองรับ CSV (comma / semicolon) และ Excel (sheet 0)

3. **Structural analysis** (ทำใน Python — ไม่ใช้ LLM):
   - Data type inference จาก sample values:
     - `^[0-9]{4,6}$` → `string` + suggest `pad_left:N:0`
     - `^\d{1,2}/\d{1,2}/\d{2}$` → `date` + `thai_date_short`
     - `^\d{1,2}/\d{1,2}/\d{4}$` → `date` + `thai_date_full`
     - Numeric with commas → `number`
     - All-zero or all-empty alternate rows → possible double-entry (suggest Flatten Row mode)
   - Pattern detection:
     - pad_left: value length < max_length and left-padded with "0"
     - thai_date_short: year part 60-99 (พ.ศ. 2560-2599)
     - static column: all values identical → `static_value`

4. **Semantic column matching** (ใช้ Claude claude-haiku-4-5 หรือ fuzzy match):
   - Match column header (Thai/English) → LF internal field name
   - Strategy A (fast): string similarity (rapidfuzz) ระหว่าง header กับ known field aliases
   - Strategy B (fallback): LLM prompt ถ้า similarity < 70%
   - Field alias table สำหรับ Thai headers:
     - "วันที่", "ว/ด/ป" → `voucher_date` / `invoice_date`
     - "รหัสบัญชี", "Account Code" → `account_code`
     - "คำอธิบาย", "รายละเอียด" → `description` / `transaction_desc`
     - "จำนวนเงินก่อนภาษี", "ก่อนภาษี" → `net_amount`
     - ฯลฯ

5. **Template mode detection**:
   - นับ unique values ของคอลัมน์แรก (Voucher_No หรือ ลำดับ)
   - ถ้า unique < total rows → หลาย rows ต่อ document → `Flatten Row`
   - ถ้า unique = total rows → 1 row ต่อ document → `Flat Document`
   - ตรวจ debit/credit pattern → double-entry → suggest `journal_lines` row source

**Frontend:**

6. Screen `s-schema-analyzer` (ตาม prototype):
   - Upload zone (drag & drop หรือ file picker)
   - Progress animation (Step 1→2→3 ตาม API response)
   - Results: column mapping table + confidence badges + data profile + AI insights
   - คอลัมน์ที่ confidence < 80% → highlight เหลือง ให้ user confirm
   - ปุ่ม "Apply to Configurator →" → navigate to Template Configurator พร้อม pre-filled state

**AnalysisResult JSON schema:**

```json
{
  "file_info": {
    "filename": "Express_GL_May2569.csv",
    "rows_detected": 1024,
    "encoding_detected": "tis-620",
    "file_size_kb": 48
  },
  "suggested_template_mode": "flatten_row",
  "suggested_row_source": "journal_lines",
  "suggested_encoding": "tis-620",
  "columns": [
    {
      "position": 1,
      "original_header": "วันที่",
      "lf_field": "voucher_date",
      "confidence": 0.95,
      "data_type": "date",
      "suggested_transform": "thai_date_short",
      "match_method": "alias_table",
      "sample_values": ["04/05/69", "05/05/69", "06/05/69"]
    }
  ],
  "warnings": [
    {
      "column": "คำอธิบาย",
      "message": "Low confidence match — please confirm LF field",
      "alternatives": ["description", "memo"]
    }
  ],
  "data_profile": {
    "unique_account_codes": 42,
    "date_format_detected": "DD/MM/YY",
    "debit_credit_balanced": true,
    "null_rate_by_column": {}
  }
}
```

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/services/schema_analyzer.py` | File parser + structural analysis + column matching |
| Create | `src/backend/api/schema_analyze.py` | FastAPI router: POST /api/v1/templates/analyze |
| Modify | `src/backend/app/endpoints.py` | Mount schema_analyze router |
| Create | `src/frontend/screens/SchemaAnalyzer.tsx` | Screen component (upload → analyze → results) |
| Modify | `src/frontend/screens/Templates.tsx` | Add "Auto-detect จาก Sample File" button |
| Create | `tests/services/test_schema_analyzer.py` | Unit tests for parser, type inference, column matching |
| Create | `tests/api/test_schema_analyze_api.py` | Integration test: upload real CSV → verify AnalysisResult |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1009_upload | POST /api/v1/templates/analyze accepts CSV and Excel files | test_upload_csv, test_upload_xlsx |
| ac_1009_encoding | TIS-620 and UTF-8 files both parsed correctly | test_encoding_detection |
| ac_1009_type_date | Date columns with DD/MM/YY pattern detected as date + thai_date_short | test_date_type_inference |
| ac_1009_type_padded | Zero-padded codes (e.g., "05100") suggest pad_left:5:0 | test_padleft_detection |
| ac_1009_thai_header | Thai column headers ("วันที่", "รหัสบัญชี") match to correct LF fields | test_thai_header_matching |
| ac_1009_confidence | Unmatched columns (<80% confidence) appear in warnings | test_low_confidence_warning |
| ac_1009_mode | Double-entry data (debit/credit alternating) → Flatten Row mode suggested | test_template_mode_detection |
| ac_1009_profile | Data profile includes unique account codes, null rates, balance check | test_data_profile |
| ac_1009_apply | Frontend "Apply to Configurator" pre-fills Template Configurator with analysis result | test_apply_to_configurator (Playwright) |

### Governance fields

```json
{
  "task_id": "TASK-1009",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2b-analysis",
  "allowed_scope": ["src/backend/services/schema_analyzer.py", "src/backend/api/**", "src/frontend/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 6,
  "escalation_policy": "human",
  "notes": "LLM usage (claude-haiku-4-5) only as fallback for column matching when fuzzy match < 70%. All structural analysis (type inference, pattern detection) is deterministic Python."
}
```

---

*Created: 2026-06-15*
*Last updated: 2026-06-24*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
