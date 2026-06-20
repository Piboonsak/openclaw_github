# Epic 15 — Sales Tax Report: Tasks Detail

> **Phase**: II/2 (Post-Go-Live, CR-based)
> **Pattern**: Same as Purchase Tax Report (Epic 11) — template-based rendering
> **Created**: 2026-06-15

---

## TASK-1501: Sales Tax Report Template Definition

**Owner**: Full-stack Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-11

### Purpose

กำหนด columns และ fields สำหรับรายงานภาษีขาย (ภ.พ.30 ฝั่งขาย) — ใช้ pattern เดียวกับ Purchase Tax Report แต่เปลี่ยน fields เป็นฝั่งขาย.

### What exists today

- Purchase Tax Report template (TASK-1101) — working reference
- Template engine (TASK-1001) — column mapping + transforms
- ExportTemplate DB model with JSONB columns
- Revenue Department standard format for ภาษีขาย

### What to build

1. **Sales tax report column definition**:
   - ลำดับที่ (row number)
   - วัน เดือน ปี (date — Thai Buddhist Era)
   - เลขที่ใบกำกับภาษี (tax invoice number — issued by company)
   - ชื่อผู้ซื้อ (buyer name)
   - เลขประจำตัวผู้เสียภาษี ผู้ซื้อ (buyer tax ID)
   - สถานประกอบการ (branch — สำนักงานใหญ่/สาขาที่ N)
   - มูลค่าสินค้า/บริการ (amount before VAT)
   - จำนวนเงินภาษี (VAT amount)
   - หมายเหตุ (remarks)
2. **Field mapping** to extraction results:
   - Map header fields from document extraction to sales tax columns
   - Handle: sales invoices issued by the company (not OCR input — may be manual entry or ERP data)
3. **Validation rules**:
   - VAT = amount * 7% (standard rate)
   - Tax ID format: 13 digits
   - Date format: Thai Buddhist Era

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/services/sales_tax_report.py` | Sales tax report column definitions + field mapping |
| Create | `tests/services/test_sales_tax_report.py` | Column definition tests |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1501_01 | Sales tax columns defined matching Revenue Department format | test_sales_tax_columns |
| ac_1501_02 | Field mapping covers all required columns | test_field_mapping_complete |
| ac_1501_03 | VAT calculation validation (7% standard) | test_vat_calculation |
| ac_1501_04 | Tax ID format validation (13 digits) | test_tax_id_format |
| ac_1501_05 | Thai Buddhist Era date format correct | test_thai_date_format |

### Governance fields

```json
{
  "task_id": "TASK-1501",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/services/**", "alembic/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1502: Sales Tax Report Rendering + Master Template Seed

**Owner**: Full-stack Dev
**Risk**: LOW
**Duration**: ~3 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-11

### Purpose

Implement rendering ของ Sales Tax Report ผ่าน template engine + seed master template ลง DB via Alembic migration. ต้อง consistent กับ Purchase Tax Report styling (Thai formatting, encoding, layout).

### What exists today

- Purchase Tax Report rendering (`create_purchase_tax_report()` — 240 lines, xlsxwriter)
- Template engine (TASK-1001) with column mapping + transforms
- Export service supports CSV (UTF-8 BOM, TIS-620) + Excel
- Master template seed pattern from TASK-1004

### What to build

1. **Sales Tax Report rendering**:
   - Use template engine for column mapping (not hardcoded)
   - CSV export: UTF-8 BOM encoding (consistent with purchase tax)
   - Excel export: styled worksheets with Thai headers
   - Thai formatting: Buddhist Era dates, Thai number format, currency
2. **Master template seed migration**:
   - Alembic migration to insert sales tax master template
   - Template name: "รายงานภาษีขาย (มาตรฐาน)"
   - Template type: `sales_tax`
   - Columns JSONB matching TASK-1501 definition
3. **API endpoint**:
   - `POST /api/v1/export/sales-tax-report` — generate sales tax report
   - Parameters: company_id, period (month/year), template_id (optional)
   - Response: file download (CSV or Excel)
4. **Consistency with Purchase Tax Report**:
   - Same styling patterns (xlsxwriter formats)
   - Same encoding options
   - Same preview functionality

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/services/sales_tax_report.py` | Add rendering logic |
| Modify | `src/backend/services/export_service.py` | Add sales tax export function |
| Create | `alembic/versions/xxx_seed_sales_tax_template.py` | Seed master sales tax template |
| Create | `src/backend/api/export_sales_tax.py` | Sales tax export endpoint |
| Modify | `src/backend/app/endpoints.py` | Register sales tax export router |
| Create | `tests/services/test_sales_tax_rendering.py` | Rendering tests |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1502_01 | Sales tax report renders to CSV with correct columns | test_sales_tax_csv_render |
| ac_1502_02 | Sales tax report renders to Excel with styled headers | test_sales_tax_excel_render |
| ac_1502_03 | Master template seeded via Alembic migration | test_sales_tax_template_seeded |
| ac_1502_04 | Thai Buddhist Era dates formatted correctly | test_thai_date_rendering |
| ac_1502_05 | Thai currency formatting consistent with purchase tax | test_currency_formatting |
| ac_1502_06 | API endpoint returns file download | test_export_endpoint |
| ac_1502_07 | UTF-8 BOM encoding option works | test_utf8_bom_encoding |

### Governance fields

```json
{
  "task_id": "TASK-1502",
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
