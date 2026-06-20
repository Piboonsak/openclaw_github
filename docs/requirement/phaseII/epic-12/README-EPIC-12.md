# Epic 12 — Admin UI + Login

**Goal**: หน้าจอ Login, Dashboard, Company/COA management, User management สำหรับ MVP (2 roles: Admin/Staff)

## Documentation

- **[EPIC-12-TASKS-DETAIL.md](EPIC-12-TASKS-DETAIL.md)** — full design for all tasks with ACs, schemas, governance fields

## At a glance

| Aspect | Details |
|--------|---------|
| Lead | Full-stack Dev |
| Duration | 1.5 weeks (W5-W6) |
| Status | Design |
| Critical path | **Yes** — Login blocks all authenticated features for production use |
| Week | W5-W6 |

## Task overview

| Task | Title | Complexity | Status | Pain points closed |
|------|-------|-----------|--------|-------------------|
| TASK-1201 | Login screen + JWT session management | M | New | PP-2, PP-3, PP-5, PP-8 |
| TASK-1202 | MVP Dashboard | M | New | PP-2, PP-3, PP-5, PP-11 |
| TASK-1203 | Company management + COA import | M | New | PP-2, PP-3, PP-5, PP-8 |
| TASK-1204 | User management + RBAC (2 roles MVP) | M | New | PP-2, PP-3, PP-5, PP-8 |
| TASK-1207 | Vendor & Customer master import | M | New | PP-2, PP-5 |

## Dependencies

- **Upstream**: Epic 8 TASK-803 (JWT auth backend -- login API, token verify, refresh), Epic 8 TASK-801 (DB integration for data queries)
- **Downstream**: All authenticated features in production (every page requires login)

## Execution order

```text
W5 Day 1-2:  TASK-1201 — Login screen + JWT session (must come first, all pages need auth)
W5 Day 3-5:  TASK-1203 — Company management + COA import (companies needed for dashboard + templates)
W6 Day 1-3:  TASK-1202 — MVP Dashboard (needs data from documents, companies, api_usage tables)
W6 Day 3-5:  TASK-1204 — User management + RBAC (last -- admin-only feature, 2 roles for MVP)
W6 Day 4-5:  TASK-1207 — Vendor & Customer master import (parallel with TASK-1204, extends TASK-1203 pattern)
```

## Definition of Done

1. Login form authenticates via POST /api/v1/auth/login and stores JWT in localStorage
2. Token refresh happens automatically before expiry
3. Protected pages redirect to login if no valid token
4. Logout clears token and redirects to login
5. Dashboard shows real document counts, processing status breakdown, recent activity, and cost meter
6. Company CRUD (add/edit) works with data persisted to DB
7. COA import accepts YAML and CSV files, creates chart_of_accounts records per company
8. COA list view shows account_code, account_name, account_type per company
9. Admin can add/edit users with role assignment (Admin/Staff)
10. Staff users see only companies assigned to them via user_company_assignments
11. Admin users see all companies within their tenant
12. Vendor import accepts CSV with vendor_code, vendor_name, tax_id — upserts per company
13. Customer import accepts CSV with customer_code, customer_name, tax_id — upserts per company
14. Template engine resolves vendor/customer codes from DB for Express CSV export
15. All ACs pass with pytest tests

## Discussion Prompts

1. **JWT storage**: localStorage vs httpOnly cookie? localStorage is simpler but vulnerable to XSS. For MVP with single-page HTML, localStorage is pragmatic -- upgrade to httpOnly cookie in hardening phase?
2. **Token expiry duration**: Recommend 1 hour access token + 7 day refresh token. สำนักงานบัญชีอาจเปิดหน้าจอทั้งวัน -- 1 hour สั้นไปไหม?
3. **COA format**: ลูกค้าใช้ YAML or CSV สำหรับ COA? ถ้าทั้งสองต้อง support ทั้งคู่ -- หรือ CSV พอสำหรับ MVP?
4. **Dashboard cost meter**: แสดง LLM usage vs budget -- ใช้ข้อมูลจาก `api_usage` table. Unit แสดงเป็น USD หรือ THB? ควรมี conversion rate ที่ configurable?
5. **RBAC expansion**: MVP มี 2 roles (Admin/Staff). Phase II/2 หรือ post-go-live จะขยายเป็น 4 roles (Admin/Manager/Staff/Reviewer) -- ออกแบบ DB schema รองรับ 4 roles ตั้งแต่ตอนนี้ แต่ enforce แค่ 2 roles ใน MVP?

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
