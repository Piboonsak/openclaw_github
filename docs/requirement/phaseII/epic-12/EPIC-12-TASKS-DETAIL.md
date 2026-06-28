# Epic 12 — Tasks Detail

> Admin UI + Login (W5-W6)
> Parent: [README-EPIC-12.md](README-EPIC-12.md)

---

## TASK-1201: Login screen + JWT session management

**Owner**: Full-stack Dev
**Risk**: HIGH
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-8

### Purpose

สร้างหน้า Login ที่เชื่อมกับ JWT auth backend (TASK-803) -- login form, token storage, auto-refresh, logout, protected route redirect. เป็น gate สำหรับทุกหน้าจอที่ต้อง authenticate ใน production.

### What exists today

- Frontend prototype (`src/frontend/ux-ui-prototype.html`) with tabs for Upload, Review, Export -- ไม่มี login
- JWT auth backend จะถูกสร้างใน TASK-803 (Epic 8):
  - POST /api/v1/auth/login -- returns access_token + refresh_token
  - POST /api/v1/auth/refresh -- returns new access_token
  - GET /api/v1/auth/me -- returns current user info
- DB models for `users` table with password_hash, role, is_active

### What to build

1. **Login page:**
   - Username + password form
   - POST /api/v1/auth/login on submit
   - Show error message on invalid credentials (401)
   - Redirect to Dashboard on success
2. **Token management:**
   - Store JWT access_token in localStorage
   - Store refresh_token in localStorage (MVP) -- consider httpOnly cookie post-MVP
   - Attach `Authorization: Bearer {token}` header to all API requests
   - Auto-refresh: check token expiry, call /api/v1/auth/refresh before expiry (~5 min before)
3. **Protected routes:**
   - On page load: check if valid token exists in localStorage
   - If no token or expired (and refresh fails): redirect to login page
   - After login: redirect back to originally requested page (or Dashboard)
4. **Logout:**
   - Clear access_token and refresh_token from localStorage
   - Redirect to login page
   - [Logout] button in top-right user menu
5. **User display:**
   - Show current user display_name + role in header area
   - Fetch from GET /api/v1/auth/me on page load

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/frontend/ux-ui-prototype.html` | Add Login page, token management JS, protected route logic, user display in header, logout button |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1201_login | Login form submits credentials, receives JWT, stores in localStorage | test_login_flow (Playwright) |
| ac_1201_invalid | Invalid credentials show error message, no token stored | test_invalid_login (Playwright) |
| ac_1201_protect | Accessing protected page without token redirects to login | test_protected_redirect (Playwright) |
| ac_1201_refresh | Token auto-refreshes before expiry (no user interruption) | test_token_refresh |
| ac_1201_logout | Logout clears tokens and redirects to login page | test_logout (Playwright) |
| ac_1201_header | Authorization header attached to all API requests after login | test_auth_header |
| ac_1201_display | Current user display_name and role shown in header | test_user_display (Playwright) |

### Governance fields

```json
{
  "task_id": "TASK-1201",
  "risk_tier": "HIGH",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/frontend/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1202: MVP Dashboard

**Owner**: Full-stack Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-11

### Purpose

Dashboard แสดงภาพรวมการทำงานของระบบ -- จำนวนเอกสาร, สถานะ processing, recent activity, และ cost meter (LLM usage vs budget). ให้ Admin/Staff เห็นสถานะงานทั้งหมดในหน้าเดียว.

### What exists today

- Frontend prototype มี tab structure แต่ไม่มี Dashboard tab
- DB models for `documents` (status field), `api_usage` (LLM costs), `audit_logs` (activity)
- No dashboard API endpoint

### What to build

1. **Dashboard API endpoint:**
   - `GET /api/v1/dashboard/stats`
   - Response:
     ```json
     {
       "document_counts": {
         "total": 150,
         "today": 12,
         "this_month": 89
       },
       "status_breakdown": {
         "uploaded": 5,
         "processing": 2,
         "review_scan": 30,
         "review_mapping": 25,
         "exported": 77
       },
       "recent_activity": [
         { "action": "upload", "document": "INV-001.pdf", "user": "somchai", "timestamp": "..." }
       ],
       "cost_meter": {
         "used_usd": 12.50,
         "budget_usd": 50.00,
         "percentage": 25.0
       }
     }
     ```
   - Scoped by company (Staff sees assigned companies only, Admin sees all)
2. **Dashboard UI (new tab):**
   - **Document count cards**: Total / Today / This Month with icons
   - **Status breakdown**: horizontal stacked bar or donut chart (simple CSS, no chart library for MVP)
   - **Recent activity feed**: last 10 actions (upload, process, confirm, export) with timestamp + user
   - **Cost meter**: progress bar showing LLM usage vs monthly budget (color: green < 60%, yellow 60-80%, red > 80%)
3. **Auto-refresh**: refresh dashboard data every 30 seconds (or manual refresh button)

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/api/dashboard.py` | FastAPI router with GET /api/v1/dashboard/stats |
| Modify | `src/backend/app/endpoints.py` | Mount dashboard router |
| Modify | `src/frontend/ux-ui-prototype.html` | Add Dashboard tab with stats cards, status breakdown, activity feed, cost meter |
| Create | `tests/api/test_dashboard.py` | Dashboard API tests (counts, scoping, cost calculation) |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1202_counts | Document counts (total, today, this_month) are accurate from DB | test_document_counts |
| ac_1202_status | Status breakdown matches actual document statuses in DB | test_status_breakdown |
| ac_1202_activity | Recent activity shows last 10 actions with correct user and timestamp | test_recent_activity |
| ac_1202_cost | Cost meter reflects actual api_usage sum vs budget_limits | test_cost_meter |
| ac_1202_scope | Staff user sees only assigned companies' data | test_dashboard_scoping |
| ac_1202_ui | Dashboard renders all 4 sections (counts, status, activity, cost) | test_dashboard_render (Playwright) |

### Governance fields

```json
{
  "task_id": "TASK-1202",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/frontend/**", "src/backend/api/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1203: Company management + COA import

**Owner**: Full-stack Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-8

### Purpose

หน้าจอจัดการบริษัทลูกค้า (add/edit) และ import ผังบัญชี (Chart of Accounts) จาก YAML หรือ CSV file. สำนักงานบัญชีดูแลหลายบริษัท ต้องมี COA แยกแต่ละบริษัท.

### What exists today

- DB models: `companies` table (name, tax_id, branch_code, address, business_type, settings, is_active) and `chart_of_accounts` table (company_id, account_code, account_name, account_type, is_active)
- `companies.json` file used by PoC for company list (will be migrated to DB in TASK-802)
- Frontend has company selector dropdown on Upload tab but no management screen

### What to build

1. **Company CRUD API endpoints:**
   - `GET /api/v1/companies` -- list companies (tenant-scoped)
   - `POST /api/v1/companies` -- create new company
   - `GET /api/v1/companies/{id}` -- get company detail
   - `PUT /api/v1/companies/{id}` -- update company
2. **COA import API:**
   - `POST /api/v1/companies/{id}/coa/import` -- upload YAML or CSV file
   - YAML format:
     ```yaml
     accounts:
       - code: "11001"
         name: "เงินสด"
         type: "asset"
       - code: "21001"
         name: "เจ้าหนี้การค้า"
         type: "liability"
     ```
   - CSV format: `account_code,account_name,account_type` (header row required)
   - Upsert logic: update if account_code exists for company, create if new
3. **COA list API:**
   - `GET /api/v1/companies/{id}/coa` -- list accounts for company (paginated)
4. **COA import from PDF** *(added 2026-06-27 — client has 3 PDF COA files)*:
   - `POST /api/v1/companies/{id}/coa/import-pdf` — upload PDF → AI extract → preview JSON → save
   - AI extraction: ใช้ Claude API อ่าน PDF → return structured list `[{account_code, account_name, account_type}]`
   - Data files on hand: `private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ ผังบัญชี.pdf`, Comp_2, Comp_3
   - Review step: show extracted rows ให้ human confirm ก่อน upsert (กัน hallucination)
5. **enable_stock flag** *(added 2026-06-27 — ประหยัดค่า OCR สำหรับบริษัทที่ไม่ต้อง line items)*:
   - DB: `ALTER TABLE companies ADD COLUMN enable_stock BOOLEAN NOT NULL DEFAULT FALSE`
   - API: include `enable_stock` in `PUT /api/v1/companies/{id}` request/response
   - Pipeline: ถ้า `enable_stock=False` → skip line item OCR + skip line item confirm step
   - UI checkbox: ☐ "สแกน Line Items (สินค้า)" บนหน้า Add/Edit Company — unchecked by default
   - Tooltip: "ปิดใช้งานเพื่อประหยัดค่า OCR สำหรับบริษัทที่ไม่ต้อง track สินค้า"
6. **Company management UI (new tab):**
   - Company list with [Add] button
   - Add/Edit form (name, tax_id, branch_code, address, business_type, `enable_stock` checkbox)
   - Per-company COA section:
     - [Import COA] button (file upload: .yaml, .yml, .csv, .pdf)
     - PDF: แสดง extracted preview → [Confirm & Save] หรือ [Edit Before Save]
     - COA table: account_code | account_name | account_type
     - Search/filter by account_code or name
7. **Validation:**
   - tax_id: 13 digits, unique per tenant
   - account_code: unique per company
   - Reject invalid YAML/CSV format with clear error message

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/api/companies.py` | FastAPI router for company CRUD + COA import (YAML/CSV/PDF) |
| Create | `src/backend/api/schemas/company_schemas.py` | Pydantic models for company + COA (include enable_stock) |
| Create | `alembic/versions/012_add_enable_stock.py` | ALTER TABLE companies ADD COLUMN enable_stock BOOLEAN DEFAULT FALSE |
| Modify | `src/backend/db/models.py` | Add enable_stock field to Company model |
| Modify | `src/backend/services/document_pipeline.py` | Skip line_item_ocr + line_item_confirm if enable_stock=False |
| Modify | `src/backend/app/endpoints.py` | Mount company router |
| Modify | `src/frontend/ux-ui-prototype.html` | Companies tab with CRUD UI + COA import + enable_stock checkbox |
| Create | `tests/api/test_companies.py` | Company CRUD + COA import + enable_stock + pipeline skip tests |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1203_list | GET /api/v1/companies returns tenant-scoped company list | test_list_companies |
| ac_1203_create | POST /api/v1/companies creates company with all fields | test_create_company |
| ac_1203_update | PUT /api/v1/companies/{id} updates company data | test_update_company |
| ac_1203_taxid | Duplicate tax_id within tenant is rejected (409 Conflict) | test_duplicate_taxid |
| ac_1203_coa_yaml | COA import from YAML creates chart_of_accounts records | test_coa_import_yaml |
| ac_1203_coa_csv | COA import from CSV creates chart_of_accounts records | test_coa_import_csv |
| ac_1203_coa_upsert | Re-importing COA updates existing accounts (by code), creates new ones | test_coa_upsert |
| ac_1203_coa_list | GET /api/v1/companies/{id}/coa returns accounts for specific company | test_coa_list |
| ac_1203_coa_pdf | POST /coa/import-pdf extracts account_code + account_name from PDF (≥90% rows correct) | test_coa_pdf_extract |
| ac_1203_coa_review | PDF import shows extracted preview for human confirm before DB save | test_coa_pdf_review_step |
| ac_1203_enable_stock_default | New company has enable_stock=False by default | test_enable_stock_default |
| ac_1203_enable_stock_skip | enable_stock=False → line_item_ocr step NOT called during document processing | test_pipeline_skip_line_items |
| ac_1203_enable_stock_include | enable_stock=True → line_item_ocr called normally | test_pipeline_include_line_items |
| ac_1203_enable_stock_ui | Company edit form has enable_stock checkbox, saves and reloads correctly | test_enable_stock_ui (Playwright) |

### Governance fields

```json
{
  "task_id": "TASK-1203",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/frontend/**", "src/backend/api/**", "src/backend/db/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1204: User management + RBAC (3 roles MVP)

**Owner**: Full-stack Dev
**Risk**: HIGH
**Duration**: ~3 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-8
**Updated**: 2026-06-27 — เพิ่ม sys_admin role (ลูกค้ายืนยันใน meeting)

### Purpose

หน้าจอจัดการ users (Admin/SysAdmin only) และ role-based access control สำหรับ MVP — **3 roles**:

| Role | ความสามารถ |
|------|-----------|
| `staff` | เห็นเฉพาะบริษัทที่ assign, upload/review/export ได้ ไม่ manage users |
| `admin` | เห็นทุกบริษัท, manage users (staff/admin), import masters, clone templates |
| `sys_admin` | ทุกอย่างของ admin + เมนู internal: system logs, billing, สร้าง/ลบ company, deploy config |

> **Note**: DB schema รองรับ 4 roles มาตั้งแต่ต้น ปรับ enforce จาก 2 → 3 roles

### What exists today

- DB models: `users` table (email, username, password_hash, display_name, role, is_active, last_login) and `user_company_assignments` table (user_id, company_id, role_override, assigned_at)
- JWT auth from TASK-803 provides current user identity
- No user management UI or RBAC enforcement on endpoints

### What to build

1. **User management API (Admin/SysAdmin only):**
   - `GET /api/v1/users` — list users (tenant-scoped, Admin+ only)
   - `POST /api/v1/users` — create user (Admin+ only)
   - `GET /api/v1/users/{id}` — get user detail
   - `PUT /api/v1/users/{id}` — update user (email, display_name, role, is_active)
   - `POST /api/v1/users/{id}/assign-companies` — assign user to companies
   - `DELETE /api/v1/users/{id}/assign-companies/{company_id}` — remove assignment
2. **SysAdmin-only internal API:**
   - `GET /api/admin/logs` — system audit logs (SysAdmin only)
   - `GET /api/admin/billing` — API cost/usage (SysAdmin only)
   - `POST /api/v1/companies` — create company (SysAdmin only — Admin can edit, not create)
   - `DELETE /api/v1/companies/{id}` — delete company (SysAdmin only)
3. **RBAC middleware / dependency (3-tier):**
   - `require_role("staff")` — any authenticated user
   - `require_role("admin")` — Admin or SysAdmin
   - `require_role("sys_admin")` — SysAdmin only
   - JWT payload: `role: "staff" | "admin" | "sys_admin"`
   - Company scoping: Staff auto-filter by `user_company_assignments`; Admin/SysAdmin see all
4. **User management UI:**
   - User list table: username, display_name, email, role (badge), status, last_login
   - Role dropdown: Staff / Admin / SysAdmin (SysAdmin can assign any role; Admin cannot assign SysAdmin)
   - Company assignments: checklist per user
5. **SysAdmin-only UI sections (hidden for admin/staff):**
   - "System" menu item in sidebar
   - System Logs viewer
   - Billing/cost dashboard
   - Company create/delete buttons
6. **Company scoping enforcement:**
   - Staff: `WHERE company_id IN (SELECT company_id FROM user_company_assignments WHERE user_id = ?)`
   - Admin/SysAdmin: no company restriction (see all within tenant)
7. **Role validation summary:**
   - Document operations: Staff+ (own companies)
   - User management: Admin+ (403 for Staff)
   - Template master management: Admin+ (403 for Staff)
   - Internal menus: SysAdmin only (403 for Admin/Staff)
   - Seed admin user: uses `sys_admin` role (was previously admin)

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/api/users.py` | FastAPI router for user CRUD + company assignment |
| Create | `src/backend/api/schemas/user_schemas.py` | Pydantic models for user management |
| Create | `src/backend/auth/rbac.py` | RBAC dependency: require_role(), get_company_scope() |
| Modify | `src/backend/app/endpoints.py` | Mount user router, apply RBAC to existing endpoints |
| Modify | `src/frontend/ux-ui-prototype.html` | Add Users tab (Admin only), company assignment UI |
| Create | `tests/api/test_users.py` | User CRUD tests |
| Create | `tests/auth/test_rbac.py` | RBAC enforcement tests (role check, company scoping) |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1204_list | GET /api/v1/users returns user list (Admin+ only, 403 for Staff) | test_list_users_admin_only |
| ac_1204_create | POST /api/v1/users creates user with hashed password and role | test_create_user |
| ac_1204_assign | POST /api/v1/users/{id}/assign-companies creates assignment records | test_assign_companies |
| ac_1204_staff_scope | Staff user queries return only data from assigned companies | test_staff_company_scope |
| ac_1204_admin_scope | Admin/SysAdmin queries return all companies within tenant | test_admin_tenant_scope |
| ac_1204_role_403 | Staff accessing admin-only endpoints receives 403 Forbidden | test_role_enforcement |
| ac_1204_sysadmin | SysAdmin token can access GET /api/admin/logs (200 OK) | test_sysadmin_logs_access |
| ac_1204_admin_deny | Admin token receives 403 at GET /api/admin/logs | test_admin_deny_logs |
| ac_1204_staff_deny | Staff token receives 403 at POST /api/v1/companies (create) | test_staff_deny_company_create |
| ac_1204_ui | Users tab visible to Admin+ role only, hidden for Staff | test_admin_tab_visibility (Playwright) |
| ac_1204_system_menu | System menu visible to SysAdmin only, hidden for Admin/Staff | test_sysadmin_menu (Playwright) |
| ac_1204_assignment_ui | Company assignment checklist works (check/uncheck saves) | test_company_assignment_ui (Playwright) |

### Governance fields

```json
{
  "task_id": "TASK-1204",
  "risk_tier": "HIGH",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/frontend/**", "src/backend/api/**", "src/backend/auth/**", "src/backend/db/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/ml/**", "src/backend/pipeline/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1207: Vendor & Customer master import

**Owner**: Full-stack Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-5
**Added**: 2026-06-15 — client requirement + [CLIENT-TEMPLATE-ANALYSIS.md](../epic-10/CLIENT-TEMPLATE-ANALYSIS.md) gap analysis

### Purpose

Import รายชื่อผู้จำหน่าย (Vendor) และ รายชื่อลูกค้า (Customer) เข้าระบบ เพื่อให้ template export engine (Epic 10) สามารถ lookup vendor_code → vendor_name และ customer_code → customer_name ได้. เป็น master data ที่จำเป็นต่อการ export CSV สำหรับ Express Accounting.

### Client requirement (verbatim)

> "วันก่อนเห็นว่า มีการโยนผังบัญชีเข้าไปได้ ซึ่งแต่ละบริษัท ผังต่างกัน
> ถ้าพี่มี list รายชื่อผู้จำหน่าย, รายชื่อลูกค้า เข้าไปในระบบ,
> ai สามารถตรวจเช็คและเลือก รหัสผู้จำหน่าย หรือ รหัส ลูกหนี้ ขึ้นมาใส่ให้ได้เองไหมคะ
> กรณีที่มีเจ้าหนี้ หรือ ลูกหนี้รายใหม่ เพิ่มเข้ามา"

### Requirement decomposition

| Sub-requirement | Scope | Phase |
| --- | --- | --- |
| **A. Import vendor/customer lists** (CSV/Excel upload, CRUD) | This task (TASK-1207) | **II/1** |
| **B. AI auto-match** vendor/customer from OCR (fuzzy match seller_name → vendor_code) | [BACKLOG BL-001](../BACKLOG.md) | **Backlog** |
| **C. New vendor/customer detection** (flag unknown entities for user to create) | [BACKLOG BL-001](../BACKLOG.md) | **Backlog** |

This task covers **Sub-requirement A only**. Sub-requirements B and C are AI/ML features that require fuzzy matching, confidence scoring, and user confirmation workflow — deferred to backlog.

### What exists today

- COA import pattern established in TASK-1203: `POST /api/v1/companies/{id}/coa/import` (CSV/YAML → DB upsert)
- DB model `ChartOfAccount` in `src/backend/db/models.py` with company_id, code, name, type pattern
- No vendor or customer DB models exist yet
- Template engine (TASK-1001) lists `vendor_code`, `vendor_name`, `customer_code`, `customer_name` as Express source fields requiring master lookup

### What to build

1. **DB models:**

   ```python
   class Vendor(Base):
       __tablename__ = "vendors"
       id = Column(Integer, primary_key=True)
       company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
       vendor_code = Column(String(20), nullable=False)
       vendor_name = Column(String(200), nullable=False)
       tax_id = Column(String(13), nullable=True)
       is_active = Column(Boolean, default=True)
       # Unique constraint: (company_id, vendor_code)

   class Customer(Base):
       __tablename__ = "customers"
       id = Column(Integer, primary_key=True)
       company_id = Column(Integer, ForeignKey("companies.id"), nullable=False)
       customer_code = Column(String(20), nullable=False)
       customer_name = Column(String(200), nullable=False)
       tax_id = Column(String(13), nullable=True)
       is_active = Column(Boolean, default=True)
       # Unique constraint: (company_id, customer_code)
   ```

2. **Import API endpoints (same pattern as COA import in TASK-1203):**
   - `POST /api/v1/companies/{id}/vendors/import` — CSV upload: `vendor_code,vendor_name,tax_id`
   - `GET /api/v1/companies/{id}/vendors` — list vendors (paginated, searchable)
   - `POST /api/v1/companies/{id}/customers/import` — CSV upload: `customer_code,customer_name,tax_id`
   - `GET /api/v1/companies/{id}/customers` — list customers (paginated, searchable)
   - Upsert logic: update if code exists for company, create if new (same as COA)

3. **Admin UI (extend Company management tab from TASK-1203):**
   - Per-company: 3 sub-tabs → COA | Vendors | Customers
   - Vendor tab:
     - [Import Vendors] button (CSV upload)
     - Vendor table: vendor_code | vendor_name | tax_id
     - Search/filter by code or name
     - CSV template download
   - Customer tab: same layout as Vendor tab
   - Expected CSV format:

     ```csv
     vendor_code,vendor_name,tax_id
     5004,ธนาคารกสิกรไทย,0107536000226
     1238,บจก.ช่างซ่อมดี,0105564098765
     ```

4. **Template engine integration (link to TASK-1001):**
   - Field resolver for `vendor_code`/`vendor_name`: lookup from `vendors` table by matching `seller_name` (exact match first)
   - Field resolver for `customer_code`/`customer_name`: lookup from `customers` table
   - For MVP: exact match only. Fuzzy/AI match → backlog BL-001.

5. **Alembic migration:**
   - Create `vendors` and `customers` tables
   - Add unique constraints: `(company_id, vendor_code)`, `(company_id, customer_code)`

### Files changed (TASK-1207)

| Action | File | What |
| --- | --- | --- |
| Modify | `src/backend/db/models.py` | Add Vendor, Customer models |
| Create | `alembic/versions/004_add_vendor_customer_tables.py` | Migration for vendors + customers tables |
| Modify | `src/backend/api/companies.py` | Add vendor/customer import + list endpoints |
| Modify | `src/backend/api/schemas/company_schemas.py` | Add Pydantic models for vendor/customer |
| Modify | `src/frontend/ux-ui-prototype.html` | Add Vendors/Customers sub-tabs in Company management |
| Modify | `src/backend/services/template_engine.py` | Add vendor/customer field resolver using DB lookup |
| Create | `tests/api/test_vendor_customer.py` | Import + list + upsert + template lookup tests |

### Acceptance criteria (TASK-1207)

| ID | Condition | Test |
| --- | --- | --- |
| ac_1207_vendor_import | CSV upload creates vendor records per company | test_vendor_import_csv |
| ac_1207_customer_import | CSV upload creates customer records per company | test_customer_import_csv |
| ac_1207_upsert | Re-importing updates existing records (by code), creates new ones | test_vendor_customer_upsert |
| ac_1207_list | GET endpoints return paginated, searchable vendor/customer lists | test_vendor_customer_list |
| ac_1207_unique | Duplicate code within same company is rejected or upserted (not duplicated) | test_unique_constraint |
| ac_1207_lookup | Template engine resolves vendor_code/vendor_name from DB for export | test_template_vendor_lookup |
| ac_1207_ui | Vendor/Customer tabs render in Company management with import + table | test_vendor_customer_ui (Playwright) |

### Governance fields

```json
{
  "task_id": "TASK-1207",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/frontend/**", "src/backend/api/**", "src/backend/db/**", "src/backend/services/template_engine.py", "alembic/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1208: LoveBot data CSV export (6 book types)

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~1 day
**Week**: W4
**Closes pain points**: PP-2 (interface contract), PP-8 (integration with external tool)
**Added**: 2026-06-27 — client meeting, LoveAutoBot integration clarified

### Purpose

LedgerFlow export transaction data เป็น CSV format ที่ LoveAutoBot program อ่านได้โดยตรง
Format ตรงกับ 6 template files ใน `private_data/poc/Comp_1/template/`

> **Architecture insight**: iniComList files (101 cols, UTF-8 BOM) = robot script ที่ LoveBot อ่านแยก
> LF ต้องแค่ generate **data CSV** ตาม template 6 ไฟล์ — ไม่ต้อง generate iniComList

```
LF export API → TemplateEngine (TASK-1001) → data CSV (cp874/TIS-620)
                                                     ↓
                                             User downloads & hands to LoveBot
                                                     ↓
                                LoveBot reads data CSV + pre-built iniComList
                                                     ↓
                                Bot clicks Express Accounting → enters data
```

### Template column mapping (verified from client files)

| Book | Template name | Columns | Doc# pattern | Amount |
|------|--------------|---------|-------------|--------|
| 12 | ซื้อสด บรรทัดเดียว | ลำดับ, วันที่, เลขที่เอกสาร, เลขที่ใบกำกับ, จำนวนเงินก่อนภาษี, รหัสผู้จำหน่าย, ชื่อผู้จำหน่าย, รหัสลงบัญชี | YYMM/NNN from 001 | net_amount |
| 14 | ซื้อเชื่อ บรรทัดเดียว | same as 12 | YYMM/NNN from 100 | net_amount |
| 15 | ค่าใช้จ่ายอื่นๆ บรรทัดเดียว | เพิ่ม คำอธิบาย (col5) | YYMM/NNN from 100 | net_amount |
| 15+WHT | ค่าใช้จ่ายอื่นๆ(มีหัก) | เพิ่ม เลขที่เอกสาร(สูตร) (OE prefix) | YYMM/NNN + OEprefix | net_amount |
| 22 | ขายสด บรรทัดเดียว | ลำดับ, วันที่, เลขที่เอกสาร, จำนวนเงินรวมภาษี, รหัสลูกค้า, ชื่อลูกค้า, รหัสลงบัญชี | YYMM###### (6 digits) | total_amount |
| 24 | ขายเชื่อ บรรทัดเดียว | same as 22 | YYMM###### | total_amount |

All templates: **encoding=cp874 (TIS-620)**, date=`thai_date_short` (DD/MM/YY as text)

### What to build

1. **New export endpoint:**
   - `POST /api/v1/exports/lovebot` — body: `{company_id, book_type, period, transaction_ids[]}`
   - book_type enum: `"12"`, `"14"`, `"15"`, `"15wht"`, `"22"`, `"24"`
   - Returns: CSV file download (Content-Disposition: attachment)
   - Encoding: cp874, BOM-less, comma delimiter
2. **LoveBot master templates** (DB seed, `is_master=true`):
   - 6 templates seeded (extends TASK-1004 seed migration, or new migration 013)
   - Each template has pre-configured column definitions matching verified client files
3. **Date format**: `thai_date_short` — `DD/MM/YY` as plain text string (no Excel auto-convert)
4. **Doc# generation**:
   - Book 12/14/15: `YYMM/NNN` — sequence from 001 or 100 per book type, reset monthly
   - Book 22/24: `YYMM######` — 6-digit padded sequence

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/api/exports.py` | New router: POST /exports/lovebot |
| Create | `src/backend/api/schemas/export_schemas.py` | LoveBotExportRequest Pydantic model |
| Modify | `src/backend/services/template_engine.py` | Add LoveBot-specific column resolver if needed |
| Create | `alembic/versions/013_seed_lovebot_templates.py` | Seed 6 LoveBot master templates |
| Modify | `src/backend/app/endpoints.py` | Mount exports router |
| Create | `tests/api/test_lovebot_export.py` | Export tests per book type |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1208_csv12 | Export Book 12: 8 columns in correct order, encoding cp874, no BOM | test_export_book12 |
| ac_1208_csv14 | Export Book 14: doc_number starts from YYMM/100 | test_export_book14_docno |
| ac_1208_csv15 | Export Book 15: 9 columns (includes คำอธิบาย) | test_export_book15 |
| ac_1208_csv15wht | Export Book 15+WHT: 11 columns, formula_doc_number has OE prefix | test_export_book15wht |
| ac_1208_csv22 | Export Book 22: 7 columns, doc_number format YYMM###### (10 chars) | test_export_book22 |
| ac_1208_encoding | Downloaded CSV opens in Express (TIS-620) without mojibake | test_cp874_encoding |
| ac_1208_date | Date columns written as plain text DD/MM/YY (not date cell) | test_date_as_text |
| ac_1208_multi | Multiple transactions in one export appear as sequential rows | test_multi_transaction |

### Governance fields

```json
{
  "task_id": "TASK-1208",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": [
    "src/backend/api/exports.py",
    "src/backend/api/schemas/export_schemas.py",
    "src/backend/services/template_engine.py",
    "alembic/versions/013_*",
    "src/backend/app/endpoints.py",
    "tests/**"
  ],
  "forbidden_scope": [".env*", "src/backend/auth/**", "private_data/**"],
  "max_loops": 4,
  "escalation_policy": "human",
  "prerequisite": "TASK-1001 (template engine), TASK-1004 (master template seed pattern)"
}
```

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
