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
4. **Company management UI (new tab):**
   - Company list with [Add] button
   - Add/Edit form (name, tax_id, branch_code, address, business_type)
   - Per-company COA section:
     - [Import COA] button (file upload: .yaml, .yml, .csv)
     - COA table: account_code | account_name | account_type
     - Search/filter by account_code or name
5. **Validation:**
   - tax_id: 13 digits, unique per tenant
   - account_code: unique per company
   - Reject invalid YAML/CSV format with clear error message

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/api/companies.py` | FastAPI router for company CRUD + COA import |
| Create | `src/backend/api/schemas/company_schemas.py` | Pydantic models for company + COA |
| Modify | `src/backend/app/endpoints.py` | Mount company router |
| Modify | `src/frontend/ux-ui-prototype.html` | Add Companies tab with CRUD UI + COA import |
| Create | `tests/api/test_companies.py` | Company CRUD + COA import tests |

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

## TASK-1204: User management + RBAC (2 roles MVP)

**Owner**: Full-stack Dev
**Risk**: HIGH
**Duration**: ~3 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-8

### Purpose

หน้าจอจัดการ users (Admin only) และ role-based access control สำหรับ MVP -- 2 roles: Admin (เห็นทุกบริษัท, จัดการ users/templates) และ Staff (เห็นเฉพาะบริษัทที่ assign). DB schema รองรับ 4 roles ตั้งแต่ตอนนี้ (Admin/Manager/Staff/Reviewer) แต่ MVP enforce แค่ 2.

### What exists today

- DB models: `users` table (email, username, password_hash, display_name, role, is_active, last_login) and `user_company_assignments` table (user_id, company_id, role_override, assigned_at)
- JWT auth from TASK-803 provides current user identity
- No user management UI or RBAC enforcement on endpoints

### What to build

1. **User management API (Admin only):**
   - `GET /api/v1/users` -- list users (tenant-scoped, Admin only)
   - `POST /api/v1/users` -- create user (Admin only)
   - `GET /api/v1/users/{id}` -- get user detail
   - `PUT /api/v1/users/{id}` -- update user (email, display_name, role, is_active)
   - `POST /api/v1/users/{id}/assign-companies` -- assign user to companies
   - `DELETE /api/v1/users/{id}/assign-companies/{company_id}` -- remove assignment
2. **RBAC middleware / dependency:**
   - `require_role("admin")` -- FastAPI dependency that checks current user role
   - Company scoping: Staff queries auto-filter by `user_company_assignments`
   - Admin bypasses company filter (sees all within tenant)
3. **User management UI (Admin only tab):**
   - User list table: username, display_name, email, role, status, last_login
   - [Add User] button -> form (username, email, display_name, password, role: Admin/Staff)
   - [Edit] button -> update form (no password change in v1 -- separate endpoint later)
   - Company assignments: checklist of available companies per user
4. **Company scoping enforcement:**
   - All data endpoints (documents, templates, exports, dashboard) must respect company scoping
   - Staff: `WHERE company_id IN (SELECT company_id FROM user_company_assignments WHERE user_id = ?)`
   - Admin: `WHERE tenant_id = ?` (no company restriction)
5. **Role validation on endpoints:**
   - User management endpoints: Admin only (403 for Staff)
   - Template master management: Admin only
   - Template clone/edit (company templates): Admin + Staff (own companies)
   - Document operations: Admin + Staff (own companies)

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
| ac_1204_list | GET /api/v1/users returns user list (Admin only, 403 for Staff) | test_list_users_admin_only |
| ac_1204_create | POST /api/v1/users creates user with hashed password and role | test_create_user |
| ac_1204_assign | POST /api/v1/users/{id}/assign-companies creates assignment records | test_assign_companies |
| ac_1204_staff_scope | Staff user queries return only data from assigned companies | test_staff_company_scope |
| ac_1204_admin_scope | Admin user queries return all companies within tenant | test_admin_tenant_scope |
| ac_1204_role_403 | Staff accessing admin-only endpoints receives 403 Forbidden | test_role_enforcement |
| ac_1204_ui | Users tab visible only to Admin role, hidden for Staff | test_admin_tab_visibility (Playwright) |
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

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
