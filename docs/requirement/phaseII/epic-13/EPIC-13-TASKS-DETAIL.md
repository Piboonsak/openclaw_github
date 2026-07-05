ิ# Epic 13 — Infrastructure + Deployment: Tasks Detail

> **Phase**: II/1 (parallel W1-W8)
> **Infrastructure Decision**: Hostinger VPS all-in (compute + DB + storage ทุกอย่างบน VPS)
> **Created**: 2026-06-15

---

## TASK-1301: VPS Architecture Design — ✅ DONE (2026-06-21)

**Owner**: DevOps
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5
**Output**: `docs/architecture/vps-architecture.md` (consolidated all sections into one document)

### Purpose

กำหนด blueprint ของ infrastructure ทั้งหมดก่อนเริ่ม build — ป้องกันการ re-work ระหว่าง sprint. Document ว่า service ไหนอยู่ที่ไหน, network flow เป็นอย่างไร, resource sizing เท่าไร.

### What exists today

- PoC Docker Compose (`docker-compose.yml`) มี backend, postgres, redis, minio — แต่เป็น dev mode
- PoC runs on Hostinger VPS (single instance, demo.bwcacc.biz)
- Architecture diagram ใน PHASE-II-EPIC-ROADMAP.md (high-level)

### What to build

1. Detailed service topology document
2. Network diagram: nginx (SSL termination) → backend (FastAPI) → celery-worker → postgres → redis → minio
3. Resource sizing justification:
   - UAT: KVM 2 (2 vCPU, 8GB RAM) — sufficient for testing workloads
   - PROD: KVM 4 (4 vCPU, 16GB RAM) — handles 10K-20K docs/month
4. Port mapping (internal Docker network vs exposed)
5. Volume mount strategy (data persistence)
6. Environment separation strategy (UAT vs PROD configs)

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docs/architecture/vps-architecture.md` | Service topology + network diagram |
| Create | `docs/architecture/resource-sizing.md` | Sizing justification + capacity planning |
| Create | `docs/architecture/environment-strategy.md` | UAT vs PROD config separation |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1301_01 | Architecture document has service topology diagram | Manual review |
| ac_1301_02 | Resource sizing justified with workload estimates | Manual review |
| ac_1301_03 | Network diagram shows all service connections + ports | Manual review |
| ac_1301_04 | Environment separation strategy documented (UAT vs PROD) | Manual review |

### Governance fields

```json
{
  "task_id": "TASK-1301",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docs/**", "docker/**"],
  "forbidden_scope": [".env*", "src/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

## TASK-1302: VPS Procurement — UAT + PROD — ✅ DONE (2026-06-20)

**Owner**: DevOps
**Risk**: LOW
**Duration**: ~1 day
**Closes pain points**: PP-2, PP-5
**Output**: UAT VPS 1772060 (`72.62.74.232`), PROD VPS 1772174 (`72.62.247.9`) — both DC 21 Singapore

### Purpose

สั่งซื้อ VPS instances จาก Hostinger เพื่อให้มี environment พร้อมสำหรับ setup. ต้องได้ Singapore DC เพื่อ latency ต่ำสำหรับ users ในไทย.

### What exists today

- PoC VPS on Hostinger (demo.bwcacc.biz) — ใช้ต่อสำหรับ demo
- Hostinger account ready

### What to build

1. Order Hostinger KVM 2 for UAT (~$10-15/mo)
2. Order Hostinger KVM 4 for PROD (~$16-25/mo)
3. Verify Singapore DC for both instances
4. Verify SSH access (key-based)
5. Document IP addresses, hostnames, specs

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docs/infrastructure/vps-inventory.md` | IP addresses, specs, DC location, costs |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1302_01 | UAT VPS accessible via SSH | `ssh user@uat-ip 'hostname'` |
| ac_1302_02 | PROD VPS accessible via SSH | `ssh user@prod-ip 'hostname'` |
| ac_1302_03 | Both VPS in Singapore DC | Verify in Hostinger panel |
| ac_1302_04 | VPS specs match order (UAT: 2vCPU/8GB, PROD: 4vCPU/16GB) | `nproc && free -h` |

### Governance fields

```json
{
  "task_id": "TASK-1302",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docs/**"],
  "forbidden_scope": [".env*", "src/**", "docker/**", "scripts/**"],
  "max_loops": 3,
  "escalation_policy": "human"
}
```

---

## TASK-1303: Base OS Setup + Docker Engine + Security Hardening — ✅ DONE (2026-06-21)

**Owner**: DevOps
**Risk**: MEDIUM
**Duration**: ~3 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-15
**Output**: `scripts/infra/setup-vps.sh` (idempotent, ran on both UAT + PROD 2026-06-21)

### Purpose

ติดตั้ง Docker Engine + hardening ทั้ง UAT และ PROD — เป็น foundation สำหรับทุก service ที่ deploy ผ่าน Docker Compose. Security hardening ป้องกัน brute-force + unauthorized access.

### What exists today (verified 2026-06-21)

- ✅ Docker 29.6.0 + Compose 5.1.4 on both VPS (pre-installed by Hostinger)
- ✅ fail2ban active (sshd jail), PasswordAuthentication=no, PubkeyAuthentication=yes
- ✅ PermitRootLogin=prohibit-password (progressive hardening — will tighten to `no` at go-live)
- ✅ `deploy` user in docker group, can run `docker ps`
- ✅ UFW active: 22/80/443 open, deny all others
- ✅ Swap: 2G (UAT), 4G (PROD)
- ✅ sysctl tuned (vm.swappiness=10, vm.overcommit_memory=1)
- ✅ /opt/ledgerflow + /backup/db directories created, owned by deploy
- ✅ htop installed for resource monitoring

### What to build

1. **Docker Engine + Docker Compose** — install on both UAT and PROD
2. **Security hardening**:
   - Disable root SSH login
   - SSH key-only authentication (disable password auth)
   - Install + configure fail2ban (SSH brute-force protection)
   - Create system user `deploy` for Docker operations
3. **System tuning**:
   - Swap configuration (2GB swap file)
   - sysctl tuning for PostgreSQL (vm.overcommit_memory, vm.swappiness)
4. **Setup script** — idempotent, can re-run safely

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `scripts/infra/setup-vps.sh` | Idempotent VPS setup script |
| Create | `scripts/infra/harden-ssh.sh` | SSH hardening script |
| Create | `docs/infrastructure/security-hardening.md` | Hardening checklist + verification steps |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1303_01 | Docker Engine runs on both VPS | `docker version` returns version |
| ac_1303_02 | Docker Compose runs on both VPS | `docker compose version` returns version |
| ac_1303_03 | Root SSH disabled | `ssh root@host` rejected |
| ac_1303_04 | SSH key-only auth | `ssh -o PasswordAuthentication=yes` rejected |
| ac_1303_05 | fail2ban active and monitoring SSH | `fail2ban-client status sshd` shows active |
| ac_1303_06 | Deploy user can run Docker | `su - deploy -c 'docker ps'` works |
| ac_1303_07 | Swap configured | `swapon --show` shows 2GB swap |

### Governance fields

```json
{
  "task_id": "TASK-1303",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docs/**", "docker/**", "scripts/**"],
  "forbidden_scope": [".env*", "src/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1304: DNS Delegation + Certbot SSL — ✅ DONE (2026-06-21)

**Owner**: DevOps
**Risk**: MEDIUM
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-15

### Purpose

ตั้ง DNS subdomains ให้ชี้มาที่ VPS ที่ถูกต้อง + SSL certificates สำหรับ HTTPS. Domain `bwcacc.biz` จดบน Hostinger โดยตรง — ทีมเราจัดการ DNS ผ่าน Hostinger REST API.

SIT note:

- SIT currently uses `sit.yahwan.biz` on the PoC/SIT host `76.13.210.250`
- SIT DNS/TLS work must be tracked alongside UAT/PROD so `dev -> uat` promotion is not blocked by missing infra parity
- execution details live in `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md`

### What exists today (updated 2026-06-21)

- ✅ `demo.bwcacc.biz` → `76.13.210.250` (PoC VPS) — LIVE
- ✅ `uat.bwcacc.biz` → `72.62.74.232` (UAT VPS) — LIVE
- ✅ `app.bwcacc.biz` → `72.62.247.9` (PROD VPS) — LIVE
- ✅ CAA record → `0 issue "letsencrypt.org"` — LIVE
- ✅ SSL cert for `uat.bwcacc.biz` — issued 2026-06-21, expires 2026-09-18
- ✅ SSL cert for `app.bwcacc.biz` — issued 2026-06-21, expires 2026-09-18
- ✅ certbot.timer enabled (auto-renew twice daily)

### What was built

1. ~~DNS records~~ — ✅ DONE via Hostinger REST API (2026-06-21)
2. ~~Certbot Let's Encrypt SSL~~ — ✅ DONE via `scripts/infra/setup-certbot.sh` (standalone mode)
3. ~~Auto-renew~~ — ✅ DONE via systemd certbot.timer (dry-run passed)
4. **nginx SSL config** template for Docker — deferred to TASK-1307 (Docker Compose)

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `scripts/infra/setup-certbot.sh` | Certbot installation + certificate issuance |
| Create | `docker/nginx/nginx.conf.template` | nginx config with SSL termination |
| Create | `docs/infrastructure/dns-setup.md` | DNS records + SSL certificate details |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1304_01 | app.bwcacc.biz resolves to PROD VPS IP | `dig app.bwcacc.biz +short` returns PROD IP |
| ac_1304_02 | uat.bwcacc.biz resolves to UAT VPS IP | `dig uat.bwcacc.biz +short` returns UAT IP |
| ac_1304_03 | SSL certificate valid for app.bwcacc.biz | `curl -v https://app.bwcacc.biz` shows valid cert |
| ac_1304_04 | SSL certificate valid for uat.bwcacc.biz | `curl -v https://uat.bwcacc.biz` shows valid cert |
| ac_1304_05 | Auto-renew cron configured | `crontab -l` shows certbot renew entry |
| ac_1304_06 | HTTP → HTTPS redirect works | `curl -I http://app.bwcacc.biz` returns 301 to HTTPS |
| ac_1304_07 | SIT DNS/TLS exception is documented with owner and exit criteria | Manual review |

### Governance fields

```json
{
  "task_id": "TASK-1304",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docker/**", "scripts/**", "docs/**"],
  "forbidden_scope": [".env*", "src/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1305: CI/CD Pipeline Design — ✅ DONE (2026-06-21)

**Owner**: DevOps
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-15, PP-16
**Output**: `docs/cicd/pipeline-design.md` + `docs/cicd/prod-safety-rules.md`

### Purpose

ออกแบบ CI/CD pipeline ก่อน implement — กำหนด branch strategy, deploy steps, safety rules สำหรับ PROD. ป้องกัน "deploy succeeded but unhealthy" (PP-16).

SIT note:

- this design task now includes SIT as the required `dev` promotion gate
- `docs/cicd/pipeline-design.md` and `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md` must stay aligned

### What exists today

- Existing GitHub Actions workflows (lint, test, governance gate)
- PoC deployed manually via SSH + git pull
- Branch: dev → main (current), need to add uat

### What to build

1. **Branch strategy document**:
   - `dev` → development (feature branches merge here)
   - `uat` → triggers UAT deploy
   - `main` → triggers PROD deploy
2. **Deploy workflow design**:
   - SSH into VPS
   - `git pull` latest code
   - `docker compose build` (if Dockerfile changed)
   - `alembic upgrade head` (DB migration)
   - `docker compose up -d` (restart services)
   - Health check (GET /api/health)
   - Playwright smoke test
   - LINE notification (success/fail)
3. **PROD safety rules**:
   - Must pass UAT first (branch protection)
   - Snapshot DB before migration
   - No force push to main
   - Rollback procedure documented
4. **SIT gate documentation**:
   - DNS/TLS/Auth prerequisites documented
   - smoke/readiness/runtime evidence gates documented
   - secret reuse vs new-create policy documented

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docs/cicd/pipeline-design.md` | Workflow diagrams + branch strategy |
| Create | `docs/cicd/prod-safety-rules.md` | PROD deployment safety rules + rollback |
| Create | `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md` | SIT setup and execution source of truth |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1305_01 | Branch strategy documented (dev → uat → main) | Manual review |
| ac_1305_02 | Deploy workflow steps documented with sequence diagram | Manual review |
| ac_1305_03 | PROD safety rules include: UAT gate, DB snapshot, no force push | Manual review |
| ac_1305_04 | Rollback procedure documented step-by-step | Manual review |
| ac_1305_05 | SIT gate prerequisites and secret policy documented | Manual review |

### Governance fields

```json
{
  "task_id": "TASK-1305",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docs/**", ".github/**"],
  "forbidden_scope": [".env*", "src/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1306: CI/CD Pipeline Implementation — ✅ DONE (2026-06-21)

**Owner**: DevOps
**Risk**: HIGH
**Duration**: ~4 days
**Closes pain points**: PP-5, PP-8, PP-15, PP-16, PP-17
**Output**: `.github/workflows/bwcacc-deploy-uat.yml`, `.github/workflows/bwcacc-deploy-prod.yml`, `scripts/deploy/health-check.sh`, `scripts/deploy/pre-deploy-snapshot.sh`, `scripts/deploy/notify-line.sh` — GitHub Secrets set (7 × `BWCACC_*`), Environments `uat` + `production` created

### Purpose

Implement the CI/CD pipeline designed in TASK-1305. This is the highest-risk infra task — deployment automation ต้องทำงานถูกต้อง 100% เพราะผิดพลาดจะกระทบ PROD.

SIT note:

- UAT/PROD implementation remains complete, but active promotion governance now depends on TASK-1306A SIT readiness being green.

### What exists today

- Existing GitHub Actions: lint, test, governance gate workflows
- `.github/workflows/` directory with existing YAML files
- SSH key available for VPS access

### What to build

1. **deploy-uat.yml** — GitHub Actions workflow:
   - Trigger: push to `uat` branch
   - Steps: SSH → git pull → docker build → alembic migrate → docker up → health check → smoke test → LINE notify
2. **deploy-prod.yml** — GitHub Actions workflow:
   - Trigger: push/merge to `main` branch
   - Pre-deploy: DB snapshot (pg_dump)
   - Steps: same as UAT + DB snapshot step
   - Post-deploy: verify health check + LINE notify
3. **GitHub secrets setup**:
   - SSH private key (`VPS_SSH_KEY`)
   - VPS host/user (`UAT_HOST`, `PROD_HOST`, `DEPLOY_USER`)
   - LINE notify token (`LINE_NOTIFY_TOKEN`)
   - reference SIT-specific Openclaw secrets from TASK-1306A for `dev -> uat` gating
4. **Health check script** for CI/CD to call
5. **Playwright smoke test** integration in CI/CD

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `.github/workflows/deploy-uat.yml` | UAT deployment workflow |
| Create | `.github/workflows/deploy-prod.yml` | PROD deployment workflow |
| Create | `scripts/deploy/health-check.sh` | Health check script (GET /api/health) |
| Create | `scripts/deploy/pre-deploy-snapshot.sh` | DB snapshot before PROD migration |
| Create | `scripts/deploy/notify-line.sh` | LINE notification script |
| Modify | `.github/workflows/` (existing) | Add branch filters for uat/main |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1306_01 | Push to uat branch triggers UAT deploy | test_deploy_uat_trigger |
| ac_1306_02 | Merge to main triggers PROD deploy | test_deploy_prod_trigger |
| ac_1306_03 | Health check passes after deploy | `curl /api/health` returns 200 |
| ac_1306_04 | LINE notification sent on success | LINE message received |
| ac_1306_05 | LINE notification sent on failure | Simulate failure, verify LINE message |
| ac_1306_06 | PROD deploy creates DB snapshot before migration | Snapshot file exists on VPS |
| ac_1306_07 | Deploy fails gracefully if health check fails | Workflow shows failure + LINE alert |
| ac_1306_08 | UAT/PROD implementation docs reference SIT gate dependency clearly | Manual review |

### Governance fields

```json
{
  "task_id": "TASK-1306",
  "risk_tier": "HIGH",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": [".github/workflows/**", "scripts/**", "docker/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
  "max_loops": 5,
  "escalation_policy": "stop"
}
```

---

## TASK-1306A: SIT Environment with Real Runtime Services — ✅ DONE (2026-06-28)

**Owner**: DevOps
**Risk**: HIGH
**Duration**: ~3-4 days
**Closes pain points**: PP-2, PP-5, PP-8, PP-15, PP-16, PP-17
**Output**: `docker/docker-compose.sit.yml`, `docker/nginx/nginx-sit.conf`, `docker/.env.sit.example`, `scripts/deploy/deploy-sit.sh`, `scripts/deploy/smoke-sit.sh`, `scripts/seed_sit.py`, `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md`, Openclaw workflow evidence: [run 28332426427](https://github.com/Piboonsak/Openclaw/actions/runs/28332426427), [run 28335254413](https://github.com/Piboonsak/Openclaw/actions/runs/28335254413)

### Purpose

Create an internal-only SIT environment (`sit.yahwan.biz`) that runs real runtime services before UAT promotion. SIT is the runtime parity gate to catch container/network/service problems that do not appear on laptops.

Primary execution document for this task:

- `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md`

Branch/environment alignment:

- `feature/* -> dev -> uat -> main`
- `dev` promotion gate runs on SIT VPS `76.13.210.250` (`sit.yahwan.biz`)
- `uat` deploy target is UAT VPS `72.62.74.232` (`uat.bwcacc.biz`)
- `main` deploy target is PROD VPS `72.62.247.9` (`app.bwcacc.biz`)

### What to build

1. **SIT compose stack**: frontend, backend, postgres, redis, minio, celery-worker, nginx
2. **Security boundary**: Basic Auth gate + noindex header, only 80/443 exposed externally
3. **Deploy flow**: branch sync -> build -> dependency up -> alembic migrate -> seed anonymized data -> app up -> smoke
4. **Smoke checks**:
    - `/api/health` returns 200
    - `/api/health/ready` returns 200
    - PostgreSQL/Redis/MinIO checks pass
    - Celery control ping responds
    - Export/template route responds (availability gate)
5. **Feature test gate (real runtime, not dry run)**:
   - execute core feature flow on SIT via UI/API
   - verify records are persisted in PostgreSQL and readable back in the same run
   - verify Redis cache participation in request path
   - verify MinIO object write/read works for upload/export artifact path
6. **Promotion gate documentation**: `CI pass -> SIT deploy pass -> SIT smoke pass -> SIT feature pass -> UAT allowed`

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docker/docker-compose.sit.yml` | SIT stack with isolated project/volumes and private service network |
| Create | `docker/nginx/nginx-sit.conf` | SIT vhost with Basic Auth + noindex |
| Create | `docker/.env.sit.example` | SIT environment template (no secrets) |
| Create | `scripts/deploy/deploy-sit.sh` | SIT deploy script (build/migrate/seed/smoke) |
| Create | `scripts/deploy/smoke-sit.sh` | SIT health + dependency smoke checks |
| Create | `scripts/seed_sit.py` | Anonymized seed wrapper for SIT |
| Create | `samples/sit/companies.anonymized.json` | Seed data source for SIT |
| Create | `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md` | Primary SIT setup, secret, blocker, and execution plan |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_sit_01 | `sit.yahwan.biz` routes to SIT app over HTTPS (or pending SSL documented) | `curl -I https://sit.yahwan.biz` |
| ac_sit_02 | SIT uses real PostgreSQL + Redis + MinIO runtime services | smoke script + container logs |
| ac_sit_03 | Alembic migration runs during deploy | deploy output includes `alembic upgrade head` success |
| ac_sit_04 | Anonymized seed data loaded for SIT login/workflow smoke | seed output + DB rows |
| ac_sit_05 | `/api/health` and `/api/health/ready` pass | smoke script HTTP checks |
| ac_sit_06 | Celery worker reachable via control ping | smoke script Celery ping |
| ac_sit_07 | PostgreSQL/Redis/MinIO not publicly exposed | external nmap/nc proof |
| ac_sit_08 | SIT is access-protected by Basic Auth (or equivalent) | unauthorized request gets 401 |
| ac_sit_09 | UAT procedure explicitly references SIT-pass gate | docs review |
| ac_sit_10 | SIT supports clickable feature testing with real writes | test evidence from UI/API + DB/cache/object proof |
| ac_sit_11 | No secrets committed | secret scan + manual review |

### Governance fields

```json
{
   "task_id": "TASK-1306A",
   "risk_tier": "HIGH",
   "model_tier": "tier-2a-copilot",
   "allowed_scope": ["docker/**", "scripts/**", "docs/**", "samples/**", "config/**"],
   "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/ml/**"],
   "max_loops": 5,
   "escalation_policy": "stop"
}
```

### Rollback notes

If SIT deploy is unhealthy:

1. `docker compose -f docker/docker-compose.sit.yml --env-file docker/.env.sit down`
2. Checkout previous known-good commit on SIT branch
3. Re-run `scripts/deploy/deploy-sit.sh`
4. Re-run `scripts/deploy/smoke-sit.sh` and attach evidence before reopening UAT gate

### Evidence required before UAT

- SIT deploy log with migration + seed success
- SIT smoke log showing `/api/health` + `/api/health/ready` + dependency checks
- SIT feature-flow evidence: UI/API run output plus proof of PostgreSQL write/read, Redis cache hit/update, and MinIO object write/read
- Network exposure check output showing 5432/6379/9000/9001 closed externally
- Basic Auth challenge proof (401 without credentials)
- Openclaw control-plane workflow run URL used for SIT/UAT gate dispatch

### Completion evidence (2026-06-29 refresh)

- First full green workflow for SIT gate: `Piboonsak/Openclaw` Actions run `28332426427`
- Re-validation after edge/auth hardening: `Piboonsak/Openclaw` Actions run `28335254413` (head SHA `c7fec6ab8e56a1a2008d79e84a71303c917da387`)
- Deploy flow passed: SSH preflight, SIT stack deploy, public edge provision, smoke, runtime evidence, HTTP gate evidence, network exposure evidence, summary generation, artifact upload
- Runtime state verified during final run: backend/postgres/redis/minio healthy, Celery running, Basic Auth gate enforced, internal dependency ports not publicly exposed
- HTTP verification after final run:
   - No auth => `401 Unauthorized` on `https://sit.yahwan.biz/api/health`
   - With auth => `200 OK` on `/api/health` and `/api/health/ready`

### Rollout blockers encountered and resolved

1. **SSH timeout during runner preflight**
   - Why it blocked: control-plane workflow could not reach the SIT host reliably from the GitHub runner
   - Why it happened: runner-to-host reachability was intermittent; one-shot SSH preflight was too brittle
   - Fix applied: defaulted SIT deploy user to `root` for this host and added bounded SSH preflight retries in the Openclaw workflow
   - Prevention for UAT/PROD: keep retryable SSH preflight in shared deploy workflows and validate the real remote user per environment before rollout
2. **Readiness `503` after deploy**
   - Why it blocked: `/api/health/ready` stayed red, so SIT could not be promoted
   - Why it happened: LLM runtime keys were missing in the control-plane path and MinIO endpoint format was invalid for the backend storage client
   - Fix applied: injected `OPENROUTER_API_KEY`, `BWCACC_OPENROUTER_API_KEY`, and `OPENAI_API_KEY` into the live SIT env; rewrote MinIO/storage endpoint values to `http://minio:9000`
   - Prevention for UAT/PROD: add a pre-deploy config assertion that required runtime keys are present and endpoint variables use the URL form expected by the application
3. **MinIO reported unhealthy despite container running**
   - Why it blocked: Docker health state prevented confidence in the dependency gate
   - Why it happened: the MinIO image did not include the tools assumed by the original healthcheck
   - Fix applied: simplified the healthcheck to an image-compatible TCP probe and aligned runtime endpoint config
   - Prevention for UAT/PROD: verify healthcheck commands against the target image, not against local shell assumptions
4. **Evidence-stage failures after smoke was green**
   - Why it blocked: workflow status remained failed even though the app stack was healthy
   - Why it happened: one step passed a literal shell expression to `psql`, and another assumed `nmap` existed on the runner
   - Fix applied: fixed shell expansion for Postgres defaults and replaced runner-side `nmap` with a host-side read-only `ss` probe over SSH
   - Prevention for UAT/PROD: keep evidence steps shell-safe and dependency-light; test them as part of the workflow, not as an afterthought
5. **Edge auth file unreadable (`500` on `/api/health`)**
   - Why it blocked: SIT smoke failed at liveness check via public edge even though backend container returned `200`
   - Why it happened: nginx could not read `/opt/ledgerflow/secrets/sit/.htpasswd` (`Permission denied`) because file mode was too strict
   - Fix applied: changed workflow provisioning to write `.htpasswd` with mode `644`
   - Prevention for UAT/PROD: for host-level auth files used by nginx, validate runtime read permissions in smoke evidence
6. **Basic Auth mismatch (`401` despite credentials supplied)**
   - Why it blocked: SIT smoke still failed at liveness check with `Expected 200, got 401`
   - Why it happened: active edge credential did not match workflow-provided secret values used in smoke
   - Fix applied: reset `BWCACC_SIT_BASIC_AUTH_USER`/`BWCACC_SIT_BASIC_AUTH_PASS`, reran deploy to regenerate `.htpasswd` deterministically from secrets
   - Prevention for UAT/PROD: keep one canonical secret source for gate auth and re-provision auth artifacts on every deploy run
7. **Review surface routes `/prototype` and `/phase2` returned `404`** (W4 UX approval gate blocker)
   - Why it blocked: W4 UX approval gates could not open — reviewers could not reach the Phase II prototype and timeline pages on SIT
   - Why it happened: `nginx-sit-yahwan.conf` catch-all `location /` forwarded all non-API traffic to the **frontend static container** (port 18180, serving `src/frontend` files only), but `/prototype`, `/phase2`, `/phase2/timeline`, `/phase2/prototype`, `/timeline`, and `/manual` are FastAPI route handlers that only exist in the **backend** (port 18081); the static container had no knowledge of these paths → 404
   - Fix applied: added explicit location blocks for these backend routes **before** `location /` in `deploy/sit-site/nginx-sit-yahwan.conf`; commit `e2e8a51` pushed to `dev`; Openclaw SIT workflow run [28692639601](https://github.com/Piboonsak/Openclaw/actions/runs/28692639601) deployed and verified
   - Also: added `^deploy/` to `ACTION_PATTERNS` in `scripts/min_action_check.py` so future infra changes in `deploy/` are classified as actionable by the pre-commit hook
   - Prevention for UAT/PROD: map out every route served by the application and ensure the edge nginx config has explicit proxy rules for any non-static FastAPI routes before the catch-all

### Completion evidence (2026-07-04 refresh — review surface fixed)

- Review surface routing fix: `Piboonsak/Openclaw` Actions run [28692639601](https://github.com/Piboonsak/Openclaw/actions/runs/28692639601) (commit `e2e8a51`)
- Verification result (2026-07-04):

| Route | HTTP (with auth) | HTTP (no auth) |
|-------|-----------------|----------------|
| `/api/health` | 200 ✅ | 401 ✅ |
| `/api/health/ready` | 200 ✅ | 401 ✅ |
| `/prototype` | 200 ✅ | 401 ✅ |
| `/phase2` | 200 ✅ | 401 ✅ |
| `/phase2/timeline` | 200 ✅ | — |
| `/phase2/prototype` | 200 ✅ | — |
| `/timeline` | 307 → `/phase2/timeline` ✅ | — |
| `/manual` | 200 ✅ | — |

W4 UX approval gates unblocked: all 4 primary acceptance criteria met.

### Manual prerequisites

- DNS A record for `sit.yahwan.biz` to SIT host
- TLS certificate for `sit.yahwan.biz` (Let's Encrypt)
- Basic Auth file provisioned at `/opt/ledgerflow/secrets/sit/.htpasswd`
- GitHub secret required for SIT gate: `BWCACC_SIT_BASIC_AUTH_USER`
- GitHub secret required for SIT gate: `BWCACC_SIT_BASIC_AUTH_PASS`
- Canonical deploy dispatch must be from Openclaw control-plane workflow (`deploy-openclaw-github-private-secrets.yml`)

---

## TASK-1307: Docker Compose — UAT — ✅ DONE (2026-06-21)

**Owner**: DevOps
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-15
**Output**: `docker/docker-compose.uat.yml`, `docker/nginx/nginx-uat.conf`, `docker/.env.uat.example`, `.env.uat` deployed to UAT VPS

### Purpose

สร้าง Docker Compose สำหรับ UAT environment — ให้ client + team ทดสอบได้ก่อน deploy PROD. Environment-specific configs แยก UAT จาก PROD.

SIT note:

- UAT compose should be read as the next environment after SIT parity validation, not as the first shared runtime target
- any UAT-only divergence from SIT should be intentional and documented

### What exists today

- `docker-compose.yml` (dev mode) with backend, postgres, redis, minio
- Dockerfile for backend service
- PoC running on single VPS

### What to build

1. **docker-compose.uat.yml** with all services:
   - nginx (SSL termination, proxy to backend)
   - backend (FastAPI, uvicorn)
   - celery-worker (background processing)
   - celery-beat (scheduled tasks)
   - postgres (PostgreSQL 16)
   - redis (Redis 7)
   - minio (S3-compatible storage)
2. **Environment-specific configs**:
   - DB name: `ledgerflow_uat`
   - API keys via .env.uat (reference only, not committed)
   - Debug mode: on (for UAT troubleshooting)
3. **Volume mounts** for data persistence
4. **Network**: internal Docker network, only nginx exposed

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docker/docker-compose.uat.yml` | UAT Docker Compose configuration |
| Create | `docker/.env.uat.example` | Example environment variables (no secrets) |
| Create | `docker/nginx/nginx-uat.conf` | nginx config for UAT |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1307_01 | `docker compose -f docker-compose.uat.yml up -d` starts all services | All containers in "running" state |
| ac_1307_02 | Health check endpoint returns 200 via nginx | `curl https://uat.bwcacc.biz/api/health` |
| ac_1307_03 | PostgreSQL accessible from backend container | Backend logs show DB connection |
| ac_1307_04 | Redis accessible from celery container | Celery logs show Redis broker connected |
| ac_1307_05 | MinIO accessible from backend container | Upload test file, verify stored |
| ac_1307_06 | Data persists after container restart | Stop + start, verify DB data intact |
| ac_1307_07 | UAT compose assumptions do not bypass mandatory SIT gate | Manual review |

### Governance fields

```json
{
  "task_id": "TASK-1307",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docker/**", "config/**"],
  "forbidden_scope": [".env*", "src/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1308: Docker Compose — PROD — ✅ DONE (2026-06-21)

**Owner**: DevOps
**Risk**: MEDIUM
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-15
**Output**: `docker/docker-compose.prod.yml`, `docker/nginx/nginx-prod.conf`, `docker/.env.prod.example`, `.env.prod` deployed to PROD VPS

### Purpose

PROD Docker Compose ต้อง production-grade — resource limits ป้องกัน OOM, restart policies ให้ service recover อัตโนมัติ, log rotation ไม่ให้ disk เต็ม.

SIT note:

- PROD remains downstream of both SIT and UAT; SIT exists to catch runtime parity issues before they ever reach this task's promotion path

### What exists today

- `docker-compose.uat.yml` (from TASK-1307) — base to fork from
- Dev Docker Compose (no resource limits, no restart policies)

### What to build

1. **docker-compose.prod.yml** with production settings:
   - All services from UAT + production hardening
   - Resource limits per container:
     - backend: 1 CPU, 2GB RAM
     - celery-worker: 1 CPU, 2GB RAM
     - postgres: 1.5 CPU, 4GB RAM
     - redis: 0.5 CPU, 512MB RAM
     - minio: 0.5 CPU, 1GB RAM
     - nginx: 0.25 CPU, 256MB RAM
   - Restart policies: `always` for critical services (backend, postgres, redis, nginx), `on-failure` for workers
   - Log rotation: `max-size: 10m`, `max-file: 5` per container
2. **Production environment**:
   - DB name: `ledgerflow_prod`
   - Debug mode: off
   - Gunicorn with 4 workers (instead of uvicorn dev mode)
3. **Health check** definitions in compose file

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docker/docker-compose.prod.yml` | PROD Docker Compose configuration |
| Create | `docker/.env.prod.example` | Example environment variables (no secrets) |
| Create | `docker/nginx/nginx-prod.conf` | nginx config for PROD (stricter headers) |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1308_01 | PROD compose starts all services | All containers in "running" state |
| ac_1308_02 | Resource limits applied | `docker stats` shows limits enforced |
| ac_1308_03 | Restart policy works | `docker kill backend`, verify auto-restart |
| ac_1308_04 | Log rotation configured | `docker inspect --format='{{.HostConfig.LogConfig}}'` shows limits |
| ac_1308_05 | Health check endpoint returns 200 | `curl https://app.bwcacc.biz/api/health` |
| ac_1308_06 | Gunicorn running with 4 workers | `ps aux | grep gunicorn` shows 4 workers |
| ac_1308_07 | PROD docs preserve SIT -> UAT -> PROD promotion dependency | Manual review |

### Governance fields

```json
{
  "task_id": "TASK-1308",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docker/**", "config/**"],
  "forbidden_scope": [".env*", "src/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1309: Network + Firewall Setup — ✅ DONE (2026-06-21)

**Owner**: DevOps
**Risk**: HIGH
**Duration**: ~3 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-15, PP-16

### Purpose

Lockdown VPS network — only expose necessary ports, block everything else. DB (5432) and MinIO (9000) must NOT be accessible externally. Security-critical task — misconfiguration can expose data.

SIT note:

- The same public-port restriction logic applies to SIT (`sit.yahwan.biz`) even when the host is shared with PoC/demo responsibilities.

### What exists today

- VPS has default firewall (likely allow all or minimal rules)
- No UFW configured
- No SSH access logging

### What to build

1. **UFW firewall rules** (both VPS):
   - Allow: 80 (HTTP), 443 (HTTPS), 22 (SSH from whitelist IPs only)
   - Block: everything else
   - DB port 5432: internal Docker network only
   - MinIO port 9000/9001: internal Docker network only
   - Redis port 6379: internal Docker network only
   - SIT host must follow the same external closure rule for 5432/6379/9000/9001
2. **SSH access logging**:
   - Install auditd for SSH session logging
   - Log: who logged in, when, from where
3. **BAU support flow** documented:
   - How to SSH into VPS
   - How to view logs
   - How to restart services
   - Emergency contacts

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `scripts/infra/setup-firewall.sh` | UFW configuration script |
| Create | `scripts/infra/setup-auditd.sh` | SSH audit logging setup |
| Create | `docs/infrastructure/bau-support.md` | BAU support procedures |
| Create | `docs/infrastructure/firewall-rules.md` | Firewall rules documentation |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1309_01 | UFW active on both VPS | `ufw status` shows active |
| ac_1309_02 | Only ports 80/443/22 open externally | `nmap -Pn host` shows only 80/443/22 |
| ac_1309_03 | PostgreSQL not accessible externally | `nc -zv host 5432` fails from external |
| ac_1309_04 | MinIO not accessible externally | `nc -zv host 9000` fails from external |
| ac_1309_05 | Redis not accessible externally | `nc -zv host 6379` fails from external |
| ac_1309_06 | auditd logging SSH sessions | `ausearch -m LOGIN` shows entries |
| ac_1309_07 | BAU support document complete | Manual review |
| ac_1309_08 | SIT host external port policy documented and verified | Manual review + `nmap` proof |

### Governance fields

```json
{
  "task_id": "TASK-1309",
  "risk_tier": "HIGH",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["scripts/**", "docs/**", "docker/**"],
  "forbidden_scope": [".env*", "src/**"],
  "max_loops": 5,
  "escalation_policy": "stop"
}
```

---

## TASK-1310: DB Backup Automation

> ⏸️ **DEFERRED** — ทำหลัง first successful PROD deploy. R2 credentials ต้องพร้อมก่อน (ดู setup guide ด้านล่าง)

**Owner**: DevOps
**Risk**: MEDIUM
**Duration**: ~2 days
**Closes pain points**: PP-2, PP-3, PP-5, PP-16, PP-17

### Cloudflare R2 Setup Guide (ทำก่อน implement task นี้)

**เมื่อไหร่:** ก่อน first PROD deploy ที่มี real data

**Step 1 — สร้าง R2 Bucket**

1. เข้า [Cloudflare Dashboard → R2](https://dash.cloudflare.com/?to=/:account/r2)
2. **Create bucket** → ชื่อ `ledgerflow-backup`
3. Location: **Asia Pacific (APAC)** — ใกล้ Singapore
4. Default storage class: Standard

**Step 2 — สร้าง R2 API Token**

1. R2 Overview → **Manage R2 API tokens** → **Create API token**
2. Token name: `ledgerflow-vps-backup`
3. Permissions: **Object Read & Write** (scope to bucket `ledgerflow-backup` เท่านั้น)
4. บันทึก 3 ค่า: `Access Key ID`, `Secret Access Key`, `Account ID`

Ref: [Cloudflare R2 API Tokens](https://developers.cloudflare.com/r2/api/s3/tokens/)

**Step 3 — Install rclone บน PROD VPS**

```bash
curl https://rclone.org/install.sh | sudo bash

rclone config create r2 s3 \
  provider Cloudflare \
  access_key_id YOUR_ACCESS_KEY_ID \
  secret_access_key YOUR_SECRET_ACCESS_KEY \
  endpoint https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com \
  acl private

# Test
rclone ls r2:ledgerflow-backup
```

Ref: [rclone + Cloudflare R2](https://rclone.org/s3/#cloudflare-r2)

**Step 4 — เพิ่ม GitHub Secrets**

```bash
gh secret set BWCACC_R2_ACCESS_KEY_ID    --body "YOUR_ACCESS_KEY_ID"
gh secret set BWCACC_R2_SECRET_ACCESS_KEY --body "YOUR_SECRET_ACCESS_KEY"
gh secret set BWCACC_R2_ACCOUNT_ID       --body "YOUR_ACCOUNT_ID"
```

### Purpose

Automated backup ป้องกัน data loss — pg_dump ทุก 6 ชั่วโมง + offsite sync to Cloudflare R2 + LINE alert on failure. RPO: 6hr, RTO: 6hr.

### What exists today

- PostgreSQL running in Docker container (no backup automation)
- No offsite backup
- No backup monitoring/alerting

### What to build

1. **Backup script** (`set -euo pipefail`):
   - pg_dump from Docker postgres container
   - Compress with gzip
   - Filename: `ledgerflow_prod_YYYYMMDD_HHMMSS.sql.gz`
   - Store in `/backup/db/` on VPS
2. **Schedule**: cron every 6 hours (00:00, 06:00, 12:00, 18:00)
3. **Cloudflare R2 offsite sync**:
   - Install rclone
   - Configure R2 remote
   - Sync after each backup
4. **Retention policy**:
   - Local: 7 days (cleanup old backups)
   - R2: 30 days
5. **LINE alert on failure**:
   - Script exits with error → LINE notification
   - Daily success summary (optional)

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `scripts/backup/backup-db.sh` | pg_dump + compress + cleanup |
| Create | `scripts/backup/sync-r2.sh` | rclone sync to Cloudflare R2 |
| Create | `scripts/backup/setup-backup-cron.sh` | Install cron jobs |
| Create | `docs/infrastructure/backup-strategy.md` | Backup strategy + RPO/RTO |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1310_01 | pg_dump runs successfully | Backup file created in `/backup/db/` |
| ac_1310_02 | Backup file compressed with gzip | File ends in `.sql.gz` |
| ac_1310_03 | Cron runs every 6 hours | `crontab -l` shows 0 0,6,12,18 schedule |
| ac_1310_04 | R2 sync works | `rclone ls r2:backup-bucket` shows files |
| ac_1310_05 | Local retention: files older than 7 days cleaned | Old files removed after cleanup |
| ac_1310_06 | LINE alert fires on backup failure | Simulate failure, verify LINE message |
| ac_1310_07 | Backup script uses `set -euo pipefail` | Script inspection |

### Governance fields

```json
{
  "task_id": "TASK-1310",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["scripts/**", "docker/**", "docs/**"],
  "forbidden_scope": [".env*", "src/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1311: Housekeeping

**Owner**: DevOps
**Risk**: LOW
**Duration**: ~1 day
**Closes pain points**: PP-2, PP-3, PP-5, PP-16

### Purpose

ป้องกัน disk full — log rotation, temp file cleanup, disk monitoring. ถ้า disk เต็มจะกระทบ DB writes + backup + all services.

### What exists today

- Docker default logging (no rotation = disk fills up over time)
- No disk monitoring
- Temp files from upload processing not cleaned

### What to build

1. **Docker log rotation** (in compose files):
   - `max-size: 10m`, `max-file: 5` per container
   - Applied via Docker daemon config or per-container
2. **Temp file cleanup**:
   - Clean `/tmp` files older than 24 hours
   - Clean upload staging directory
   - Cron: daily at 03:00
3. **Disk monitoring**:
   - Script checks disk usage
   - Alert via LINE at 80% usage
   - Cron: every 6 hours

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `scripts/infra/housekeeping.sh` | Temp cleanup + disk check |
| Create | `scripts/infra/setup-housekeeping-cron.sh` | Install cron jobs |
| Modify | `docker/docker-compose.prod.yml` | Add log rotation config (if not in TASK-1308) |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1311_01 | Docker log rotation configured | `docker inspect` shows log rotation |
| ac_1311_02 | Temp file cleanup cron runs daily | `crontab -l` shows 03:00 daily entry |
| ac_1311_03 | Disk monitoring alerts at 80% | Simulate 80%+ usage, verify LINE alert |
| ac_1311_04 | Old temp files cleaned | Files older than 24h removed from /tmp staging |

### Governance fields

```json
{
  "task_id": "TASK-1311",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["scripts/**", "docker/**", "docs/**"],
  "forbidden_scope": [".env*", "src/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1312: Go-Live Checklist + Smoke Tests + Restore Drill

**Owner**: DevOps / Full-stack
**Risk**: MEDIUM
**Duration**: ~3 days
**Closes pain points**: PP-5, PP-15, PP-16, PP-17

### Purpose

Go-live readiness validation — ทุกอย่างต้องทำงานจริงก่อนเปิด PROD ให้ลูกค้า. Restore drill พิสูจน์ว่า backup ใช้งานได้จริง (ไม่ใช่แค่ "backup runs" แต่ "restore works").

### What exists today

- Playwright installed (used for existing tests)
- Some smoke test patterns from PoC
- Backup script from TASK-1310 (not yet tested restore)

### What to build

1. **Pre-go-live checklist**:
   - Security: SSH hardened, firewall active, SSL valid
   - Backup: pg_dump running, R2 sync working, restore tested
   - Monitoring: health check, disk alerts, backup alerts
   - DNS: all subdomains resolve, SSL valid
   - CI/CD: deploy workflows tested
   - App: all features work E2E
2. **Playwright E2E smoke tests**:
   - Login → upload document → process → review extracted data → export
   - Health check endpoints
   - Error handling (invalid file, oversized file)
3. **Restore drill**:
   - Download backup from R2
   - Restore to separate DB instance
   - Verify data integrity (row counts, spot checks)
   - Document restore procedure + time taken
4. **Performance baseline**:
   - p95 response times for key endpoints
   - Document processing throughput (docs/minute)
   - DB query performance

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docs/go-live/checklist.md` | Pre-go-live checklist |
| Create | `tests/e2e/smoke-test.spec.ts` | Playwright E2E smoke tests |
| Create | `scripts/backup/restore-drill.sh` | Restore drill script |
| Create | `docs/go-live/performance-baseline.md` | p95 response times + throughput |
| Create | `docs/go-live/restore-drill-report.md` | Restore drill results |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1312_01 | Pre-go-live checklist complete (all items checked) | Manual review |
| ac_1312_02 | Playwright smoke tests pass on UAT | `npx playwright test smoke-test.spec.ts` passes |
| ac_1312_03 | Restore drill succeeds | Data restored, row counts match |
| ac_1312_04 | Restore time documented | RTO within 6hr target |
| ac_1312_05 | Performance baseline documented | p95 response times for key endpoints |
| ac_1312_06 | Login → upload → process → review → export flow works E2E | Playwright test passes |

### Governance fields

```json
{
  "task_id": "TASK-1312",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["tests/**", "scripts/**", "docs/**", "docker/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-1313: CI/CD Migration — Openclaw as CD Hub

> ⏸️ **STANDBY** — รอ 2026-06-24 ถ้า YAHWAN-SHOP billing ยังไม่ resolve ให้ execute migration plan นี้

**Owner**: DevOps
**Risk**: MEDIUM
**Deadline trigger**: 2026-06-24 (3 วันหลังพบปัญหา 2026-06-21)
**Closes pain points**: CI/CD startup_failure, secrets management

### Background / Problem

YAHWAN-SHOP org มีปัญหา billing ทำให้ GitHub Actions ทุก workflow ใน `ai-accounting-copilot` repo ได้รับ `startup_failure` (0 jobs created) ตั้งแต่ 2026-06-11 พยายามแก้ billing แล้ว 10+ ครั้ง ยังไม่ผ่าน

**Root cause confirmed:** Banner ใน GitHub repo settings แสดง *"We have a problem billing the YAHWAN-SHOP organization"* → Actions ถูก block ทั้ง org

**Current workaround:** Deploy ด้วย SSH manual (ทำ first deploy UAT + PROD สำเร็จแล้ว 2026-06-21)

### Target Architecture

```
push uat/main branch
YAHWAN-SHOP/ai-accounting-copilot  ← source code only, no deploy secrets
        │
        │  git post-push hook (local, curl)  ← ไม่ต้องใช้ YAHWAN-SHOP Actions เลย
        ▼
Piboonsak/Openclaw
├── deploy-ai-accounting-copilot-uat.yml   ← trigger: repository_dispatch + workflow_dispatch
└── deploy-ai-accounting-copilot-prod.yml  ← trigger: workflow_dispatch + manual approve
        │
        │  checkout YAHWAN-SHOP/ai-accounting-copilot@sha
        │  SSH → docker compose → alembic upgrade head
        ▼
UAT VPS (72.62.74.232) / PROD VPS (72.62.247.9)
```

**Branch mapping:**
- push `uat` → auto-deploy UAT (via post-push hook → dispatch)
- push `main` → manual approve ก่อน deploy PROD

### Migration Steps (เรียงลำดับ execute)

**Step 1 — สร้าง deploy workflows ใน Openclaw**

| Action | File (Piboonsak/Openclaw) | What |
|--------|--------------------------|------|
| Create | `.github/workflows/deploy-ai-accounting-copilot-uat.yml` | Clone จาก `deploy-ai-accounting-copilot-poc.yml` ปรับ target branch/VPS |
| Create | `.github/workflows/deploy-ai-accounting-copilot-prod.yml` | เพิ่ม environment approval + pre-deploy snapshot |

**Step 2 — ย้าย secrets จาก YAHWAN-SHOP → Openclaw**

Secrets ที่ต้องเพิ่มใน `Piboonsak/Openclaw`:
```
BWCACC_UAT_HOST       = 72.62.74.232
BWCACC_PROD_HOST      = 72.62.247.9
BWCACC_DEPLOY_USER    = deploy
BWCACC_VPS_SSH_KEY    = (private key ของ ~/.ssh/id_ed25519_hostinger)
BWCACC_LINE_CHANNEL_ACCESS_TOKEN  = (จาก YAHWAN-SHOP secrets เดิม)
BWCACC_LINE_USER_ID               = (จาก YAHWAN-SHOP secrets เดิม)
```
หมายเหตุ: `OPENROUTER_API_KEY` และ `ANTHROPIC_API_KEY` มีอยู่ใน Openclaw แล้ว

**Step 3 — ตั้ง git post-push hook บน developer machine**

```bash
# ไฟล์: .git/hooks/post-push  (ไม่ commit เข้า repo)
#!/bin/bash
BRANCH=$(git rev-parse --abbrev-ref HEAD)
SHA=$(git rev-parse HEAD)
PAT="${OPENCLAW_DISPATCH_PAT}"  # ตั้งใน ~/.bashrc หรือ ~/.zshrc

if [[ "$BRANCH" == "uat" ]]; then
  echo "→ Triggering UAT deploy in Openclaw..."
  curl -sf -X POST \
    -H "Authorization: Bearer ${PAT}" \
    -H "Accept: application/vnd.github+json" \
    https://api.github.com/repos/Piboonsak/Openclaw/dispatches \
    -d "{\"event_type\":\"deploy-aiacc-uat\",\"client_payload\":{\"sha\":\"${SHA}\",\"ref\":\"uat\"}}"
  echo "→ Deploy triggered (Openclaw Actions will notify via LINE)"
fi
```

**Step 4 — Cleanup YAHWAN-SHOP workflows**

หลัง Openclaw CD ทำงานแล้ว ให้ remove ออกจาก `ai-accounting-copilot`:
- ลบ `.github/workflows/bwcacc-deploy-uat.yml`
- ลบ `.github/workflows/bwcacc-deploy-prod.yml`
- คง `.github/workflows/ci.yml` (tests/lint) ไว้ — จะ run ได้เองเมื่อ billing ถูกแก้

**Step 5 — Transfer repo (ถ้า YAHWAN-SHOP ยังมีปัญหา billing ต่อ)**

ถ้า billing ไม่ resolve ภายใน 1 สัปดาห์ ให้ transfer repo:
```
YAHWAN-SHOP/ai-accounting-copilot → Piboonsak/ai-accounting-copilot
```
- Settings → General → Danger Zone → Transfer repository
- GitHub redirect URL เก่าให้ temporary
- Update VPS git remote URL หลัง transfer

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_1313_01 | push uat → Openclaw deploy workflow triggers ใน 60s | Check Openclaw Actions tab |
| ac_1313_02 | UAT deploy สำเร็จ (health check 200) | `curl https://uat.bwcacc.biz/api/health` |
| ac_1313_03 | PROD deploy ต้อง manual approve ก่อนรัน | Workflow ค้างรอ approval |
| ac_1313_04 | ไม่มี deploy secrets ใน YAHWAN-SHOP repo | `gh secret list -R YAHWAN-SHOP/ai-accounting-copilot` — ไม่มี SSH_KEY, VPS_HOST |
| ac_1313_05 | LINE notification ส่งเมื่อ deploy success/fail | ตรวจสอบ LINE message |

### Governance fields

```json
{
  "task_id": "TASK-1313",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": [".github/workflows/**", "scripts/**", "docs/**"],
  "forbidden_scope": [".env*", "src/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

*Created: 2026-06-15*
*Updated: 2026-06-22 — added TASK-1313 CI/CD migration plan*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
