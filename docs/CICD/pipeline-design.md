# CI/CD Pipeline Design — LedgerFlow Phase II

> **TASK-1305** | Created: 2026-06-21 | Owner: DevOps
> **Status**: Design — ready for TASK-1306 implementation

---

## 1. Branch Strategy

### 1.1 Branch Flow

```
feature/*  ──→  dev  ──→  uat  ──→  main
                │               │                │
             SIT VPS        UAT VPS         PROD VPS
           76.13.210.250   72.62.74.232      72.62.247.9
            sit.yahwan.biz  uat.bwcacc.biz   app.bwcacc.biz
```

### 1.2 Branch Rules

| Branch | Purpose | Deploy Target | Protection |
|--------|---------|---------------|------------|
| `feature/*` | Feature development | None (local) | None |
| `dev` | Integration + SIT validation gate | SIT VPS (`76.13.210.250`) | Require PR, 1 approval |
| `uat` | UAT environment | UAT VPS (`72.62.74.232`) | Require PR from `dev`, SIT gate pass, CI pass |
| `main` | Production | PROD VPS (`72.62.247.9`) | Require PR from `uat`, CI pass, manual approval |

SIT execution source of truth:

- `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md`

### 1.3 Merge Rules

- `feature/* → dev`: Squash merge via PR, CI must pass (lint + test)
- `dev → uat`: Merge commit via PR, only allowed after SIT runtime gate is green
- `uat → main`: Merge commit via PR, requires manual approval, triggers PROD deploy
- **No force push** on `uat` or `main`
- **No direct commits** to `uat` or `main`

---

## 2. Existing Workflows (unchanged)

These workflows continue to run as-is:

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Push/PR to main/dev | Lint (ruff), typecheck (mypy), pytest |
| `agent_gate.yml` | PR to main/dev | Governance gate — scope/evidence/HDR risk |
| `e2e-smokes.yml` | Push/PR | Playwright E2E with Docker stack |
| `governance-watch.yml` | Schedule (hourly/daily) | Expire bypass labels, validate project board |
| `intake-sync.yml` | Issue label | Parse issues to agent state files |

---

## 3. New Deploy Workflows

> Control-plane compliance:
>
> - Canonical deploy dispatch is owned by `Piboonsak/Openclaw`.
> - Execution-plane workflows in this repo are mirror/break-glass only and must not be treated as source-of-truth deploy control.

### 3.0 SIT Runtime Validation Gate (TASK-1306A)

SIT is an internal-only runtime parity environment that must pass before UAT deploy is considered safe.
This is a real test environment for feature testing, not a dry run and not health-only verification.

Primary execution document:

- `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md`

### 3.0.1 `deploy-sit.yml` Architecture

**Trigger**: `dev` branch gate passed and Openclaw dispatches the SIT workflow.

This repository does not own the canonical deploy trigger. The control plane workflow dispatches the SIT run, and the execution plane applies the runtime stack on the SIT VPS.

```text
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  CI Pass     │────→│  Openclaw    │────→│  SIT VPS     │
│  (dev branch)│     │  dispatch    │     │  runtime     │
└──────────────┘     └──────────────┘     └──────┬───────┘
              │
          ┌──────────────┐    ┌─────────┴─────────┐
          │  Migrate +   │←───│  Build + Compose   │
          │  Seed data    │    │  nginx/backend/... │
          └──────┬───────┘    └─────────┬─────────┘
            │                      │
          ┌──────┴───────┐    ┌─────────┴─────────┐
          │ Smoke +      │────│ Feature runtime   │
          │ readiness    │    │ evidence checks   │
          └──────────────┘    └───────────────────┘
```

SIT runtime profile:

- SIT URL: `https://sit.yahwan.biz`
- SIT VPS: `76.13.210.250`
- Access gate: Nginx Basic Auth + `X-Robots-Tag: noindex`
- Runtime stack: nginx, frontend, backend, postgres, redis, minio, celery-worker
- Compose / env surface: `docker/docker-compose.sit.yml`, `docker/.env.sit.example`, `docker/nginx/nginx-sit.conf`

SIT prerequisites before any smoke or feature evidence run:

1. `sit.yahwan.biz` resolves publicly to `76.13.210.250`
2. TLS certificate for `sit.yahwan.biz` is valid
3. SIT Basic Auth credentials exist in Openclaw secrets
4. `.htpasswd` is provisioned at `/opt/ledgerflow/secrets/sit/.htpasswd`
5. External public ports are restricted to intended edge ports only

### 3.0.2 `deploy-sit.yml` Flow

1. Checkout the `dev` branch state that passed CI
2. Validate required SIT secrets before SSH
3. SSH to the SIT host and bootstrap `/opt/ledgerflow` if needed
4. Build SIT images
5. Start dependency services (postgres, redis, minio)
6. Run Alembic migration (`alembic upgrade head`)
7. Seed anonymized SIT data (`scripts/seed_sit.py`)
8. Start app services (frontend, backend, celery-worker, nginx)
9. Run smoke checks (`scripts/deploy/smoke-sit.sh`)
10. Run SIT feature flow checks against real services (UI/API actions that write to DB and use Redis/MinIO)

### 3.0.3 Smoke and Feature Contract

- `GET /api/health` returns 200
- `GET /api/health/ready` returns 200 and dependency states are ready
- PostgreSQL, Redis, MinIO connectivity confirmed from runtime containers
- Celery responds to control ping
- Export/template route is reachable (200/401/403 accepted)
- At least one core user flow is executed end-to-end on SIT (upload/process/review/export)
- Test writes are persisted in PostgreSQL and visible via API/UI readback
- Redis cache activity is observed during request path (cache set/get evidence)
- MinIO object write/read is verified for uploaded or generated artifacts
- Evidence is attached to PR: command logs + screenshots/API responses

### 3.0.4 Failure Handling

If `/api/health/ready` returns `503`, SIT must be treated as blocked and diagnostics must capture:

- backend logs
- readiness response body
- dependency state for postgres/redis/minio/celery
- the Openclaw workflow run URL associated with the failure

If the readiness gate fails, do not promote to UAT until the failure is understood and the SIT evidence gate is green.

### 3.1 deploy-uat.yml

**Trigger**: Push to `uat` branch (after PR merge from `dev`)

This repository workflow is kept as an execution-plane mirror for emergency/manual use.
Primary SIT/UAT gate dispatch must be executed from Openclaw control-plane workflow dispatch.

UAT is not allowed to proceed unless the SIT execution plan gate is green:

- `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md`

```text
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  CI Pass     │────→│  SSH to UAT  │────→│  Git Pull    │
│  (reuse ci)  │     │  VPS         │     │  Latest Code │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                     ┌──────────────┐     ┌───────┴──────┐
                     │  Health      │←────│  Docker      │
                     │  Check       │     │  Compose Up  │
                     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────┴───────┐     ┌──────────────┐
                     │  Smoke Test  │────→│  LINE Notify │
                     │  (optional)  │     │  Result      │
                     └──────────────┘     └──────────────┘
```

**Steps**:
1. SSH into UAT VPS as `deploy` user
2. `cd /opt/ledgerflow && git pull origin uat`
3. `docker compose -f docker-compose.uat.yml build` (only if Dockerfile changed)
4. `docker compose -f docker-compose.uat.yml run --rm backend alembic upgrade head`
5. `docker compose -f docker-compose.uat.yml up -d`
6. Wait 15s for services to start
7. Health check: `curl -sf http://localhost:8000/api/health`
8. LINE notify result (success/failure)

**Failure handling**:
- If health check fails → rollback: `docker compose up -d` with previous image
- LINE notify with error details

### 3.2 deploy-prod.yml

**Trigger**: Push to `main` branch (after PR merge from `uat`)

```text
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Manual      │────→│  DB Snapshot  │────→│  SSH to PROD │
│  Approval    │     │  (pg_dump)    │     │  VPS         │
└──────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                     ┌──────────────┐     ┌───────┴──────┐
                     │  Health      │←────│  Docker      │
                     │  Check       │     │  Compose Up  │
                     └──────┬───────┘     └──────────────┘
                            │
                     ┌──────┴───────┐     ┌──────────────┐
                     │  Smoke Test  │────→│  LINE Notify │
                     │  (Playwright)│     │  Result      │
                     └──────────────┘     └──────────────┘
```

**Steps**:
1. **Manual approval** (GitHub environment protection rule)
2. SSH into PROD VPS as `deploy` user
3. **Pre-deploy DB snapshot**: `pg_dump` → `/backup/db/pre-deploy-$(date).sql.gz`
4. `cd /opt/ledgerflow && git pull origin main`
5. `docker compose -f docker-compose.prod.yml build`
6. `docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head`
7. `docker compose -f docker-compose.prod.yml up -d`
8. Wait 30s for services to start
9. Health check: `curl -sf https://app.bwcacc.biz/api/health`
10. Playwright smoke test (optional, if available)
11. LINE notify result

**Failure handling**:
- If health check fails after deploy:
  1. `docker compose down`
  2. Restore DB from pre-deploy snapshot
  3. `git checkout HEAD~1`
  4. `docker compose up -d`
  5. LINE notify with rollback details

---

## 4. GitHub Secrets Required

| Secret | Value | Used In |
| --- | --- | --- |
| `BWCACC_SIT_HOST` | `76.13.210.250` | SIT gate workflow dispatch / diagnostics |
| `BWCACC_VPS_SSH_KEY` | SSH private key (ed25519) | bwcacc-deploy-uat, bwcacc-deploy-prod |
| `BWCACC_UAT_HOST` | `72.62.74.232` | bwcacc-deploy-uat |
| `BWCACC_PROD_HOST` | `72.62.247.9` | bwcacc-deploy-prod |
| `BWCACC_DEPLOY_USER` | `deploy` | bwcacc-deploy-uat, bwcacc-deploy-prod |
| `BWCACC_LINE_CHANNEL_ACCESS_TOKEN` | LINE Messaging API token | bwcacc-deploy-uat, bwcacc-deploy-prod |
| `BWCACC_LINE_CHANNEL_SECRET` | LINE channel secret | (reserved for webhook verification) |
| `BWCACC_LINE_USER_ID` | LINE user ID (push target) | bwcacc-deploy-uat, bwcacc-deploy-prod |
| `BWCACC_SIT_BASIC_AUTH_USER` | SIT Basic Auth username | SIT gate workflow / edge auth proof |
| `BWCACC_SIT_BASIC_AUTH_PASS` | SIT Basic Auth password | SIT gate workflow / edge auth proof |

> **Naming convention**: Prefix `BWCACC_` ใช้สำหรับ multi-client namespace — เมื่อเพิ่ม client ใหม่ ใช้ prefix ของ client นั้น (e.g., `NEWCO_VPS_SSH_KEY`)
>
> **LINE notification**: ใช้ LINE Messaging API push (เดียวกับ NongKung bot ใน Openclaw) — ไม่ใช่ LINE Notify (deprecated)

Secret policy:

- Reuse Openclaw control-plane secrets when already present and policy-approved.
- Create new SIT-specific secrets when a required value is missing or unsafe to share with UAT/PROD.
- Runtime service credentials remain environment-local and must not be committed.

Reference:

- `docs/CICD/SECRETS-CHECKLIST.md`
- `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md`

### GitHub Environment Setup

| Environment | Protection Rules | Reviewers |
| --- | --- | --- |
| `uat` | None (auto-deploy) | — |
| `production` | Required reviewers (1), wait timer (0) | Project Owner |

---

## 5. PROD Safety Rules

### 5.1 Pre-Deploy Gates

1. **UAT gate**: Code must have been deployed and tested on UAT first (enforced by branch flow: `dev → uat → main`)
2. **SIT gate**: UAT promotion is blocked/unsafe unless SIT deploy + smoke pass (`dev → sit gate → uat`)
3. **SIT feature pass**: health/ready + feature-flow tests with real DB/cache/storage must pass
4. **CI pass**: All CI checks (lint, typecheck, pytest) must pass
5. **Manual approval**: At least 1 reviewer must approve the `uat → main` PR
6. **No force push**: Branch protection prevents force push to `main`

### 5.2 Pre-Deploy DB Snapshot

Every PROD deploy creates a DB backup **before** running migrations:

```bash
# Runs as step 3 in deploy-prod.yml
docker exec postgres pg_dump -U ledgerflow ledgerflow_prod \
  | gzip > /backup/db/pre-deploy-$(date +%Y%m%d_%H%M%S).sql.gz
```

- Retained for 7 days minimum
- Enables rollback to exact pre-deploy state

### 5.3 Rollback Procedure

**Scenario**: PROD deploy broke something, need to revert.

```
Step 1: Identify the issue
─────────────────────────
  Check logs:  docker logs backend --tail 100
  Check health: curl https://app.bwcacc.biz/api/health

Step 2: Stop the broken deployment
──────────────────────────────────
  docker compose -f docker-compose.prod.yml down

Step 3: Revert code
────────────────────
  git log --oneline -5          # find the last good commit
  git checkout <good-commit>    # revert to it

Step 4: Restore DB (if migration was destructive)
──────────────────────────────────────────────────
  ls -lah /backup/db/pre-deploy-*           # find latest pre-deploy snapshot
  gunzip < /backup/db/pre-deploy-XXXX.sql.gz | docker exec -i postgres psql -U ledgerflow ledgerflow_prod

Step 5: Restart services
────────────────────────
  docker compose -f docker-compose.prod.yml up -d

Step 6: Verify
──────────────
  curl -s https://app.bwcacc.biz/api/health
  # Notify team via LINE

Step 7: Post-mortem
───────────────────
  Create issue documenting: what broke, root cause, fix plan
```

**RTO target**: < 30 minutes for code rollback, < 1 hour including DB restore.

---

## 6. Health Check Contract

The deploy workflows depend on a health endpoint:

### Endpoint

```
GET /api/health
```

### Expected Response (200 OK)

```json
{
  "status": "healthy",
  "version": "2.0.0",
  "services": {
    "database": "connected",
    "redis": "connected",
    "minio": "connected"
  }
}
```

### Failure Response (503)

```json
{
  "status": "unhealthy",
  "error": "database connection failed"
}
```

The health check must verify:
- Database connectivity (PostgreSQL)
- Redis connectivity
- MinIO connectivity (optional, warn-only)

---

## 7. LINE Notification Format

### Success

```
✅ LedgerFlow Deploy SUCCESS
Environment: UAT / PROD
Branch: uat / main
Commit: abc1234
Health: /api/health → 200 OK
Time: 2026-06-21 14:30:00 UTC
```

### Failure

```
❌ LedgerFlow Deploy FAILED
Environment: UAT / PROD
Branch: uat / main
Commit: abc1234
Error: Health check failed (503)
Action: Auto-rollback triggered
Time: 2026-06-21 14:30:00 UTC
```

---

## 8. Deploy Scripts (to be created in TASK-1306)

| Script | Purpose | Location |
|--------|---------|----------|
| `scripts/deploy/deploy-sit.sh` | Build + migrate + seed + start SIT stack | VPS |
| `scripts/deploy/smoke-sit.sh` | SIT dependency smoke checks | VPS |
| `scripts/seed_sit.py` | Seed SIT with anonymized defaults | VPS |
| `scripts/deploy/health-check.sh` | `curl` health endpoint, exit 0/1 | VPS |
| `scripts/deploy/pre-deploy-snapshot.sh` | `pg_dump` before PROD migration | VPS |
| `scripts/deploy/notify-line.sh` | Send LINE notification | GitHub Actions |
| `.github/workflows/bwcacc-deploy-uat.yml` | UAT deploy workflow | Repo |
| `.github/workflows/bwcacc-deploy-prod.yml` | PROD deploy workflow | Repo |
| `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md` | SIT execution source of truth | Repo |

---

## 9. Promotion Gate Summary

Promotion chain is now:

`CI pass -> SIT deploy pass -> SIT smoke pass -> SIT feature/runtime evidence pass -> UAT deploy allowed -> PROD approval/deploy`

If SIT fails, UAT deploy must be treated as blocked/unsafe until SIT evidence is green.

If SIT DNS/TLS/Auth prerequisites are incomplete, SIT must be treated as not ready and UAT promotion remains blocked.

---

## Appendix: Sequence Diagram (UAT Deploy)

```
Developer          GitHub Actions       UAT VPS
   │                    │                  │
   │  merge PR to uat   │                  │
   │───────────────────→│                  │
   │                    │  SSH connect     │
   │                    │─────────────────→│
   │                    │  git pull        │
   │                    │─────────────────→│
   │                    │  docker build    │
   │                    │─────────────────→│
   │                    │  alembic migrate │
   │                    │─────────────────→│
   │                    │  docker up -d    │
   │                    │─────────────────→│
   │                    │  health check    │
   │                    │─────────────────→│
   │                    │  200 OK          │
   │                    │←─────────────────│
   │  LINE notify ✅    │                  │
   │←───────────────────│                  │
```

---

*Created: 2026-06-21*
*Implementation: TASK-1306*
*Architecture: `docs/architecture/vps-architecture.md`*
