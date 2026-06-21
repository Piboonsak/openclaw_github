# UX Click Audit & Interaction Inventory

> **TASK-001** | Epic 0 — UX Contract & Workflow Freeze
> **Audited**: 2026-06-20
> **Source**: `docs/requirement/phaseII/PHASE-II-PROTOTYPE.html` (v2, 2,519 lines)
> **IA Reference**: `docs/requirement/phaseII/MENU-TREE-IA.html`

---

## Summary

| Metric | Count |
|--------|-------|
| Total screens audited | 14 + Login |
| Visible primary actions (CTAs) | 52 |
| Classification: **MVP** | 38 |
| Classification: **mock-only** | 8 |
| Classification: **disable** (future scope) | 4 |
| Classification: **Phase II/2** | 2 |
| Modals/Drawers inventoried | 6 |
| Mobile behavior | Desktop-only prototype (no responsive nav) |

### 2026-06-20 Owner Review Decisions

These decisions override the first-pass click audit where they conflict:

| Area | Decision | Impact |
|------|----------|--------|
| Dashboard cost card | Do **not** show LLM provider/model names to owners or customer admins. Replace with page credit usage. | Customer-facing UX + DB billing contract |
| Processing screen | Replace raw progress/loading bars with a calm step indicator: done checkmarks, one active spinner, clear status text, and auto-advance hint. | Prototype patch only; uses `processing_progress` JSONB |
| Export flow | `Download CSV` must not immediately download. It should open export config/preview where users can choose columns, date formats, data types, encoding, and file type. | Export UX + `export_templates.columns` JSONB contract |
| Company detail settings | `ตั้งค่า` tab must show company COA/mapping settings, not an empty placeholder. | Company admin UX; uses `chart_of_accounts` + `account_mapping_rules` |
| Templates | Create/View/Edit/Clone/Delete buttons must open real prototype screens or modals so stakeholders can discuss behavior. | TASK-004 prototype patch |
| Users | Edit and Reset Password actions must open drawer/modal flows. | TASK-004 prototype patch; uses existing `users` |
| Cost Control / Audit Log / Settings | These are **LedgerFlow system-admin/internal** screens, not customer tenant admin screens. Remove from customer admin sidebar or move to internal workspace. | Role/navigation contract; internal-only |

---

## Screen-by-Screen Audit

### Screen 0: Login

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | Username input | Text input | **MVP** | `users.username` or `users.email` |
| 2 | Password input | Text input + toggle visibility | **MVP** | `users.password_hash` |
| 3 | เข้าสู่ระบบ button | POST /api/auth/login → JWT | **MVP** | `users.last_login` update, `audit_logs` insert |
| 4 | Error message | Show/hide on failed login | **MVP** | — |
| 5 | System status indicator | "ระบบพร้อมใช้งาน" | **mock-only** | Health check endpoint |

**DB entities**: `users` (existing), JWT token (stateless or `sessions` table TBD)
**Role guards**: None (pre-auth)
**Decision needed**: Use JWT stateless or store sessions in DB? → **Recommend JWT stateless** (no session table needed for MVP)

---

### Screen 1: Dashboard

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | KPI: วันนี้ เอกสารทั้งหมด | Read aggregation | **MVP** | `SELECT COUNT(*) FROM documents WHERE company_id=? AND DATE(created_at)=today` |
| 2 | KPI: รอ Review | Read aggregation | **MVP** | `documents WHERE status IN ('review_scan','review_mapping')` |
| 3 | KPI: เดือนนี้ ทั้งหมด | Read aggregation | **MVP** | `documents WHERE company_id=? AND created_at >= month_start` |
| 4 | KPI: Export แล้ว | Read aggregation | **MVP** | `documents WHERE status='exported'` |
| 5 | กิจกรรมล่าสุด table | Read latest audit_logs | **MVP** | `audit_logs ORDER BY created_at DESC LIMIT 10` |
| 6 | Page Credits card | Show used / included / remaining credits | **MVP** | `company_credit_plans` + `page_credit_usage` |
| 7 | Document type usage breakdown | Show scanned pages by document type | **MVP** | `page_credit_usage GROUP BY document_type` |
| 8 | Quick Action: อัปโหลดใหม่ | Navigate to Upload | **MVP** | — |
| 9 | Quick Action: ไปที่ Review | Navigate to Review Scan | **MVP** | — |

**Customer-facing rule**: Owners and customer admins must **not** see LLM provider/model names, token usage, or internal model routing cost. Use package/page-credit language only.

**Example package display**:
- Plan: `Pro Premium`
- Full price: `45,000 THB`
- Discounted price: `25,500 THB`
- Included usage: `20,000 page credits`
- Dashboard metric: `used pages / 20,000`, remaining credits, and document-type breakdown.

**DB entities**: `documents`, `audit_logs`, `company_credit_plans`, `page_credit_usage`. Internal `api_usage` remains system-admin only.
**Role guards**: Admin + Staff can view. Staff sees only assigned companies.

---

### Screen 2: Upload

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | Step indicator (1/2) | Visual state | **MVP** | — |
| 2 | Company selector dropdown | Choose target company | **MVP** | `companies WHERE tenant_id=? AND is_active=true` |
| 3 | Drag & drop zone | Select files (PDF/JPG/PNG) | **MVP** | — (client-side) |
| 4 | File list with tax ID check | Show uploaded files + tax ID match | **MVP** | Client-side check → `companies.tax_id` |
| 5 | Remove file (✕) | Remove from queue | **MVP** | — (client-side) |
| 6 | ⚠ Tax ID mismatch warning | Warn if buyer_tax_id ≠ company.tax_id | **MVP** | — |
| 7 | ต่อไป → button | Upload files → create batch → navigate to Processing | **MVP** | **Creates `DocumentBatch`** + `Document` records |

**DB entities needed**:
- **`DocumentBatch` (NEW)** — `id`, `company_id`, `uploaded_by`, `status`, `total_files`, `created_at`
- `Document` (existing) — `batch_id` FK → `document_batches.id`

**Critical decision**: Upload creates a **batch** (one upload session = one batch). Files are validated client-side, uploaded to storage, then `Document` records created with `status='uploaded'`.

**API**:
- `POST /api/v1/batches` → create batch + upload files → return `batch_id`
- Files uploaded to MinIO/R2 at `{tenant_id}/{company_id}/{year}/{month}/{sha256}.{ext}`

---

### Screen 3: Processing

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | Calm progress stepper | Real-time progress (polling/WS) with done checkmarks + one active spinner | **MVP** | `DocumentBatch.status`, aggregated document statuses |
| 2 | Status counters (เสร็จ/กำลัง/ผิดพลาด/รอ) | Read aggregation | **MVP** | `COUNT(*) GROUP BY status WHERE batch_id=?` |
| 3 | Per-document pipeline table | 4-stage progress (OCR/จำแนก/สกัด/Map) | **MVP** | `Document.processing_stage` or derived from status |
| 4 | ✓ checkmark per stage | Show completed stages | **MVP** | — (derived from document status progression) |
| 5 | ⟳ spinner | Show active stage | **MVP** | — |
| 6 | ✗ error + "ดู Error" link | Show processing error | **MVP** | `Document.processing_error` (existing) |
| 7 | "ข้ามไปที่ Review →" button | Navigate to Review Scan | **MVP** | — |
| 8 | Auto-navigate hint | "จะนำทางไปที่ Review Scan โดยอัตโนมัติ" | **mock-only** | WS/polling needed |

**DB entities**:
- `DocumentBatch.status` → `uploading`, `processing`, `review_scan`, `review_mapping`, `ready_export`, `exported`
- `Document.status` needs granular processing sub-states OR separate `processing_stage` field

**Critical decision**: How to track processing stages?
- **Option A**: Single `status` field with values `ocr_running`, `classifying`, `extracting`, `mapping_coa`, `review_scan`
- **Option B**: `status` = high-level + JSONB `processing_progress` = `{"ocr": "done", "classify": "done", "extract": "running", "map": "pending"}`
- **Recommend Option B** — status stays high-level, processing_progress is JSONB for the 4-stage detail

**Perceived-wait UX decision**: Do not show many animated loaders at once. Use checkmarks for completed stages, one active spinner for the current stage, muted pending dots, and a clear auto-advance message. This makes the page feel alive without making users feel stuck waiting.

---

### Screen 4: Review Scan

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | Progress bar (อนุมัติแล้ว 5/11) | Read aggregation | **MVP** | `documents WHERE batch_id=? AND scan_status='approved'` |
| 2 | Document list (left panel) | List documents in batch | **MVP** | `documents WHERE batch_id=? ORDER BY filename` |
| 3 | Document list: status badges (✓/🚩/●) | Show scan review status | **MVP** | `Document.scan_status` |
| 4 | Document list: confidence % | Show overall_confidence | **MVP** | `Document.overall_confidence` (existing) |
| 5 | PDF preview (center panel) | Show document image/PDF | **MVP** | Fetch from storage via `Document.storage_key` |
| 6 | Zoom controls (−/+) | Client-side zoom | **MVP** | — |
| 7 | Document type badge | Show classified type | **MVP** | `Document.document_type` (existing) |
| 8 | Confidence badge | Show % | **MVP** | `Document.overall_confidence` |
| 9 | WHT badge | Show WHT rate if detected | **MVP** | `Document.wht_rate`, `Document.wht_amount` |
| 10 | VAT mode badge | Show Inclusive/Exclusive | **MVP** | `Extraction.extraction_json` → vat layout |
| 11 | Field form: วันที่ | Editable input | **MVP** | **FieldCorrection** or overwrite `Document.invoice_date` |
| 12 | Field form: เลขที่ใบแจ้งหนี้ | Editable input | **MVP** | **FieldCorrection** or overwrite `Document.invoice_number` |
| 13 | Field form: เลขผู้เสียภาษีผู้ขาย | Editable input | **MVP** | **FieldCorrection** or overwrite `Document.seller_tax_id` |
| 14 | Field form: ชื่อผู้ขาย | Editable input | **MVP** | **FieldCorrection** or overwrite `Document.seller_name` |
| 15 | Amount panel: ยอดก่อนภาษี | Read-only display | **MVP** | `Document.net_amount` |
| 16 | Amount panel: VAT 7% | Read-only display | **MVP** | `Document.vat_amount` |
| 17 | Amount panel: WHT 3% | Read-only display | **MVP** | `Document.wht_amount` |
| 18 | Amount panel: ยอดสุทธิ | Read-only display | **MVP** | `Document.total_amount` |
| 19 | ✓ Approve button | Approve scan extraction | **MVP** | `Document.scan_status='approved'`, `scan_reviewed_by`, `scan_reviewed_at` |
| 20 | 🚩 Flag button | Open flag modal | **MVP** | Creates **`DocumentFlag`** record |
| 21 | ← ก่อนหน้า | Navigate to previous doc | **MVP** | — |
| 22 | ✓ Approve All ที่เหลือ | Bulk approve remaining | **MVP** | Batch update scan_status |
| 23 | ไปที่ Review Mapping → | Navigate | **MVP** | — |

**DB entities needed**:
- **`Document` additions**: `scan_status` (enum: pending/approved/flagged), `scan_reviewed_by` (FK→users), `scan_reviewed_at` (datetime)
- **`FieldCorrection` (NEW)** — tracks field-level human edits with old/new values
- **`DocumentFlag` (NEW)** — `id`, `document_id`, `flagged_by`, `reason`, `comment`, `status` (open/resolved), `created_at`

**Critical decision**: Field correction tracking strategy:
- **Option A**: Append-only `field_corrections` table — preserves audit trail, old + new values per field
- **Option B**: Overwrite `Document` columns directly — simpler, no audit trail for individual fields
- **Recommend Option A for MVP** — append-only corrections table. Accounting users need audit trail of what was changed.

---

### Screen 5: Review Mapping

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | Progress badge (Confirm แล้ว 4/11) | Read aggregation | **MVP** | `journal_vouchers WHERE confirmed_at IS NOT NULL` |
| 2 | Document list (left panel) | Same as Review Scan | **MVP** | Same query |
| 3 | Doc list: Confirmed badge | Show mapping confirmation status | **MVP** | `JournalVoucher.status` |
| 4 | Doc list: Unbalanced badge | Show balance error | **MVP** | `JournalVoucher.is_balanced` |
| 5 | Voucher header (No/Date/Book) | Read-only display | **MVP** | `JournalVoucher` fields |
| 6 | Balance indicator (✓/✗) | Show Sum Dr = Sum Cr | **MVP** | `JournalVoucher.is_balanced` |
| 7 | Journal lines table | Editable account codes | **MVP** | `JournalLine.account_code` (editable) |
| 8 | Account code inputs | Inline edit with COA lookup | **MVP** | Validate against `chart_of_accounts` |
| 9 | Dr/Cr amounts | Read-only display | **MVP** | `JournalLine.amount`, `JournalLine.is_debit` |
| 10 | Total row | Computed sum | **MVP** | — (client-side sum) |
| 11 | ← แก้ไข Scan | Navigate back to Review Scan | **MVP** | — |
| 12 | ✓ Confirm Mapping | Confirm voucher mapping | **MVP** | `JournalVoucher.confirmed_by`, `.confirmed_at`, `.status='confirmed'` |
| 13 | ไปที่ Export → | Navigate | **MVP** | — |

**DB entities**: `JournalVoucher` (existing), `JournalLine` (existing), `ChartOfAccount` (existing)
**No new tables needed.** Existing schema covers this screen.

**Note**: If user edits account_code on a journal line, this should:
1. Update `JournalLine.account_code` and `account_name`
2. Recalculate `JournalVoucher.is_balanced`
3. Log change in `audit_logs` (not FieldCorrection — that's for extraction fields)
4. If vendor+account pair is confirmed, increment `AccountMappingRule.confirmed_count`

---

### Screen 6: Export

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | Template selector | Choose export template | **MVP** | `export_templates WHERE company_id=? OR is_master=true` |
| 2 | Format radio (CSV/Excel) | Select output format | **MVP** | — (request param) |
| 3 | Encoding radio (UTF-8/TIS-620) | Select encoding | **MVP** | — (request param) |
| 4 | Document selection table | Checkbox per document | **MVP** | Client-side selection |
| 5 | Select all checkbox | Toggle all | **MVP** | — |
| 6 | Voucher No column | Display | **MVP** | `JournalVoucher.voucher_no` |
| 7 | Balance status badges | ✓ Balanced / ⚠ Unbalanced | **MVP** | `JournalVoucher.is_balanced` |
| 8 | Balance summary bar | "10 Balance, 1 ไม่ Balance" | **MVP** | Aggregation |
| 9 | 👁 Preview button | Open export preview modal | **MVP** | Generate preview (not persisted) |
| 10 | 📥 Download CSV button | Open export config/preview, then generate + download file | **MVP** | **Creates `ExportJob`** + `ExportFile` after confirmation |
| 11 | Export history table | List previous exports | **MVP** | `export_jobs ORDER BY created_at DESC` |
| 12 | History: download button | Re-download previous export | **MVP** | `ExportFile.storage_key` |
| 13 | Export config modal/page | Choose columns, data type, date format, number/text handling | **MVP** | `export_templates.columns` JSONB + request params |

**DB entities needed**:
- **`ExportJob` (NEW)** — `id`, `company_id`, `template_id` (FK), `created_by` (FK), `status`, `total_documents`, `format`, `encoding`, `created_at`
- **`ExportFile` (NEW)** — `id`, `export_job_id` (FK), `filename`, `storage_key`, `file_size_bytes`, `created_at`
- Link table or JSONB: `export_job_documents` — which documents were included

**Critical decision**: Export job linking
- **Option A**: `export_job_documents` join table (export_job_id, document_id)
- **Option B**: JSONB array `ExportJob.document_ids`
- **Recommend Option A** — proper FK constraints, queryable "which exports included this document?"

**Export formatting decision**: Users must be able to adjust output before download: column include/exclude, order, header label, source field, data type (`text`, `number`, `date`, `boolean`), date pattern (`dd-mm-yy`, `dd/mm/yyyy`, `yyyy-mm-dd`), number formatting, file type, delimiter, and encoding. The first click on `Download CSV` should open this config/preview if not already confirmed.

---

### Screen 7: Companies

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | Search input | Filter companies by name/tax_id | **MVP** | `companies WHERE name ILIKE ?` |
| 2 | + เพิ่มบริษัท button | Open company drawer | **MVP** | — |
| 3 | Company table | List all companies | **MVP** | `companies WHERE tenant_id=?` |
| 4 | เอกสาร/เดือน column | Document count per company | **MVP** | `COUNT(*) FROM documents WHERE company_id=? AND month=current` |
| 5 | Active/Inactive badge | Show status | **MVP** | `companies.is_active` |
| 6 | แก้ไข button | Open company edit drawer | **MVP** | `companies` UPDATE |
| 7 | COA button | Navigate to Company Detail | **MVP** | — |

**DB entities**: `companies` (existing) — no changes needed.
**Role guards**: Admin only.

---

### Screen 8: Company Detail

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | ← กลับรายการบริษัท | Navigate back | **MVP** | — |
| 2 | Company header info | Display name, tax_id, branch | **MVP** | `companies` read |
| 3 | Tab: ผังบัญชี (COA) | Show COA list | **MVP** | — |
| 4 | Tab: ตั้งค่า | Show company settings, COA defaults, and mapping rules | **MVP** | `companies.settings`, `account_mapping_rules` |
| 5 | Search COA | Filter by account_code/name | **MVP** | `chart_of_accounts WHERE company_id=? AND (code ILIKE ? OR name ILIKE ?)` |
| 6 | + เพิ่มรายการ button | Add COA entry | **MVP** | `chart_of_accounts` INSERT |
| 7 | 📁 นำเข้า YAML/CSV button | Open import modal | **MVP** | Bulk INSERT `chart_of_accounts` |
| 8 | COA table | List accounts | **MVP** | `chart_of_accounts WHERE company_id=?` |
| 9 | Account type badges | Asset/Liability/Revenue/Expense | **MVP** | `chart_of_accounts.account_type` |
| 10 | แก้ไข button per row | Edit COA entry | **MVP** | `chart_of_accounts` UPDATE |
| 11 | โหลดเพิ่ม button | Pagination | **MVP** | OFFSET/LIMIT or cursor |
| 12 | Mapping rules table | Show vendor/document-type → account mapping rules | **MVP** | `account_mapping_rules WHERE company_id=?` |
| 13 | Add/Edit mapping rule | Configure default account mapping | **MVP** | INSERT/UPDATE `account_mapping_rules` |

**DB entities**: `chart_of_accounts`, `account_mapping_rules`, `companies.settings` (all existing) — no new table needed.
**Role guards**: Admin only.

---

### Screen 9: Users

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | Search input | Filter users | **MVP** | `users WHERE display_name ILIKE ?` |
| 2 | + เพิ่มผู้ใช้ button | Open user drawer | **MVP** | — |
| 3 | User table | List users | **MVP** | `users WHERE tenant_id=?` |
| 4 | Role badge (Admin/Staff) | Display role | **MVP** | `users.role` |
| 5 | บริษัทที่ดูแล column | Show assigned companies | **MVP** | JOIN `user_company_assignments` |
| 6 | เข้าสู่ระบบล่าสุด column | Show last login | **MVP** | `users.last_login` |
| 7 | Active/Inactive badge | Show status | **MVP** | `users.is_active` |
| 8 | แก้ไข button | Open user edit drawer | **MVP** | `users` UPDATE |
| 9 | Reset PW button | Open reset password modal | **MVP** | `users.password_hash` UPDATE |

**DB entities**: `users`, `user_company_assignments` (both existing) — no changes needed.
**Role guards**: Customer tenant Admin only. Internal system-admin user management is separate.

**Prototype patch requirement**: `แก้ไข` and `Reset PW` must be clickable in the prototype. `แก้ไข` opens the user drawer populated with row data. `Reset PW` opens a confirmation/modal flow with temporary password or reset-link behavior.

---

### Screen 10: Templates

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | + สร้าง Template ใหม่ button | Create new template | **MVP** | `export_templates` INSERT |
| 2 | Tab: Master Templates | Show master templates | **MVP** | `export_templates WHERE is_master=true` |
| 3 | Tab: Templates บริษัท | Show company-specific clones | **MVP** | `export_templates WHERE company_id IS NOT NULL` |
| 4 | Template cards (Master) | Display template info | **MVP** | Read `export_templates` |
| 5 | 👁 ดู button | View template details | **MVP** | Navigate to Template Configurator (read-only) |
| 6 | 📋 Clone to Company | Clone master → company template | **MVP** | INSERT with `cloned_from` FK |
| 7 | ✏️ แก้ไข button (company) | Navigate to Template Configurator | **MVP** | — |
| 8 | 🗑 delete button (company) | Delete company template | **MVP** | `export_templates` DELETE (soft delete?) |

**DB entities**: `export_templates` (existing) — no changes needed.
**Role guards**: Admin can manage all. Staff cannot access.

**Prototype patch requirement**: `+ สร้าง Template ใหม่`, `ดู`, `Clone to Company`, `แก้ไข`, and delete confirmation must be clickable. These actions can stay prototype-only, but they must reveal the intended screen/modal so stakeholders can discuss the workflow.

---

### Screen 11: Template Configurator

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | ← กลับ Templates | Navigate back | **MVP** | — |
| 2 | Available Fields panel (left) | List extraction + journal fields | **MVP** | — (hardcoded field catalog) |
| 3 | Field search | Filter available fields | **MVP** | — |
| 4 | [+] add field button | Add field to selected columns | **MVP** | — (client-side) |
| 5 | Selected Columns panel (center) | Ordered column list | **MVP** | `export_templates.columns` JSONB |
| 6 | ☰ drag handle | Reorder columns | **MVP** | — (client-side, persisted on save) |
| 7 | ✕ remove column | Remove from selection | **MVP** | — (client-side) |
| 8 | Transform badges | Show applied transforms | **MVP** | `columns[].transform` in JSONB |
| 9 | Preview table (5 rows) | Show sample output | **MVP** | Server-side or client-side render |
| 10 | Format toggle (CSV/Excel) | Switch format | **MVP** | `export_templates.file_format` |
| 11 | Encoding toggle (UTF-8/TIS-620) | Switch encoding | **MVP** | `export_templates.encoding` |
| 12 | Column Settings panel (right) | Edit selected column properties | **MVP** | Per-column JSONB fields |
| 13 | Header Label input | Custom column header | **MVP** | `columns[].header_label` |
| 14 | Source Field (read-only) | Show source field name | **MVP** | `columns[].source_field` |
| 15 | Data Type dropdown | string/number/date/boolean | **MVP** | `columns[].data_type` |
| 16 | Transform dropdown | uppercase/thai_date/pad_left/strip_dash | **MVP** | `columns[].transform` |
| 17 | Default Value input | Fallback value | **MVP** | `columns[].default_value` |
| 18 | Format Pattern input | Date/number format | **mock-only** | `columns[].format_pattern` (disabled for non-date) |
| 19 | Preview value box | Show transform result | **MVP** | — (client-side) |
| 20 | Cancel button | Discard changes | **MVP** | — |
| 21 | 💾 บันทึก button | Save template | **MVP** | `export_templates` UPDATE |

**DB entities**: `export_templates` (existing) — JSONB `columns` field handles all column config.
**No new tables needed.**

---

### Screen 12: Cost Control — Internal System Admin Only

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | Date filter pills (วันนี้/สัปดาห์/เดือนนี้/กำหนดเอง) | Switch time range | **MVP** | Changes query WHERE clause |
| 2 | KPI: วันนี้ cost | Read aggregation | **Internal MVP** | `SUM(estimated_cost_usd) FROM api_usage WHERE DATE(created_at)=today` |
| 3 | KPI: เดือนนี้ cost | Read aggregation | **MVP** | Same, monthly |
| 4 | KPI: Tokens เดือนนี้ | Read aggregation | **MVP** | `SUM(input_tokens+output_tokens)` |
| 5 | KPI: Budget เหลือ | Computed | **MVP** | `budget_limits.max_usd - SUM(cost)` |
| 6 | Budget per company bars | Per-company budget usage | **MVP** | `api_usage GROUP BY company_id` vs `budget_limits` |
| 7 | ตั้งค่า Budget button | Open budget config | **MVP** | `budget_limits` CRUD |
| 8 | Model/Provider breakdown table | Detailed cost breakdown | **Internal MVP** | `api_usage GROUP BY company_id, model, stage` |
| 9 | Custom date range inputs | Date picker | **MVP** | — |

**DB entities**: `api_usage`, `budget_limits` (both existing) — no changes needed.
**Role guards**: LedgerFlow system-admin only. Hide from customer tenant admin/sidebar.

---

### Screen 13: Audit Log — Internal System Admin Only

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | 📥 Export CSV button | Export audit log | **Phase II/2** | Generate CSV from `audit_logs` |
| 2 | Filter: ผู้ใช้ | Dropdown filter | **MVP** | `audit_logs WHERE user_id=?` |
| 3 | Filter: ประเภทการกระทำ | Dropdown filter | **MVP** | `audit_logs WHERE action=?` |
| 4 | Filter: date range | Date inputs | **MVP** | `audit_logs WHERE created_at BETWEEN ? AND ?` |
| 5 | ค้นหา button | Apply filters | **MVP** | — |
| 6 | Audit table | Display log entries | **MVP** | `audit_logs` read |
| 7 | Action type badges | Color-coded actions | **MVP** | — (UI only) |
| 8 | โหลดเพิ่ม button | Pagination | **MVP** | OFFSET/LIMIT |

**DB entities**: `audit_logs` (existing) — no changes needed.
**Audit action types from prototype**: `login`, `upload`, `approve_scan`, `confirm_mapping`, `export`, `create_user`, `update_template`
**Role guards**: LedgerFlow system-admin only for cross-tenant/system audit. Customer-facing audit history, if needed, should be a separate tenant-scoped screen.

---

### Screen 14: Settings — Internal System Admin Only

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | Tab: Model Router | Show routing policy | **MVP** | — (read-only display for MVP) |
| 2 | Model routing table | Display model tiers | **MVP** | `Tenant.settings` JSONB or hardcoded |
| 3 | Budget threshold inputs | Edit tier limits | **MVP** | `budget_limits` UPDATE |
| 4 | Alert threshold input | Edit alert % | **MVP** | `budget_limits.alert_threshold_pct` |
| 5 | 💾 บันทึกการตั้งค่า | Save budget settings | **MVP** | `budget_limits` UPDATE |
| 6 | Tab: API Keys | Show/edit API keys | **disable** | MVP: keys in env vars only |
| 7 | Tab: System Status | Show connection statuses | **mock-only** | Health check endpoints |
| 8 | Tab: PDPA | Compliance checkboxes | **disable** | Phase II/2 |
| 9 | Data retention days input | Set retention | **Phase II/2** | `data_retention_policies` |
| 10 | 💾 บันทึก API Keys | Save keys | **disable** | Not in MVP — env vars |
| 11 | 💾 บันทึกนโยบาย PDPA | Save PDPA settings | **disable** | Phase II/2 |

**DB entities**: `budget_limits` (existing), `data_retention_policies` (existing but Phase II/2)
**Role guards**: LedgerFlow system-admin only. Hide Model Router, API Keys, System Status, PDPA, and provider cost settings from customer tenant admin/sidebar.

---

## Modals & Drawers Inventory

| # | Component | Trigger | Classification | DB Impact |
|---|-----------|---------|---------------|-----------|
| 1 | Flag Modal (`modal-flag`) | 🚩 Flag button on Review Scan | **MVP** | INSERT `document_flags` |
| 2 | Processing Error Modal (`modal-proc-error`) | "ดู Error" link on Processing | **MVP** | Read `Document.processing_error` |
| 3 | Export Preview Modal (`modal-export-preview`) | 👁 Preview on Export | **MVP** | Generate preview (no DB write) |
| 4 | Import COA Modal (`modal-import-coa`) | 📁 นำเข้า on Company Detail | **MVP** | Bulk INSERT `chart_of_accounts` |
| 5 | Company Drawer (`drawer-company`) | + เพิ่มบริษัท on Companies | **MVP** | INSERT/UPDATE `companies` |
| 6 | User Drawer (`drawer-user`) | + เพิ่มผู้ใช้ on Users | **MVP** | INSERT/UPDATE `users` + `user_company_assignments` |

---

## Top Bar & Navigation

| # | Element | Action | Classification | DB Impact |
|---|---------|--------|---------------|-----------|
| 1 | Company selector (top bar) | Switch active company context | **MVP** | Changes query filter for all screens |
| 2 | User name display | Show current user | **MVP** | From JWT payload |
| 3 | User avatar/logout | Logout action | **MVP** | Invalidate JWT, `audit_logs` insert |
| 4 | Sidebar navigation (13 items) | Screen navigation | **MVP** | — |
| 5 | Sidebar: Review badge count (23) | Show pending review count | **MVP** | Real-time count from `documents` |

---

## Mobile Behavior

**Current state**: Prototype is desktop-only. No responsive breakpoints, no mobile navigation.

**Decision**: Phase II/1 is **desktop-only**. Mobile/tablet support is Phase II/2 or Phase III.

**Rationale**: Target users (accountants at สำนักงานบัญชี) work on desktop. PDF review and data table interactions are not practical on mobile. This avoids adding responsive layout complexity to MVP.

---

## Dead / Non-functional Actions Identified

| Screen | Element | Current Behavior | Recommendation |
|--------|---------|-----------------|----------------|
| Settings | API Keys tab | Shows masked keys | **Internal only** — keys stay in env vars for MVP |
| Settings | PDPA tab | Shows checkboxes | **Internal only / Phase II/2** |
| Settings | System Status tab | Shows all "Connected" | **Internal mock-only** — implement health endpoints later |
| Company Detail | ตั้งค่า tab | Empty | **MVP patch required** — show COA defaults + mapping rules |
| Audit Log | Export CSV button | Toast only | **Phase II/2** — not critical for MVP |
| Dashboard | Trend arrows (↑/↓) | Static numbers | **mock-only** — needs historical data comparison |
| Templates | Create/View/Edit/Clone controls | Several controls dead | **MVP patch required** — open configurator/modal flows |
| Users | Edit/Reset PW controls | Dead controls | **MVP patch required** — open drawer/modal flows |
| Customer sidebar | Cost Control / Audit Log / Settings visible | Mixed customer admin with system admin | **MVP patch required** — move to internal workspace |

---

## Summary of New DB Entities Required

| Entity | Phase | Screens that need it |
|--------|-------|---------------------|
| `DocumentBatch` | **II/1 MVP** | Upload, Processing, Export, Audit Log |
| `FieldCorrection` | **II/1 MVP** | Review Scan |
| `DocumentFlag` | **II/1 MVP** | Review Scan |
| `ExportJob` | **II/1 MVP** | Export |
| `ExportFile` | **II/1 MVP** | Export |
| `ExportJobDocument` (join) | **II/1 MVP** | Export |
| `CompanyCreditPlan` | **II/1 MVP** | Dashboard page credits |
| `PageCreditUsage` | **II/1 MVP** | Dashboard page credits + billing audit |
| `Document` additions | **II/1 MVP** | Processing, Review Scan |
| `TemplateVersion` | **II/2** | Templates |
| `ReviewAssignment` | **II/2** | Review Scan |

## Document Field Additions Required

| Field | Type | Purpose | Screen |
|-------|------|---------|--------|
| `Document.scan_status` | Enum | Separate scan review status | Review Scan |
| `Document.scan_reviewed_by` | FK→users | Who approved scan | Review Scan |
| `Document.scan_reviewed_at` | DateTime | When scan was approved | Review Scan |
| `Document.processing_progress` | JSONB | 4-stage pipeline progress | Processing |
| `Document.batch_id` | FK→document_batches | **Change from UUID to FK** | Upload, Processing |

---

*Audit completed: 2026-06-20*
*Next: TASK-002 (Workflow State Machine) + TASK-003 (DB Impact Contract)*
