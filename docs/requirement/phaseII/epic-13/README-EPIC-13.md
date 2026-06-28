# Epic 13 — Infrastructure + Deployment

**Goal**: Hostinger VPS all-in — UAT + PROD environments, DNS bwcacc.biz subdomains, CI/CD automation, backup offsite R2, firewall, monitoring — ทำ parallel กับ development ตลอด 8 สัปดาห์

## Documentation

- **[EPIC-13-TASKS-DETAIL.md](EPIC-13-TASKS-DETAIL.md)** — full design for all tasks with ACs, schemas, governance fields
- **[INFRA-PREREQUISITES-RUNBOOK.md](INFRA-PREREQUISITES-RUNBOOK.md)** — DNS/SSL/VPS 8-gate runbook (team-managed)
- **[INFRA-PREREQUISITES-CHECKLIST.html](INFRA-PREREQUISITES-CHECKLIST.html)** — interactive pre-deploy checklist (browser-based)

## At a glance

| Aspect | Details |
|--------|---------|
| Lead | DevOps / Backend Dev |
| Duration | ~2 weeks effort (spread across W1-W8, parallel with dev) |
| Status | Design |
| Critical path | **No** — runs parallel, but blocks deployment milestones (UAT W6, PROD W8) |
| Week | W1-W8 (parallel) |
| Phase | II/1 |

## Task overview

| Task | Title | Complexity | Status | Pain points closed |
|------|-------|-----------|--------|-------------------|
| TASK-1301 | VPS Architecture Design | M | ✅ **Done** | PP-2, PP-3, PP-5 |
| TASK-1302 | VPS Procurement — UAT + PROD | S | ✅ **Done** | PP-2, PP-5 |
| TASK-1303 | Base OS setup + Docker Engine + security hardening | M | ✅ **Done** | PP-2, PP-3, PP-5, PP-15 |
| TASK-1304 | DNS delegation + Certbot SSL | M | ✅ **Done** | PP-2, PP-3, PP-5, PP-15 |
| TASK-1305 | CI/CD Pipeline Design | M | ✅ **Done** | PP-2, PP-3, PP-5, PP-15, PP-16 |
| TASK-1306 | CI/CD Pipeline Implementation | L | New | PP-5, PP-8, PP-15, PP-16, PP-17 |
| TASK-1306A | SIT Environment with Real Runtime Services | L | ✅ **Done** (2026-06-28) | PP-2, PP-5, PP-8, PP-15, PP-16, PP-17 |
| TASK-1307 | Docker Compose — UAT | M | New | PP-2, PP-3, PP-5, PP-15 |
| TASK-1308 | Docker Compose — PROD | M | New | PP-2, PP-3, PP-5, PP-15 |
| TASK-1309 | Network + Firewall Setup | M | ✅ **Done** | PP-2, PP-3, PP-5, PP-15, PP-16 |
| TASK-1310 | DB Backup Automation | M | New | PP-2, PP-3, PP-5, PP-16, PP-17 |
| TASK-1311 | Housekeeping | S | New | PP-2, PP-3, PP-5, PP-16 |
| TASK-1312 | Go-Live Checklist + Smoke Tests + Restore Drill | M | New | PP-5, PP-15, PP-16, PP-17 |

## Dependencies

- **Upstream**: Epic 8 (`TASK-801A` schema slice + `TASK-801B` DB integration — needed for service/runtime definitions), Epic 12 (TASK-1201 Login — needed for E2E smoke tests)
- **Downstream**: All epics depend on infra for deployment — UAT deploy gates W6, PROD deploy gates W8

## Execution order

```text
W1 Day 1-2:  TASK-1301 — VPS Architecture Design (design first, build later)
W1 Day 3-5:  TASK-1302 — VPS Procurement (order KVM instances while designing)
W1-2:        TASK-1303 — Base OS setup + Docker Engine + hardening (both VPS)
W2:          TASK-1304 — DNS delegation + Certbot SSL (parallel with OS setup)
W2-3:        TASK-1305 — CI/CD Pipeline Design (design workflows)
W3-4:        TASK-1306 — CI/CD Pipeline Implementation (deploy-uat.yml, deploy-prod.yml)
W4:          TASK-1306A — SIT Runtime Gate (sit.yahwan.biz, smoke + security boundary)
W4:          TASK-1307 — Docker Compose UAT (deploy UAT environment)
W5:          TASK-1308 — Docker Compose PROD (deploy PROD environment)
W5-6:        TASK-1309 — Network + Firewall Setup (lockdown before go-live)
W6:          TASK-1310 — DB Backup Automation (pg_dump + R2 offsite)
W6:          TASK-1311 — Housekeeping (log rotation, disk monitoring)
W7-8:        TASK-1312 — Go-Live Checklist + Smoke Tests + Restore Drill
```

## Definition of Done

1. VPS architecture document with service topology diagram, resource sizing justified
2. Both VPS instances (UAT KVM 2, PROD KVM 4) accessible via SSH, Singapore DC confirmed
3. Docker Engine + Docker Compose installed, SSH key-only auth, fail2ban active, root SSH disabled
4. DNS subdomains (app.bwcacc.biz, uat.bwcacc.biz, demo.bwcacc.biz) resolve, SSL certificates valid, auto-renew configured
5. CI/CD design document with workflow diagrams and PROD safety rules
6. GitHub Actions deploy workflows functional — push to uat triggers UAT deploy, merge to main triggers PROD deploy
7. UAT Docker Compose starts all services, health check passes
8. PROD Docker Compose starts all services with resource limits, restart policies, log rotation
9. UFW firewall active — only ports 80/443/22 exposed, DB/MinIO not accessible externally
10. pg_dump runs every 6 hours, syncs to Cloudflare R2, LINE alert on failure
11. Log rotation configured, disk monitoring alerts at 80%, temp file cleanup automated
12. Go-live checklist complete, Playwright E2E smoke tests pass, restore drill succeeds, performance baseline documented
13. SIT environment (`sit.yahwan.biz`) validated with real runtime services and gate evidence before UAT promotion

## SIT Rollout Update (2026-06-28)

- Final green control-plane run: `Piboonsak/Openclaw` Actions run `28332426427`
- Final result: deploy, smoke, DB/Redis/MinIO runtime evidence, HTTP gate evidence, network exposure evidence, and artifact upload all passed
- Task status impact: `TASK-1306A` can now be treated as complete for `dev -> uat` promotion planning

### Lessons learned for next planning pass

1. SSH reachability from GitHub runners to the SIT host was intermittent even when manual SSH from operator machines worked. The workflow must include bounded SSH preflight retries instead of assuming one-shot connectivity.
2. SIT runtime keys were missing in the control-plane workflow path. Readiness stayed degraded until `OPENROUTER_API_KEY`, `BWCACC_OPENROUTER_API_KEY`, and `OPENAI_API_KEY` were injected into the live SIT env.
3. MinIO health and readiness depended on valid URL-style endpoints. `minio:9000` was not accepted by the backend storage client; `http://minio:9000` was required.
4. Evidence steps must avoid runner-only tooling assumptions. `nmap` was not present on the runner, so the public-port proof had to move to a read-only host-side `ss` probe over SSH.

### UAT/PROD prevention rules

1. Reuse the same control-plane env injection pattern for UAT/PROD before the first gated deploy. Do not assume runtime LLM/storage secrets already exist on the target host.
2. Keep healthchecks image-native. If a container image does not include `wget`/`curl`/`nc`, use a healthcheck that matches binaries guaranteed by the image.
3. Treat URL-vs-host endpoint shape as a deployment invariant. Storage endpoints must be validated in example env files and rewritten env files before promotion.
4. Keep evidence probes dependency-light. Prefer `curl`, `ss`, `docker compose exec`, and in-container checks over extra packages that may be absent on runners.

## DNS/Registrar Design Review (2026-06-20)

**Decision: CONDITIONAL_GO** — weighted risk score 2.275 / 5.0

### Current Architecture (updated 2026-06-21)

| Component | Value |
|-----------|-------|
| Domain | `bwcacc.biz` — registered on Hostinger directly |
| DNS Zone Management | Hostinger REST API (`developers.hostinger.com`) |
| VPS (PoC) | Hostinger KVM 4, IP `76.13.210.250` → `demo.bwcacc.biz` |
| VPS (UAT) | Hostinger KVM 2, IP `72.62.74.232` → `uat.bwcacc.biz` |
| VPS (PROD) | Hostinger KVM 4, IP `72.62.247.9` → `app.bwcacc.biz` |
| SSL | Let's Encrypt via certbot (standalone) — UAT + PROD certs issued, expires 2026-09-18 |
| Ops Model | Internal team executes all DNS/SSL changes |

### Risk Scorecard

| Category | Score | Weight | Weighted |
|----------|-------|--------|----------|
| Availability | 2.5 | 0.20 | 0.50 |
| Security | 2.5 | 0.20 | 0.50 |
| Change Safety | 2.0 | 0.15 | 0.30 |
| Recoverability | 2.5 | 0.15 | 0.375 |
| Operational Complexity | 2.0 | 0.10 | 0.20 |
| Vendor Dependency | 2.0 | 0.10 | 0.20 |
| Certificate Lifecycle | 2.0 | 0.10 | 0.20 |
| **Total** | | | **2.275** |

### Blocking Conditions (must close before go-live)

| # | Item | Effort | Owner |
|---|------|--------|-------|
| 1 | Add CAA record: `0 issue "letsencrypt.org"` in Hostinger hPanel | 10 min | DevOps |
| 2 | Create `deploy` user, disable root SSH login | 1-2 hrs | DevOps |
| 3 | Add cert expiry monitoring (Uptime Kuma HTTPS check or cron) | 1 hr | DevOps |
| 4 | Set A record TTL = 300s for rollback readiness | 10 min | DevOps |
| 5 | Export DNS zone backup → `infra/dns-zone-backup.txt` | 10 min | DevOps |

### Post-Go-Live Hardening (30-60 days)

| # | Item | Target |
|---|------|--------|
| 1 | Migrate DNS to Cloudflare (free plan) for Anycast + DDoS protection | D+30 |
| 2 | Enable DNSSEC (Cloudflare + DS record at Hostinger) | D+45 |
| 3 | Setup Uptime Kuma → LINE Notify alerts | D+14 |
| 4 | Document DNS change procedure with approval flow | D+30 |
| 5 | Establish monthly security audit schedule | D+60 |

### Recommendation

**Keep** current Hostinger DNS + certbot setup for go-live. **Migrate** DNS to Cloudflare post-launch (Week 2-4). Rationale: `bwcacc.biz` is now on Hostinger directly (no Squarespace dependency) — DNS management is simpler. big-bang DNS migration before go-live increases risk (NS propagation 24-48h, cert reissuance needed). Current setup is functional for initial small user base.

---

## Discussion Prompts

1. **VPS sizing**: UAT KVM 2 (2 vCPU, 8GB) เพียงพอสำหรับ testing + client UAT review ไหม? หรือ KVM 1 พอ (ประหยัดค่า hosting)?
2. **Backup frequency**: pg_dump ทุก 6 ชั่วโมง (RPO 6hr) เพียงพอไหม? ธุรกิจบัญชีสำคัญเรื่อง data loss มาก — ควรเป็นทุก 1 ชั่วโมงไหม?
3. **DNS (self-managed)**: `bwcacc.biz` จดบน Hostinger โดยตรง — จัดการ DNS ผ่าน Hostinger REST API ไม่มี external dependency ไม่กระทบ timeline (A records + CAA ✅ DONE 2026-06-21)
4. **Restore drill**: ทำ restore drill ครั้งเดียว (W7) พอไหม? หรือควรทำ quarterly post-go-live?
5. **PROD safety rules**: merge to main triggers PROD deploy — ต้องมี manual approval step ใน GitHub Actions ไหม? หรือ auto-deploy เลย (เพราะมี UAT gate อยู่แล้ว)?
6. **Monitoring**: W1-8 ยังไม่มี Sentry (Epic 16) — ช่วง go-live ใช้ Docker logs + health check endpoint พอไหม? หรือต้อง setup basic monitoring ก่อน?

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
