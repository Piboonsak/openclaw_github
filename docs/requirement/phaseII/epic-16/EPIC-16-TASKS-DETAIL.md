# Epic 16 — Full Dashboard + Monitoring: Tasks Detail

> **Phase**: II/2 (Post-Go-Live, CR-based)
> **Extends**: TASK-1202 MVP Dashboard (Epic 12)
> **Created**: 2026-06-15

---

## TASK-1601: Full KPI Dashboard

**Owner**: Full-stack Dev
**Risk**: LOW
**Duration**: ~3 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-17

### Purpose

Extend MVP Dashboard (TASK-1202) เป็น full KPI dashboard — accuracy trends over time, throughput analytics, cost analytics. ให้ admin เห็นภาพรวมของ system performance + business metrics.

### What exists today

- MVP Dashboard (TASK-1202): document count, processing status, recent activity
- DB models: documents, extraction_results, audit_logs
- LLM usage likely logged (model, tokens) — need to verify table structure
- Frontend: ux-ui-prototype.html with dashboard tab

### What to build

1. **Accuracy trends**:
   - Per company: avg accuracy score over time (weekly/monthly)
   - Per document type: accuracy by doc_type (invoice, receipt, tax invoice)
   - Charts: line chart with trend, comparison across companies
2. **Throughput analytics**:
   - Documents processed per day/week/month
   - Processing time trends (avg, p95 per period)
   - Queue depth (pending documents)
3. **Cost analytics**:
   - LLM spend by company, by model, by time period
   - Token usage breakdown (input vs output)
   - Cost per document trend
4. **API endpoints** for dashboard data:
   - `GET /api/v1/dashboard/accuracy?company_id=X&period=monthly`
   - `GET /api/v1/dashboard/throughput?period=daily`
   - `GET /api/v1/dashboard/cost?company_id=X&period=monthly`

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/api/dashboard.py` | Dashboard analytics API endpoints |
| Create | `src/backend/services/analytics_service.py` | Analytics aggregation queries |
| Modify | `src/frontend/ux-ui-prototype.html` | Extend dashboard tab with charts |
| Create | `tests/api/test_dashboard.py` | API endpoint tests |
| Create | `tests/services/test_analytics_service.py` | Analytics query tests |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1601_01 | Accuracy trends show per-company data over time | test_accuracy_trends |
| ac_1601_02 | Throughput chart shows documents/day with real data | test_throughput_analytics |
| ac_1601_03 | Cost analytics show LLM spend by company + model | test_cost_analytics |
| ac_1601_04 | Dashboard loads within 3 seconds | test_dashboard_performance |
| ac_1601_05 | Period filters work (daily/weekly/monthly) | test_period_filters |

### Governance fields

```json
{
  "task_id": "TASK-1601",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/frontend/**", "src/backend/api/**", "src/backend/services/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1602: Sentry Integration

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-16, PP-18

### Purpose

Production error tracking + performance monitoring — ถ้ามี error ใน PROD ต้องรู้ทันที ไม่ใช่รอ user แจ้ง. Sentry captures stack traces, request context, performance traces. ช่วยป้องกัน "repeat failures without learning" (PP-18).

### What exists today

- structlog installed in requirements.txt (but not fully activated)
- No error tracking service
- Errors visible only in Docker logs (hard to search/aggregate)

### What to build

1. **Sentry SDK setup**:
   - Install `sentry-sdk[fastapi]`
   - Initialize in FastAPI app startup
   - DSN from environment variable (`SENTRY_DSN`)
   - Environment tag: `production` / `uat`
2. **Structured logging activation**:
   - Configure structlog with JSON output
   - Integrate with Sentry breadcrumbs
   - Log levels: ERROR → Sentry, WARNING → log file, INFO → structured log
3. **Alert rules**:
   - Critical errors: immediate Sentry alert
   - Error rate spike: alert if >10 errors/hour
   - Performance: alert if p95 response time >5s
4. **Performance monitoring**:
   - Trace: document upload → OCR → LLM extraction → DB save
   - Slow query detection
   - traces_sample_rate: 0.1 (10% sampling in PROD)

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/app/main.py` | Add Sentry SDK initialization |
| Create | `src/backend/core/logging_config.py` | structlog configuration |
| Modify | `config/settings.py` | Add SENTRY_DSN setting |
| Modify | `requirements.txt` | Add sentry-sdk[fastapi] |
| Create | `docs/monitoring/sentry-setup.md` | Sentry configuration + alert rules |
| Create | `tests/core/test_sentry_init.py` | Verify Sentry initializes correctly |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1602_01 | Sentry SDK initializes on app startup | test_sentry_init |
| ac_1602_02 | Unhandled exceptions captured in Sentry | test_error_capture |
| ac_1602_03 | Performance traces visible in Sentry | test_performance_tracing |
| ac_1602_04 | structlog outputs JSON format | test_structured_logging |
| ac_1602_05 | Alert rules configured (error rate spike) | Manual verification in Sentry UI |
| ac_1602_06 | Environment tag correct (production/uat) | test_environment_tag |

### Governance fields

```json
{
  "task_id": "TASK-1602",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/**", "config/**", "tests/**"],
  "forbidden_scope": [".env*"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1603: Audit Log Viewer

**Owner**: Full-stack Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-17

### Purpose

ให้ admin ค้นหา + filter audit logs ผ่าน UI — ใครทำอะไร เมื่อไร กับ entity ไหน. สำคัญสำหรับธุรกิจบัญชี (compliance, accountability). Export CSV สำหรับ external audit.

### What exists today

- AuditLog DB model (from Epic 8 ORM models)
- Audit log entries written during document processing
- No search/filter UI
- No export capability

### What to build

1. **Audit log search API**:
   - `GET /api/v1/audit-logs?user_id=X&action=update&entity=document&from=2026-06-01&to=2026-06-15`
   - Filters: user_id, action (create/update/delete/export/login), entity_type, entity_id, date_range
   - Pagination: offset + limit (default 50 per page)
   - Sort: newest first (default)
2. **Audit log viewer UI**:
   - Search bar + filter dropdowns
   - Table: timestamp, user, action, entity, details
   - Expandable row for full details (JSON payload)
3. **CSV export**:
   - `GET /api/v1/audit-logs/export?...` (same filters as search)
   - CSV with Thai headers
   - UTF-8 BOM encoding

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/api/audit_logs.py` | Audit log search + export endpoints |
| Modify | `src/frontend/ux-ui-prototype.html` | Add audit log viewer tab |
| Modify | `src/backend/app/endpoints.py` | Register audit_logs router |
| Create | `tests/api/test_audit_logs.py` | Search + filter + export tests |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1603_01 | Search returns filtered audit logs | test_audit_log_search |
| ac_1603_02 | User filter works | test_filter_by_user |
| ac_1603_03 | Action filter works | test_filter_by_action |
| ac_1603_04 | Date range filter works | test_filter_by_date_range |
| ac_1603_05 | Pagination works (offset + limit) | test_pagination |
| ac_1603_06 | CSV export generates correct file | test_csv_export |
| ac_1603_07 | UI shows searchable table with filters | Manual verification |

### Governance fields

```json
{
  "task_id": "TASK-1603",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/frontend/**", "src/backend/api/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1604: Budget Alert Notifications

**Owner**: Backend Dev
**Risk**: LOW
**Duration**: ~1 day
**Closes pain points**: PP-2, PP-3, PP-5, PP-16

### Purpose

Alert เมื่อ LLM cost ใกล้ถึง budget — ป้องกัน bill shock. ส่ง LINE notification เมื่อใช้ไป 80% ของ monthly budget. Per-company + global alerts.

### What exists today

- LLM usage tracking (model, tokens per request) — need to verify current logging
- LINE notification infrastructure (from CI/CD LINE alerts in TASK-1306)
- Celery Beat for scheduled tasks
- No budget tracking or alerts

### What to build

1. **Budget configuration**:
   - Global monthly budget (e.g., ฿5,000/month)
   - Per-company monthly budget (optional, e.g., ฿500/company/month)
   - Configurable threshold (default 80%)
2. **Budget check worker** (Celery Beat):
   - Runs every hour
   - Calculates current month LLM spend (sum tokens * price per model)
   - Compares against budget threshold
3. **Alert notification**:
   - LINE notification when threshold reached
   - Alert cooldown: max 1 alert per day per company (prevent spam)
   - Message includes: company name, current spend, budget, % used
4. **Budget tracking API**:
   - `GET /api/v1/budget/status?company_id=X` — current spend vs budget

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `src/backend/workers/budget_checker.py` | Celery Beat task for budget checking |
| Create | `src/backend/services/budget_service.py` | Budget calculation + threshold logic |
| Modify | `config/settings.py` | Add budget configuration settings |
| Modify | `src/backend/workers/celery_config.py` | Register budget_checker periodic task |
| Create | `tests/services/test_budget_service.py` | Budget calculation + alert tests |
| Create | `tests/workers/test_budget_checker.py` | Worker scheduling tests |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1604_01 | Alert fires when 80% of monthly budget consumed | test_budget_threshold_alert |
| ac_1604_02 | Cooldown prevents more than 1 alert per day per company | test_alert_cooldown |
| ac_1604_03 | LINE notification delivered with correct content | test_line_notification |
| ac_1604_04 | Per-company budget tracking works | test_per_company_budget |
| ac_1604_05 | Global budget tracking works | test_global_budget |
| ac_1604_06 | Budget status API returns current spend vs budget | test_budget_status_api |

### Governance fields

```json
{
  "task_id": "TASK-1604",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/workers/**", "src/backend/services/**", "config/**", "tests/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
