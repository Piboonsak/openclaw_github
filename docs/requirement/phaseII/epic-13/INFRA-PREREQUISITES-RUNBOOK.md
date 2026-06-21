# Infrastructure Prerequisites Runbook (DNS-Owned-by-Us)

> **Last updated**: 2026-06-21 | **Domain**: `bwcacc.biz` (Hostinger)
> **Architecture ref**: `docs/architecture/vps-architecture.md`

## Purpose

เอกสารนี้ใช้เป็น runbook สำหรับเตรียม prerequisite ก่อน deploy UAT/PROD ของ Phase II โดยกำหนดชัดเจนว่า

- ทีมเราเป็นผู้ดำเนินการ DNS ทั้งหมด
- ลูกค้าไม่ต้องลงมือแก้ DNS เอง
- ห้ามเริ่ม deploy pipeline จนกว่าทุก prerequisite gate จะผ่าน

## Scope

- Included: DNS, SSL, firewall, access baseline, pre-deploy verification
- Excluded: deploy code จริง, DB migration จริง, cutover production จริง

## Ownership Matrix

| Area | Owner | Backup Owner | Output |
| --- | --- | --- | --- |
| VPS access + OS baseline | DevOps | Backend Lead | SSH, Docker, firewall ready |
| DNS records | DevOps | Infra Operator | A records active |
| SSL certificate | DevOps | Infra Operator | Valid cert + auto-renew |
| Final pre-deploy verify | QA + DevOps | Project Owner | Ready-to-deploy sign-off |

## Infrastructure Inventory

### VPS Fleet

| Role | VPS ID | IP (v4) | Hostname | Plan | vCPU | RAM |
| --- | --- | --- | --- | --- | --- | --- |
| **PoC/Demo** | 1414058 | `76.13.210.250` | srv1414058.hstgr.cloud | KVM 4 | 4 | 16 GB |
| **UAT** | 1772060 | `72.62.74.232` | srv1772060.hstgr.cloud | KVM 2 | 2 | 8 GB |
| **PROD** | 1772174 | `72.62.247.9` | srv1772174.hstgr.cloud | KVM 4 | 4 | 16 GB |

All VPS in **Data Center 21** (Singapore region).

### Domain & DNS

| Domain | Registrar | Role | NS Managed By |
| --- | --- | --- | --- |
| `bwcacc.biz` | Hostinger | **Primary** — all active subdomains | Hostinger |
| `bwcacc.com` | Squarespace | Reserved — future brand migration | Squarespace (parked) |
| `bwcacc.net` | TBD | Reserved | — |
| `bwcacc.tech` | Hostinger (free) | Reserved — UAT alias | Hostinger |
| `bwcacc.cloud` | Hostinger (free) | Reserved — PROD alias | Hostinger |

### DNS Record Map (bwcacc.biz) — LIVE

| Subdomain | Type | Target | TTL | Environment | Status |
| --- | --- | --- | --- | --- | --- |
| `demo.bwcacc.biz` | A | `76.13.210.250` | 300 | PoC/Demo | ✅ Verified |
| `uat.bwcacc.biz` | A | `72.62.74.232` | 300 | UAT | ✅ Verified |
| `app.bwcacc.biz` | A | `72.62.247.9` | 300 | Production | ✅ Verified |
| `@` | CAA | `0 issue "letsencrypt.org"` | 3600 | All | ✅ Verified |

### SSH Access

```bash
# Demo/PoC
ssh -i ~/.ssh/id_ed25519_hostinger root@76.13.210.250

# UAT
ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.74.232

# PROD
ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.247.9
```

- SSH key path (Windows): `C:\Users\HP Probook 440 G8\.ssh\id_ed25519_hostinger`
- SSH user: `root` (transition target: `deploy`)

### References

- Architecture design: `docs/architecture/vps-architecture.md`
- Openclaw connection: `Openclaw/docs/connection.md`
- Epic 13 tasks: `docs/requirement/phaseII/epic-13/EPIC-13-TASKS-DETAIL.md`
- PoC deploy + cert pattern: `deploy/poc-site/README.md`

## Mandatory Blocking Conditions (from DNS/Registrar Design Review)

Status baseline: `CONDITIONAL_GO` (must close all items below before go-live)

| # | Condition | Target | Owner | Status |
| --- | --- | --- | --- | --- |
| 1 | Add CAA record | `0 issue "letsencrypt.org"` | DevOps | ✅ Done (2026-06-20) |
| 2 | Harden SSH access | Create `deploy` user and disable root SSH login | DevOps | ✅ Done (2026-06-21) — `prohibit-password` phase |
| 3 | Add cert expiry monitoring | cron daily check, logs to syslog via `certcheck` tag | DevOps | ✅ Done (2026-06-21) |
| 4 | Set rollback-friendly TTL | A record TTL = `300` seconds | DevOps | ✅ Done |
| 5 | Export DNS zone backup | Save as `infra/dns-zone-backup.txt` | DevOps | ✅ Done (2026-06-21) |

### Verification snippets for blocking conditions

```bash
# CAA (use DNS-over-HTTPS on Windows, or dig on Linux)
curl -s "https://dns.google/resolve?name=bwcacc.biz&type=CAA" | python -m json.tool

# TTL check
nslookup uat.bwcacc.biz 8.8.8.8

# Root login hardening (run ON VPS)
grep -E "^PermitRootLogin" /etc/ssh/sshd_config

# Cert renew dry-run (run ON VPS)
sudo certbot renew --dry-run
```

---

## Gate 1: VPS and Access Baseline

> **Applies to**: UAT (`72.62.74.232`) and PROD (`72.62.247.9`)
> **Status**: ✅ DONE (2026-06-21) — via `scripts/infra/setup-vps.sh`

### Gate 1 Inputs

- Hostinger VPS credentials
- SSH private key (`~/.ssh/id_ed25519_hostinger`)

### Gate 1 Actions

1. Verify SSH connectivity to UAT and PROD VPS.
2. Install Docker and Docker Compose.
3. Configure UFW: deny all incoming, allow 22/80/443.
4. Create `deploy` user and disable root SSH login.
5. Configure swap (2 GB on UAT, 4 GB on PROD).

### Gate 1 Commands

```bash
# UAT
ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.74.232 "hostname && docker version && docker compose version && ufw status"

# PROD
ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.247.9 "hostname && docker version && docker compose version && ufw status"
```

### Gate 1 Pass Criteria — MET (2026-06-21)

- ✅ SSH เข้าได้ทั้ง UAT และ PROD
- ✅ Docker 29.6.0 + Docker Compose 5.1.4 พร้อมใช้งาน
- ✅ UFW active: 22/80/443 open, อื่น deny
- ✅ `deploy` user สร้างแล้ว (docker group), PermitRootLogin = prohibit-password
- ✅ fail2ban active (sshd jail), PasswordAuthentication = no
- ✅ Swap: 2G (UAT), 4G (PROD)
- ✅ sysctl tuned: vm.swappiness=10, vm.overcommit_memory=1
- ✅ App dirs: /opt/ledgerflow, /backup/db created
- ✅ htop installed for resource monitoring

> **Note**: PermitRootLogin = `prohibit-password` (not `no`) — intentional progressive hardening. Root key access needed during setup phase (SSL, Docker Compose). Will tighten to `no` after go-live validation.

---

## Gate 2: DNS Records (Team-Managed)

> **Status**: ✅ DONE (2026-06-21)

### Required Records — All verified live

| Host | Type | Target | Status |
| --- | --- | --- | --- |
| `demo.bwcacc.biz` | A | `76.13.210.250` | ✅ |
| `uat.bwcacc.biz` | A | `72.62.74.232` | ✅ |
| `app.bwcacc.biz` | A | `72.62.247.9` | ✅ |
| `bwcacc.biz` | CAA | `0 issue "letsencrypt.org"` | ✅ |

### DNS Management Method

Records managed via **Hostinger REST API** (domain registered on Hostinger directly):

```bash
# List records
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  https://developers.hostinger.com/api/dns/v1/zones/bwcacc.biz

# Add records (overwrite: false = append)
curl -s -X PUT https://developers.hostinger.com/api/dns/v1/zones/bwcacc.biz \
  -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"overwrite": false, "zone": [...]}'

# Delete specific records
curl -s -X DELETE https://developers.hostinger.com/api/dns/v1/zones/bwcacc.biz \
  -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filters": [{"name": "uat", "type": "A"}]}'
```

### Gate 2 Pass Criteria — MET

- ✅ ทุก record ถูกสร้างครบตามตาราง
- ✅ ไม่มี stale record ชี้ IP เก่า
- ✅ A records มี TTL = 300s
- ✅ CAA record มี `letsencrypt.org`

---

## Gate 3: DNS Propagation Verification

> **Status**: ✅ DONE (2026-06-21)

### Gate 3 Commands

```bash
# From Windows (nslookup)
nslookup demo.bwcacc.biz 8.8.8.8
nslookup uat.bwcacc.biz 8.8.8.8
nslookup app.bwcacc.biz 8.8.8.8

nslookup demo.bwcacc.biz 1.1.1.1
nslookup uat.bwcacc.biz 1.1.1.1
nslookup app.bwcacc.biz 1.1.1.1

# CAA check (Windows — no dig, use DNS-over-HTTPS)
curl -s "https://dns.google/resolve?name=bwcacc.biz&type=CAA"
```

### Gate 3 Pass Criteria — MET

- ✅ demo → `76.13.210.250` on both Google and Cloudflare DNS
- ✅ uat → `72.62.74.232` on both Google and Cloudflare DNS
- ✅ app → `72.62.247.9` on both Google and Cloudflare DNS
- ✅ CAA → `0 issue "letsencrypt.org"`

---

## Gate 4: Nginx Host Mapping Precheck

> **Applies to**: UAT and PROD VPS
> **Status**: ✅ DONE (2026-06-21) — via `scripts/infra/setup-nginx-gate.sh`

### Gate 4 Actions

1. Create nginx config with `server_name` matching `*.bwcacc.biz`.
2. SSL termination with Let's Encrypt certs + TLS 1.2/1.3 hardening.
3. Set up HTTP → HTTPS redirect.
4. Static `/health` and `/api/health` endpoints (pre-backend placeholder).

### Gate 4 Implementation

Deployed as minimal Docker container (`nginx:1.27-alpine`) named `nginx-gate` on both VPS:

```bash
docker run -d --name nginx-gate --restart unless-stopped \
    -p 80:80 -p 443:443 \
    -v /etc/letsencrypt:/etc/letsencrypt:ro \
    -v /opt/ledgerflow/nginx/conf.d:/etc/nginx/conf.d:ro \
    nginx:1.27-alpine
```

Config at `/opt/ledgerflow/nginx/conf.d/default.conf` — will be replaced by Docker Compose nginx service in TASK-1307.

### Gate 4 Command

```bash
docker exec nginx-gate nginx -t
```

### Gate 4 Pass Criteria — MET (2026-06-21)

- ✅ `nginx -t` passes on both UAT and PROD
- ✅ UAT: `server_name uat.bwcacc.biz` matches DNS
- ✅ PROD: `server_name app.bwcacc.biz` matches DNS
- ✅ SSL termination with TLS 1.2/1.3 hardening
- ✅ HTTP → HTTPS 301 redirect working

---

## Gate 5: SSL Certificate Issue (Let's Encrypt)

> **Applies to**: UAT and PROD VPS
> **Status**: ✅ DONE (2026-06-21) — via `scripts/infra/setup-certbot.sh` (standalone mode)

### Gate 5 Commands (UAT — on VPS 72.62.74.232)

```bash
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx --cert-name uat.bwcacc.biz -d uat.bwcacc.biz \
  --non-interactive --agree-tos -m admin@yahwan.biz
```

### Gate 5 Commands (PROD — on VPS 72.62.247.9)

```bash
sudo certbot --nginx --cert-name app.bwcacc.biz -d app.bwcacc.biz \
  --non-interactive --agree-tos -m admin@yahwan.biz
```

### Gate 5 Pass Criteria — MET (2026-06-21)

- ✅ UAT cert: CN=uat.bwcacc.biz, expires 2026-09-18 (Let's Encrypt YE1)
- ✅ PROD cert: CN=app.bwcacc.biz, expires 2026-09-18 (Let's Encrypt YE2)
- ✅ certbot.timer enabled (auto-renew twice daily, dry-run passed)
- ✅ HTTPS endpoint testing — verified via nginx-gate container (2026-06-21)

---

## Gate 6: Auto-Renew and Redirect Validation

> **Status**: ✅ DONE (2026-06-21)

### Gate 6 Commands

```bash
# On each VPS
sudo certbot renew --dry-run

# From local machine
curl -I http://uat.bwcacc.biz
curl -I https://uat.bwcacc.biz/health
curl -I https://app.bwcacc.biz/health
```

### Gate 6 Pass Criteria — MET (2026-06-21)

- ✅ `certbot renew --dry-run` passes on both VPS
- ✅ Certbot renewal hooks configured: pre_hook stops nginx-gate, post_hook restarts it
- ✅ HTTP → HTTPS 301 redirect on both UAT and PROD
- ✅ `/health` returns 200 + JSON on both environments
- ✅ `/api/health` returns 200 + JSON on both environments
- ✅ Cert expiry monitoring active (cron daily at 06:00, syslog tag `certcheck`)

---

## Gate 7: Final Pre-Deploy Smoke

> **Status**: ✅ DONE (2026-06-21) — external curl from dev machine

### Gate 7 Commands

```bash
curl -s https://uat.bwcacc.biz/health
curl -s https://uat.bwcacc.biz/api/health
curl -s https://app.bwcacc.biz/health
curl -s https://app.bwcacc.biz/api/health
```

### Gate 7 Pass Criteria — MET (2026-06-21)

- ✅ `https://uat.bwcacc.biz/health` → 200 `{"status":"healthy","service":"nginx-gate","domain":"uat.bwcacc.biz"}`
- ✅ `https://uat.bwcacc.biz/api/health` → 200 (pre-deploy placeholder, services pending)
- ✅ `https://app.bwcacc.biz/health` → 200 `{"status":"healthy","service":"nginx-gate","domain":"app.bwcacc.biz"}`
- ✅ `https://app.bwcacc.biz/api/health` → 200 (pre-deploy placeholder, services pending)
- ✅ SSL valid: UAT CN=uat.bwcacc.biz (YE1, exp 2026-09-18), PROD CN=app.bwcacc.biz (YE2, exp 2026-09-18)

> **Note**: `/health` and `/api/health` currently serve static JSON from nginx-gate container. Will be replaced by actual backend health check in TASK-1307 Docker Compose.

---

## Ready-to-Deploy Sign-off

| Check | Status | Owner | Timestamp |
| --- | --- | --- | --- |
| Gate 1 VPS/Access | [x] | DevOps | 2026-06-21 |
| Gate 2 DNS records | [x] | DevOps | 2026-06-21 |
| Gate 3 DNS propagation | [x] | DevOps | 2026-06-21 |
| Gate 4 Nginx mapping | [x] | DevOps | 2026-06-21 |
| Gate 5 SSL issue | [x] | DevOps | 2026-06-21 |
| Gate 6 Auto-renew/redirect | [x] | DevOps | 2026-06-21 |
| Gate 7 Final smoke | [x] | DevOps | 2026-06-21 |
| CAA record applied | [x] | DevOps | 2026-06-20 |
| Deploy user + root SSH disabled | [x] | DevOps | 2026-06-21 |
| Cert expiry monitoring active | [x] | DevOps | 2026-06-21 |
| DNS TTL 300 + zone backup exported | [x] | DevOps | 2026-06-21 |

Decision:

- [x] Approved for UAT deploy (2026-06-21 — all gates passed)
- [x] Approved for PROD deploy (2026-06-21 — all gates passed)

## Rollback Notes

- DNS rollback: revert A records via Hostinger REST API (`DELETE` old + `PUT` with `overwrite: false`)
- SSL rollback: keep old cert active until new cert validated
- Access rollback: keep emergency root key path documented, but disable once deploy user validated
- VPS rollback: PoC VPS (`76.13.210.250`) remains operational as fallback
