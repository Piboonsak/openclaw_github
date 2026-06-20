# Epic 13 — Infrastructure + Deployment

**Goal**: Hostinger VPS all-in — UAT + PROD environments, DNS bwc.biz subdomains, CI/CD automation, backup offsite R2, firewall, monitoring — ทำ parallel กับ development ตลอด 8 สัปดาห์

## Documentation

- **[EPIC-13-TASKS-DETAIL.md](EPIC-13-TASKS-DETAIL.md)** — full design for all tasks with ACs, schemas, governance fields

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
| TASK-1301 | VPS Architecture Design | M | New | PP-2, PP-3, PP-5 |
| TASK-1302 | VPS Procurement — UAT + PROD | S | New | PP-2, PP-5 |
| TASK-1303 | Base OS setup + Docker Engine + security hardening | M | New | PP-2, PP-3, PP-5, PP-15 |
| TASK-1304 | DNS delegation + Certbot SSL | M | New | PP-2, PP-3, PP-5, PP-15 |
| TASK-1305 | CI/CD Pipeline Design | M | New | PP-2, PP-3, PP-5, PP-15, PP-16 |
| TASK-1306 | CI/CD Pipeline Implementation | L | New | PP-5, PP-8, PP-15, PP-16, PP-17 |
| TASK-1307 | Docker Compose — UAT | M | New | PP-2, PP-3, PP-5, PP-15 |
| TASK-1308 | Docker Compose — PROD | M | New | PP-2, PP-3, PP-5, PP-15 |
| TASK-1309 | Network + Firewall Setup | M | New | PP-2, PP-3, PP-5, PP-15, PP-16 |
| TASK-1310 | DB Backup Automation | M | New | PP-2, PP-3, PP-5, PP-16, PP-17 |
| TASK-1311 | Housekeeping | S | New | PP-2, PP-3, PP-5, PP-16 |
| TASK-1312 | Go-Live Checklist + Smoke Tests + Restore Drill | M | New | PP-5, PP-15, PP-16, PP-17 |

## Dependencies

- **Upstream**: Epic 8 (TASK-801 DB integration — needed for Docker Compose service definitions), Epic 12 (TASK-1201 Login — needed for E2E smoke tests)
- **Downstream**: All epics depend on infra for deployment — UAT deploy gates W6, PROD deploy gates W8

## Execution order

```text
W1 Day 1-2:  TASK-1301 — VPS Architecture Design (design first, build later)
W1 Day 3-5:  TASK-1302 — VPS Procurement (order KVM instances while designing)
W1-2:        TASK-1303 — Base OS setup + Docker Engine + hardening (both VPS)
W2:          TASK-1304 — DNS delegation + Certbot SSL (parallel with OS setup)
W2-3:        TASK-1305 — CI/CD Pipeline Design (design workflows)
W3-4:        TASK-1306 — CI/CD Pipeline Implementation (deploy-uat.yml, deploy-prod.yml)
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
4. DNS subdomains (app.bwc.biz, uat.bwc.biz, demo.bwc.biz) resolve, SSL certificates valid, auto-renew configured
5. CI/CD design document with workflow diagrams and PROD safety rules
6. GitHub Actions deploy workflows functional — push to uat triggers UAT deploy, merge to main triggers PROD deploy
7. UAT Docker Compose starts all services, health check passes
8. PROD Docker Compose starts all services with resource limits, restart policies, log rotation
9. UFW firewall active — only ports 80/443/22 exposed, DB/MinIO not accessible externally
10. pg_dump runs every 6 hours, syncs to Cloudflare R2, LINE alert on failure
11. Log rotation configured, disk monitoring alerts at 80%, temp file cleanup automated
12. Go-live checklist complete, Playwright E2E smoke tests pass, restore drill succeeds, performance baseline documented

## Discussion Prompts

1. **VPS sizing**: UAT KVM 2 (2 vCPU, 8GB) เพียงพอสำหรับ testing + client UAT review ไหม? หรือ KVM 1 พอ (ประหยัดค่า hosting)?
2. **Backup frequency**: pg_dump ทุก 6 ชั่วโมง (RPO 6hr) เพียงพอไหม? ธุรกิจบัญชีสำคัญเรื่อง data loss มาก — ควรเป็นทุก 1 ชั่วโมงไหม?
3. **DNS delegation**: ต้องขอ DNS delegation จาก bwc.biz admin — กี่วันจะได้? ถ้าล่าช้าจะกระทบ SSL setup + deployment timeline
4. **Restore drill**: ทำ restore drill ครั้งเดียว (W7) พอไหม? หรือควรทำ quarterly post-go-live?
5. **PROD safety rules**: merge to main triggers PROD deploy — ต้องมี manual approval step ใน GitHub Actions ไหม? หรือ auto-deploy เลย (เพราะมี UAT gate อยู่แล้ว)?
6. **Monitoring**: W1-8 ยังไม่มี Sentry (Epic 16) — ช่วง go-live ใช้ Docker logs + health check endpoint พอไหม? หรือต้อง setup basic monitoring ก่อน?

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
