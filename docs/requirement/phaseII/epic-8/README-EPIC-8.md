# Epic 8 — Platform Foundation

**Goal**: เปิดใช้ infrastructure ที่ติดตั้งไว้แล้วใน requirements.txt / docker-compose แต่ยังไม่ได้ใช้จริง — PostgreSQL, JWT Auth, MinIO S3, Celery workers

## Documentation

- **[EPIC-8-TASKS-DETAIL.md](EPIC-8-TASKS-DETAIL.md)** — full design for all tasks with ACs, schemas, governance fields

## At a glance

| Aspect | Details |
|--------|---------|
| Lead | Backend Dev |
| Duration | 2 weeks (W1-W2) |
| Status | Partial |
| Critical path | **Yes** — blocks Epic 10, 11, 12 (ทุก epic ต้องอ่าน/เขียน DB) |
| Week | W1-W2 |

## Task overview

| Task | Title | Complexity | Status | Pain points closed |
|------|-------|-----------|--------|-------------------|
| TASK-801A | SQLAlchemy models + Alembic schema slice | L | New | PP-2, PP-3, PP-5 |
| TASK-801B | Pipeline to DB integration | L | New | PP-2, PP-3, PP-4, PP-5 |
| TASK-802 | Data migration script | M | New | PP-2, PP-3, PP-5 |
| TASK-804 | MinIO S3 storage integration | M | New | PP-2, PP-3, PP-4, PP-5 |
| TASK-805 | Celery + Redis workers | M | Done (W2) | PP-2, PP-3, PP-4, PP-5 |
| TASK-803 | JWT Authentication + Login API | M | New | PP-2, PP-3, PP-5, PP-8 |
| TASK-806 | Health check endpoint + startup validation | S | New | PP-2, PP-3, PP-5, PP-16 |
| TASK-807 | PDPA auto-cleanup | S | New | PP-2, PP-3, PP-5, PP-8 |
| TASK-808 | Edge case handling | S | New | PP-2, PP-3, PP-5, PP-10 |

## Dependencies

- **Upstream**: None (this is the foundation layer)
- **Downstream**: Epic 10 (Template Engine), Epic 11 (Purchase Tax), Epic 12 (Admin UI), Epic 13 (Infrastructure CI/CD)

## Execution order

```text
W1 Day 1-2:  TASK-801A — Schema slice first (models, migrations, enums, tests)
W1 Day 2-3:  TASK-802 — Data migration (seed companies, templates, admin user)
W1 Day 3-4:  TASK-804 — MinIO S3 storage (upload/download/presigned URL)
W1 Day 4-5:  TASK-801B — Pipeline to DB dual-write on top of frozen schema
W2 Day 1:    TASK-808 — Edge case handling (small, hardens upload path)
W2 Day 2-3:  TASK-805 — Celery + Redis workers (wrap pipeline as background task)
W2 Day 3-4:  TASK-803 — JWT Auth (security-sensitive, needs careful review)
W2 Day 4:    TASK-806 — Health check endpoint (small, validates all services)
W2 Day 5:    TASK-807 — PDPA auto-cleanup (depends on Celery Beat from TASK-805)
```

## Definition of Done

1. `TASK-801A` lands workflow/export/page-credit schema slice with migration chain `001 -> 008`
2. `TASK-801B` writes extraction results to PostgreSQL while old file cache still works during transition
3. companies.json data migrated to DB, master templates seeded, admin user created
4. JWT login returns token, protected endpoints reject without token, refresh works
5. Document uploads stored in MinIO S3 with proper path structure, presigned URLs work
6. Pipeline runs as Celery background task, status is trackable via API
7. Health check endpoint returns connectivity status for DB, Redis, MinIO
8. PDPA auto-cleanup deletes expired documents from MinIO + marks DB records as purged
9. Oversized files (>20MB) rejected with 413, bad images set `ocr_failed` status, encrypted PDFs rejected with clear message
10. Export/runtime flows remain compatible with preview-first export contract
11. All ACs pass with pytest tests

## Discussion Prompts

1. **Dual-mode transition period**: `TASK-801B` writes to both file + DB after `TASK-801A` schema lands. When do we cut over to DB-only reads? W3 (when Template Engine starts) or W5 (when Admin UI needs it)?
2. **JWT secret rotation**: TASK-803 uses a single JWT secret. Do we need key rotation support for go-live, or is that post-go-live hardening?
3. **MinIO bucket structure**: TASK-804 uses `{tenant_id}/{company_id}/{year}/{month}/{sha256}.{ext}`. Should we add `{document_type}` to the path for easier browsing?
4. **Celery worker scaling**: TASK-805 starts with 1 worker. At what document volume do we add worker replicas? (design capacity is 10K-20K docs/month)
5. **PDPA retention defaults**: TASK-807 needs default retention_days. Recommend 90 days for documents, 365 days for audit logs. Confirm with client?
6. **File size limit**: TASK-808 sets 20MB. Is this sufficient for multi-page scanned PDFs at 300 DPI?

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
