# Epic 11 — Tasks Detail

> Purchase Tax Report Integration (W3)
> Parent: [README-EPIC-11.md](README-EPIC-11.md)

---

## TASK-1101: Purchase Tax Report -> template-based

**Owner**: Backend Dev
**Risk**: MEDIUM
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-11

### Purpose

ย้าย Purchase Tax Report จาก hardcoded 240-line function เป็น template-based rendering ผ่าน template engine (TASK-1001). รักษา output เดิม (Thai formatting, VAT bucket splitting, xlsxwriter styling) ให้เหมือนเดิมทุกประการ พร้อม backward compatibility สำหรับ old endpoint.

### What exists today

- `create_purchase_tax_report()` function (~240 lines) ใน `src/backend/services/export_service.py`
- Thai column headers (ลำดับ, เลขที่ใบกำกับ, วันที่, ชื่อผู้ขาย, เลขประจำตัวผู้เสียภาษี, etc.)
- VAT bucket splitting logic (แยก 7% VAT items ตาม bucket)
- xlsxwriter styling (borders, header formatting, number formats)
- `POST /api/export-purchase-tax-report` endpoint ใน `endpoints.py`

### What to build

1. **Refactor to use template engine:**
   - Load Purchase Tax Report master template from DB (seeded in TASK-1004)
   - Pass document data through template engine (TASK-1001) for column mapping
   - Keep VAT bucket splitting as pre-processing step (before template rendering)
   - Keep Thai date formatting via `thai_date` transform in template definition
2. **Migrate endpoint:**
   - New: `POST /api/v1/export` with `{ template_id, document_ids[], format: "xlsx" }`
   - Old endpoint `/api/export-purchase-tax-report` redirects to new (307 Temporary Redirect)
3. **Preserve output fidelity:**
   - Compare old output vs new output row-by-row for 10 sample documents
   - Same column order, same number formatting, same Thai headers
   - xlsxwriter styling preserved (template engine's Excel writer handles this)
4. **VAT bucket splitting logic:**
   - Extract VAT bucket logic from hardcoded function into reusable preprocessor
   - Template engine receives pre-processed data (buckets already split)

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/services/export_service.py` | Refactor create_purchase_tax_report() to use template engine; extract VAT bucket preprocessor |
| Modify | `src/backend/app/endpoints.py` | Add redirect from old endpoint to new; mount unified export |
| Create | `tests/services/test_purchase_tax_template.py` | Regression tests: output comparison old vs new |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1101_output | Template-based output matches hardcoded output for 10 sample documents (column order, values, formatting) | test_output_regression |
| ac_1101_thai | Thai headers preserved (ลำดับ, เลขที่ใบกำกับ, วันที่, etc.) | test_thai_headers |
| ac_1101_vat | VAT bucket splitting produces same grouping as hardcoded function | test_vat_bucket_splitting |
| ac_1101_redirect | Old endpoint /api/export-purchase-tax-report returns 307 redirect to new endpoint | test_backward_compat_redirect |
| ac_1101_excel | Excel output has same xlsxwriter styling (borders, headers, number formats) | test_excel_styling |

### Governance fields

```json
{
  "task_id": "TASK-1101",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/services/export_service.py", "src/backend/api/**", "tests/services/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1104: Preview + balance validation

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~1 day
**Closes pain points**: PP-2, PP-3, PP-5, PP-9

### Purpose

เพิ่ม preview ก่อน download (ดูข้อมูล 5-10 rows แรกในรูปแบบตาราง) และ balance validation ที่ตรวจสอบ Sum(Debit) = Sum(Credit) per voucher ก่อน export. ถ้าไม่ balance ให้ block export และแสดง voucher ที่มีปัญหา.

### What exists today

- Export functions ส่ง file download โดยตรง ไม่มี preview
- ไม่มี balance validation -- export ได้เสมอแม้ Dr/Cr ไม่ตรง
- Journal voucher data มี `total_debit`, `total_credit` fields ใน DB model

### What to build

1. **Preview endpoint:**
   - `POST /api/v1/export/preview`
   - Body: `{ template_id, document_ids[] }`
   - Response: JSON table data (headers + rows, first 5-10 rows)
   - Uses template engine to format data but returns JSON instead of file
2. **Balance validation:**
   - Check per voucher: `Sum(journal_lines.debit) == Sum(journal_lines.credit)`
   - Tolerance: allow rounding difference <= 0.01 THB
   - If unbalanced vouchers found:
     - Return 422 with list of unbalanced vouchers (voucher_no, total_debit, total_credit, difference)
     - Block export until user fixes mapping
3. **Validation API:**
   - `POST /api/v1/export/validate` -- standalone validation (no preview data)
   - Returns: `{ valid: true/false, unbalanced_vouchers: [...] }`
4. **UI integration:**
   - Preview button shows formatted table before download
   - If validation fails: show warning with unbalanced voucher list
   - Download button disabled until validation passes

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/services/export_service.py` | Add preview rendering (JSON output), balance validation logic |
| Modify | `src/backend/app/endpoints.py` | Add POST /api/v1/export/preview and POST /api/v1/export/validate |
| Modify | `src/frontend/ux-ui-prototype.html` | Preview table display, validation warning UI |
| Create | `tests/services/test_balance_validation.py` | Balance validation tests (balanced, unbalanced, rounding tolerance) |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1104_preview | Preview returns formatted JSON table data with correct headers and first 5-10 rows | test_preview_json_output |
| ac_1104_balanced | Balanced vouchers (Dr == Cr) pass validation and allow export | test_balanced_voucher_passes |
| ac_1104_unbalanced | Unbalanced vouchers return 422 with list of affected vouchers and amounts | test_unbalanced_voucher_blocks |
| ac_1104_tolerance | Rounding difference <= 0.01 THB is tolerated (treated as balanced) | test_rounding_tolerance |
| ac_1104_report | Validation response includes voucher_no, total_debit, total_credit, difference per unbalanced voucher | test_validation_detail |

### Governance fields

```json
{
  "task_id": "TASK-1104",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/services/**", "src/backend/api/**", "src/frontend/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
