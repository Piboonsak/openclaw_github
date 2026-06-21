# DB Impact Contract for Workflow Entities

> **TASK-003** | Epic 0 — UX Contract & Workflow Freeze
> **Created**: 2026-06-20
> **Status**: PENDING APPROVAL — do not modify ORM models until accepted
> **References**: [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md), [WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md)

---

## 1. Entity Decision Matrix

Every workflow concept from the UX audit is classified below.

| UX Concept | DB Decision | Rationale |
|-----------|-------------|-----------|
| Upload batch | **NEW TABLE** `document_batches` | Batch is a first-class aggregate — progress tracking, export scoping, audit entity reference |
| Document processing stages | **JSONB field** `Document.processing_progress` | 4-5 sub-stages change rapidly during Celery task — separate table would over-normalize |
| Document scan review | **NEW COLUMNS** on `Document` | `scan_status`, `scan_reviewed_by`, `scan_reviewed_at` — tight coupling with document lifecycle |
| Document flags | **NEW TABLE** `document_flags` | Multiple flags per document, each with reason/comment/status — can't fit in a single column |
| Field corrections (scan review edits) | **NEW TABLE** `field_corrections` | Append-only audit trail of field-level edits — accounting compliance requires knowing what changed |
| Export job | **NEW TABLE** `export_jobs` | Export is a first-class event — needs status, template reference, file metadata |
| Export file | **NEW TABLE** `export_files` | Generated files stored in object storage — need metadata + download tracking |
| Export-document link | **JOIN TABLE** `export_job_documents` | Which documents were in each export — proper FK, queryable both directions |
| Customer page credit plan | **NEW TABLE** `company_credit_plans` | Customer dashboard must show page credits/package usage, not internal LLM model or token cost |
| Page credit usage ledger | **NEW TABLE** `page_credit_usage` | Need auditable usage by scanned document type and page count; reprocess must not double-charge |
| Export column/format configuration | **JSONB field** `ExportTemplate.columns` | Existing template JSON can hold column order, data type, date format, number/text options |
| COA defaults + mapping rule settings | **EXISTING TABLES** `chart_of_accounts`, `account_mapping_rules`, `companies.settings` | Company detail "settings" tab should expose existing COA/rule config, not require new tables |
| Internal system admin screens | **ROLE/NAVIGATION RULE** | Cost Control, Audit Log, Settings are LedgerFlow internal system-admin screens, hidden from customer admin workspace |
| Template versioning | **Phase II/2** | MVP has no version history — edit-in-place is sufficient. Version tracking deferred. |
| Review assignment/locking | **Phase II/2** | MVP uses shared queue — no per-user assignment locks |
| Company settings | **JSONB field** `Company.settings` | Already exists. No separate table needed for MVP. |
| API key storage (per-company) | **Phase II/2** | MVP uses env vars. DB-stored keys need encryption at rest. |
| Session management | **NOT NEEDED** | JWT stateless auth — no session table |

---

## 2. Proposed DB Additions

### 2.1 NEW TABLE: `document_batches`

**Purpose**: Groups documents from a single upload session. Provides aggregate status, progress tracking, and export scoping.

**Used by screens**: Upload, Processing, Export, Dashboard, Audit Log

```python
class DocumentBatch(Base):
    __tablename__ = "document_batches"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    batch_label: Mapped[str | None] = mapped_column(String(100))  # e.g. "Batch #2605-001"
    status: Mapped[str] = mapped_column(String(30), default="draft")
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company] = relationship()
    documents: Mapped[list[Document]] = relationship(back_populates="batch")

    __table_args__ = (
        Index("ix_batches_company_status", "company_id", "status"),
    )
```

**Status values**: `draft`, `uploading`, `processing`, `review_scan`, `review_mapping`, `ready_export`, `exported`, `failed`, `archived`

### 2.2 MODIFIED TABLE: `documents` — New Columns

| Column | Type | Purpose |
|--------|------|---------|
| `batch_id` | FK → `document_batches.id` | **Change from bare UUID to FK** |
| `status` | String(30) | **Constrain** to `DocumentStatus` enum values |
| `scan_status` | String(20), default `"pending"` | Separate scan review status: `pending`, `approved`, `flagged` |
| `scan_reviewed_by` | FK → `users.id`, nullable | Who approved/flagged scan |
| `scan_reviewed_at` | DateTime, nullable | When scan was reviewed |
| `processing_progress` | JSONB, nullable | 4-stage progress: `{"ocr":"done","classify":"done","extract":"running","map_coa":"pending"}` |

```python
# Changes to Document model:
batch_id: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("document_batches.id", ondelete="SET NULL")  # was bare UUID
)
scan_status: Mapped[str] = mapped_column(String(20), default="pending")
scan_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
    ForeignKey("users.id", ondelete="SET NULL")
)
scan_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
processing_progress: Mapped[dict | None] = mapped_column(JSONB)
```

### 2.3 NEW TABLE: `document_flags`

**Purpose**: Human-raised flags on documents during review. Multiple flags per document allowed.

**Used by screens**: Review Scan (Flag modal)

```python
class DocumentFlag(Base):
    __tablename__ = "document_flags"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    flagged_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "incorrect_amount", "wrong_vendor", "unreadable"
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")  # open, resolved, dismissed
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = _now()

    document: Mapped[Document] = relationship()

    __table_args__ = (
        Index("ix_flags_document_status", "document_id", "status"),
    )
```

**Flag reasons (enum)**: `incorrect_amount`, `wrong_vendor`, `wrong_tax_id`, `unreadable`, `duplicate`, `missing_info`, `other`

### 2.4 NEW TABLE: `field_corrections`

**Purpose**: Append-only log of field-level edits during scan review. Tracks old → new values for audit.

**Used by screens**: Review Scan (when user edits extraction fields)

```python
class FieldCorrection(Base):
    __tablename__ = "field_corrections"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "invoice_number", "seller_name"
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    corrected_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _now()

    document: Mapped[Document] = relationship()

    __table_args__ = (
        Index("ix_corrections_document", "document_id"),
    )
```

**Important**: When a user corrects a field in Review Scan:
1. INSERT into `field_corrections` (old + new)
2. UPDATE the corresponding `Document` column (e.g., `seller_name`)
3. Both in same transaction

### 2.5 NEW TABLE: `export_jobs`

**Purpose**: Tracks each export action with template, format, status, and link to generated file.

**Used by screens**: Export, Dashboard (activity log)

```python
class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("export_templates.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, generating, completed, failed, downloaded
    total_documents: Mapped[int] = mapped_column(Integer, default=0)
    file_format: Mapped[str] = mapped_column(String(10), default="csv")
    encoding: Mapped[str] = mapped_column(String(20), default="utf-8")
    created_at: Mapped[datetime] = _now()

    company: Mapped[Company] = relationship()
    template: Mapped[ExportTemplate | None] = relationship()
    files: Mapped[list[ExportFile]] = relationship(back_populates="export_job")
    documents: Mapped[list[ExportJobDocument]] = relationship(back_populates="export_job")

    __table_args__ = (
        Index("ix_export_jobs_company", "company_id"),
    )
```

### 2.6 NEW TABLE: `export_files`

**Purpose**: Generated export file metadata + storage key.

```python
class ExportFile(Base):
    __tablename__ = "export_files"

    id: Mapped[uuid.UUID] = _uuid_pk()
    export_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("export_jobs.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _now()

    export_job: Mapped[ExportJob] = relationship(back_populates="files")
```

### 2.7 NEW TABLE: `export_job_documents` (Join)

**Purpose**: Links export jobs to the documents they included.

```python
class ExportJobDocument(Base):
    __tablename__ = "export_job_documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    export_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("export_jobs.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    export_job: Mapped[ExportJob] = relationship(back_populates="documents")
    document: Mapped[Document] = relationship()

    __table_args__ = (
        UniqueConstraint("export_job_id", "document_id", name="uq_export_job_document"),
    )
```

### 2.8 NEW TABLE: `company_credit_plans`

**Purpose**: Stores customer-facing subscription/package terms for page credits. This replaces the dashboard's LLM/token-cost presentation for company owners.

**Used by screens**: Dashboard (customer-facing page credit card), Companies (internal billing/admin)

```python
class CompanyCreditPlan(Base):
    __tablename__ = "company_credit_plans"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    plan_name: Mapped[str] = mapped_column(String(100), nullable=False)
    billing_model: Mapped[str] = mapped_column(String(30), default="page_credit")
    included_page_credits: Mapped[int] = mapped_column(Integer, default=0)
    price_original_thb: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    price_effective_thb: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    cycle_start: Mapped[date | None] = mapped_column(Date)
    cycle_end: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company] = relationship()

    __table_args__ = (
        Index("ix_credit_plans_company_active", "company_id", "is_active"),
    )
```

**Example package**: Pro Premium, original 45,000 THB, effective 25,500 THB, included 20,000 page credits.

### 2.9 NEW TABLE: `page_credit_usage`

**Purpose**: Append-only ledger for customer-facing page credit consumption by document scan. This is separate from internal `api_usage`.

**Used by screens**: Dashboard (usage breakdown by document type), Upload/Processing (charge once per accepted scan), internal billing review

```python
class PageCreditUsage(Base):
    __tablename__ = "page_credit_usage"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_batches.id", ondelete="SET NULL")
    )
    document_type: Mapped[str | None] = mapped_column(String(50))
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    credits_used: Mapped[int] = mapped_column(Integer, default=1)
    usage_reason: Mapped[str] = mapped_column(String(30), default="scan")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _now()

    company: Mapped[Company] = relationship()
    document: Mapped[Document | None] = relationship()
    batch: Mapped[DocumentBatch | None] = relationship()

    __table_args__ = (
        Index("ix_page_credit_company_created", "company_id", "created_at"),
        Index("ix_page_credit_document", "document_id"),
    )
```

**Charging rule**: Charge once when a document/page is accepted into an upload batch. Retry/reprocess does not create another usage row unless explicitly recorded as an adjustment.

---

## 3. Existing Tables — No Changes Needed

These tables are sufficient for MVP as-is:

| Table | Used by screens | Notes |
|-------|----------------|-------|
| `tenants` | All (multi-tenant filter) | OK |
| `companies` | Companies, Upload, all queries | OK — `settings` JSONB covers future config |
| `users` | Users, Login, all queries | OK |
| `user_company_assignments` | Users, role-filtered queries | OK |
| `extractions` | Review Scan (detailed JSON) | OK — `extraction_json` JSONB |
| `journal_vouchers` | Review Mapping, Export | OK — `confirmed_by/at` already present |
| `journal_lines` | Review Mapping | OK |
| `chart_of_accounts` | Company Detail, Review Mapping (COA lookup) | OK |
| `account_mapping_rules` | Review Mapping (ML feedback) | OK |
| `export_templates` | Templates, Template Configurator, Export | OK — JSONB `columns` handles column order, data type, date format, number/text options |
| `api_usage` | Internal Cost Control only | OK — internal LLM/token cost; must not appear on customer dashboard |
| `budget_limits` | Internal Cost Control, internal Settings, Processing guard | OK — internal safeguard, not customer package balance |
| `audit_logs` | Internal Audit Log, Dashboard activity | OK — customer-facing activity must be filtered by tenant and role |
| `data_retention_policies` | Settings (Phase II/2) | OK — exists but not active in MVP |

---

## 4. No-Go List — Explicitly NOT in Phase II/1

| Concept | Reason | When |
|---------|--------|------|
| `TemplateVersion` table | MVP edits templates in-place; no version history needed yet | Phase II/2 |
| `ReviewAssignment` table | MVP uses shared queue; no per-user locking | Phase II/2 |
| `ApiCredential` table (per-company keys) | MVP uses env vars; DB-stored keys need encryption | Phase II/2 |
| `Sessions` table | JWT is stateless; no server-side session storage | Not needed |
| `Notification` table | MVP has no notification system (no email/LINE alerts) | Phase II/2 or III |
| `DocumentLineItem` table | Item-level extraction (SKU, Qty) is TASK-906 PoC; table deferred until Go/No-Go | Phase II/2 (if PoC passes) |
| `BrokerTemplate` table | Broker document routing is Phase II/2 | Phase II/2 |
| `PasswordResetToken` table | MVP handles password reset via Admin "Reset PW" button directly | Not needed |
| `SystemAdminUser` table | Use existing `users.role`/tenant rules and navigation guards; do not create a parallel auth model | Not needed |

---

## 5. Migration Order

Migrations MUST land in this order for Epic 8 (`TASK-801A`):

| Order | Migration | Depends on | Alembic revision |
|-------|-----------|-----------|-----------------|
| 1 | Create `document_batches` table | — | TBD |
| 2 | Add `Document` columns (`scan_status`, `scan_reviewed_by/at`, `processing_progress`) + change `batch_id` to FK | Migration 1 (FK target exists) | TBD |
| 3 | Create `document_flags` table | — | TBD |
| 4 | Create `field_corrections` table | — | TBD |
| 5 | Create `export_jobs` table | — | TBD |
| 6 | Create `export_files` table | Migration 5 (FK target) | TBD |
| 7 | Create `export_job_documents` table | Migration 5 (FK target) | TBD |
| 8 | Create `company_credit_plans` table | `companies` exists | TBD |
| 9 | Create `page_credit_usage` table | `companies`, `documents`, `document_batches`, `users` exist | TBD |

**Migrations 1-4 must land before**: TASK-802 (Auth + Upload endpoint), TASK-803 (Processing pipeline to DB)
**Migrations 5-7 must land before**: TASK-805 (Export service) or can be parallel
**Migrations 8-9 must land before**: customer dashboard page credit implementation

### Data Migration from PoC

The PoC has no persistent data to migrate — file-cache is regenerable. DB starts clean.

However, these seed data tasks are needed:
1. Seed master `export_templates` (Express GL + ภ.พ.30)
2. Seed default `budget_limits` (global)
3. Import `companies.json` into `companies` table
4. Import YAML COA files into `chart_of_accounts`

---

## 6. Compatibility with PoC Dual-Mode

During Epic 8 transition, the pipeline writes to both file-cache AND DB. This contract ensures:

| Pipeline Stage | File-cache (existing) | DB (new) | When to drop file-cache |
|---------------|----------------------|---------|------------------------|
| OCR output | `ocr_output.json` | Not stored (regenerable) | Never (keep as cache) |
| Extraction output | `extraction_output.json` | `extractions.extraction_json` | After TASK-803 verified |
| Journal output | `journal_output.json` | `journal_vouchers` + `journal_lines` | After TASK-803 verified |
| Stage C budget | `stage_c_budget.json` | `api_usage` + `budget_limits` | After TASK-804; internal only, not customer dashboard |
| Customer page credits | N/A | `company_credit_plans` + `page_credit_usage` | Required before customer dashboard billing card |
| COA rules | `rules/{company_id}/rule_coa.yaml` | Keep as file (git-versioned config) | **Never** — stays file-based |

---

## 7. Schema Summary (Before vs After)

### Before (15 tables)
```
tenants, companies, users, user_company_assignments,
documents, extractions, journal_vouchers, journal_lines,
chart_of_accounts, account_mapping_rules, export_templates,
api_usage, budget_limits, audit_logs, data_retention_policies
```

### After (23 tables)
```
[existing 15]
+ document_batches        (NEW — upload session aggregate)
+ document_flags          (NEW — human flag during review)
+ field_corrections       (NEW — field-level edit audit trail)
+ export_jobs             (NEW — export action tracking)
+ export_files            (NEW — generated file metadata)
+ export_job_documents    (NEW — join: which docs in each export)
+ company_credit_plans    (NEW — customer package/page credit plan)
+ page_credit_usage       (NEW — page credit usage ledger)

[modified]
~ documents               (ADD: scan_status, scan_reviewed_by/at, processing_progress; CHANGE: batch_id → FK)
```

**Net change**: +8 tables, +5 columns on existing table. No tables removed.

---

## 8. Approval Checklist

Before `TASK-801A` implementation begins, confirm:

- [ ] `DocumentBatch` as table (not UUID tag) — **approved**
- [ ] `Document.status` high-level + `processing_progress` JSONB — **approved**
- [ ] `FieldCorrection` as append-only table — **approved**
- [ ] `DocumentFlag` as separate table (not JSONB on Document) — **approved**
- [ ] `ExportJob` + `ExportFile` as separate tables — **approved**
- [ ] `export_job_documents` join table (not JSONB array) — **approved**
- [ ] `CompanyCreditPlan` + `PageCreditUsage` for customer-facing page credits — **approved**
- [ ] Customer dashboard hides LLM provider/model/token/internal cost — **approved**
- [ ] Cost Control, Audit Log, Settings are internal system-admin screens — **approved**
- [ ] Export format options stay in `export_templates.columns` JSONB — **approved**
- [ ] No-go list items confirmed deferred — **approved**
- [ ] Migration order accepted — **approved**

**Sign-off**: _________________________ Date: _____________

---

*Created: 2026-06-20*
*Blocks: TASK-801A (models + migrations), TASK-801B (pipeline to DB), TASK-803 (auth + upload)*
