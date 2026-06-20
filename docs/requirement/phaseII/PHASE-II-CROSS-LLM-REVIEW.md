# Phase II Plan — Cross-LLM Review Brief

> **Purpose:** สรุปแผน Phase II ให้ AI อื่น (Gemini / GPT) review และให้ second opinion
> **Date:** 2026-06-15
> **Project:** AI Pre-Accounting Copilot (LedgerFlow)

---

## 1. What This System Does

ระบบ **Pre-Accounting** สำหรับสำนักงานบัญชีไทย ช่วยจัดการเอกสารก่อนบันทึกบัญชีใน Express Accounting:

```
สแกนเอกสาร → OCR อ่านข้อมูล → AI สกัดตัวเลข+จัดประเภท → ตรวจสอบ/แก้ไข → Export CSV/Excel → นำเข้า Express
```

- **Phase I (PoC):** เสร็จแล้ว — Thai OCR + AI extraction pipeline ทำงานจริง 4 stages (OCR → Field Extraction → LLM Repair → Export Mapping), มี frontend prototype, deploy อยู่บน Hostinger VPS
- **Phase II:** ยก PoC ขึ้นเป็น MVP production-ready

---

## 2. Phase II Scope Split

### Phase II/1 — Go-Live MVP (8 สัปดาห์, developer คนเดียว)

| Epic | Title | สัปดาห์ | สาระสำคัญ |
|------|-------|---------|----------|
| **8** | Platform Foundation | W1-2 | เปิดใช้ PostgreSQL + Alembic (ติดตั้งไว้แล้ว), JWT Auth, MinIO S3, Celery workers |
| **9** | Extraction Accuracy + Line Item PoC | W1-2 | แก้ VAT disambiguation, WHT detection, OCR gridline + PoC line item extraction |
| **10** | Template Engine + Configurator UI | W3-5 | **Core ของ Phase II** — dynamic column mapping, drag-drop UI, Master/Clone workflow |
| **11** | Purchase Tax Report Integration | W3 | ย้าย hardcoded report → template-based |
| **12** | Admin UI + Login | W5-6 | Login (JWT), MVP Dashboard, Company/COA management, 2-role RBAC |
| **13** | Infrastructure + Deployment | W1-8 parallel | Hostinger VPS (UAT+Prod), DNS bwc.biz, CI/CD, Firewall, Backup automation |

### Phase II/2 — Post-Go-Live (CR-based, scope ขึ้นกับผล PoC)

| Epic | Title | สาระสำคัญ |
|------|-------|----------|
| **14** | Line Item + Inventory Full | Full line item extraction + inventory data prep (scope ขึ้นกับผล TASK-906) |
| **15** | Sales Tax Report | รายงานภาษีขาย |
| **16** | Full Dashboard + Monitoring | Sentry, Audit log UI, Budget alerts |

### Payment Structure: 50% Kickoff / 10% UAT / 20% Prod / 20% Phase II/2

---

## 3. Key Decision: TASK-906 Line Item PoC (Week 1)

**ปัญหา:** ลูกค้าต้องการ line item extraction (SKU, Qty, Unit Price, Line Amount) แต่ยังไม่รู้ว่า:
- ทำได้จริงไหม (Thai invoices หลาย format)
- Cost เป็นอย่างไร (LLM API cost per document × 10K-20K docs/month)

**แผน:** ทำ PoC สัปดาห์แรก ก่อนเริ่ม development จริง

| ขั้นตอน | รายละเอียด |
|---------|-----------|
| เตรียมตัวอย่าง | 10-15 invoices หลาย format |
| ทดสอบ 3 models | Gemini Flash (free) vs Gemini Pro vs Claude Sonnet |
| วัด cost | tokens/doc → project monthly cost |
| วัด accuracy | per-field: product_name, qty, unit_price, line_amount, unit |
| Feasibility report | go/no-go recommendation |

**ผลกระทบ:**
- Go → Phase II/2 includes full line item (Epic 14) + กำหนดราคางวด 4
- No-Go → defer to Phase III, ลดราคางวด 4

---

## 4. Infrastructure Decision: Hostinger VPS All-In

### สิ่งที่เลือก

- **Hosting:** Hostinger KVM VPS (Singapore DC) — ทั้ง compute, DB, storage บน VPS เดียว
- **UAT:** KVM 2 (2 vCPU, 8GB RAM) ≈ ฿350-520/เดือน
- **PROD:** KVM 4 (4 vCPU, 16GB RAM) ≈ ฿550-860/เดือน
- **Backup offsite:** Cloudflare R2 (S3-compatible) ≈ ฿3-8/เดือน
- **Total:** ≈ ฿900-1,400/เดือน ($25-40 USD)
- **DNS:** bwc.biz → app.bwc.biz (PROD), uat.bwc.biz (UAT), demo.bwc.biz (PoC)
- **SSL:** Let's Encrypt + Certbot auto-renew
- **CI/CD:** GitHub Actions → SSH → Docker Compose

### เหตุผลที่เลือก Hostinger (ไม่ใช่ GCP/Azure/DO)

| เหตุผล | รายละเอียด |
|--------|-----------|
| **PoC ทำงานแล้ว** | Pipeline ทั้งหมดทดสอบบน Hostinger — ไม่ย้าย platform ระหว่าง sprint 8 สัปดาห์ |
| **ลด migration risk** | ย้าย infra + พัฒนา feature พร้อมกัน = เสี่ยงเกินไปสำหรับ solo dev |
| **MCP + AI agent** | Hostinger มี MCP tool ให้ AI agent จัดการ VPS ได้ — productivity สูงกว่า |
| **Cost** | ฿900-1,400/เดือน vs GCP ≈ ฿3,000-5,000/เดือน (managed services) |
| **LLM API independent** | Gemini/Anthropic API เรียกจาก Hostinger ได้ — ไม่ต้องอยู่ GCP |

### Concerns ที่รู้ (และ mitigation)

| Concern | Mitigation |
|---------|-----------|
| DB ใน Docker (ไม่มี managed PostgreSQL) | pg_dump daily + Cloudflare R2 offsite + restore drill ก่อน go-live |
| No auto-scaling | Scale: < 20 users, 670 docs/day ← 2 vCPU KVM handles 2,800+/day |
| Single point of failure | Hostinger snapshot ก่อนทุก deploy + R2 offsite backup |
| SLA อาจไม่เท่า managed cloud | ดู actual uptime 1-2 เดือนหลัง go-live แล้วประเมินอีกที |

### Post-Go-Live Migration Criteria (Appendix A in roadmap)

ถ้า Hostinger มีปัญหาจริงหลัง go-live → ประเมินย้าย GCP เมื่อ:
- Uptime < 99.5% monthly
- Backup/restore fail
- Gemini Vision แทน PaddleOCR ได้ (ลด VPS size → GCP cost ลดลง)
- Multi-tenant > 3 tenants

---

## 5. Architecture Overview (Phase II)

```
Docker Compose (per VPS):
├── nginx          — reverse proxy + SSL termination
├── backend        — FastAPI (Python 3.12)
├── celery-worker  — background OCR/extraction tasks
├── celery-beat    — scheduled tasks (backup, cleanup)
├── postgres       — PostgreSQL 16
├── redis          — Celery broker + result backend
└── minio          — S3-compatible document storage

Pipeline: Upload → MinIO → Celery task → PaddleOCR → Field Extraction
  → LLM Repair (Gemini Flash) → Export Mapping → PostgreSQL → Export
```

**DB:** 15 tables (ORM models เขียนเสร็จแล้ว) — tenants, companies, users, documents, extractions, journal_vouchers, journal_lines, chart_of_accounts, export_templates, api_usage, budget_limits, audit_logs, etc.

**Auth:** JWT (issue + refresh), 2 roles MVP (Admin/Staff), multi-company assignment

**Template Engine:** JSONB column definitions, Master/Clone workflow, field→column mapping + transforms (uppercase, thai_date, pad_left, etc.), CSV + Excel output

---

## 6. Scale & Constraints

| Dimension | Value |
|-----------|-------|
| Users | < 20 (single accounting firm) |
| Client companies | 5-15 |
| Documents/month | 10,000-20,000 pages |
| Documents/day (peak) | ~670 |
| Processing time/doc | 5-30 seconds (Celery background) |
| LLM budget | $30-100/month (Gemini Flash free tier + paid fallback) |
| Developer | Solo (1 person, full-stack) |
| Frontend | Enhanced HTML prototype (not React SPA) |

---

## 7. Questions for Review

ช่วยประเมินและให้ความเห็นในประเด็นเหล่านี้:

### Architecture & Infrastructure

1. **Hostinger VPS all-in decision** — สำหรับ scale นี้ (< 20 users, 670 docs/day) การใช้ Hostinger VPS แทน managed cloud (GCP/Azure) เป็นการตัดสินใจที่สมเหตุสมผลไหม? มี blind spot อะไรที่ควรระวัง?

2. **PostgreSQL in Docker** — ที่ scale นี้ DB ใน Docker + pg_dump daily + offsite backup (Cloudflare R2) เพียงพอไหม? ควรทำ WAL archiving / streaming replication เพิ่มหรือยังไม่จำเป็น?

3. **MinIO vs Cloudflare R2 direct** — ใช้ MinIO บน VPS เป็น document storage แล้ว backup ไป R2 — หรือควรใช้ R2 เป็น primary storage เลย?

### Project Management

4. **8-week timeline** — สำหรับ solo developer, 6 epics (30+ tasks) ใน 8 สัปดาห์ realistic ไหม? Epic ไหนเป็น risk สูงสุดที่อาจ delay?

5. **Phase II/1 vs II/2 split** — การแยก core go-live (II/1) กับ CR-based enhancement (II/2) เหมาะสมไหม? มีอะไรที่ควรสลับ phase?

6. **Payment 50/10/20/20** — เหมาะกับ project structure นี้ไหม? มีปัญหาอะไรที่เห็น?

### Technical

7. **TASK-906 Line Item PoC approach** — ทดสอบ 3 LLM models กับ 10-15 invoices สัปดาห์แรก แล้วตัดสินใจ go/no-go — approach นี้เพียงพอไหม? ควรทดสอบอะไรเพิ่ม?

8. **Template Engine design** — JSONB column definitions + Master/Clone workflow — มี pattern ที่ดีกว่านี้สำหรับ configurable export templates ไหม?

9. **VAT disambiguation (arithmetic-first)** — ทดสอบ 4 combinations (2 amount slots × 2 layout modes) แล้วเลือก best-fitting — approach นี้ robust พอไหม?

10. **Missing items** — มีอะไรที่แผนนี้ขาดหรือควรเพิ่ม สำหรับระบบ pre-accounting ที่ใช้งานจริง?

---

## 8. Risk Summary

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Epic 8 (DB integration) delays → blocks everything | Medium | High | PoC pipeline works, DB is additive |
| DNS delegation from bwc.biz delays | Medium | Medium | ใช้ temporary domain ถ้าล่าช้า |
| Solo dev capacity ไม่พอ 8 สัปดาห์ | Medium | High | Phase II/2 เป็น buffer, cut scope ถ้าจำเป็น |
| Line Item PoC shows high cost | Low | Low | Phase II/2 pricing adjusts, not Phase II/1 |
| Express CSV format ยังไม่ได้ตัวอย่าง | Low | Medium | Template engine handles any column order |
| Hostinger reliability post-go-live | Low | High | Monitor → GCP migration if needed |

---

## 9. Full Document References

รายละเอียดเต็มอยู่ที่:
- **Epic Roadmap (40+ tasks):** `PHASE-II-EPIC-ROADMAP.md`
- **Master Plan (design details):** `PHASE-II-MASTER-PLAN.md`
- **Architecture:** `docs/ARCHITECTURE.md`
- **Mapping Architecture:** `docs/MAPPING-ARCHITECTURE.md`

---

*Generated: 2026-06-15 | For cross-LLM validation purposes*
