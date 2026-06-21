# Phase II Epic Roadmap & Critical Path

**Timeline: 8 สัปดาห์ (Phase II/1 Go-Live) + CR-based (Phase II/2)**
**Baseline Date: 2026-06-15**
**Payment: 50% Kickoff → 10% UAT → 20% Prod → 20% Phase II/2**

---

## Epic Overview Table

### Phase II/1 — Go-Live MVP (8 สัปดาห์)

| Epic | Title | Focus | Key Tasks | Req# | Status | Est. |
|------|-------|-------|-----------|------|--------|------|
| **0** | UX Contract & Workflow Freeze | Lock workflow, state machine, API/DB impact before DB work | TASK-001~006 | ux,infra | Done | 2-4d |
| **8** | Platform Foundation | DB activation, JWT Auth, MinIO S3, Celery workers | TASK-801A~808 | infra,10 | Partial | 2w |
| **9** | Extraction Accuracy + Line Item PoC | VAT fix, WHT, OCR gridline, Line item feasibility | TASK-901~906 | 1,2,4 | Partial | 1.5w |
| **10** | Template Engine + Configurator UI | Dynamic export, drag-drop UI, Master/Clone | TASK-1001~1006 | 5,6,7,8,9 | Design | 2.5w |
| **11** | Purchase Tax Report Integration | ภาษีซื้อ integrate กับ template engine | TASK-1101,1104 | 3 | Partial | 0.5w |
| **12** | Admin UI + Login | Login, MVP Dashboard, Company/COA, User mgmt | TASK-1201~1204 | 7 | Design | 1.5w |
| **13** | Infrastructure + Deployment | Hostinger VPS (UAT/Prod), DNS bwcacc.com, CI/CD, Firewall, Backup, Offsite R2 | TASK-1301~1312 | 10 | Design | ~2w (parallel) |

### Phase II/2 — Post-Go-Live Enhancement (CR-based)

| Epic | Title | Focus | Key Tasks | Req# | Est. |
|------|-------|-------|-----------|------|------|
| **14** | Line Item + Inventory (Full) | Full line item extraction + inventory data prep | TASK-1401~1404 | 2,4 | 2-3w |
| **15** | Sales Tax Report | รายงานภาษีขาย | TASK-1501~1502 | 3 | 1w |
| **16** | Full Dashboard + Monitoring | Full KPI dashboard, Sentry, Audit log UI | TASK-1601~1604 | infra | 1.5w |

---

## Requirement Traceability Matrix

| Req# | Requirement | Phase | Epic | Tasks | หมายเหตุ |
|------|------------|-------|------|-------|----------|
| 0 | UX workflow + state/API contract | II/1 pre-work | 0 | 001~006 | Gate ก่อน DB integration |
| 1 | อ่านเอกสารบัญชี (OCR) | II/1 | 9 | 903 | PoC working + gridline fix |
| 2 | ดึงข้อมูลสำคัญ (header) | II/1 | 9 | 901,902,905 | VAT/WHT/branch fix |
| 2b | ดึง line item (SKU, Qty, Price) | II/1 PoC → II/2 Full | 9→14 | 906→1401~1404 | PoC W1, Full = CR |
| 3 | รายงานภาษีซื้อ | II/1 | 11 | 1101,1104 | Integrate template engine |
| 3b | รายงานภาษีขาย | II/2 | 15 | 1501,1502 | CR หลัง go-live |
| 4 | เตรียมข้อมูลสต็อก | II/2 | 14 | 1403,1404 | ไปกับ line item full |
| 5 | Export flexible (CSV/Excel) | II/1 | 10 | 1001,1006 | Template engine |
| 6 | เลือก field, ลำดับ column, ตั้งชื่อ | II/1 | 10 | 1003 | Configurator UI |
| 7 | กำหนดผังบัญชี/account code | II/1 | 10+12 | 1003,1203 | Field picker + COA import |
| 8 | Template กลาง + clone | II/1 | 10 | 1004,1005 | Master/Clone workflow |
| 9 | Template เฉพาะบริษัท | II/1 | 10 | 1005,1006 | Clone → customize |
| 10 | Cloud hosting (UAT/Prod) | II/1 | 13 | 1301~1312 | VPS + DNS + CI/CD |

---

## Task Breakdown Per Epic

### Epic 0: UX Contract & Workflow Freeze (W0 / before W1)

ล็อก UX workflow, state machine, API contract, และ DB impact ก่อนเริ่มแก้ schema / pipeline integration เพื่อป้องกัน rework ระหว่าง Epic 8, 10, 12

| Task | งาน | Complexity | สถานะ | สัปดาห์ |
|------|------|-----------|--------|---------|
| TASK-001 | PoC UX click audit + interaction inventory | S | Done | W0 |
| TASK-002 | MVP workflow state machine freeze | M | Done | W0 |
| TASK-003 | DB impact contract for workflow entities | M | Done | W0 |
| TASK-004 | Prototype interaction patch scope | M | Done | W0 |
| TASK-005 | API / route contract for Phase II screens | M | Done | W0 |
| TASK-006 | Epic 8 handoff checklist + sign-off | S | Done | W0 |

**สิ่งที่ต้องล็อกก่อน Epic 8:**
- Batch lifecycle และ document lifecycle
- Review Scan / Review Mapping state + role guards
- Export job/history + selected document behavior
- Template configurator scope: MVP vs Phase II/2
- Mobile navigation decision: usable now vs desktop-first
- DB impact list: table vs JSONB vs deferred

**Dependency:** Blocks Epic 8 DB integration decisions, informs Epic 10/12 UI/API scope

---

### Epic 8: Platform Foundation (W1-2)

เปิดใช้ infrastructure ที่ติดตั้งไว้แล้วใน requirements.txt / docker-compose แต่ยังไม่ได้ใช้จริง

| Task | งาน | Complexity | สถานะ | สัปดาห์ |
|------|------|-----------|--------|---------|
| TASK-801A | SQLAlchemy models + Alembic schema slice (workflow/export/page credits) | L | New | W1 |
| TASK-801B | Pipeline → DB dual-write integration (extraction/journal write ลง DB แทน file cache) | L | New | W1 |
| TASK-802 | Data migration script (companies.json → DB, seed master templates, seed admin user) | M | New | W1 |
| TASK-804 | MinIO S3 storage integration (upload/download/presigned URL) | M | New | W1 |
| TASK-805 | Celery + Redis workers (wrap pipeline เป็น background task, export job runtime, status tracking) | M | New | W2 |
| TASK-803 | JWT Authentication + Login API endpoint + FastAPI middleware | M | New | W2 |
| TASK-806 | Health check endpoint + DB connection pool + startup validation | S | New | W2 |
| TASK-807 | PDPA auto-cleanup (Celery Beat cron ลบไฟล์ + DB records เกิน retention period, configurable days) | S | New | W2 |
| TASK-808 | Edge case handling — file size limit (20MB), unreadable image → `ocr_failed` status, encrypted PDF → reject with message | S | New | W2 |

**สิ่งที่ทำเสร็จแล้ว:**
- ORM models 15 tables (`src/backend/db/models.py`)
- Alembic migration infrastructure + `001_initial_schema.py`
- DB session factory (`src/backend/db/session.py`)
- `config/settings.py` มี DATABASE_URL แล้ว
- Docker Compose มี PostgreSQL + Redis + MinIO containers

**Dependency:** `TASK-801A` blocks DB contract rollout, `TASK-801B` blocks live data flow; together they unblock Epic 10, 11, 12

---

### Epic 9: Extraction Accuracy + Line Item PoC (W1-2)

ยกระดับ accuracy จาก PoC feedback + พิสูจน์ feasibility ของ line item extraction

| Task | งาน | Complexity | สถานะ | สัปดาห์ |
|------|------|-----------|--------|---------|
| **TASK-906** | **Line Item Extraction PoC — Black Box Clear** | **M** | **New** | **W1** |
| TASK-901 | VAT disambiguation — arithmetic-first, ทดสอบ 4 combinations (2 slots x 2 modes) | L | New | W1-2 |
| TASK-902 | WHT detection + backfill solver + has_wht flag + PND3/PND53 form detection | M | New | W2 |
| TASK-903 | OCR gridline removal (OpenCV morphological preprocessing) | M | New | W2 |
| TASK-905 | Vendor branch extraction (สำนักงานใหญ่/สาขา) | S | **Done** | — |

**TASK-906 Detail: Line Item Extraction PoC**

> **เป้าหมาย:** ตอบ 3 คำถามให้ชัดก่อนเริ่มงานจริง — ทำได้ไหม? Cost เท่าไร? แพงไหม?

| ขั้นตอน | รายละเอียด |
|---------|-----------|
| 1. เตรียมตัวอย่าง | **20-30 documents** หลาย format (ดู diversity checklist ด้านล่าง) |
| 2. ทดสอบ 3 models | Gemini Flash (free) vs Gemini Pro vs Claude Sonnet |
| 3. วัด cost | tokens per document → คูณ 10K-20K docs/month → monthly cost projection |
| 4. วัด accuracy | **6 metrics** (ดูด้านล่าง) |
| 5. Feasibility report | go/no-go + recommended model + cost estimate + accuracy range |

**Document Diversity Checklist (20-30 docs ต้องครอบคลุม):**

| Category | ตัวอย่าง | ขั้นต่ำ |
|----------|---------|--------|
| สแกนชัด (300 DPI+) | สแกนเนอร์สำนักงาน | 5 docs |
| สแกนเบลอ / ถ่ายมือถือ | กล้องมือถือ, เอียง, แสงไม่ดี | 3 docs |
| PDF ดิจิทัล (มี text layer) | ออกจากระบบ e-Tax / ERP | 3 docs |
| ตาราง gridline ชัด | invoice มีเส้นตาราง | 5 docs |
| ไม่มี gridline (text-only layout) | ใบเสร็จทั่วไป | 3 docs |
| หลายหน้า (multi-page) | invoice > 1 หน้า | 2 docs |
| มี discount / WHT | หัก ณ ที่จ่าย, ส่วนลด | 3 docs |
| VAT included vs excluded | ทั้ง 2 แบบ | 2 docs |

**Metrics (6 ตัวชี้วัด):**

| # | Metric | วิธีวัด | Go Threshold |
|---|--------|--------|-------------|
| 1 | Per-field accuracy | % ถูกต้องต่อ field (product_name, qty, unit_price, line_amount, unit) | ≥ 80% ทุก field |
| 2 | **Document-level success rate** | % ของ docs ที่ **ทุก field ถูกครบ** | ≥ 60% |
| 3 | **Line total reconciliation** | sum(line_amounts) = invoice total? pass/fail per doc | ≥ 70% pass |
| 4 | Cost per document | tokens × price per model | ≤ ฿1.50/doc |
| 5 | Processing time per document | seconds (LLM call only) | ≤ 15 sec |
| 6 | **Manual correction time** | เวลาเฉลี่ยที่คนต้องแก้ไข per doc (ประเมินจาก error count) | ≤ 3 นาที/doc |

**Go/No-Go Criteria:**

| Result | Decision | Impact on Phase II/2 |
|--------|---------|---------------------|
| ≥ 4/6 metrics pass | **Go** — Full implementation | Epic 14 scope + pricing confirmed |
| 3/6 metrics pass | **Conditional** — Limited doc types only | Epic 14 scope reduced, specific formats only |
| ≤ 2/6 metrics pass | **No-Go** — Defer | Epic 14 deferred to Phase III, งวด 4 ลดราคาตาม scope |

**Output:** Feasibility report (3-5 pages) ที่ตอบ:

- Model ไหนเหมาะที่สุด (cost vs accuracy tradeoff)
- ต้นทุน/เดือนที่ 10K docs ≈ $XX → ฿XX
- 6 metrics per model (comparison table)
- Go/No-Go recommendation + เหตุผล
- ข้อจำกัดที่พบ (format ไหนอ่านไม่ได้, field ไหนมีปัญหา)
- ถ้า Conditional: แนะนำ format ที่ support ได้ vs ไม่ได้

**ผลนี้เป็น input กำหนด scope + ราคางวดที่ 4 (Phase II/2)**

**สิ่งที่ทำเสร็จแล้ว:**
- TASK-905 vendor branch extraction (regex patterns + zero-padded 5-digit codes)
- OCR pipeline (PaddleOCR + Tesseract) working
- Field extraction regex v29 working
- LLM repair (Stage C) with model router working

**Files to modify:**
- `src/backend/ml/amount_reconciler.py` — TASK-901
- `src/backend/ml/field_extractor.py` — TASK-902
- `src/backend/ml/ocr.py` — TASK-903

---

### Epic 10: Template Engine + Configurator UI (W3-5)

**Core ของ Phase II** — Req 5-9 ทั้งหมดอยู่ใน Epic นี้

| Task | งาน | Complexity | สถานะ | สัปดาห์ |
|------|------|-----------|--------|---------|
| TASK-1001 | Template engine backend (column mapping logic, field→column rendering, transforms) | L | New | W3 |
| TASK-1002 | Template CRUD + Clone API endpoints (REST) | M | New | W3 |
| TASK-1003 | Template Configurator UI (drag-drop reorder, field picker, inline rename) | L | Demo done | W4 |
| TASK-1004 | Master templates (Express GL 8-col, Purchase Tax 12-col) + seed migration | M | New | W4 |
| TASK-1005 | Clone workflow (Master → Company, deep-copy columns JSONB, open editor) | M | New | W5 |
| TASK-1006 | Export screen integration (template selector → preview → download CSV/Excel) | M | New | W5 |

**UI Interactions (Req #5-9 coverage):**

| Requirement | UI Feature | Implementation |
|---|---|---|
| #5 เลือก fields | Checkbox field picker (Available → Selected) | Click = add to Selected Columns |
| #6 ลำดับ + rename | Drag-drop (☰ handle) + inline rename | SortableJS + contenteditable |
| #7 Account code | account_code in field picker + COA lookup | Journal fields available |
| #8 Clone master | [Clone to Company] button on master | POST clone API + open editor |
| #9 Company template | Save customized template per company | company_id FK in DB |

**API Endpoints:**
- `GET /api/v1/templates` — list by company
- `POST /api/v1/templates` — create new
- `GET /api/v1/templates/{id}` — get with columns
- `PUT /api/v1/templates/{id}` — update columns/order/names
- `DELETE /api/v1/templates/{id}` — soft delete
- `POST /api/v1/templates/{id}/clone` — clone master → company
- `POST /api/v1/templates/{id}/preview` — preview with sample data

**Files to create/modify:**
- สร้าง `src/backend/services/template_engine.py` — mapping engine
- แก้ไข `src/backend/services/export_service.py` — template_id แทน hardcode
- สร้าง `src/backend/api/templates.py` — CRUD + clone endpoints
- แก้ไข `src/frontend/ux-ui-prototype.html` — Template Manager + Configurator

**สิ่งที่ทำเสร็จแล้ว:**
- Template Configurator demo HTML (`template-configurator-demo.html`)
- Export service (GL Ledger + Purchase Tax Report — hardcoded format)
- DB model `ExportTemplate` with JSONB columns

---

### Epic 11: Purchase Tax Report Integration (W3)

| Task | งาน | Complexity | สถานะ | สัปดาห์ |
|------|------|-----------|--------|---------|
| TASK-1101 | Purchase Tax Report → ย้ายจาก hardcode เป็น template-based | M | Partial | W3 |
| TASK-1104 | Preview + balance validation (Sum Dr = Sum Cr per voucher) before export | S | New | W3 |

**สิ่งที่ทำเสร็จแล้ว:**
- `create_purchase_tax_report()` function (240 lines)
- `POST /api/export-purchase-tax-report` endpoint
- Thai formatting, VAT bucket splitting, xlsxwriter

---

### Epic 12: Admin UI + Login (W5-6)

| Task | งาน | Complexity | สถานะ | สัปดาห์ |
|------|------|-----------|--------|---------|
| TASK-1201 | Login screen + JWT session management (token refresh, logout) | M | New | W5 |
| TASK-1202 | MVP Dashboard (document count, processing status, recent activity) | M | New | W6 |
| TASK-1203 | Company management + COA import (YAML/CSV upload) | M | New | W5-6 |
| TASK-1204 | User management + RBAC (Admin/Staff, 2 roles สำหรับ MVP) | M | New | W6 |

**Files to create:**
- `src/backend/auth/auth.py` — JWT token logic (issue, verify, refresh)
- `src/backend/auth/dependencies.py` — FastAPI `Depends()` for auth
- `src/backend/auth/router.py` — `/api/v1/auth/login`, `/api/v1/auth/me`, `/api/v1/auth/refresh`
- แก้ไข `src/frontend/ux-ui-prototype.html` — Login page, Dashboard tab, Company tab

---

### Epic 13: Infrastructure + Deployment (parallel W1-8)

> **Infrastructure Decision:** Hostinger VPS all-in (compute + DB + storage ทุกอย่างบน VPS)
> PoC ทำงานบน Hostinger อยู่แล้ว — ไม่ย้าย platform ระหว่าง sprint, ลด risk
> Gemini/LLM API เรียกจาก Hostinger ได้เลย ไม่ต้องอยู่ GCP
> Post-go-live: ประเมินย้าย GCP ถ้า Hostinger มีปัญหาจริง (ดู Appendix A)

**งานนี้ทำ parallel กับ development ตลอด — ไม่ใช่ทำท้ายสุด**

| Task | งาน | Complexity | สถานะ | สัปดาห์ |
|------|------|-----------|--------|---------|
| TASK-1301 | VPS Architecture Design (services, networking, resource sizing) | M | New | W1 |
| TASK-1302 | Hostinger VPS Procurement — UAT + PROD instances (Singapore DC) | S | New | W1 |
| TASK-1303 | Base OS setup + Docker Engine + security hardening | M | New | W1-2 |
| TASK-1304 | DNS delegation (bwcacc.com → subdomains) + Certbot SSL | M | New | W2 |
| TASK-1305 | CI/CD Pipeline Design (GitHub Actions → VPS deploy flow) | M | New | W2-3 |
| TASK-1306 | CI/CD Pipeline Implementation (deploy-uat.yml, deploy-prod.yml) | L | New | W3-4 |
| TASK-1307 | Docker Compose — UAT (docker-compose.uat.yml) | M | New | W4 |
| TASK-1308 | Docker Compose — PROD (docker-compose.prod.yml) | M | New | W5 |
| TASK-1309 | Network + Firewall Setup — UFW + PROD lockdown | M | New | W5-6 |
| TASK-1310 | DB Backup Automation — pg_dump daily + Cloudflare R2 offsite + LINE alert | M | New | W6 |
| TASK-1311 | Housekeeping (log rotation, temp cleanup, disk monitoring) | S | New | W6 |
| TASK-1312 | Go-Live Checklist + Smoke Tests (Playwright E2E) + Restore Drill | M | Partial | W7-8 |

#### TASK-1301: VPS Architecture Design

```
┌─────────────────────────────────────────────────────┐
│                    bwcacc.com DNS                       │
│  app.bwcacc.com (PROD)  │  uat.bwcacc.com  │  demo.bwcacc.com│
└───────┬───────────────┴───────┬───────┴──────┬───────┘
        │                       │              │
   ┌────▼────────────┐    ┌────▼────────┐  (existing PoC)
   │ Hostinger PROD  │    │ Hostinger   │
   │ KVM 4-8         │    │ UAT KVM 2   │
   │ (locked down)   │    │             │
   └────┬────────────┘    └────┬────────┘
        │                       │
   ┌────▼──────────────────┐ ┌──▼──────────────────────┐
   │  Docker Compose PROD  │ │  Docker Compose UAT     │
   │  ├ nginx (SSL term)   │ │  ├ nginx (SSL term)     │
   │  ├ backend (FastAPI)  │ │  ├ backend (FastAPI)     │
   │  ├ celery-worker      │ │  ├ celery-worker         │
   │  ├ celery-beat        │ │  ├ postgres              │
   │  ├ postgres           │ │  ├ redis                  │
   │  ├ redis              │ │  └ minio                  │
   │  └ minio              │ └────────────────────────────┘
   └───────┬───────────────┘
           │ pg_dump daily (cron)
   ┌───────▼───────────────┐
   │  Cloudflare R2        │
   │  Offsite backup       │
   │  (S3-compatible)      │
   │  ≈ ฿3-8/mo            │
   └───────────────────────┘
```

#### TASK-1304: DNS Structure (bwcacc.com)

| Subdomain | Environment | VPS | หมายเหตุ |
|-----------|------------|-----|----------|
| `app.bwcacc.com` | **PROD** | Hostinger PROD | Production — locked down |
| `uat.bwcacc.com` | UAT | Hostinger UAT | Testing + client review |
| `demo.bwcacc.com` | Demo | Existing PoC VPS | Demo/showcase |

**DNS Setup Steps:**

1. เปิด Squarespace Domains panel → ตั้ง custom nameservers → `pixel.dns-parking.com`, `byte.dns-parking.com`
2. เปิด Hostinger hPanel DNS Zone → สร้าง A records → VPS IP addresses (TTL=300)
3. Certbot auto-SSL (Let's Encrypt) สำหรับทุก subdomain
4. Auto-renew cron job

> bwcacc.com เป็นโดเมนของทีม (Squarespace Domains, team-managed) — ไม่ต้องรอ client

#### TASK-1309: PROD Security — Lockdown Policy

| Rule | รายละเอียด | เหตุผล |
|------|-----------|--------|
| **No direct SSH from local** | SSH key-based only, จาก IP whitelist เท่านั้น | กัน AI/human พลาดไปแก้อะไรตรง ๆ |
| **No manual file edits** | ทุก change ผ่าน Git → GitHub Actions → Deploy | Audit trail + rollback safety |
| **Firewall rules (UFW)** | Allow: 80/443 (web), 22 (SSH from whitelist) only | Minimize attack surface |
| **BAU Support access** | SSH key สำหรับ support team, session logging | ให้เข้าได้แต่ track ทุกอย่าง |
| **DB access** | ไม่เปิด port 5432 ออก public, access ผ่าน SSH tunnel only | Data protection |
| **MinIO access** | Internal Docker network only, ไม่เปิด public | Storage isolation |
| **Environment vars** | Secrets ผ่าน GitHub Actions, ไม่เก็บใน repo | Credential security |

**BAU Support Flow:**
```
Support Engineer
    ↓ SSH (key-based, IP whitelisted)
    ↓ Session logged (auditd)
VPS PROD
    ↓ docker exec (read-only by default)
    ↓ docker logs (read-only)
    ↓ psql (read-only user for investigation)
    ↓ Need write? → Git PR → Deploy pipeline
```

#### TASK-1310: Backup Strategy — pg_dump + Cloudflare R2 Offsite

| Component | Method | Frequency | Retention | Location |
|-----------|--------|-----------|-----------|----------|
| PostgreSQL | pg_dump + gzip | **Every 6 hours** (00:00, 06:00, 12:00, 18:00) | 7 days local, 30 days R2 | VPS /backup/ + **Cloudflare R2** |
| MinIO documents | rclone sync | Daily 03:00 | 90 days | **Cloudflare R2** |
| Docker volumes | volume backup script | Weekly | 4 weeks | VPS /backup/ |
| Git repo | Already on GitHub | Every push | Permanent | GitHub |
| DB migration state | Alembic version tracked | Every deploy | Permanent | Git + DB |
| **Pre-deploy snapshot** | Hostinger snapshot API | **Before every PROD deploy** | 3 snapshots | Hostinger |

**Backup Script (cron every 6 hours: 00:00, 06:00, 12:00, 18:00):**
```bash
#!/bin/bash
set -euo pipefail
TIMESTAMP=$(date +%Y%m%d_%H%M)
BACKUP_DIR=/backup
ALERT_ON_FAIL=true

# 1. pg_dump
docker exec postgres pg_dump -U copilot ai_accounting \
  | gzip > ${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz

# 2. Sync to Cloudflare R2 (offsite)
rclone sync ${BACKUP_DIR}/ r2:ledgerflow-backup/db/ --max-age 30d

# 3. Cleanup local (keep 7 days)
find ${BACKUP_DIR}/ -name "*.sql.gz" -mtime +7 -delete

# 4. Alert if backup fails
if [ $? -ne 0 ] && [ "$ALERT_ON_FAIL" = true ]; then
  curl -s "https://notify-api.line.me/api/notify" \
    -H "Authorization: Bearer ${LINE_TOKEN}" \
    -d "message=⚠️ PROD DB backup FAILED at ${TIMESTAMP}"
fi
```

**RPO / RTO (Contract SLA):**
- **RPO (max data loss): 6 ชม.** — pg_dump ทุก 6 ชม., offsite sync ไป R2
- **RTO (recovery time): 6 ชม.** — รวมเวลา detect + restore + verify + Hostinger ticket ถ้า VPS ล่ม
  - Best case (VPS OK, DB corrupt only): 15-30 นาที (pg_restore + docker compose up)
  - Worst case (VPS ล่ม, ต้องเปิด Hostinger ticket): ≤ 6 ชม.
- Setup effort: 3 ชม. one-time
- Ongoing effort: ~15 นาที/เดือน (verify backup logs)
- **WAL archiving:** post-go-live hardening (ลด RPO เป็น ~5 นาที ถ้าจำเป็น)

**Restore procedure:**
1. Stop services: `docker compose stop backend celery-worker`
2. Download from R2 (if VPS lost): `rclone copy r2:ledgerflow-backup/db/latest.sql.gz /backup/`
3. Restore DB: `gunzip -c /backup/latest.sql.gz | docker exec -i postgres psql -U copilot ai_accounting`
4. Verify: `alembic current` matches expected version
5. Start services: `docker compose up -d`
6. Health check: `curl https://app.bwcacc.com/api/health`

**TASK-1312 includes Restore Drill:** ทดสอบ restore จริง 1 ครั้งก่อน go-live

#### TASK-1305: CI/CD Pipeline Design

```
Developer
    ↓ git push (dev branch)
    ↓
GitHub Actions CI
    ├ ruff check + format
    ├ mypy type check
    ├ pytest + coverage
    ├ alembic check (no pending migrations)
    └ build Docker image
        ↓ PR merge
        ↓
┌────────────────────────────────────────────────┐
│ Branch Strategy                                 │
│                                                 │
│  dev ──PR──▶ uat ──PR──▶ main                  │
│               │            │                    │
│         deploy-uat    deploy-prod               │
│               │            │                    │
│     Hostinger UAT    Hostinger PROD             │
│      uat.bwcacc.com      app.bwcacc.com              │
└────────────────────────────────────────────────┘

Deploy Pipeline (per environment):
    1. SSH to Hostinger VPS (key-based)
    2. git pull target branch
    3. docker compose build --no-cache
    4. [PROD only] Hostinger snapshot before migration
    5. alembic upgrade head (DB migration)
    6. docker compose up -d
    7. Health check (GET /api/health)
    8. Celery worker health check
    9. Playwright smoke test (critical path)
   10. LINE notification (success/fail)
```

**PROD-specific rules:**
- Deploy ต้อง pass UAT smoke test ก่อน
- Hostinger snapshot + pg_dump ก่อนทุก migration
- Rollback plan: `alembic downgrade -1` + redeploy previous commit
- No force push to main — ever

#### Hostinger VPS Sizing & Cost

| Resource | UAT (KVM 2) | PROD (KVM 4) | หมายเหตุ |
|----------|-------------|-------------|----------|
| vCPU | 2 | **4** | PaddleOCR + Celery workers |
| RAM | 8 GB | **16 GB** | OCR ~2GB + PostgreSQL ~1GB + Celery + buffer |
| NVMe SSD | 100 GB | **200 GB** | DB + MinIO + logs + backups |
| Bandwidth | 8 TB | 8 TB | เกินพอ |
| DC | Singapore | Singapore | Low latency สำหรับ Thailand |
| Price/month | **≈ $10-15 (฿350-520)** | **≈ $16-25 (฿550-860)** | |
| **Total VPS** | | | **≈ ฿900-1,380/เดือน** |
| Cloudflare R2 | | | ≈ ฿3-8/เดือน (offsite backup) |
| **Grand Total** | | | **≈ ฿900-1,400/เดือน** |

#### LLM API — เรียกจาก Hostinger ได้เลย

ไม่ต้องอยู่ GCP เพื่อใช้ Gemini — เรียก API ผ่าน internet ตามปกติ:

| Provider | API | เรียกจาก Hostinger | หมายเหตุ |
|----------|-----|-------------------|----------|
| Google AI Studio | Gemini 2.5 Flash (free tier) | ✓ | ใช้อยู่แล้วผ่าน OpenRouter |
| Vertex AI | Gemini 2.5 Flash (paid) | ✓ | Direct API, ไม่ต้อง OpenRouter |
| Anthropic | Claude Sonnet (fallback) | ✓ | ใช้อยู่แล้ว |

Latency เพิ่ม ~20-50ms เทียบกับ internal GCP → ไม่สำคัญสำหรับ Celery background task (5-30 วินาที/doc)

---

## 8-Week Execution Timeline

```
        ┃ Development Stream                ┃ Infrastructure Stream (parallel)    ┃
━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋
 W0     ┃ Epic 0: UX Contract gate          ┃                                    ┃
        ┃   (001, 002, 003, 004, 005, 006)  ┃                                    ┃
        ┃ ── Gate: DB-ready workflow ────── ┃                                    ┃
━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋
 W1     ┃ Epic 8: DB activation (801,802)   ┃ Epic 13: VPS Architecture (1301)   ┃
        ┃ Epic 9: Line Item PoC ★ (906)     ┃ Epic 13: VPS Procurement (1302)    ┃
        ┃ Epic 9: VAT disambig start (901)  ┃ Epic 13: Base OS setup (1303)      ┃
        ┃                                   ┃                                    ┃
 W2     ┃ Epic 8: Auth + MinIO + Celery     ┃ Epic 13: DNS + Certbot (1304)      ┃
        ┃   (803, 804, 805, 806)            ┃ Epic 13: CI/CD Design (1305)       ┃
        ┃ Epic 9: WHT + OCR (902, 903)      ┃                                    ┃
        ┃                                   ┃                                    ┃
        ┃ ── Milestone: Foundation Ready ── ┃ ── Milestone: VPS + DNS Ready ──  ┃
━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋
 W3     ┃ Epic 10: Template backend (1001)  ┃ Epic 13: CI/CD Implement (1306)    ┃
        ┃ Epic 10: CRUD + Clone API (1002)  ┃                                    ┃
        ┃ Epic 11: Purchase Tax (1101,1104) ┃                                    ┃
        ┃                                   ┃                                    ┃
 W4     ┃ Epic 10: Configurator UI (1003)   ┃ Epic 13: Docker UAT (1307)         ┃
        ┃ Epic 10: Master templates (1004)  ┃                                    ┃
        ┃                                   ┃                                    ┃
        ┃ ── Milestone: Template MVP ────── ┃ ── Milestone: CI/CD Ready ──────  ┃
━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋
 W5     ┃ Epic 10: Clone + Export (1005,6)  ┃ Epic 13: Docker PROD (1308)        ┃
        ┃ Epic 12: Login screen (1201)      ┃ Epic 13: Firewall (1309)           ┃
        ┃ Epic 12: Company/COA (1203)       ┃                                    ┃
        ┃                                   ┃                                    ┃
 W6     ┃ Epic 12: Dashboard (1202)         ┃ Epic 13: Backup (1310)             ┃
        ┃ Epic 12: User mgmt (1204)         ┃ Epic 13: Housekeeping (1311)       ┃
        ┃                                   ┃                                    ┃
        ┃ ── Milestone: All Features ────── ┃ ── Milestone: Infra Complete ──── ┃
━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋
 W7     ┃ Integration testing               ┃ Deploy to UAT (uat.bwcacc.com)        ┃
        ┃ E2E Playwright tests              ┃ Client UAT testing                 ┃
        ┃ Bug fixes                         ┃ Epic 13: Smoke tests (1312)        ┃
        ┃                                   ┃                                    ┃
        ┃ ── Milestone: UAT Sign-off ────── ┃ ── Payment: 10% UAT ────────────  ┃
━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋
 W8     ┃ UAT bug fixes                     ┃ Deploy to PROD (app.bwcacc.com)       ┃
        ┃ Final QA                          ┃ PROD smoke test                    ┃
        ┃ User manual update                ┃ Monitoring verification            ┃
        ┃                                   ┃                                    ┃
        ┃ ────── ★ PRODUCTION GO-LIVE ★ ── ┃ ── Payment: 20% Prod ───────────  ┃
━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╋

─── Post Go-Live (Phase II/2, CR-based) ─── Payment: 20% Phase II/2 ───────────
 W9+    ┃ Epic 14: Line Item Full (1401~4)  ┃ Ongoing: monitoring + BAU support  ┃
        ┃ Epic 15: Sales Tax Report (1501~2)┃                                    ┃
        ┃ Epic 16: Full Dashboard (1601~4)  ┃                                    ┃
```

---

## Critical Path & Dependencies

```
W1: Epic 8 (DB) + Epic 9 (PoC+VAT) + Epic 13 (VPS) ← parallel start
        ↓
W2: Epic 8 (Auth/MinIO/Celery) + Epic 9 (WHT/OCR) + Epic 13 (DNS/CI/CD)
        ↓ DB + Auth ready
W3: Epic 10 (Template backend) + Epic 11 (Purchase Tax)
        ↓
W4: Epic 10 (Configurator UI) + Epic 13 (Docker UAT)
        ↓
W5: Epic 10 (Clone+Export) + Epic 12 (Login/Company)
        ↓
W6: Epic 12 (Dashboard/Users) + Epic 13 (Backup/Firewall)
        ↓ All features complete
W7: Integration test + UAT deploy (uat.bwcacc.com) → UAT sign-off
        ↓
W8: PROD deploy (app.bwcacc.com) → Go-Live

Critical Path: Epic 8 → Epic 10 → Epic 12 → UAT → PROD
Parallel:      Epic 9 (accuracy) + Epic 13 (infrastructure)
```

**Bottlenecks:**

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Epic 8 (DB integration) delays | High — blocks everything | PoC pipeline works, DB is additive not rewrite |
| DNS A records (bwcacc.com) | Low — self-managed, team controls Squarespace + Hostinger DNS | ตั้ง A records ได้ทันที ไม่มี external dependency |
| VPS procurement delay | Medium — blocks deployment | Order W1, fallback to existing PoC VPS temporarily |
| Express CSV format unknown | Low — template engine is flexible | Template engine handles any column order, adjust later |
| Line Item PoC shows high cost | Low — scope is CR-based | Results inform Phase II/2 pricing, not Phase II/1 |

---

## Payment Milestones

| งวด | % | จำนวน (ฐาน ฿300K) | เงื่อนไข | Milestone |
|-----|---|-------------------|---------|-----------|
| **1 — Kickoff** | 50% | ฿150,000 | ลงนามสัญญา Phase II | ก่อนเริ่มงาน W1 |
| **2 — UAT** | 10% | ฿30,000 | Deploy uat.bwcacc.com + client ทดสอบผ่าน | W7 |
| **3 — Production** | 20% | ฿60,000 | Deploy app.bwcacc.com + Go-live + Warranty 7 วัน | W8 + 7 วัน |
| **4 — Phase II/2** | 20% | ฿60,000 | ส่งมอบ Phase II/2 (Line item, Sales tax, Dashboard) | W9+ ตามแผน |

> **Note:** ฐานราคา ฿300K เป็นตัวอย่าง — ราคาจริงตามที่ตกลงในสัญญา

---

## Phase II/2: Post-Go-Live Epics (Detail)

### Epic 14: Line Item + Inventory Full Implementation

| Task | งาน | Complexity | Req# |
|------|------|-----------|------|
| TASK-1401 | Line item extraction (full) — LLM prompt engineering + post-processing | L | 2 |
| TASK-1402 | Line item DB schema + API endpoints | M | 2 |
| TASK-1403 | Inventory data structure (product, qty, supplier, doc ref, amount) | M | 4 |
| TASK-1404 | Inventory export template (template engine based) | M | 4 |

**Scope ขึ้นกับผล TASK-906 (Line Item PoC):**
- ถ้า accuracy > 85% + cost acceptable → Full implementation
- ถ้า accuracy 70-85% → Limited scope (specific doc types only)
- ถ้า accuracy < 70% or cost too high → Defer to Phase III with different approach

### Epic 15: Sales Tax Report

| Task | งาน | Complexity | Req# |
|------|------|-----------|------|
| TASK-1501 | Sales Tax Report template definition (ภาษีขาย format) | M | 3 |
| TASK-1502 | Sales Tax Report rendering + master template seed | M | 3 |

### Epic 16: Full Dashboard + Monitoring

| Task | งาน | Complexity |
|------|------|-----------|
| TASK-1601 | Full KPI Dashboard (accuracy trends, throughput, cost analytics) | M |
| TASK-1602 | Sentry integration (error tracking + performance monitoring) | M |
| TASK-1603 | Audit log viewer (search, filter, export) | M |
| TASK-1604 | Budget alert notifications (LINE/email when 80% threshold) | S |

---

## Success Criteria

### Phase II/1 Go-Live (W8)

| # | Criteria | วิธีทดสอบ |
|---|---------|----------|
| 1 | Login ด้วย username/password → เข้า Dashboard ได้ | E2E test |
| 2 | Upload เอกสาร → OCR + extraction → ผลบันทึกใน DB | API + DB query |
| 3 | Background processing ไม่ timeout (เอกสาร ≤ 30 วินาที) | Load test |
| 4 | Review Scan + Review Mapping → Confirm → Export ตาม template | E2E test |
| 5 | Template Configurator: เลือก fields, drag-drop, rename, save | UI test |
| 6 | Clone master template → company template → customize → export | E2E test |
| 7 | Purchase Tax Report export ถูกต้อง (format, VAT buckets, totals) | Sample comparison |
| 8 | VAT disambiguation accuracy ดีขึ้นวัดได้ (before/after) | Test corpus |
| 9 | WHT badge แสดงถูกต้อง | Test corpus |
| 10 | Company management + COA import ทำงานได้ | UI test |
| 11 | Deploy on app.bwcacc.com + uat.bwcacc.com สำเร็จ | Health check + smoke test |
| 12 | PROD access locked down ตาม security policy | Pentest + audit |
| 13 | Backup automated + restore tested | Restore drill |

### Phase II/1 Go-Live — Line Item PoC (W1)

| # | Criteria |
|---|---------|
| 1 | ทดสอบ ≥ 10 ตัวอย่าง invoices หลาย format |
| 2 | ทดสอบ ≥ 3 LLM models (cost comparison) |
| 3 | Feasibility report with go/no-go recommendation |
| 4 | Cost projection ที่ 10K docs/month |
| 5 | Per-field accuracy measurement |

---

## Ownership & Escalation

| Epic | Owner | Approver | Escalation |
|------|-------|----------|-----------|
| 8 — Foundation | Backend Dev | Tech Lead | Product Owner |
| 9 — Accuracy | ML/Backend Dev | Tech Lead | Product Owner |
| 10 — Template Engine | Full-stack Dev | Tech Lead | Product Owner |
| 11 — Tax Reports | Backend Dev | Accountant | Product Owner |
| 12 — Admin UI | Frontend Dev | Tech Lead | Product Owner |
| 13 — Infrastructure | DevOps | Tech Lead | Product Owner |
| 14-16 — Phase II/2 | Full-stack Dev | Tech Lead | Product Owner |

---

## Weekly Status Checkpoints

| Week | Active Epics | Checkpoint Gate | Payment |
|------|-------------|----------------|---------|
| W0 | 0 | UX contract frozen + prototype patched + API contract approved + Epic 8 handoff ready | — |
| W1 | 8 + 9 + 13 | `801A` schema ready + `802` seed plan + `804` storage path + Line Item PoC report + VPS ordered | **50% Kickoff** |
| W2 | 8 + 9 + 13 | Auth working + DNS configured + CI/CD designed | — |
| W3 | 10 + 11 + 13 | Template engine core + Purchase tax integrated | — |
| W4 | 10 + 13 | Configurator UI working + CI/CD pipeline deployed | — |
| W5 | 10 + 12 + 13 | Full template flow + Login screen | — |
| W6 | 12 + 13 | All features complete + Backup configured | — |
| W7 | QA + 13 | UAT deployed (uat.bwcacc.com) + Client testing | **10% UAT** |
| W8 | Go-Live | PROD deployed (app.bwcacc.com) + Warranty start | **20% Prod** (after 7-day warranty) |

---

## Contract-Ready Clauses

### Client Responsibilities (สิ่งที่ลูกค้าต้องจัดส่ง)

| # | รายการ | ส่งเมื่อไร | ถ้าไม่ส่ง |
|---|--------|-----------|----------|
| 1 | ตัวอย่าง CSV/Excel ที่ import เข้า Express ได้จริง (column order, encoding, delimiter) | ก่อน W3 | Template Engine delay ไม่นับเป็น vendor delay |
| 2 | ผังบัญชี (COA) ของทุกบริษัทลูกค้า (account code + account name) | ก่อน W5 | Company/COA setup delay |
| 3 | ตัวอย่างเอกสาร 20-30 ใบ หลาย format (ดู TASK-906 diversity checklist) | ก่อน W1 | Line Item PoC + accuracy test delay |
| 4 | UAT feedback หลัง deploy uat.bwcacc.com | ภายใน 5 วันทำการ | ถือว่า accept, timeline เลื่อนเท่าวันที่ล่าช้า |
| 5 | UAT sign-off หลังแก้ bug รอบสุดท้าย | ภายใน 3 วันทำการ | ถือว่า accept |
| 6 | DNS A records verified — uat.bwcacc.com, app.bwcacc.com ชี้ถูก VPS | ก่อน W2 | ทีม set A records เองได้เลย (bwcacc.com self-managed) |

### AI/OCR Accuracy Disclaimer

> *"ระบบ LedgerFlow ใช้เทคโนโลยี AI/OCR ในการอ่านและสกัดข้อมูลจากเอกสาร ซึ่งอาจมีความคลาดเคลื่อน ผู้ใช้งานต้องตรวจสอบและยืนยันข้อมูลก่อนนำไป export หรือใช้งานทุกครั้ง (Human-in-the-Loop)*
>
> *ผู้พัฒนาไม่รับผิดชอบต่อความถูกต้องของข้อมูลทางบัญชี ภาษี หรือการเงินที่ผู้ใช้นำไปใช้โดยไม่ได้ตรวจสอบ ระบบนี้เป็นเครื่องมือช่วยจัดเตรียมข้อมูล (Pre-Accounting) ไม่ใช่ระบบบัญชี และไม่ได้ทดแทนโปรแกรม Express Accounting"*

### Change Request (CR) Rules

**รวมในราคาสัญญา:**

| รายการ | ขอบเขต |
|--------|--------|
| Master templates | ≤ 3 แบบ (Express GL, Purchase Tax, Sales Tax) |
| Company-specific templates (clone จาก master) | ≤ 10 บริษัท |
| UAT revision rounds | ≤ 2 รอบ |
| Bug fix (Warranty) | 30 วันหลัง go-live |
| Template แก้ไข (MA period) | ≤ 2 ครั้ง/เดือน |

**คิดเพิ่มเป็น CR:**

| รายการ | หมายเหตุ |
|--------|----------|
| Master template แบบที่ 4+ | ราคาตาม scope |
| บริษัทที่ 11+ (clone + COA setup) | ราคาตาม scope |
| UAT revision รอบที่ 3+ | ราคาตาม scope |
| Feature ใหม่ / report format ใหม่ | Quote แยก |
| Document type ใหม่ที่ต้อง train/tune | Quote แยก |
| Template แก้ไขเกิน 2 ครั้ง/เดือน (MA) | ตาม MA rate |

### Export Mapping Scope Clarification

> **หมายเหตุสำคัญ:** ระบบ LedgerFlow ทำหน้าที่ **จัดเตรียมข้อมูลสำหรับ export** (Export Mapping / Account Code Suggestion) เท่านั้น
>
> - **ทำ:** อ่านเอกสาร → สกัดข้อมูล → แนะนำ account code → จัดรูปแบบ → export CSV/Excel
> - **ไม่ทำ:** บันทึกบัญชี (GL posting), ยื่นภาษี, สร้าง voucher ในระบบบัญชี
> - **ผู้ใช้ต้อง:** import ไฟล์ export เข้า Express Accounting ด้วยตนเอง

---

## Document References

| Document | Location | Purpose |
|----------|---------|---------|
| Phase II Master Plan | `docs/requirement/phaseII/PHASE-II-MASTER-PLAN.md` | Full scope + design details |
| PoC Master Roadmap | `docs/PoC/plan/MASTER-ROADMAP.md` | PoC epic structure reference |
| Contract Draft | `docs/CONTRACT-SOFTWARE-DEVELOPMENT.html` | Payment + SLA + scope |
| Architecture | `docs/ARCHITECTURE.md` | System architecture |
| Mapping Architecture | `docs/MAPPING-ARCHITECTURE.md` | Export mapping / account code suggestion design |
| CI/CD Procedures | `D:\01_gitrepo\Openclaw\docs\cicd\README.md` | Deployment procedures |
| Template Configurator Demo | `src/frontend/template-configurator-demo.html` | UI prototype |

---

## Appendix A: Post-Go-Live GCP Migration Evaluation

> **เมื่อไร:** ประเมินหลัง go-live 1-2 เดือน (เมื่อระบบ stable แล้ว)
> **เป้าหมาย:** ตัดสินใจว่าควรย้ายจาก Hostinger → GCP/Cloud Run หรืออยู่ Hostinger ต่อ

### Evaluation Triggers (ถ้าเกิดข้อใดข้อหนึ่ง → ประเมินย้าย)

| # | Trigger | วิธีวัด | Threshold |
|---|---------|---------|-----------|
| 1 | VPS downtime สูง | Uptime Kuma logs | < 99.5% monthly uptime |
| 2 | Performance bottleneck ที่แก้ด้วย scale ไม่ได้ | p95 response time | > 3s sustained |
| 3 | Backup/restore ไม่เชื่อถือได้ | Restore drill results | Fail > 1 ครั้ง |
| 4 | Gemini Vision แทน PaddleOCR ได้ | TASK-906 + accuracy test | Accuracy ≥ PaddleOCR + cost OK |
| 5 | ลูกค้าเพิ่ม (multi-tenant) | Tenant count | > 3 tenants |
| 6 | Compliance requirement | Client/legal request | Data residency rules |

### Evaluation Criteria (ถ้าต้องประเมิน)

| Dimension | Hostinger (ปัจจุบัน) | GCP Cloud Run | ตัดสินอย่างไร |
|-----------|---------------------|---------------|-------------|
| **Cost** | ฿900-1,400/mo fixed | ฿3,000-5,000/mo (estimate) | Total cost of ownership 12 เดือน |
| **Uptime** | 99.9% SLA (shared) | 99.95% SLA (managed) | ดู actual uptime logs |
| **Scaling** | Manual (upgrade plan) | Auto-scale | ต้องการ auto-scale จริงไหม? |
| **DB** | Docker PostgreSQL | Cloud SQL (managed) | Backup/HA คุ้มค่าที่ราคาเพิ่มไหม? |
| **OCR** | PaddleOCR on VPS (need CPU) | Gemini Vision API (no local OCR) | ถ้า Vision แทนได้ → VM เล็กลงมาก |
| **DevOps effort** | SSH + Docker Compose | Cloud Run + Terraform | Solo dev capacity |
| **Migration risk** | N/A (อยู่แล้ว) | 1-2 สัปดาห์ work + downtime risk | มี bandwidth ไหม? |
| **MCP/AI agent** | Hostinger MCP ✓ | GCP MCP ✓ | ทั้งคู่รองรับ |

### Decision Matrix

```
Score each dimension 1-5 (5 = GCP clearly better)

Total < 20  → Stay on Hostinger
Total 20-28 → Evaluate deeper (pilot migration)
Total > 28  → Migrate to GCP

Current estimate: ~16 (Stay on Hostinger)
Re-evaluate when triggers fire.
```

### Key Insight: Gemini Vision = Game Changer

ถ้า Google Gemini Vision สามารถอ่านเอกสารได้ accuracy เทียบเท่า PaddleOCR:
- **ไม่ต้อง PaddleOCR บน VPS** → ลด CPU/RAM ลงมาก
- **VM เล็กลง** → GCP cost ลดลงใกล้เคียง Hostinger
- **ไม่ต้อง maintain OCR dependencies** → DevOps effort ลดลง
- **TASK-906 (Line Item PoC)** จะทดสอบ Gemini Vision เป็น by-product อยู่แล้ว

---

*Last Updated: 2026-06-15*
*Next Review: Weekly (every Monday)*
