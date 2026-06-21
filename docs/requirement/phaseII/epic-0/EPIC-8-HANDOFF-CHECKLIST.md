# Epic 8 Handoff Checklist & Sign-Off

> **TASK-006** | Epic 0 — UX Contract & Workflow Freeze
> **Created**: 2026-06-20
> **Purpose**: Gate checklist before `TASK-801A` / `TASK-801B` DB implementation begins

---

## Pre-Implementation Gate

All items below MUST be confirmed before modifying `src/backend/db/models.py` or running `alembic revision`.

### 1. UX Contract Decisions (from TASK-001 + TASK-004)

| # | Decision | Status | Document |
|---|----------|--------|----------|
| 1 | All 14 screens inventoried with action classifications | ✅ Done | [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md) |
| 2 | 52 primary actions classified (38 MVP, 8 mock, 4 disable, 2 II/2) | ✅ Done | [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md) |
| 3 | 6 modals/drawers inventoried | ✅ Done | [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md) |
| 4 | Mobile scope = desktop-only for Phase II/1 | ✅ Decided | [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md) |
| 5 | Dead/non-functional actions identified and categorized | ✅ Done | [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md) |
| 5.1 | Customer dashboard uses page credits, not LLM provider/model/token cost | ✅ Decided | [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md) |
| 5.2 | Processing page uses calm stepper/checkmarks with only one active spinner | ✅ Decided | [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md) |
| 5.3 | Download CSV opens export config/preview before final file download | ✅ Decided | [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md) |
| 5.4 | COA settings + mapping rules are MVP company-detail settings | ✅ Decided | [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md) |
| 5.5 | Template create/view/edit/clone/delete and User edit/reset flows must be clickable for review | ✅ Decided | [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md) |
| 5.6 | Cost Control, Audit Log, Settings are internal system-admin screens, not customer admin screens | ✅ Decided | [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md) |

### 2. Workflow State Machine (from TASK-002)

| # | Decision | Status | Document |
|---|----------|--------|----------|
| 6 | Batch states defined (9 states) | ✅ Frozen | [WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md) |
| 7 | Document states defined (10 high-level states) | ✅ Frozen | [WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md) |
| 8 | Processing sub-stages tracked via JSONB | ✅ Decided | [WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md) |
| 9 | Journal voucher states defined (4 states) | ✅ Frozen | [WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md) |
| 10 | Export job states defined (5 states) | ✅ Frozen | [WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md) |
| 11 | Flag states defined (3 states) | ✅ Frozen | [WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md) |
| 12 | Role guards documented (Admin vs Staff) | ✅ Done | [WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md) |
| 13 | Error/edge states documented (8 scenarios) | ✅ Done | [WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md) |
| 14 | Python enum names defined for all state types | ✅ Done | [WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md) |

### 3. DB Impact Contract (from TASK-003)

| # | Decision | Status | Document |
|---|----------|--------|----------|
| 15 | Entity decision matrix complete, including page credits and system-admin separation | ✅ Done | [DB-IMPACT-CONTRACT.md](DB-IMPACT-CONTRACT.md) |
| 16 | 8 new tables proposed with full schema (6 workflow/export + 2 page-credit billing) | ✅ Done | [DB-IMPACT-CONTRACT.md](DB-IMPACT-CONTRACT.md) |
| 17 | 5 new columns on `documents` table | ✅ Done | [DB-IMPACT-CONTRACT.md](DB-IMPACT-CONTRACT.md) |
| 18 | `batch_id` changed from UUID to FK | ✅ Done | [DB-IMPACT-CONTRACT.md](DB-IMPACT-CONTRACT.md) |
| 19 | Migration order defined (9 steps) | ✅ Done | [DB-IMPACT-CONTRACT.md](DB-IMPACT-CONTRACT.md) |
| 20 | No-go list explicit (7 deferred items) | ✅ Done | [DB-IMPACT-CONTRACT.md](DB-IMPACT-CONTRACT.md) |
| 21 | PoC dual-mode compatibility confirmed | ✅ Done | [DB-IMPACT-CONTRACT.md](DB-IMPACT-CONTRACT.md) |
| 22 | Existing 15 tables confirmed; internal `api_usage`/`budget_limits` not customer dashboard data | ✅ Done | [DB-IMPACT-CONTRACT.md](DB-IMPACT-CONTRACT.md) |

---

## Epic 8 Task Annotations

Based on Epic 0 findings, the following `TASK-801A` / `TASK-801B` / `TASK-802` / `TASK-803` assumptions changed:

### TASK-801A: SQLAlchemy Models + Alembic

| Original Assumption | Epic 0 Change |
|---------------------|--------------|
| 15 existing models are sufficient | Need 8 new tables + 5 new columns |
| `Document.batch_id` is bare UUID | Must be FK → `document_batches` |
| `Document.status` is generic string | Must use `DocumentStatus` enum values |
| No processing progress tracking | Add `Document.processing_progress` JSONB |
| Dashboard can show LLM cost/model | Customer dashboard must show page credits; internal cost stays system-admin only |

**Updated TASK-801A scope**:
1. Add `DocumentBatch` model
2. Add `DocumentFlag` model
3. Add `FieldCorrection` model
4. Add `ExportJob`, `ExportFile`, `ExportJobDocument` models
5. Add `CompanyCreditPlan` and `PageCreditUsage` models
6. Modify `Document` model (new columns + FK change)
7. Create status enums module (`src/backend/db/enums.py`)
8. Generate 7 Alembic migrations in correct order (`002` through `008`)

### TASK-801B: Pipeline to DB Integration

| Original Assumption | Epic 0 Change |
|---------------------|--------------|
| Pipeline can write directly once schema exists | Must wait for `TASK-801A` migration chain and frozen route contract |
| Upload creates individual documents | Upload creates a `DocumentBatch` first, then documents within it |
| No batch concept in API | Need `POST /api/v1/batches` endpoint |
| Export remains direct download | Pipeline/runtime must coexist with export preview-first contract |

### TASK-802: Seed / Migration Data

| Original Assumption | Epic 0 Change |
|---------------------|--------------|
| Only companies/templates/admin seed are needed | Seed strategy must coexist with `company_credit_plans` and customer-facing page-credit dashboard |
| Master template seed can stay export-only | Template seed must support preview-first export config |

### TASK-803: Auth + Upload Endpoints

| Original Assumption | Epic 0 Change |
|---------------------|--------------|
| Document status is simple progression | Status uses 10-value enum + JSONB processing_progress |
| No scan review fields | Pipeline must set `scan_status='pending'` after extraction |

### TASK-805: Export Service

| Original Assumption | Epic 0 Change |
|---------------------|--------------|
| Export is direct download | Export creates `ExportJob` + `ExportFile` records |
| No export history | Export history reads from `export_jobs` table |
| Download CSV can immediately generate file | Download CSV opens export config/preview first, then generates final file |
| Export template only chooses columns | Template config must support column order, label, source field, data type, date format, number/text formatting, delimiter, encoding |

### TASK-804 / Dashboard Billing Boundary

| Original Assumption | Epic 0 Change |
|---------------------|--------------|
| Dashboard can show LLM provider/model cost | Customer dashboard hides model/provider/token/internal cost |
| Budget is customer-facing | `api_usage` + `budget_limits` are internal system-admin controls |
| No page credit ledger needed | Add `company_credit_plans` + `page_credit_usage` before customer billing dashboard |

---

## Sign-Off Block

### Approve (proceed to `TASK-801A`)

| Decision | Approve | Defer | Notes |
|----------|---------|-------|-------|
| `DocumentBatch` as first-class table | ☑ | ☐ | Frozen in Epic 0 contract |
| `Document` status enum (10 values) | ☑ | ☐ | Frozen in workflow state machine |
| `processing_progress` as JSONB (not separate table) | ☑ | ☐ | Frozen in workflow state machine |
| `FieldCorrection` as append-only table | ☑ | ☐ | Approved in DB impact contract |
| `DocumentFlag` as separate table | ☑ | ☐ | Approved in DB impact contract |
| `ExportJob` + `ExportFile` tables | ☑ | ☐ | Required by export history + preview-first flow |
| `export_job_documents` join table | ☑ | ☐ | Required by export selection/history |
| `CompanyCreditPlan` for customer package/page credit plan | ☑ | ☐ | Required by customer dashboard |
| `PageCreditUsage` ledger for scanned page credits | ☑ | ☐ | Required by customer dashboard |
| Customer dashboard hides LLM model/provider/token/internal cost | ☑ | ☐ | Prototype + route contract aligned |
| Cost Control/Audit Log/Settings moved to internal system-admin area | ☑ | ☐ | Prototype + route contract aligned |
| Export config/preview before final CSV/Excel download | ☑ | ☐ | Prototype + route contract aligned |
| COA settings + mapping rules visible in company settings tab | ☑ | ☐ | Prototype + route contract aligned |
| Template/User action buttons open reviewable flows in prototype | ☑ | ☐ | Prototype patch completed |
| JWT stateless (no session table) | ☑ | ☐ | Frozen for MVP auth direction |
| Desktop-only for Phase II/1 | ☑ | ☐ | Frozen in UX audit |
| TemplateVersion deferred to II/2 | ☑ | ☐ | Explicit no-go for MVP |
| ReviewAssignment deferred to II/2 | ☑ | ☐ | Explicit no-go for MVP |

**Approved by**: _________________________ **Date**: _____________

---

## Risk Note: What Happens If Epic 0 Is Skipped

If `TASK-801A` or `TASK-801B` proceeds without this contract:

1. **Batch table will be missing** → Processing and Export screens can't work properly → Alembic ALTER TABLE mid-sprint
2. **Document status will be unstable** → Frontend and backend disagree on allowed values → broken state transitions
3. **No field correction tracking** → Review Scan edits overwrite data silently → accounting audit failure
4. **No export job records** → Export history impossible to implement → re-add table and backfill
5. **batch_id stays as bare UUID** → No referential integrity → orphaned batch references
6. **No page credit ledger** → customer billing dashboard cannot reconcile package usage → manual spreadsheet workaround
7. **Internal cost screens leak into customer admin** → customers see provider/model/token details → commercial and trust risk
8. **Prototype action buttons stay dead** → DB/API implementation guesses wrong modal/form requirements → UX rework before demo

**Estimated rework if skipped**: 3-5 days of Alembic migrations + endpoint refactoring + test fixes + prototype rework

---

## First DB Implementation Slice (`TASK-801A`)

The first commit of `TASK-801A` should include:

1. `src/backend/db/enums.py` — all status enums from WORKFLOW-STATE-MACHINE.md
2. `src/backend/db/models.py` — add 8 new models + modify Document
3. `alembic/versions/002_add_document_batches.py`
4. `alembic/versions/003_add_document_review_columns.py`
5. `alembic/versions/004_add_document_flags.py`
6. `alembic/versions/005_add_field_corrections.py`
7. `alembic/versions/006_add_export_job_tables.py`
8. `alembic/versions/007_add_company_credit_plans.py`
9. `alembic/versions/008_add_page_credit_usage.py`
10. Seed script: `scripts/seed_master_templates.py`
11. Tests: `tests/db/test_models.py` — verify FK constraints, enum values, relationships

**Estimated effort**: 1.5-2 days (within `TASK-801A` allocation if migrations are kept focused)

---

*Created: 2026-06-20*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
