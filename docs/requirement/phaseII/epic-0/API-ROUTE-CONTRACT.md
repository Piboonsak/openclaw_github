# API / Route Contract for Phase II Screens

> **TASK-005** | Epic 0 — UX Contract & Workflow Freeze
> **Created**: 2026-06-20
> **Status**: FROZEN FOR W0 SIGN-OFF
> **References**: [UX-CLICK-AUDIT.md](UX-CLICK-AUDIT.md), [WORKFLOW-STATE-MACHINE.md](WORKFLOW-STATE-MACHINE.md), [DB-IMPACT-CONTRACT.md](DB-IMPACT-CONTRACT.md)

---

## 1. Contract Principles

This document is the MVP route contract for Phase II/1. It exists to keep the prototype, DB design, and API implementation aligned before `TASK-801A` and `TASK-801B`.

Locked decisions:
- Customer-facing routes stay under `/api/v1/*`
- Internal LedgerFlow system-admin routes stay under `/api/v1/system/*`
- Customer dashboard shows page credits, not LLM provider/model/token/internal cost
- Export is `preview/config -> confirm job -> download`, not direct file generation on first click
- Company settings tab must expose COA defaults and mapping rules in MVP

---

## 2. Screen to Route Map

| Screen | Primary routes | Notes |
|-------|----------------|-------|
| Login | `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `POST /api/v1/auth/refresh` | JWT auth |
| Dashboard | `GET /api/v1/dashboard/summary`, `GET /api/v1/dashboard/activity` | Customer-facing tenant scope |
| Upload | `POST /api/v1/batches`, `POST /api/v1/batches/{id}/documents`, `GET /api/v1/batches/{id}` | Batch-first upload flow |
| Processing | `GET /api/v1/batches/{id}/processing`, `GET /api/v1/documents/{id}/status` | Read current state only |
| Review Scan | `GET /api/v1/documents/{id}`, `POST /api/v1/documents/{id}/approve-scan`, `POST /api/v1/documents/{id}/flags` | Human review |
| Review Mapping | `GET /api/v1/vouchers/{id}`, `PUT /api/v1/vouchers/{id}/lines`, `POST /api/v1/vouchers/{id}/confirm` | Mapping confirmation |
| Export | `POST /api/v1/exports/preview`, `POST /api/v1/exports/jobs`, `GET /api/v1/exports/jobs/{id}`, `GET /api/v1/exports/files/{id}/download` | Preview-first |
| Companies | `GET /api/v1/companies`, `POST /api/v1/companies`, `PUT /api/v1/companies/{id}` | Customer tenant admin only |
| Company Detail / COA | `GET /api/v1/companies/{id}/coa`, `POST /api/v1/companies/{id}/coa/import`, `PUT /api/v1/coa/{id}` | COA + settings tab |
| Company Detail / Settings | `GET /api/v1/companies/{id}/settings`, `GET /api/v1/companies/{id}/mapping-rules`, `PUT /api/v1/companies/{id}/mapping-rules/{rule_id}` | MVP, not placeholder |
| Templates | `GET /api/v1/templates`, `POST /api/v1/templates`, `GET /api/v1/templates/{id}`, `PUT /api/v1/templates/{id}`, `DELETE /api/v1/templates/{id}`, `POST /api/v1/templates/{id}/clone` | Customer tenant admin only |
| Users | `GET /api/v1/users`, `POST /api/v1/users`, `PUT /api/v1/users/{id}`, `POST /api/v1/users/{id}/reset-password` | Customer tenant admin only |
| Internal Cost Control | `GET /api/v1/system/cost/summary`, `GET /api/v1/system/cost/usage`, `PUT /api/v1/system/budget-limits/{id}` | Internal only |
| Internal Audit Log | `GET /api/v1/system/audit-logs`, `GET /api/v1/system/audit-logs/{id}` | Internal only |
| Internal Settings | `GET /api/v1/system/settings/model-routing`, `PUT /api/v1/system/settings/model-routing`, `GET /api/v1/system/settings/status` | Internal only |

---

## 3. Public Route Contract

### 3.1 Auth

#### `POST /api/v1/auth/login`

```json
{
  "username": "somchai",
  "password": "********"
}
```

```json
{
  "access_token": "jwt",
  "refresh_token": "jwt",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "usr_001",
    "display_name": "สมชาย กิตติคุณ",
    "role": "admin"
  }
}
```

#### `GET /api/v1/auth/me`

```json
{
  "id": "usr_001",
  "email": "somchai@bwc.co.th",
  "display_name": "สมชาย กิตติคุณ",
  "role": "admin",
  "company_ids": ["cmp_001", "cmp_002"]
}
```

### 3.2 Dashboard

#### `GET /api/v1/dashboard/summary`

Customer-facing dashboard payload must not expose provider/model/token or internal cost-routing fields.

```json
{
  "document_counts": {
    "today_total": 47,
    "pending_review": 23,
    "month_total": 312,
    "month_exported": 289
  },
  "page_credit_plan": {
    "plan_name": "Pro Premium",
    "included_page_credits": 20000,
    "used_page_credits": 7430,
    "remaining_page_credits": 12570,
    "cycle_label": "June 2026"
  },
  "usage_by_document_type": [
    { "document_type": "invoice", "pages": 4210 },
    { "document_type": "receipt", "pages": 1880 },
    { "document_type": "tax_invoice", "pages": 1340 }
  ]
}
```

#### `GET /api/v1/dashboard/activity`

```json
{
  "items": [
    {
      "id": "act_001",
      "occurred_at": "2026-06-20T14:52:00+07:00",
      "user_display_name": "สมชาย ก.",
      "action": "upload",
      "entity_type": "document",
      "entity_label": "INV-2605-012.pdf"
    }
  ]
}
```

### 3.3 Batch / Upload / Processing

#### `POST /api/v1/batches`

```json
{
  "company_id": "cmp_001",
  "batch_label": "Batch #2605-001"
}
```

```json
{
  "id": "bat_001",
  "company_id": "cmp_001",
  "status": "draft",
  "total_files": 0
}
```

#### `POST /api/v1/batches/{id}/documents`

Multipart upload. Response:

```json
{
  "batch_id": "bat_001",
  "accepted": [
    {
      "document_id": "doc_001",
      "filename": "INV-2605-001.pdf",
      "status": "uploaded"
    }
  ],
  "rejected": [
    {
      "filename": "encrypted.pdf",
      "code": "encrypted_pdf",
      "detail": "PDF is password-protected"
    }
  ]
}
```

#### `GET /api/v1/batches/{id}/processing`

```json
{
  "batch_id": "bat_001",
  "status": "processing",
  "summary": {
    "completed": 5,
    "running": 3,
    "failed": 1,
    "queued": 3
  },
  "documents": [
    {
      "document_id": "doc_001",
      "filename": "INV-2605-001.pdf",
      "status": "review_scan",
      "processing_progress": {
        "ocr": "done",
        "classify": "done",
        "extract": "done",
        "map_coa": "done",
        "stage_c": "skipped"
      }
    }
  ]
}
```

### 3.4 Review Scan

#### `GET /api/v1/documents/{id}`

```json
{
  "id": "doc_001",
  "batch_id": "bat_001",
  "filename": "INV-2605-001.pdf",
  "status": "review_scan",
  "scan_status": "pending",
  "preview_url": "https://signed-url",
  "fields": {
    "invoice_number": "INV-2605-001",
    "invoice_date": "2026-05-01",
    "seller_name": "บ. เมโทร อีเล็กทริค",
    "seller_tax_id": "0105560123456",
    "net_amount": 12345.8,
    "vat_amount": 864.21,
    "wht_amount": 370.37,
    "total_amount": 12839.64
  },
  "field_confidence": {
    "invoice_number": 0.97,
    "seller_name": 0.91
  },
  "flags": []
}
```

#### `POST /api/v1/documents/{id}/approve-scan`

```json
{
  "edited_fields": {
    "seller_name": "บริษัท เมโทร อีเล็กทริค จำกัด"
  }
}
```

```json
{
  "document_id": "doc_001",
  "status": "scan_approved",
  "scan_status": "approved"
}
```

#### `POST /api/v1/documents/{id}/flags`

```json
{
  "reason": "incorrect_amount",
  "comment": "ยอด VAT ไม่ตรงกับเอกสาร"
}
```

### 3.5 Review Mapping

#### `GET /api/v1/vouchers/{id}`

```json
{
  "id": "jv_001",
  "document_id": "doc_001",
  "status": "review",
  "is_balanced": true,
  "lines": [
    {
      "id": "jvl_001",
      "line_order": 1,
      "account_code": "05100",
      "account_name": "ค่าวัสดุสำนักงาน",
      "is_debit": true,
      "amount": 12345.8,
      "description": "Vendor payment"
    }
  ]
}
```

#### `POST /api/v1/vouchers/{id}/confirm`

```json
{
  "force_confirm": false
}
```

### 3.6 Export

#### `POST /api/v1/exports/preview`

```json
{
  "company_id": "cmp_001",
  "template_id": "tmpl_003",
  "document_ids": ["doc_001", "doc_002"],
  "file_format": "csv",
  "encoding": "utf-8",
  "delimiter": ",",
  "columns": [
    {
      "source_field": "voucher_date",
      "header_label": "Date",
      "data_type": "date",
      "format_pattern": "dd/mm/yyyy"
    }
  ]
}
```

```json
{
  "template_id": "tmpl_003",
  "row_count_estimate": 44,
  "warnings": [],
  "preview_rows": [
    {
      "Voucher_No": "PV-260504-001",
      "Date": "04/05/2569"
    }
  ]
}
```

#### `POST /api/v1/exports/jobs`

```json
{
  "company_id": "cmp_001",
  "template_id": "tmpl_003",
  "document_ids": ["doc_001", "doc_002"],
  "file_format": "csv",
  "encoding": "utf-8",
  "delimiter": ",",
  "columns": [
    {
      "source_field": "voucher_date",
      "header_label": "Date",
      "data_type": "date",
      "format_pattern": "dd/mm/yyyy"
    }
  ]
}
```

```json
{
  "job_id": "exp_001",
  "status": "pending",
  "total_documents": 2
}
```

#### `GET /api/v1/exports/jobs/{id}`

```json
{
  "job_id": "exp_001",
  "status": "completed",
  "file_id": "expf_001",
  "filename": "GL-20260620.csv",
  "download_count": 0
}
```

#### `GET /api/v1/exports/files/{id}/download`

```json
{
  "file_id": "expf_001",
  "filename": "GL-20260620.csv",
  "download_url": "https://signed-url"
}
```

### 3.7 Companies / COA / Mapping Rules

#### `GET /api/v1/companies/{id}/settings`

```json
{
  "company_id": "cmp_001",
  "settings": {
    "default_book_code": "PV",
    "default_currency": "THB",
    "date_format_preference": "dd/mm/yyyy",
    "default_template_id": "tmpl_003"
  }
}
```

#### `GET /api/v1/companies/{id}/mapping-rules`

```json
{
  "items": [
    {
      "id": "map_001",
      "vendor_name": "OfficeMart",
      "document_type": "invoice",
      "recommended_debit_code": "05100",
      "recommended_credit_code": "21000",
      "confirmed_count": 12
    }
  ]
}
```

### 3.8 Templates

Templates use `export_templates.columns` JSONB as the canonical formatting structure.

```json
{
  "id": "tmpl_003",
  "template_name": "GL เมโทร อีเล็กทริค",
  "file_format": "csv",
  "encoding": "utf-8",
  "delimiter": ",",
  "columns": [
    {
      "source_field": "account_code",
      "header_label": "Account_Code",
      "data_type": "text",
      "format_pattern": null,
      "transform": "pad_left:5:0"
    }
  ]
}
```

### 3.9 Users

#### `POST /api/v1/users/{id}/reset-password`

```json
{
  "reset_mode": "temporary_password"
}
```

```json
{
  "user_id": "usr_002",
  "status": "reset_queued",
  "temporary_password_masked": "T********9"
}
```

---

## 4. Internal System Routes

These routes are not shown in the customer admin sidebar and must be guarded by LedgerFlow internal system-admin role.

| Route | Purpose |
|------|---------|
| `GET /api/v1/system/cost/summary` | Internal LLM/provider cost summary |
| `GET /api/v1/system/cost/usage` | Detailed `api_usage` records |
| `PUT /api/v1/system/budget-limits/{id}` | Internal budget thresholds |
| `GET /api/v1/system/audit-logs` | Cross-tenant audit |
| `GET /api/v1/system/audit-logs/{id}` | Audit detail |
| `GET /api/v1/system/settings/model-routing` | Internal routing config |
| `PUT /api/v1/system/settings/model-routing` | Save routing policy |
| `GET /api/v1/system/settings/status` | Dependency health / system status |

---

## 5. Standard Error Contract

All MVP endpoints must return the same error envelope:

```json
{
  "error": "Human-readable summary",
  "code": "machine_code",
  "detail": "Actionable detail for UI"
}
```

Examples:
- `file_too_large`
- `encrypted_pdf`
- `ocr_failed`
- `mapping_unbalanced`
- `export_generation_failed`
- `forbidden_internal_route`

---

## 6. Mock-Only / Deferred

The following may remain mock-only or deferred in Phase II/1:
- Internal API key management UI actions under `/api/v1/system/settings/*`
- Customer-facing audit history screen separate from internal audit log
- PDPA policy editor UI
- Cross-tenant monitoring dashboard

---

## 7. Acceptance Checklist

- [x] Every MVP prototype screen has a mapped route set
- [x] Dashboard payload uses page-credit language only
- [x] Export uses preview-first contract
- [x] Company settings and mapping rules are explicit MVP routes
- [x] Internal routes are separated under `/api/v1/system/*`
- [x] No customer-facing payload leaks provider/model/token/internal cost fields

---

*Created: 2026-06-20*
*Blocks: TASK-801A, TASK-801B, TASK-803, TASK-1002, TASK-1202, TASK-1203, TASK-1204*
