# Phase II Master Plan: AI Pre-Accounting Copilot / LedgerFlow

> **Status:** Approved for implementation
> **Approved:** 2026-06-14
> **Scope:** MVP (12 weeks) + Full (additional 6-8 weeks)
> **Team:** Solo/small developer

---

## Context

Phase I (PoC) พิสูจน์แล้วว่า Thai OCR + AI extraction ทำงานได้จริง pipeline สมบูรณ์ 4 stages (OCR → Field Extraction → LLM Repair → Journal Routing) พร้อม Excel export และ frontend prototype ที่ทำงานจริงบน VPS

**ปัญหาที่ Phase II ต้องแก้:** PoC ยัง stateless (ไม่มี DB จริง), ไม่มี auth, ไม่มี multi-tenant isolation, background jobs สูญหายเมื่อ restart, ไม่มี template engine สำหรับ custom export, และ accuracy ยังมีจุดอ่อน (VAT inclusive/exclusive, WHT, gridline OCR)

**เป้าหมาย:** ยก PoC ขึ้นเป็น MVP ที่ใช้งานจริง production-ready สำหรับสำนักงานบัญชีที่ดูแลหลายบริษัทลูกค้า โดยยึดสถาปัตยกรรมที่ออกแบบไว้ใน ARCHITECTURE.md และ MAPPING-ARCHITECTURE.md

---

## 1. Executive Summary

Phase II เปลี่ยน PoC ที่พิสูจน์แนวคิดแล้วเป็นระบบ pre-accounting ที่ใช้งานจริงได้ หลักๆ 5 ก้อนงาน:

1. **Foundation** — เปิดใช้ PostgreSQL + Alembic + Auth/RBAC + MinIO S3 + Celery (dependencies ทั้งหมดติดตั้งใน requirements.txt แล้ว ยังไม่ได้ใช้)
2. **Core Accuracy** — แก้ปัญหา VAT disambiguation, WHT, gridline OCR จาก user testing
3. **Template Engine** — dynamic column mapping สำหรับ export หลายรูปแบบ
4. **Platform Features** — หน้าจอ Login, Dashboard, Company/User management, Cost control
5. **Infrastructure** — Monitoring, PDPA compliance, UAT/Prod CI/CD

**แนะนำแบ่งเป็น 2 ก้อนราคา:**
- MVP (12 สัปดาห์): Foundation + Core Accuracy + Template Engine + Template Configurator UI + Login/Dashboard
- Full Phase II (เพิ่ม 6-8 สัปดาห์): RBAC 4 roles + Item-level extraction + Broker templates + PDPA + Monitoring

---

## 2. What Phase II Really Is

ระบบ **Pre-Accounting** ที่ช่วยนักบัญชีจัดการเอกสารก่อนบันทึกบัญชีในโปรแกรม Express:

```
สแกนเอกสาร → OCR อ่านข้อมูล → AI จัดประเภท+สกัดตัวเลข → ตรวจสอบ/แก้ไข → Export CSV/Excel → นำเข้า Express
```

**สิ่งที่ Phase II เพิ่มจาก PoC:**
- ระบบ Login และจัดการผู้ใช้ (PoC ไม่มี auth เลย)
- บันทึกข้อมูลลง Database จริง (PoC ใช้ไฟล์ cache ใน memory)
- Background processing ที่ไม่สูญหาย (PoC ใช้ ThreadPoolExecutor)
- Template engine สำหรับ export หลายรูปแบบตามลูกค้า
- ความแม่นยำสูงขึ้นจาก PoC feedback (VAT, WHT, gridline)
- เก็บไฟล์บน MinIO S3 storage (self-hosted) แทน disk ของ VPS
- Cost control และ budget monitoring ที่ track ได้จริง

---

## 3. What Phase II Is NOT

| ไม่ทำ | เหตุผล |
|-------|--------|
| ทดแทน Express Accounting | เราเป็น pre-accounting เท่านั้น ไม่ post GL |
| ระบบ Inventory เต็มรูปแบบ | จัดเตรียมข้อมูล SKU/Qty เท่านั้น ไม่มี stock management |
| ยื่นภาษีอัตโนมัติ | เตรียม template ภาษีซื้อ/ขาย แต่ไม่ส่ง e-filing |
| เชื่อมต่อ ERP โดยตรง | Phase III-IV |
| Mobile app | Web-only ผ่าน browser |
| Train custom ML model | ใช้ LLM API + rule engine ไม่ retrain model |
| React SPA rewrite | MVP ใช้ enhanced prototype HTML, React เป็น initiative แยก |
| Search/enrich missing debtor info | Phase III |

---

## 4. Scope Buckets

### A. Client Contract Scope (เก็บเงินลูกค้า)
- Core accuracy fixes (WHT, VAT, OCR)
- Template engine (dynamic export)
- Admin screens (Login, Dashboard, Upload, Review, Export)
- User/Company management
- RBAC (Admin/Staff minimum)
- Purchase/Sales tax report templates

### B. Internal Platform Dev (ลงทุนภายใน)
- PostgreSQL activation + Alembic
- Auth + JWT infrastructure
- Celery/Redis workers
- MinIO S3 storage (self-hosted, already in docker-compose)
- Model router enhancements

### C. Infra/DevOps
- UAT environment setup
- CI/CD pipeline for UAT → Prod
- Monitoring (Sentry, Uptime Kuma)

### D. Support/MA
- OS/Python patching schedule
- Dependency upgrade policy (quarterly)
- Backup strategy (DB + S3)
- SLA definition: bug fix ≤ 24h (critical), ≤ 3 days (normal)
- Change Request vs bug fix boundary

### E. Training
- User manual (Thai) — update
- Admin manual (ใหม่)
- Handover checklist

### F. Parking Lot (Phase III-IV)
- Search/enrich missing debtor info
- Tax filing workflows
- Direct ERP API integrations
- Full React SPA migration

---

## 5. Recommended MVP Phase II

**ระยะเวลา: 12 สัปดาห์** (solo developer)

| # | งาน | สัปดาห์ | Complexity | Req# |
|---|------|---------|-----------|------|
| 1 | SQLAlchemy models + Alembic + data migration | W1-2 | L | infra |
| 2 | JWT Authentication + basic RBAC (Admin/Staff) | W3-4 | M | infra |
| 3 | MinIO S3 storage integration (already in docker-compose) | W3-4 | M | 10 |
| 4 | VAT layout disambiguation (arithmetic-first) | W1-2 | L | 1,2 |
| 5 | WHT badge + backfill solver | W3-4 | M | 1,2 |
| 6 | Celery/Redis workers | W5-6 | M | infra |
| 7 | OCR gridline preprocessing | W5-6 | M | 1 |
| 8 | Template engine backend (data model + mapping + CSV/Excel) | W7-8 | L | **5,9** |
| 8b | **Template Configurator UI (drag-drop reorder, rename columns, field picker)** | W7-8 | **L** | **5,6,7** |
| 8c | **Master template cloning → company-specific templates** | W7-8 | **M** | **8,9** |
| 9 | Login screen + evolved upload/review screens | W9-10 | L | infra |
| 10 | Dashboard + cost control (budget to DB) | W9-10 | M | infra |
| 11 | Company management screen + COA import | W9-10 | M | 7 |
| 12 | Sentry integration + UAT CI/CD | W11-12 | M | 10 |

> **Updated 2026-06-14:** ย้าย Template Configurator UI (#8b) และ Template Cloning (#8c) เข้า MVP
> ตาม requirement #5-8 ที่ต้องให้ user เลือก field, ลำดับ column, ตั้งชื่อ, clone template
> MVP ขยายเป็น **12 สัปดาห์** (เพิ่ม 2 สัปดาห์สำหรับ Template UI + Login)

---

## 6. Full Phase II Scope (เพิ่มจาก MVP)

| # | งาน | สัปดาห์ | Complexity |
|---|------|---------|-----------|
| 13 | Full RBAC (4 roles + permissions matrix) | W11-12 | M |
| 14 | User management UI | W11-12 | M |
| 15 | Broker document template routing | W11-12 | M |
| 16 | Item-level extraction (SKU, Qty, Unit, Price) | W13-14 | L |
| 17 | Sales tax report template | W13-14 | M |
| 18 | Inventory data prep (structure only) | W13-14 | S |
| 19 | ~~Template cloning from Master~~ (**ย้ายเข้า MVP #8c แล้ว**) | — | — |
| 20 | PDPA compliance + data retention automation | W15-16 | M |
| 21 | Model router admin UI | W15-16 | S |
| 22 | Budget alert notifications | W17-18 | S |
| 23 | Password-protected PDF handling | W17-18 | S |
| 24 | Production hardening + load testing | W17-18 | M |

---

## 7. Application Menu Structure

```
┌─────────────────────────────────────────────────────┐
│ LedgerFlow                    [Company ▼]  [User ▼] │
├─────────────────────────────────────────────────────┤
│  Dashboard        ← สรุปภาพรวม, KPI, cost meter     │
│  Upload           ← Step 1-2: เลือกบริษัท+อัปโหลด   │
│  Processing       ← Step 3: สถานะ OCR pipeline      │
│  Review Scan      ← Step 4: ตรวจสอบข้อมูลสแกน       │
│  Review Mapping   ← Step 5: ตรวจ Dr/Cr mapping      │
│  Export           ← Step 6: เลือก template + export  │
│  ─────────────────                                  │
│  Companies        ← จัดการบริษัทลูกค้า + COA         │
│  Templates        ← จัดการ export templates          │
│  Users            ← จัดการผู้ใช้ (Admin only)        │
│  Cost Control     ← budget + usage dashboard        │
│  Audit Log        ← ประวัติการใช้งาน                 │
│  Settings         ← Model router, system config     │
└─────────────────────────────────────────────────────┘
```

---

## 8. User Role / Permission Matrix

| Permission | Admin | Manager | Staff | Reviewer |
|---|---|---|---|---|
| จัดการผู้ใช้ | Y | - | - | - |
| จัดการบริษัท | Y | - | - | - |
| จัดการ templates | Y | Y | - | - |
| ตั้ง budget limits | Y | - | - | - |
| อัปโหลดเอกสาร | Y | Y | Y | - |
| สั่ง process (OCR) | Y | Y | Y | - |
| Review scan | Y | Y | Y | Y |
| Review mapping | Y | Y | Y | Y |
| Confirm mapping | Y | Y | - | Y |
| Export | Y | Y | Y | - |
| ดู Dashboard | Y | Y | - | - |
| ดู Audit log | Y | Y | - | - |
| ดู Cost usage | Y | Y | - | - |
| จัดการ rules/COA | Y | Y | - | - |

**Multi-tenant:** ทุก query filter ด้วย `tenant_id` + Staff/Reviewer เห็นเฉพาะบริษัทที่ assign

**MVP:** 2 roles (Admin + Staff) | **Full:** 4 roles

---

## 9. Template Engine Design

### Data Model

```
export_templates
├── id, company_id (NULL = master), template_name
├── template_type: 'gl_ledger' | 'purchase_tax' | 'sales_tax' | 'inventory'
├── columns: JSONB (ordered column definitions)
├── static_values: JSONB (injected into every row)
├── file_format: 'csv' | 'xlsx'
├── encoding: 'utf-8' | 'tis-620'
├── is_master: boolean (cloneable)
└── cloned_from: FK → export_templates
```

### Column Definition

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

**Source fields:** extraction fields + journal routing fields + computed (company_name, export_date)

**Transforms:** `uppercase`, `pad_left:5:0`, `thai_date`, `strip_dash`

### Master Templates (pre-installed)

1. **Express GL** — 8 columns ตาม MAPPING-ARCHITECTURE.md Section 6
2. **Purchase Tax Report** — existing in export_service.py → template-based
3. **Sales Tax Report** — Full Phase II

### Template Configurator UI (Requirements #5-8)

> **เทคโนโลยี:** Enhanced vanilla HTML + SortableJS (drag-drop library)
> ไม่ต้อง React rewrite — ใช้ pattern เดียวกับ prototype ที่ Playwright-tested แล้ว

#### หน้าจอหลัก: Template Manager (`/templates`)

```
┌─────────────────────────────────────────────────────────────┐
│ Template Manager                          [+ New Template]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─ Master Templates ─────────────────────────────────────┐ │
│  │ Express GL Ledger (8 cols)          [Clone to Company]  │ │
│  │ Purchase Tax Report (12 cols)       [Clone to Company]  │ │
│  │ Sales Tax Report (12 cols)          [Clone to Company]  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─ Company: ABC Co. ─────────────────────────────────────┐ │
│  │ ABC GL Ledger (cloned, 10 cols)  [Edit] [Preview] [✕]  │ │
│  │ ABC Tax Report (custom, 8 cols)  [Edit] [Preview] [✕]  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌─ Company: XYZ Ltd. ────────────────────────────────────┐ │
│  │ XYZ GL Ledger (cloned, 8 cols)   [Edit] [Preview] [✕]  │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

#### หน้าจอแก้ไข: Template Configurator (`/templates/{id}/edit`)

```
┌─────────────────────────────────────────────────────────────┐
│ Edit Template: ABC GL Ledger                    [Save] [✕]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Template Name: [ABC GL Ledger      ]                       │
│  Format: [CSV ▼]   Encoding: [UTF-8 BOM ▼]                 │
│  Delimiter: [, ▼]  (CSV only)                               │
│                                                             │
│  ┌─ Available Fields ────────┐  ┌─ Selected Columns ────────┐│
│  │                          │  │ (drag to reorder)          ││
│  │  □ invoice_number        │  │ ☰ 1. Voucher_No           ││
│  │  □ invoice_date          │→ │    Source: voucher_no      ││
│  │  □ seller_name           │  │    [Rename] [✕]            ││
│  │  □ seller_tax_id         │  │                            ││
│  │  □ buyer_name            │  │ ☰ 2. Date                 ││
│  │  □ buyer_tax_id          │  │    Source: voucher_date    ││
│  │  □ net_amount            │  │    Format: YYYY-MM-DD      ││
│  │  □ vat_amount            │  │    [Rename] [✕]            ││
│  │  □ wht_amount            │  │                            ││
│  │  □ total_amount          │  │ ☰ 3. Book_Code            ││
│  │  □ document_type         │  │    Source: book_code       ││
│  │  ─── Journal Fields ───  │  │    [Rename] [✕]            ││
│  │  □ voucher_no            │  │                            ││
│  │  □ voucher_date          │  │ ☰ 4. Account_Code         ││
│  │  □ book_code             │  │    Source: account_code    ││
│  │  □ account_code          │  │    [Rename] [✕]            ││
│  │  □ account_name          │  │                            ││
│  │  □ debit                 │  │ ☰ 5. Debit_Amount         ││
│  │  □ credit                │  │    Source: debit           ││
│  │  □ description           │  │    Format: #,##0.00        ││
│  │  ─── Computed ─────────  │  │    [Rename] [✕]            ││
│  │  □ company_name          │  │                            ││
│  │  □ company_tax_id        │  │ ... (drag items up/down)   ││
│  │  □ export_date           │  │                            ││
│  │  ─── Static Value ─────  │  │ [+ Add Static Column]     ││
│  │  [+ Add Static Field]   │  └──────────────────────────── ┘│
│  └──────────────────────────┘                               │
│                                                             │
│  ┌─ Preview (first 5 rows) ─────────────────────────────── ┐│
│  │ Voucher_No | Date       | Book_Code | Account_Code | ...││
│  │ PV-001     | 2026-06-14 | 11        | 51101        | ...││
│  │ PV-001     | 2026-06-14 | 11        | 11001        | ...││
│  └──────────────────────────────────────────────────────── ┘│
└─────────────────────────────────────────────────────────────┘
```

#### UI Interactions (Req #5-8 coverage)

| Requirement | UI Feature | Implementation |
|---|---|---|
| **#5** เลือก fields ที่ต้องการ export | Checkbox field picker (Available → Selected) | Click checkbox = add to Selected Columns list |
| **#6** ลำดับ columns + rename | Drag-drop reorder (☰ handle) + inline rename button | SortableJS library + contenteditable / modal input |
| **#7** Account code column mapping | account_code field available + COA lookup helper | Field picker includes journal fields; optional COA dropdown |
| **#8** Clone master → company template | [Clone to Company] button on master templates | POST `/api/v1/templates/{master_id}/clone` with target company_id |
| **#9** Export ตาม template | Template selector on Export screen | Dropdown → preview → download |

#### Clone Workflow

```
1. User คลิก [Clone to Company] บน Master template
2. เลือก company ปลายทาง (dropdown)
3. ตั้งชื่อ template ใหม่ (default: "{company_name} {master_name}")
4. ระบบ deep-copy columns JSONB → ผูก company_id + cloned_from FK
5. เปิด Template Configurator ให้แก้ไข columns ได้ทันที
6. แก้ column order, rename headers, เพิ่ม/ลบ fields ตามต้องการ
7. Save → พร้อมใช้ตอน Export
```

#### Technical Implementation

- **SortableJS** — CDN หรือ vendor file, ~10 KB gzip
- **API endpoints:**
  - `GET /api/v1/templates` — list by company
  - `POST /api/v1/templates` — create new
  - `GET /api/v1/templates/{id}` — get with columns
  - `PUT /api/v1/templates/{id}` — update (columns order, names, etc.)
  - `DELETE /api/v1/templates/{id}` — soft delete
  - `POST /api/v1/templates/{id}/clone` — clone master → company
  - `POST /api/v1/templates/{id}/preview` — preview with sample data
- **Frontend files:**
  - เพิ่ม Template Manager tab ใน `ux-ui-prototype.html`
  - SortableJS initialize บน Selected Columns list
  - Column rename: click [Rename] → inline input → blur saves
  - Preview table: fetch first 5 rows from API

### Workflow (Updated)

1. Admin สร้าง template ใหม่ หรือ clone จาก Master → company
2. เปิด Template Configurator → เลือก fields, drag-drop ลำดับ, rename columns
3. Preview ตัวอย่าง 5 rows → Save
4. Accountant ตอน Export → เลือก template จาก dropdown → preview → download CSV/Excel

### Files
- สร้าง `src/backend/services/template_engine.py` — mapping engine
- แก้ไข `src/backend/services/export_service.py` — ใช้ template_id แทน hardcode
- สร้าง `src/backend/api/templates.py` — CRUD + clone + preview endpoints
- แก้ไข `src/frontend/ux-ui-prototype.html` — Template Manager + Configurator UI
- เพิ่ม `src/frontend/vendor/sortable.min.js` — SortableJS library

---

## 10. OCR / Extraction Pipeline (with Background Job)

### Phase II Pipeline (Celery-based)
```
POST /api/v1/documents/upload
  → validate → upload MinIO S3 → create document record → return document_id

POST /api/v1/documents/{id}/process
  → dispatch Celery task → return job_id

Celery Worker:
  → ocr.py (+ gridline removal)
  → field_extractor.py (+ WHT enhancements)
  → amount_reconciler.py (arithmetic-first VAT)
  → llm_router.py (budget from DB)
  → rule_engine.py
  → write extraction + journal to DB
  → log api_usage
  → update status: review_scan
```

### Accuracy Enhancements

**VAT Disambiguation:** `amount_reconciler.py` — test all 4 combinations (2 slots x 2 modes), pick best

**WHT Solver:** `field_extractor.py` — rate patterns (1-10%), backfill when partial data, has_wht flag

**OCR Gridline:** `ocr.py` — OpenCV morphological line removal before OCR

---

## 11. Excel / CSV Export Workflow

```
POST /api/v1/export { template_id, document_ids[], format }
  → load template → load data → map fields → generate → return URL
```

- CSV: configurable delimiter, encoding (UTF-8 BOM or TIS-620)
- Excel: styled worksheets (keep existing xlsxwriter)
- Balance validation before export: Sum(Dr) = Sum(Cr) per voucher

---

## 12. Model Router / Multi-Model Fallback

### Current (Working)
- OpenRouter (Gemini Flash) → Anthropic (Claude Sonnet 4) fallback
- Budget guards: $1/day free, $2/day paid (JSON file)

### Phase II Enhancements
1. Budget tracking → `api_usage` DB table
2. Per-company limits → `budget_limits` table
3. Admin UI for routing config
4. 80% budget alert mechanism

---

## 13. Cost Control Design

**`api_usage`** — every LLM call logged: company, user, document, provider, model, tokens, cost, tier

**`budget_limits`** — per-company or global: daily/monthly caps, alert threshold

### Enforcement Flow
```
Upload → check monthly budget → exceeded? → 429
Stage C → check daily budget → exceeded? → skip repair (regex-only)
80% threshold → emit warning
```

---

## 14. Database Schema (Multi-tenancy)

### Design: company-scoped multi-tenancy

```sql
tenants (id, name, slug, settings, created_at)
companies (id, tenant_id, name, tax_id, branch_code, address, business_type, settings, is_active)
users (id, tenant_id, email, username, password_hash, display_name, role, is_active, last_login)
user_company_assignments (id, user_id, company_id, role_override, assigned_at)
documents (id, company_id, uploaded_by, filename, storage_key, file_size_bytes, content_type,
           document_type, status, sha256, page_count, buyer_tax_id, seller_tax_id, seller_name,
           invoice_number, invoice_date, net_amount, vat_amount, wht_amount, total_amount,
           has_vat, vat_rate, wht_rate, taxid_match, overall_confidence, batch_id)
extractions (id, document_id, extraction_json, confidence_per_field, stage_c_applied,
             stage_c_provider, stage_c_model, schema_version)
journal_vouchers (id, document_id, voucher_no, voucher_date, book_code, rule_id, status,
                  is_balanced, total_debit, total_credit, confirmed_by, confirmed_at)
journal_lines (id, voucher_id, line_order, account_code, account_name, is_debit, amount,
               description, amount_field)
chart_of_accounts (id, company_id, account_code, account_name, account_type, is_active)
account_mapping_rules (id, company_id, vendor_name, document_type, recommended_debit_code,
                       confirmed_count, last_confirmed_at)
export_templates (id, company_id, template_name, template_type, columns, static_values,
                  file_format, encoding, is_master, cloned_from)
api_usage (id, company_id, user_id, document_id, provider, model, stage, input_tokens,
           output_tokens, estimated_cost_usd, tier, was_skipped)
budget_limits (id, company_id, limit_type, tier, max_usd, alert_threshold_pct, is_active)
audit_logs (id, tenant_id, company_id, user_id, document_id, action, entity_type, entity_id,
            old_values, new_values, ip_address)
data_retention_policies (id, tenant_id, entity_type, retention_days, action, is_active, last_run_at)
```

### Migration Strategy: Dual-mode
- W1-2: DB alongside files (write both)
- W3-4: Primary reads from DB (fallback files)
- W5+: Remove file fallback for user data
- YAML rules stay file-based permanently (git-versioned configuration)

---

## 15. UAT / Production Infra

| Env | Branch | Domain | Storage |
|-----|--------|--------|---------|
| dev | dev | localhost | Local disk |
| poc | poc | poc-aiaccount.yahwan.biz | VPS disk |
| uat | uat | uat-aiaccount.yahwan.biz | MinIO S3 |
| prod | main | app-aiaccount.yahwan.biz | MinIO S3 |

### Docker Compose (Phase II adds)
- celery-worker: Celery worker for OCR/extraction
- celery-beat: periodic tasks (PDPA cleanup, budget reset)

### VPS: 2-4 vCPU, 4-8 GB RAM, 50 GB SSD

### Design Capacity: 10,000-20,000 docs/month

- Pipeline throughput: ~30s/doc → Celery worker handles ~2,800 docs/day (single worker)
- Scale-out: เพิ่ม worker replicas ได้ตาม load
- Storage: MinIO bucket auto-scales, DB indexed for high-volume queries

---

## 16. CI/CD Deployment Plan

### Branch: dev → poc → uat → main (via Openclaw Control Plane)

### CI per PR: ruff + mypy + pytest + Alembic check
### CD: SSH → git pull → docker build → alembic upgrade → restart → health check → Playwright smoke

---

## 17. Monitoring: Sentry (MVP) + Uptime Kuma (MVP) + structlog (MVP) + Prometheus (Full)

## 18. MA: Critical bug ≤24h, Normal ≤3 days, Templates ≤2/month in MA

## 19. Training: User Manual + Admin Manual + System Guide + Handover Checklist

---

## 20. Risks / Questions for Client

### Key Risks
- Express CSV format ยังไม่ได้ตัวอย่าง → ต้องได้ก่อนเริ่ม template engine
- Solo dev bus factor → documentation + tests as insurance
- LLM cost uncertainty → budget guards + free tier models

### Questions
1. Express CSV format sample?
2. 2 roles or 4 roles for MVP?
3. How many client companies?
4. LLM budget per month?
5. Data retention days? (recommend 30 days)

---

## 21. Pricing: MVP ฿260-350K, Full +฿150-200K, MA ฿9-18K/month

## 22. Contract Scope: See plan file for In-Scope (13 items) and Out-of-Scope (9 items)

## 23. Next Actions

1. Get Express CSV sample from client
2. Confirm MVP vs Full scope
3. Verify MinIO S3 storage (already in docker-compose)
4. Start: SQLAlchemy models + Alembic + VAT disambiguation (parallel)

---

### Critical Files to Modify

| File | Changes |
|------|---------|
| `src/backend/app/endpoints.py` | Auth dependencies, DB writes, new endpoints |
| `src/backend/pipeline/orchestrator.py` | Celery task wrapper, DB records |
| `src/backend/ml/amount_reconciler.py` | Arithmetic-first VAT classifier |
| `src/backend/ml/field_extractor.py` | WHT detection enhancements |
| `src/backend/ml/ocr.py` | Gridline removal preprocessing |
| `src/backend/services/export_service.py` | Template-based export |
| `src/backend/ml/llm_router.py` | Budget tracking to DB |
| `config/settings.py` | DB URL, S3, Celery config |
| `docker/docker-compose.dev.yml` | celery-worker, celery-beat services |
| `requirements.txt` | celery, sentry-sdk, opencv-python-headless |

### New Files to Create

| File | Purpose |
|------|---------|
| `src/backend/db/base.py` | SQLAlchemy declarative base |
| `src/backend/db/models.py` | All DB models |
| `src/backend/db/session.py` | AsyncSession factory |
| `src/backend/auth/auth.py` | JWT token logic |
| `src/backend/auth/dependencies.py` | FastAPI auth dependencies |
| `src/backend/auth/router.py` | Auth endpoints |
| `src/backend/storage/s3.py` | MinIO S3 client (boto3) |
| `src/backend/storage/local.py` | Local fallback |
| `src/backend/workers/celery_app.py` | Celery config |
| `src/backend/workers/tasks.py` | Pipeline Celery task |
| `src/backend/services/template_engine.py` | Column mapping engine |
| `alembic/` | Migration directory |
