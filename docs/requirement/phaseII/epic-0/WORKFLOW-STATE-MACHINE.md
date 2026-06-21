# Workflow State Machine — Frozen

> **TASK-002** | Epic 0 — UX Contract & Workflow Freeze
> **Frozen**: 2026-06-20
> **Status**: FROZEN — do not change without Epic 0 sign-off

---

## 1. Overview

Two parallel state machines govern the Phase II workflow:
1. **Batch** — aggregate lifecycle of an upload session
2. **Document** — per-document lifecycle through the pipeline

Both are driven by user actions and background processing. Role guards control who can trigger transitions.

```
User uploads files
      │
      ▼
┌──────────┐    Processing     ┌──────────────┐    User reviews    ┌────────────────┐
│  BATCH   │ ───────────────▶  │   DOCUMENTS  │ ──────────────────▶│  JOURNAL       │
│  created │    (Celery)       │   extracted   │   scan + mapping   │  VOUCHERS      │
└──────────┘                   └──────────────┘                    │  confirmed     │
                                                                   └───────┬────────┘
                                                                           │
                                                                    Export  │
                                                                           ▼
                                                                   ┌──────────────┐
                                                                   │  EXPORT JOB  │
                                                                   │  completed   │
                                                                   └──────────────┘
```

---

## 2. Batch State Machine

### States

| State | Description | Entry Trigger |
|-------|-------------|---------------|
| `draft` | Batch created, files being selected | User clicks "ต่อไป" on Upload |
| `uploading` | Files uploading to storage | Upload API called |
| `processing` | OCR/extraction pipeline running | All files uploaded successfully |
| `review_scan` | At least one document ready for scan review | First document finishes processing |
| `review_mapping` | Scan review complete, mapping review started | All documents scan-approved or flagged |
| `ready_export` | All mappings confirmed | All vouchers confirmed |
| `exported` | Export completed | Export job succeeds |
| `failed` | Critical failure (all docs failed) | All documents in failed state |
| `archived` | Batch archived (PDPA / manual) | Admin archives or retention policy triggers |

### Transition Diagram

```
draft ──▶ uploading ──▶ processing ──▶ review_scan ──▶ review_mapping ──▶ ready_export ──▶ exported
  │           │             │              │                │                                  │
  │           │             │              │                │                                  │
  ▼           ▼             ▼              ▼                ▼                                  ▼
(cancel)   (failed)     (failed)      (partially         (back to                         archived
                                      flagged →           review_scan
                                      stays here)         if mapping
                                                          rejected)
```

### Allowed Transitions

| From | To | Trigger | Role |
|------|----|---------|------|
| `draft` | `uploading` | Files selected, upload begins | Admin, Staff |
| `uploading` | `processing` | All files uploaded OK | System |
| `uploading` | `failed` | Upload error (storage unavailable) | System |
| `processing` | `review_scan` | ≥1 document reaches `extracted` | System |
| `processing` | `failed` | All documents failed processing | System |
| `review_scan` | `review_mapping` | All docs approved or flagged-resolved | Admin, Staff |
| `review_scan` | `review_scan` | Partial approvals (stays in state) | Admin, Staff |
| `review_mapping` | `review_scan` | User goes back to fix scan data | Admin, Staff |
| `review_mapping` | `ready_export` | All vouchers confirmed | Admin, Staff |
| `ready_export` | `exported` | Export job completes | Admin, Staff |
| `exported` | `archived` | Manual archive or PDPA retention | Admin |
| Any | `archived` | Admin manual archive | Admin |

### Batch Status Computation

Batch status is **derived** from document statuses (not independently set):
- `processing` = any document still processing
- `review_scan` = all done processing, ≥1 not scan-approved
- `review_mapping` = all scan-approved, ≥1 voucher not confirmed
- `ready_export` = all vouchers confirmed
- `exported` = export job exists and succeeded

**Implementation note**: Store `batch.status` as a materialized field but recompute on state changes.

---

## 3. Document State Machine

### States

| State | Description | Entry Trigger |
|-------|-------------|---------------|
| `uploaded` | File received, stored in object storage | Upload API |
| `queued` | In Celery queue, waiting for worker | Batch processing starts |
| `ocr_running` | PaddleOCR/Tesseract active | Worker picks up task |
| `classifying` | Document type classification | OCR complete |
| `extracting` | Field extraction (regex + reconciliation) | Classification complete |
| `mapping_coa` | Journal routing (rule engine + COA lookup) | Extraction complete |
| `stage_c_repair` | LLM repair running (if budget allows) | Mapping complete, confidence < threshold |
| `extracted` | All pipeline stages complete | Pipeline finishes |
| `review_scan` | Ready for human scan review | Processing complete |
| `scan_approved` | Scan data approved by reviewer | User approves |
| `scan_flagged` | Flagged for issues | User flags |
| `review_mapping` | Ready for mapping review | Scan approved |
| `mapping_confirmed` | Dr/Cr mapping confirmed | User confirms |
| `exported` | Included in an export job | Export completes |
| `failed` | Processing error (unrecoverable) | Pipeline error |

### High-Level vs Processing-Detail States

For simplicity, `Document.status` uses **high-level states** only:

| `Document.status` | Values |
|-------------------|--------|
| High-level | `uploaded`, `processing`, `extracted`, `review_scan`, `scan_approved`, `scan_flagged`, `review_mapping`, `mapping_confirmed`, `exported`, `failed` |

Processing sub-stages are tracked in `Document.processing_progress` (JSONB):

```json
{
  "ocr": "done",          // "pending" | "running" | "done" | "failed" | "skipped"
  "classify": "done",
  "extract": "running",
  "map_coa": "pending",
  "stage_c": "pending"
}
```

### Transition Diagram

```
uploaded ──▶ processing ──▶ extracted ──▶ review_scan ──┬──▶ scan_approved ──▶ review_mapping ──▶ mapping_confirmed ──▶ exported
                │                                       │
                │                                       └──▶ scan_flagged ──▶ (resolve) ──▶ scan_approved
                │
                └──▶ failed ──▶ (retry) ──▶ processing
```

### Allowed Transitions

| From | To | Trigger | Role |
|------|----|---------|------|
| `uploaded` | `processing` | Batch processing starts | System |
| `processing` | `extracted` | Pipeline completes all stages | System |
| `processing` | `failed` | Unrecoverable error | System |
| `extracted` | `review_scan` | Auto-transition after extraction | System |
| `review_scan` | `scan_approved` | User approves scan data | Admin, Staff |
| `review_scan` | `scan_flagged` | User flags document | Admin, Staff |
| `scan_flagged` | `review_scan` | Flag resolved, re-review needed | Admin, Staff |
| `scan_approved` | `review_mapping` | Auto-transition | System |
| `scan_approved` | `review_scan` | User wants to re-review scan data | Admin, Staff |
| `review_mapping` | `mapping_confirmed` | User confirms Dr/Cr mapping | Admin, Staff |
| `review_mapping` | `review_scan` | User goes back to fix scan data | Admin, Staff |
| `mapping_confirmed` | `exported` | Included in export job | Admin, Staff |
| `mapping_confirmed` | `review_mapping` | User reopens mapping | Admin |
| `failed` | `processing` | Retry processing | Admin |
| `exported` | `mapping_confirmed` | Undo export (re-export needed) | Admin |

---

## 4. Journal Voucher States

| State | Description | Trigger |
|-------|-------------|---------|
| `draft` | Auto-generated by pipeline | System (pipeline) |
| `review` | Ready for mapping review | Document reaches `review_mapping` |
| `confirmed` | User confirmed Dr/Cr mapping | User confirms |
| `exported` | Included in export | Export job |

### Transitions

| From | To | Trigger | Role |
|------|----|---------|------|
| `draft` | `review` | Document scan approved | System |
| `review` | `confirmed` | User confirms mapping | Admin, Staff |
| `review` | `draft` | User edits account codes (re-enters draft) | Admin, Staff |
| `confirmed` | `exported` | Export job includes this voucher | System |
| `confirmed` | `review` | User reopens for changes | Admin |

---

## 5. Export Job States

| State | Description | Trigger |
|-------|-------------|---------|
| `pending` | Job created, generation starting | User clicks Download |
| `generating` | File being generated | System |
| `completed` | File generated and stored | System |
| `failed` | Generation error | System |
| `downloaded` | File downloaded by user | User downloads |

---

## 6. Document Flag States

| State | Description | Trigger |
|-------|-------------|---------|
| `open` | Flag raised, needs attention | User flags document |
| `resolved` | Issue resolved | Reviewer resolves |
| `dismissed` | Flag dismissed (false alarm) | Admin dismisses |

---

## 7. Role Guards Summary

`Customer Admin` means the tenant/company admin role used by the customer team. `LedgerFlow System Admin` means the internal operations role used by our team.

| Action | Customer Admin | Customer Staff | LedgerFlow System Admin |
|--------|----------------|----------------|-------------------------|
| Upload documents | Yes | Yes (assigned companies only) | No |
| Start processing | Yes | Yes | No |
| Approve scan | Yes | Yes | No |
| Flag document | Yes | Yes | No |
| Resolve flag | Yes | Yes | No |
| Confirm mapping | Yes | Yes | No |
| Export | Yes | Yes | No |
| Retry failed document | Yes | No | No |
| Archive batch | Yes | No | No |
| Reopen confirmed mapping | Yes | No | No |
| Manage companies | Yes | No | Internal support only |
| Manage users | Yes | No | Internal support only |
| Manage templates | Yes | No | Internal support only |
| View cost control | No | No | Yes |
| View cross-tenant audit log | No | No | Yes |
| Change system settings | No | No | Yes |

---

## 8. Error / Edge States

| Scenario | Document Status | Recovery |
|----------|----------------|----------|
| OCR fails (encrypted PDF) | `failed` | Admin retries or skips |
| Extraction fails (no fields found) | `failed` | Admin retries with different params |
| Stage C budget exceeded | `extracted` (repair skipped) | Proceeds without LLM repair |
| Unbalanced voucher | `review_mapping` | User edits account codes until balanced |
| All docs in batch fail | Batch `failed` | Admin retries individual docs |
| Storage unavailable | Upload fails (batch `failed`) | Retry when storage recovers |
| Duplicate document (same SHA256) | Upload warns | User decides to skip or re-upload |

---

## 9. State Names Cross-Reference

These state names MUST be used consistently across DB models, API responses, and frontend:

```python
# Document status enum
class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    REVIEW_SCAN = "review_scan"
    SCAN_APPROVED = "scan_approved"
    SCAN_FLAGGED = "scan_flagged"
    REVIEW_MAPPING = "review_mapping"
    MAPPING_CONFIRMED = "mapping_confirmed"
    EXPORTED = "exported"
    FAILED = "failed"

# Batch status enum
class BatchStatus(str, Enum):
    DRAFT = "draft"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    REVIEW_SCAN = "review_scan"
    REVIEW_MAPPING = "review_mapping"
    READY_EXPORT = "ready_export"
    EXPORTED = "exported"
    FAILED = "failed"
    ARCHIVED = "archived"

# Voucher status enum
class VoucherStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    CONFIRMED = "confirmed"
    EXPORTED = "exported"

# Export job status enum
class ExportJobStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    DOWNLOADED = "downloaded"

# Flag status enum
class FlagStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
```

---

*Frozen: 2026-06-20*
*Referenced by: TASK-003 (DB Impact Contract), TASK-801A (schema), TASK-801B (DB integration)*
