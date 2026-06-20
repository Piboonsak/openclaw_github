# Epic 8 — Platform Foundation: Tasks Detail

> **Epic Goal**: เปิดใช้ infrastructure ที่ติดตั้งไว้แล้วใน requirements.txt / docker-compose แต่ยังไม่ได้ใช้จริง
> **Duration**: W1-W2 | **Critical Path**: Yes
> **Baseline Date**: 2026-06-15

---

## TASK-801: Pipeline to DB Integration

**Owner**: Backend Dev
**Risk**: MEDIUM
**Duration**: ~3 days
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-4 (no mock integration), PP-5 (evidence required)

### Purpose

PoC pipeline writes extraction/journal results to file cache (JSON on disk). Phase II ต้องบันทึกลง PostgreSQL เพื่อให้ query, filter, audit ได้จริง. ทำ dual-mode ระหว่าง transition เพื่อไม่ทำลาย PoC workflow ที่ทำงานอยู่.

### What exists today

- Pipeline orchestrator (`src/backend/pipeline/orchestrator.py`) ทำ OCR -> extraction -> journal mapping -> เขียน file cache
- ORM models 15 tables พร้อมแล้วใน `src/backend/db/models.py`
- Alembic migration infrastructure + `001_initial_schema.py`
- DB session factory (`src/backend/db/session.py`)
- `config/settings.py` มี DATABASE_URL แล้ว
- Endpoints ใน `src/backend/app/endpoints.py` return JSON จาก file cache

### What to build

1. **Pipeline orchestrator** — หลัง extraction สำเร็จ, สร้าง Document, Extraction, JournalVoucher, JournalLine records ใน DB
2. **Dual-mode writing** — เขียนทั้ง file cache + DB พร้อมกัน (ไม่ลบ file cache ระหว่าง transition)
3. **Endpoints update** — endpoints ที่ return extraction results ให้อ่านจาก DB เป็น primary, fallback file cache
4. **Status tracking** — document status progression: `uploaded -> processing -> review_scan -> review_mapping -> confirmed -> exported`
5. **Transaction safety** — ใช้ DB transaction เพื่อให้ extraction + journal records commit พร้อมกัน

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/pipeline/orchestrator.py` | เพิ่ม DB write หลัง extraction/journal mapping สำเร็จ |
| Modify | `src/backend/app/endpoints.py` | อ่าน results จาก DB (primary), fallback file cache |
| Modify | `src/backend/db/session.py` | เพิ่ม get_db() dependency สำหรับ FastAPI |
| Create | `src/backend/db/crud.py` | CRUD functions สำหรับ Document, Extraction, JournalVoucher, JournalLine |
| Create | `tests/db/test_crud.py` | Unit tests สำหรับ CRUD operations |
| Create | `tests/pipeline/test_db_integration.py` | Integration test: pipeline run -> verify DB records |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_801_1 | Extraction results (all fields) saved in `extractions` table with correct `document_id` FK | `test_extraction_saved_to_db` |
| ac_801_2 | JournalVoucher + JournalLine records saved with correct FK chain | `test_journal_records_saved_to_db` |
| ac_801_3 | Document status updated to `review_scan` after successful extraction | `test_document_status_progression` |
| ac_801_4 | File cache still written during transition (dual-mode) | `test_file_cache_still_works` |
| ac_801_5 | API endpoints return data from DB when available, fallback to file cache | `test_endpoint_reads_from_db` |
| ac_801_6 | DB transaction rollback on extraction failure (no partial records) | `test_transaction_rollback_on_failure` |

### Governance fields

```json
{
  "task_id": "TASK-801",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/pipeline/**", "src/backend/app/**", "src/backend/db/**", "tests/**"],
  "forbidden_scope": [".env*", "config/secrets/**", "src/frontend/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-802: Data Migration Script

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-5 (evidence required)

### Purpose

PoC ใช้ `companies.json` เป็น flat file. Phase II ต้องย้ายข้อมูลนี้เข้า DB + seed master export templates (Express GL, Purchase Tax) + สร้าง admin user คนแรก เพื่อให้ระบบพร้อมใช้หลัง deploy.

### What exists today

- `companies.json` file มีข้อมูลบริษัทลูกค้า (name, tax_id, branch, address)
- ORM models สำหรับ Company, ExportTemplate, User พร้อมแล้ว
- Alembic infrastructure + `001_initial_schema.py` (schema only, no data)
- Export templates hardcoded ใน `export_service.py`

### What to build

1. **Seed script** (`scripts/seed_data.py`) — อ่าน companies.json -> insert companies + default tenant
2. **Master templates** — seed Express GL 8-col + Purchase Tax 12-col templates (columns JSONB)
3. **Admin user** — seed first admin user (password from env var, hashed)
4. **Alembic data migration** — `002_seed_data.py` ทำ seed ผ่าน Alembic เพื่อ track version
5. **Idempotent** — run ซ้ำได้ไม่ error (skip existing records)

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `scripts/seed_data.py` | Standalone seed script (can run outside Alembic) |
| Create | `alembic/versions/002_seed_data.py` | Alembic data migration |
| Modify | `src/backend/db/models.py` | เพิ่ม default values ถ้ายังไม่มี |
| Create | `tests/db/test_seed_data.py` | Test seed script idempotency + data correctness |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_802_1 | All companies from `companies.json` present in DB `companies` table | `test_companies_migrated` |
| ac_802_2 | Default tenant record created | `test_default_tenant_exists` |
| ac_802_3 | Express GL master template seeded (8 columns, is_master=True) | `test_gl_template_seeded` |
| ac_802_4 | Purchase Tax master template seeded (12 columns, is_master=True) | `test_tax_template_seeded` |
| ac_802_5 | Admin user created with hashed password (not plaintext) | `test_admin_user_created` |
| ac_802_6 | Running seed script twice does not create duplicates | `test_seed_idempotent` |

### Governance fields

```json
{
  "task_id": "TASK-802",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["scripts/**", "alembic/**", "src/backend/db/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "stop"
}
```

---

## TASK-803: JWT Authentication + Login API

**Owner**: Backend Dev
**Risk**: HIGH (auth is security-sensitive)
**Duration**: ~2 days
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-5 (evidence required), PP-8 (scope locked)

### Purpose

PoC ไม่มี auth เลย — ทุกคนเข้าถึงได้. Phase II ต้องมี login / token-based auth เพื่อรองรับ multi-user + RBAC. JWT เป็น standard สำหรับ stateless API auth ที่ scale ได้.

### What exists today

- ไม่มี auth code ใดๆ ใน codebase
- FastAPI endpoints ไม่มี `Depends()` สำหรับ auth
- User model มีแล้วใน `src/backend/db/models.py` (password_hash field)
- Admin user จะถูก seed โดย TASK-802

### What to build

1. **JWT token logic** — issue (access + refresh), verify, decode with expiration
2. **Password hashing** — bcrypt via `passlib`
3. **Login endpoint** — `POST /api/v1/auth/login` (username + password -> JWT)
4. **Me endpoint** — `GET /api/v1/auth/me` (token -> user profile)
5. **Refresh endpoint** — `POST /api/v1/auth/refresh` (refresh token -> new access token)
6. **FastAPI middleware** — `Depends(get_current_user)` สำหรับ protected endpoints
7. **Token configuration** — access token 30 min, refresh token 7 days (configurable via settings)

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/auth/__init__.py` | Package init |
| Create | `src/backend/auth/auth.py` | JWT token issue/verify/refresh, password hashing |
| Create | `src/backend/auth/dependencies.py` | `get_current_user`, `get_current_active_user`, `require_admin` |
| Create | `src/backend/auth/router.py` | Login, me, refresh endpoints |
| Modify | `src/backend/app/endpoints.py` | เพิ่ม `Depends(get_current_user)` บน protected endpoints |
| Modify | `config/settings.py` | JWT_SECRET, JWT_ACCESS_EXPIRE_MINUTES, JWT_REFRESH_EXPIRE_DAYS |
| Create | `tests/auth/test_auth.py` | Unit tests: token issue/verify/expire/refresh |
| Create | `tests/auth/test_endpoints.py` | Integration tests: login flow, protected endpoint rejection |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_803_1 | `POST /api/v1/auth/login` with valid credentials returns `access_token` + `refresh_token` | `test_login_returns_tokens` |
| ac_803_2 | `POST /api/v1/auth/login` with invalid credentials returns 401 | `test_login_invalid_credentials` |
| ac_803_3 | `GET /api/v1/auth/me` with valid token returns user profile | `test_me_with_valid_token` |
| ac_803_4 | Protected endpoints return 401 without token | `test_protected_endpoint_rejects_no_token` |
| ac_803_5 | Protected endpoints return 401 with expired token | `test_protected_endpoint_rejects_expired_token` |
| ac_803_6 | `POST /api/v1/auth/refresh` returns new access token | `test_refresh_token_works` |
| ac_803_7 | Password stored as bcrypt hash, not plaintext | `test_password_is_hashed` |

### Governance fields

```json
{
  "task_id": "TASK-803",
  "risk_tier": "HIGH",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/auth/**", "tests/auth/**", "src/backend/app/**", "config/**"],
  "forbidden_scope": [".env*", "src/backend/ml/**", "src/backend/pipeline/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-804: MinIO S3 Storage Integration

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-4 (no mock integration), PP-5 (evidence required)

### Purpose

PoC เก็บไฟล์บน local disk ของ VPS — ไม่มี backup, ไม่มี path isolation. Phase II ใช้ MinIO (self-hosted S3-compatible) ที่อยู่ใน docker-compose อยู่แล้ว เพื่อ object storage ที่ scalable + backupable.

### What exists today

- Docker Compose มี MinIO container พร้อม (port 9000/9001)
- Documents saved to local disk via `save_upload()` in endpoints
- ไม่มี S3 client code ใดๆ

### What to build

1. **S3 client wrapper** — upload, download, presigned URL, delete ผ่าน boto3
2. **Path structure** — `{tenant_id}/{company_id}/{year}/{month}/{sha256}.{ext}`
3. **Upload integration** — เปลี่ยน document upload จาก disk save เป็น MinIO upload
4. **Download / preview** — presigned URL สำหรับ frontend preview (expire 1 hour)
5. **Local fallback** — ถ้า MinIO ไม่ available ให้ fallback กลับ local disk + log warning
6. **Bucket auto-create** — สร้าง bucket อัตโนมัติตอน startup ถ้ายังไม่มี

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/storage/__init__.py` | Package init |
| Create | `src/backend/storage/s3.py` | MinIO S3 client (boto3): upload, download, presigned_url, delete |
| Create | `src/backend/storage/local.py` | Local disk fallback (same interface as s3.py) |
| Modify | `src/backend/app/endpoints.py` | ใช้ storage client แทน direct disk save |
| Modify | `config/settings.py` | MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, MINIO_BUCKET |
| Create | `tests/storage/test_s3.py` | Unit tests with mocked MinIO client |
| Create | `tests/storage/test_local.py` | Unit tests for local fallback |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_804_1 | Document upload stores file in MinIO bucket with correct path structure | `test_upload_to_minio` |
| ac_804_2 | Download retrieves correct file content from MinIO | `test_download_from_minio` |
| ac_804_3 | Presigned URL generated and accessible (1 hour expiry) | `test_presigned_url_works` |
| ac_804_4 | Delete removes file from MinIO bucket | `test_delete_from_minio` |
| ac_804_5 | Fallback to local disk works when MinIO is unavailable | `test_local_fallback` |
| ac_804_6 | Bucket auto-created on startup if not exists | `test_bucket_auto_create` |

### Governance fields

```json
{
  "task_id": "TASK-804",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/storage/**", "src/backend/app/**", "config/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "stop"
}
```

---

## TASK-805: Celery + Redis Workers

**Owner**: Backend Dev
**Risk**: MEDIUM
**Duration**: ~2 days
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-4 (no mock integration), PP-5 (evidence required)

### Purpose

PoC ใช้ `ThreadPoolExecutor` สำหรับ background processing — task สูญหายเมื่อ restart, ไม่มี retry, ไม่มี status tracking. Phase II ใช้ Celery + Redis เพื่อ persistent task queue ที่ reliable + monitorable.

### What exists today

- Pipeline runs synchronously or via `ThreadPoolExecutor` (in-process, no persistence)
- Redis container ใน docker-compose (port 6379)
- `requirements.txt` มี celery อยู่แล้ว
- Document status field ใน DB model (`status` column)

### What to build

1. **Celery app** — configuration with Redis broker + Redis result backend
2. **Pipeline task** — wrap OCR/extraction pipeline as Celery task with retry logic
3. **Status tracking** — document status progression (`uploaded -> processing -> review_scan`) via DB update
4. **Task result** — store task_id ใน document record เพื่อ query status
5. **Docker services** — เพิ่ม `celery-worker` + `celery-beat` services ใน docker-compose
6. **Timeout handling** — soft/hard time limits เพื่อป้องกัน stuck tasks

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/workers/__init__.py` | Package init |
| Create | `src/backend/workers/celery_app.py` | Celery app config: broker, backend, serializer, time limits |
| Create | `src/backend/workers/tasks.py` | `process_document` task: OCR -> extract -> journal -> DB write |
| Modify | `src/backend/app/endpoints.py` | Upload endpoint dispatches Celery task instead of ThreadPoolExecutor |
| Modify | `src/backend/pipeline/orchestrator.py` | Refactor for Celery-callable interface |
| Modify | `docker/docker-compose.dev.yml` | เพิ่ม celery-worker, celery-beat services |
| Create | `tests/workers/test_tasks.py` | Unit tests for task dispatch + status tracking |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_805_1 | Pipeline runs as Celery background task (not in-process) | `test_pipeline_runs_as_celery_task` |
| ac_805_2 | Document status updated to `processing` when task starts | `test_status_processing_on_start` |
| ac_805_3 | Document status updated to `review_scan` when task completes | `test_status_review_scan_on_complete` |
| ac_805_4 | Task status queryable via API (pending/started/success/failure) | `test_task_status_queryable` |
| ac_805_5 | Task does not timeout on documents up to 20MB (soft limit 120s, hard limit 180s) | `test_task_timeout_config` |
| ac_805_6 | Failed task sets document status to error with error message | `test_task_failure_sets_error_status` |

### Governance fields

```json
{
  "task_id": "TASK-805",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/workers/**", "src/backend/pipeline/**", "docker/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-806: Health Check Endpoint + Startup Validation

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~1 day
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-5 (evidence required), PP-16 (deploy succeeded but unhealthy)

### Purpose

ไม่มีวิธีตรวจสอบว่า services ทั้งหมดทำงานหลัง deploy. Health endpoint ให้ CI/CD pipeline, monitoring (Uptime Kuma), และ load balancer ตรวจสอบได้. Startup validation ป้องกัน accept requests เมื่อ dependencies ยังไม่พร้อม.

### What exists today

- ไม่มี health check endpoint
- ไม่มี startup validation
- CI/CD ไม่มี post-deploy health verification

### What to build

1. **Health endpoint** — `GET /api/health` returns JSON with status of DB, Redis, MinIO
2. **Liveness** — `GET /api/health/live` returns 200 (just confirms process is running)
3. **Readiness** — `GET /api/health/ready` returns 200 only when all dependencies are connected
4. **Startup validation** — on FastAPI startup, check DB + Redis + MinIO connectivity, log errors but don't crash (graceful degradation)
5. **Connection pool** — configure SQLAlchemy pool size + overflow

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/app/endpoints.py` | เพิ่ม health, liveness, readiness endpoints |
| Modify | `config/settings.py` | DB pool size, Redis timeout, MinIO timeout settings |
| Modify | `src/backend/db/session.py` | Connection pool configuration |
| Create | `tests/app/test_health.py` | Tests for health endpoint (mock dependencies up/down) |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_806_1 | `GET /api/health` returns JSON with DB/Redis/MinIO status | `test_health_endpoint_returns_status` |
| ac_806_2 | Health endpoint returns 200 when all services up, 503 when any service down | `test_health_status_codes` |
| ac_806_3 | `GET /api/health/ready` returns 503 when DB is disconnected | `test_readiness_fails_without_db` |
| ac_806_4 | Startup logs warnings for unavailable services but does not crash | `test_startup_graceful_degradation` |
| ac_806_5 | Response includes version info and uptime | `test_health_includes_metadata` |

### Governance fields

```json
{
  "task_id": "TASK-806",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/app/**", "config/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "stop"
}
```

---

## TASK-807: PDPA Auto-Cleanup

**Owner**: Backend Dev
**Risk**: MEDIUM (data deletion is irreversible)
**Duration**: ~1 day
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-5 (evidence required), PP-8 (scope locked)

### Purpose

PDPA (Thailand Personal Data Protection Act) กำหนดให้ลบข้อมูลส่วนบุคคลเมื่อเกินระยะเวลาจัดเก็บ. ระบบต้อง auto-cleanup เอกสารและ DB records ที่เกิน retention period โดยอัตโนมัติ เพื่อ compliance + ลด storage cost.

### What exists today

- ไม่มี cleanup mechanism ใดๆ
- `data_retention_policies` table มีแล้วใน ORM model
- Celery Beat จะพร้อมใช้จาก TASK-805

### What to build

1. **Celery Beat cron job** — ทำงานทุกวัน 02:00 UTC (09:00 ICT)
2. **Retention policy query** — อ่าน `data_retention_policies` table เพื่อหา entity types + retention_days
3. **Delete from MinIO** — ลบไฟล์เอกสารที่เกิน retention
4. **Mark DB records** — set `status = 'purged'` + null sensitive fields (ไม่ลบ record เพื่อ audit trail)
5. **Configurable** — retention_days per entity type (documents: 90 days default, audit_logs: 365 days default)
6. **Dry-run mode** — log what would be deleted without actually deleting (for testing)
7. **Audit log** — log every cleanup action to `audit_logs` table

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/workers/cleanup.py` | PDPA cleanup task: query policies, delete MinIO files, mark DB records |
| Modify | `src/backend/workers/celery_app.py` | Register cleanup task in Celery Beat schedule |
| Modify | `src/backend/storage/s3.py` | เพิ่ม `delete_by_prefix()` for batch deletion |
| Create | `tests/workers/test_cleanup.py` | Tests: cleanup deletes correct files, marks records, respects retention |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_807_1 | Documents older than retention_days deleted from MinIO | `test_expired_documents_deleted` |
| ac_807_2 | DB records for deleted documents marked as `purged` (not hard-deleted) | `test_records_marked_purged` |
| ac_807_3 | Sensitive fields (file content, extraction JSON) nulled on purge | `test_sensitive_fields_nulled` |
| ac_807_4 | Retention period configurable per entity type via `data_retention_policies` | `test_retention_configurable` |
| ac_807_5 | Dry-run mode logs actions without deleting | `test_dry_run_mode` |
| ac_807_6 | Cleanup action logged to `audit_logs` | `test_cleanup_audit_logged` |

### Governance fields

```json
{
  "task_id": "TASK-807",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/workers/**", "src/backend/storage/**", "src/backend/db/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-808: Edge Case Handling

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~1 day
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-5 (evidence required), PP-10 (wrong-fix retry loop)

### Purpose

PoC crashes หรือ hangs on edge cases: oversized files, unreadable images, encrypted PDFs. Phase II ต้อง handle gracefully ด้วย clear error messages เพื่อลด support tickets + prevent pipeline stuck.

### What exists today

- No file size validation (any size accepted)
- Unreadable images cause OCR to crash or return garbage
- Encrypted PDFs cause PyPDF2/pdfplumber to throw unhandled exceptions
- No structured error responses for these cases

### What to build

1. **File size limit** — reject files > 20MB at upload with 413 status + clear message
2. **Unreadable image** — catch OCR failure, set document status to `ocr_failed` (not crash), store error message
3. **Encrypted PDF** — detect password-protected PDFs before OCR, reject with message "PDF is password-protected, please provide an unprotected version"
4. **Unsupported format** — reject non-image/non-PDF files with 415 status
5. **Structured errors** — consistent error response format: `{ "error": "...", "code": "...", "detail": "..." }`

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/app/endpoints.py` | File size check, file type check at upload |
| Modify | `src/backend/pipeline/orchestrator.py` | Catch OCR failures, set `ocr_failed` status |
| Modify | `src/backend/ml/ocr.py` | Encrypted PDF detection, unreadable image handling |
| Create | `src/backend/app/error_handlers.py` | Structured error response format + exception handlers |
| Create | `tests/app/test_edge_cases.py` | Tests for all edge cases |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_808_1 | File > 20MB rejected with HTTP 413 and message "File size exceeds 20MB limit" | `test_oversized_file_rejected` |
| ac_808_2 | Unreadable image sets document status to `ocr_failed` with error message (no crash) | `test_unreadable_image_sets_ocr_failed` |
| ac_808_3 | Encrypted PDF rejected with message "PDF is password-protected" | `test_encrypted_pdf_rejected` |
| ac_808_4 | Non-image/non-PDF file rejected with HTTP 415 | `test_unsupported_format_rejected` |
| ac_808_5 | All error responses follow structured format: `{ error, code, detail }` | `test_error_response_format` |

### Governance fields

```json
{
  "task_id": "TASK-808",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/app/**", "src/backend/pipeline/**", "src/backend/ml/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "stop"
}
```

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
*Master Plan: [PHASE-II-MASTER-PLAN.md](../PHASE-II-MASTER-PLAN.md)*
