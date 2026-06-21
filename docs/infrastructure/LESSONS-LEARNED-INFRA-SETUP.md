# Lessons Learned — Infrastructure Setup for New Company

> **Source project**: LedgerFlow (ai-accounting-copilot) — Phase II, Epic 13
> **Completed**: 2026-06-21 | **Author**: DevOps
> **Use case**: Hostinger VPS + DNS + SSL + Firewall สำหรับ web app (FastAPI + React + PostgreSQL)
>
> เอกสารนี้เขียนให้ครบ ไม่ต้องไปหาที่ไหนเพิ่ม — อ่านตาม step แล้วรัน script ได้เลย

---

## Table of Contents

1. [Overview & Master Checklist](#1-overview--master-checklist)
2. [Hostinger Account & Billing](#2-hostinger-account--billing)
3. [VPS Procurement](#3-vps-procurement)
4. [Domain & DNS Setup](#4-domain--dns-setup)
5. [VPS Base OS Setup](#5-vps-base-os-setup)
6. [SSL Certificates (Certbot)](#6-ssl-certificates-certbot)
7. [nginx Verification](#7-nginx-verification)
8. [Network & Firewall](#8-network--firewall)
9. [Cert Expiry Monitoring](#9-cert-expiry-monitoring)
10. [CI/CD Branch Strategy](#10-cicd-branch-strategy)
11. [Gotchas & Ubuntu 24.04 Quirks](#11-gotchas--ubuntu-2404-quirks)
12. [Quick Reference / Cheat Sheet](#12-quick-reference--cheat-sheet)
13. [Cost Summary](#13-cost-summary)

---

## 1. Overview & Master Checklist

### What We're Setting Up

```
Internet → DNS (Hostinger) → VPS (nginx:443 → backend:8000)
                                   ├── PostgreSQL (internal)
                                   ├── Redis (internal)
                                   └── MinIO (internal)
```

3 environments: Demo/PoC, UAT, PROD — แยก VPS คนละเครื่อง, domain เดียวกัน (`bwcacc.biz`) แยกด้วย subdomain

### Master Checklist (ทำตามลำดับ)

```
[ ] 1. สร้าง Hostinger account + ซื้อ VPS plan
[ ] 2. ซื้อ domain (.biz) + ตั้ง DNS A records + CAA
[ ] 3. รอ DNS propagation (5-10 นาที ถ้า TTL 300s)
[ ] 4. รัน setup-vps.sh บนทุก VPS (Docker, firewall, SSH harden, swap)
[ ] 5. รัน setup-certbot.sh บนทุก VPS (SSL cert issue + auto-renew)
[ ] 6. รัน setup-nginx-gate.sh บนทุก VPS (nginx container + certbot hooks)
[ ] 7. Test จาก local: curl https://uat.domain.biz/health → 200
[ ] 8. Backup DNS zone → infra/dns-zone-backup.txt
[ ] 9. พร้อม deploy Docker Compose stack
```

**เวลาจริงที่ใช้**: ~4-6 ชั่วโมงรวมรอ DNS + cert issue (ไม่นับเวลาตัดสินใจ)

### Progress Tracking

- **Human (browser)**: เปิด [`docs/requirement/phaseII/epic-13/INFRA-PREREQUISITES-CHECKLIST.html`](../requirement/phaseII/epic-13/INFRA-PREREQUISITES-CHECKLIST.html) ใน browser — interactive checklist 13 gates, state จำใน localStorage, เห็น progress bar แบบ real-time
- **AI Agent**: อ่าน [`docs/requirement/phaseII/epic-13/INFRA-PREREQUISITES-RUNBOOK.md`](../requirement/phaseII/epic-13/INFRA-PREREQUISITES-RUNBOOK.md) — ดู "Ready-to-Deploy Sign-off" table ที่ท้ายไฟล์ (`[x]`/`[ ]` per gate) เพื่อรู้ว่าอะไรเสร็จ/ค้าง แล้วทำงานต่อจาก gate ที่ยังไม่ผ่าน

### Outstanding Work Tracker (for AI Agents)

เมื่อ AI agent เข้ามาทำงานต่อ ให้อ่านไฟล์ตามลำดับนี้เพื่อรู้สถานะ + สิ่งที่ต้องทำ:

```
1. อ่าน docs/requirement/phaseII/epic-13/README-EPIC-13.md
   → ดู "Task overview" table → column "Status" บอกว่า task ไหนเสร็จ/ค้าง

2. อ่าน docs/requirement/phaseII/epic-13/INFRA-PREREQUISITES-RUNBOOK.md
   → ดู "Ready-to-Deploy Sign-off" table ท้ายไฟล์
   → Gate ที่ยังเป็น [ ] คือสิ่งที่ต้องทำ
   → Gate ที่เป็น [x] คือสิ่งที่เสร็จแล้ว

3. อ่าน docs/requirement/phaseII/epic-13/EPIC-13-TASKS-DETAIL.md
   → ดู task ที่ยังไม่มี "✅ DONE" → อ่าน acceptance criteria + files to create/modify
   → ทำตาม AC ให้ครบ แล้ว mark status เป็น ✅ DONE + เพิ่ม Output line

4. อ่าน docs/cicd/pipeline-design.md (ถ้าทำ CI/CD tasks)
   → Design document สำหรับ TASK-1306 implementation

5. อ่าน docs/architecture/vps-architecture.md (ถ้าทำ Docker Compose tasks)
   → Resource sizing tables สำหรับ TASK-1307, TASK-1308
```

> **สำคัญ**: หลังทำ task เสร็จ ต้องอัพเดท 3 ที่:
> 1. `EPIC-13-TASKS-DETAIL.md` — mark task as ✅ DONE + เพิ่ม Output line
> 2. `README-EPIC-13.md` — เปลี่ยน Status column ใน task overview table
> 3. `INFRA-PREREQUISITES-RUNBOOK.md` — mark gate as `[x]` (ถ้า task map กับ gate)

---

## 2. Hostinger Account & Billing

### Plan ที่ใช้จริง

| Environment | Plan | vCPU | RAM | Disk | ราคาประมาณ | ใช้ทำอะไร |
|-------------|------|------|-----|------|-----------|----------|
| **UAT** | KVM 2 | 2 | 8 GB | 100 GB | ~$10-15/เดือน | Internal testing, 1-5 users |
| **PROD** | KVM 4 | 4 | 16 GB | 200 GB | ~$16-25/เดือน | Production, 10-50 users |
| **Demo/PoC** | KVM 4 | 4 | 16 GB | 200 GB | ~$16-25/เดือน | Demo ให้ลูกค้าดู (optional) |

> **Tip**: UAT ใช้ KVM 2 พอ — ไม่จำเป็นต้อง KVM 4 สำหรับ testing

### สิ่งที่ได้ฟรีพร้อม VPS

- **Free domain names** (2 ตัว) — Hostinger ให้ domain ฟรีเมื่อซื้อ VPS เช่น `.tech`, `.cloud`
  - เก็บไว้เป็น alias/reserve ไม่ต้องใช้ก็ได้
- **Docker pre-installed** — Ubuntu 24.04 image ของ Hostinger มี Docker 29.x + Compose 5.x มาให้แล้ว

### Hostinger API Token

สร้างที่ hPanel → Account → API Keys

```bash
export HOSTINGER_API_TOKEN="your-token-here"
```

API Base URL: `https://developers.hostinger.com/api/`

### Domain Pricing

| TLD | ราคาประมาณ | หมายเหตุ |
|-----|-----------|---------|
| `.biz` | ~$10-15/ปี | เหมาะธุรกิจ |
| `.com` | ~$12-15/ปี | Brand หลัก แต่อาจอยู่ registrar อื่น |
| `.tech` | ฟรี (VPS bonus) | เก็บไว้ reserve |
| `.cloud` | ฟรี (VPS bonus) | เก็บไว้ reserve |

---

## 3. VPS Procurement

### ขั้นตอนสั่ง VPS

1. Login Hostinger hPanel
2. VPS → Create New VPS
3. เลือก **Data Center**: DC 21 (Singapore) — สำหรับ user ไทย latency ต่ำสุด
4. เลือก **OS**: Ubuntu 24.04 LTS (plain OS, ไม่เอา template)
5. เลือก **Plan**: KVM 2 (UAT) หรือ KVM 4 (PROD)
6. ตั้ง **root password** (จะใช้แค่ครั้งแรก ก่อนเปลี่ยนเป็น key-only)
7. Upload **SSH public key** ตอนสั่ง (ed25519 recommended)

### SSH Key Setup (ทำครั้งเดียว)

```bash
# สร้าง SSH key pair สำหรับ Hostinger
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519_hostinger -C "deploy@company"

# Copy public key ไปใส่ตอนสั่ง VPS หรือ upload ภายหลังผ่าน hPanel
cat ~/.ssh/id_ed25519_hostinger.pub
```

Windows key path: `C:\Users\<USERNAME>\.ssh\id_ed25519_hostinger`

### ทดสอบ SSH ได้ทันที

```bash
ssh -i ~/.ssh/id_ed25519_hostinger root@<VPS_IP> "hostname && uname -a"
```

### Resource Sizing Guide

| Service | RAM ต่ำสุด | คำอธิบาย |
|---------|-----------|---------|
| nginx | 128 MB | SSL termination, reverse proxy |
| FastAPI backend | 512 MB - 1 GB | Depends on workers |
| Celery worker | 1.5 GB - 3 GB | OCR + LLM = memory-intensive |
| PostgreSQL | 1 GB - 4 GB | Buffer pool ยิ่งใหญ่ยิ่งเร็ว |
| Redis | 128 MB - 512 MB | Broker + cache |
| MinIO | 256 MB - 1 GB | Object storage |
| **OS + overhead** | ~2 GB | Ubuntu + Docker engine |

**สูตรง่ายๆ**: รวม service RAM + 2 GB OS → เลือก plan ที่ RAM มากกว่า 30%

---

## 4. Domain & DNS Setup

### 4.1 ซื้อ Domain

ซื้อ domain ที่ Hostinger โดยตรง — จัดการ DNS ง่ายกว่า (ไม่ต้องย้าย NS)

> **Lesson learned**: ถ้า domain อยู่ registrar อื่น (เช่น Squarespace) จะต้อง:
> - ย้าย NS records มาชี้ Hostinger (propagation 24-48 ชม.)
> - หรือใช้ DNS ของ registrar เดิม (ไม่ได้ใช้ Hostinger API)
>
> **สรุป**: ซื้อ domain ที่ Hostinger เลย ประหยัดเวลา 1-2 วัน

### 4.2 ตั้ง DNS Records

```bash
export HOSTINGER_API_TOKEN="your-token-here"
DOMAIN="yourdomain.biz"

# ดู records ปัจจุบัน
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  "https://developers.hostinger.com/api/dns/v1/zones/${DOMAIN}" | python3 -m json.tool

# เพิ่ม A records (overwrite: false = ไม่ลบ record เดิม)
curl -s -X PUT "https://developers.hostinger.com/api/dns/v1/zones/${DOMAIN}" \
  -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "overwrite": false,
    "zone": [
      {"name": "demo", "type": "A", "content": "76.13.210.250", "ttl": 300},
      {"name": "uat",  "type": "A", "content": "72.62.74.232",  "ttl": 300},
      {"name": "app",  "type": "A", "content": "72.62.247.9",   "ttl": 300}
    ]
  }'

# เพิ่ม CAA record (บังคับให้แค่ Let's Encrypt ออก cert ได้)
curl -s -X PUT "https://developers.hostinger.com/api/dns/v1/zones/${DOMAIN}" \
  -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "overwrite": false,
    "zone": [
      {"name": "@", "type": "CAA", "content": "0 issue \"letsencrypt.org\"", "ttl": 3600}
    ]
  }'
```

### 4.3 DNS Record Map Template

| Subdomain | Type | Target | TTL | Environment |
|-----------|------|--------|-----|-------------|
| `demo.<domain>` | A | `<DEMO_IP>` | 300 | PoC/Demo |
| `uat.<domain>` | A | `<UAT_IP>` | 300 | UAT |
| `app.<domain>` | A | `<PROD_IP>` | 300 | Production |
| `@` | CAA | `0 issue "letsencrypt.org"` | 3600 | All (security) |

> **TTL 300s** (5 นาที) — ตั้งต่ำเพื่อให้ rollback DNS ได้เร็ว ถ้า VPS พัง เปลี่ยน IP ใหม่ propagate ภายใน 5 นาที

### 4.4 Verify DNS Propagation

```bash
# ต้องเช็คจาก 2 DNS resolvers เพื่อยืนยัน global propagation
nslookup uat.yourdomain.biz 8.8.8.8      # Google DNS
nslookup uat.yourdomain.biz 1.1.1.1      # Cloudflare DNS

# CAA check (Windows ไม่มี dig — ใช้ DNS-over-HTTPS แทน)
curl -s "https://dns.google/resolve?name=yourdomain.biz&type=CAA" | python3 -m json.tool
```

> **ต้องรอ propagation ก่อนทำ SSL** — certbot ใช้ DNS resolve domain → VPS IP เพื่อ verify ownership ถ้า DNS ยังไม่ propagate, cert issue จะ fail

### 4.5 DNS Zone Backup

```bash
# Export DNS records เก็บไว้ใน repo เผื่อต้อง restore
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  "https://developers.hostinger.com/api/dns/v1/zones/${DOMAIN}" \
  | python3 -m json.tool > infra/dns-zone-backup.txt
```

### 4.6 DNS Rollback

```bash
# ลบ record เก่า
curl -s -X DELETE "https://developers.hostinger.com/api/dns/v1/zones/${DOMAIN}" \
  -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"filters": [{"name": "uat", "type": "A"}]}'

# เพิ่ม record ใหม่ (overwrite: false)
curl -s -X PUT "https://developers.hostinger.com/api/dns/v1/zones/${DOMAIN}" \
  -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"overwrite": false, "zone": [{"name": "uat", "type": "A", "content": "NEW_IP", "ttl": 300}]}'
```

> **สำคัญ**: `overwrite: false` = เพิ่ม record ใหม่โดยไม่ลบ record อื่น, `overwrite: true` = **ลบทุก record แล้วใส่ใหม่** — อย่าใช้ `true` ถ้าไม่แน่ใจ

---

## 5. VPS Base OS Setup

### Script: `scripts/infra/setup-vps.sh`

Script นี้ทำ 7 อย่าง (idempotent — รันซ้ำได้ปลอดภัย):

1. **apt update + upgrade** — อัพเดท OS packages
2. **สร้าง `deploy` user** — เพิ่มใน docker group, copy SSH authorized_keys จาก root
3. **SSH hardening** — ปิด password login, จำกัด root access, ตั้ง timeout
4. **fail2ban** — ban IP ที่ brute force SSH (3 attempts → ban 1 ชม.)
5. **UFW firewall** — เปิดแค่ port 22/80/443
6. **Swap** — สร้าง swap file (2G default, 4G สำหรับ PROD)
7. **App directories** — สร้าง `/opt/ledgerflow/`, `/backup/db/`

### วิธีรัน

```bash
# UAT (swap 2G default)
ssh -i ~/.ssh/id_ed25519_hostinger root@<UAT_IP> 'bash -s' < scripts/infra/setup-vps.sh

# PROD (swap 4G)
ssh -i ~/.ssh/id_ed25519_hostinger root@<PROD_IP> 'SWAP_SIZE=4G bash -s' < scripts/infra/setup-vps.sh
```

> **Pattern**: Pipe script ผ่าน SSH — ไม่ต้อง scp file ขึ้น VPS

### SSH Hardening Settings

| Setting | Value | ทำไม |
|---------|-------|------|
| `PermitRootLogin` | `prohibit-password` | Root ยังเข้าได้ด้วย key (ต้องใช้ตอน setup) — เปลี่ยนเป็น `no` หลัง go-live |
| `PasswordAuthentication` | `no` | ห้าม login ด้วย password เด็ดขาด |
| `PubkeyAuthentication` | `yes` | ใช้ SSH key เท่านั้น |
| `MaxAuthTries` | `3` | จำกัด login attempts |
| `ClientAliveInterval` | `300` | Timeout idle SSH หลัง 5 นาที |
| `ClientAliveCountMax` | `2` | ส่ง keepalive 2 ครั้งก่อนตัด |

### sysctl Tuning

```
vm.swappiness = 10          # ใช้ RAM ก่อน swap ยกเว้นจำเป็น
vm.overcommit_memory = 1    # จำเป็นสำหรับ Redis (BGSAVE fork)
net.core.somaxconn = 512    # Connection backlog
net.ipv4.tcp_keepalive_time = 600
fs.file-max = 65536
```

### Verify หลังรัน

```bash
ssh -i ~/.ssh/id_ed25519_hostinger root@<VPS_IP> \
  "hostname && docker version --format '{{.Server.Version}}' && docker compose version --short && ufw status && free -h | head -3"
```

Expected output:
```
srv1772060.hstgr.cloud
29.6.0
5.1.4
Status: active
...
Swap:          2.0Gi
```

---

## 6. SSL Certificates (Certbot)

### ทำไมใช้ standalone mode (ไม่ใช่ --nginx)

| | `--standalone` | `--nginx` |
|---|---|---|
| ต้องมี nginx host service | ❌ ไม่ต้อง | ✅ ต้องมี |
| ใช้กับ Docker nginx | ✅ ได้ | ❌ ไม่ได้ (certbot หา nginx config บน host ไม่เจอ) |
| Port 80 ต้องว่าง | ✅ ตอน issue แรกเท่านั้น | ✅ ตลอดเวลา |

> **สรุป**: ถ้า nginx จะรันใน Docker container → ใช้ `certbot certonly --standalone` เสมอ

### Script: `scripts/infra/setup-certbot.sh`

```bash
# UAT
ssh -i ~/.ssh/id_ed25519_hostinger root@<UAT_IP> \
  'DOMAIN=uat.yourdomain.biz bash -s' < scripts/infra/setup-certbot.sh

# PROD
ssh -i ~/.ssh/id_ed25519_hostinger root@<PROD_IP> \
  'DOMAIN=app.yourdomain.biz bash -s' < scripts/infra/setup-certbot.sh
```

### สิ่งที่ script ทำ

1. Install certbot (ถ้ายังไม่มี)
2. `certbot certonly --standalone -d $DOMAIN --non-interactive --agree-tos -m admin@company.biz --no-eff-email`
3. Verify cert ด้วย `openssl x509`
4. Enable `certbot.timer` (auto-renew ทุกวัน 2 ครั้ง)
5. Run `certbot renew --dry-run` เพื่อยืนยัน

### Cert Files Location

```
/etc/letsencrypt/live/<DOMAIN>/
├── fullchain.pem   ← nginx ssl_certificate
├── privkey.pem     ← nginx ssl_certificate_key
├── cert.pem        ← certificate only
└── chain.pem       ← intermediate chain
```

### Auto-Renewal

Ubuntu 24.04 ใช้ **systemd timer** (ดีกว่า cron — มี jitter ป้องกัน thundering herd):

```bash
# ตรวจสอบ timer
systemctl status certbot.timer

# ดู schedule
systemctl list-timers certbot
```

> **ไม่ต้องตั้ง cron สำหรับ cert renewal** — certbot package on Ubuntu 24.04 จัดการให้แล้ว

### Verify Cert

```bash
# จาก VPS
openssl x509 -in /etc/letsencrypt/live/$DOMAIN/cert.pem -noout -subject -dates

# จาก local machine (ผ่าน internet)
echo | openssl s_client -connect $DOMAIN:443 -servername $DOMAIN 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
```

Let's Encrypt cert มีอายุ 90 วัน — auto-renew จะ renew เมื่อเหลือ < 30 วัน

---

## 7. nginx Verification

### ทำไมต้องมี nginx ก่อน Docker Compose

เพื่อ verify ว่า DNS → SSL → reverse proxy ทำงานถูกต้อง **ก่อน** deploy app จริง ถ้ามีปัญหาจะได้รู้ว่าเป็น infra layer ไม่ใช่ app layer

### Script: `scripts/infra/setup-nginx-gate.sh`

```bash
# UAT
ssh -i ~/.ssh/id_ed25519_hostinger root@<UAT_IP> \
  'DOMAIN=uat.yourdomain.biz bash -s' < scripts/infra/setup-nginx-gate.sh

# PROD
ssh -i ~/.ssh/id_ed25519_hostinger root@<PROD_IP> \
  'DOMAIN=app.yourdomain.biz bash -s' < scripts/infra/setup-nginx-gate.sh
```

### สิ่งที่ script ทำ

1. สร้าง nginx config (`/opt/ledgerflow/nginx/conf.d/default.conf`) พร้อม:
   - HTTP → HTTPS redirect (301)
   - SSL termination (TLS 1.2/1.3)
   - Static `/health` + `/api/health` endpoints (placeholder)
2. Run `nginx:1.27-alpine` container ชื่อ `nginx-gate`
3. ตั้ง certbot renewal hooks (pre: stop nginx, post: start nginx)
4. Self-test: nginx -t, curl /health, check redirect

### Port 80 Conflict: certbot vs nginx

**ปัญหา**: ทั้ง certbot standalone และ nginx ต้องใช้ port 80
**วิธีแก้**: Certbot renewal hooks

```ini
# ถูกเขียนใน /etc/letsencrypt/renewal/<DOMAIN>.conf
[renewalparams]
pre_hook = docker stop nginx-gate || true
post_hook = docker start nginx-gate || true
```

Flow ตอน auto-renew:
```
certbot timer fires
  → pre_hook: docker stop nginx-gate (port 80 ว่าง)
  → certbot starts temp HTTP server on :80
  → ACME challenge completes
  → certbot stops temp server
  → post_hook: docker start nginx-gate (port 80 กลับมา)
```

Downtime: ~10-30 วินาที ตอน renewal (ทุก 60 วัน, กลางดึก)

### Verify จาก Local Machine

```bash
# HTTP → HTTPS redirect
curl -sI http://uat.yourdomain.biz/ | head -3
# Expected: HTTP/1.1 301 Moved Permanently

# HTTPS health
curl -s https://uat.yourdomain.biz/health
# Expected: {"status":"healthy","service":"nginx-gate","domain":"uat.yourdomain.biz"}

# SSL cert
echo | openssl s_client -connect uat.yourdomain.biz:443 -servername uat.yourdomain.biz 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates
```

### Cleanup เมื่อ Deploy Docker Compose จริง

```bash
# nginx-gate จะถูกแทนที่ด้วย nginx service ใน Docker Compose
docker rm -f nginx-gate
```

---

## 8. Network & Firewall

### UFW Rules (ตั้งโดย setup-vps.sh)

```bash
ufw status verbose
```

Expected:
```
Status: active
Default: deny (incoming), allow (outgoing)

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
```

### Network Architecture

```
External (internet)          Internal (Docker bridge)
──────────────────           ───────────────────────
Port 22  → SSH (VPS)         Port 5432 → PostgreSQL
Port 80  → nginx (redirect)  Port 6379 → Redis
Port 443 → nginx (SSL)       Port 9000 → MinIO S3
                              Port 9001 → MinIO Console
```

> **สำคัญ**: Database, Redis, MinIO อยู่ใน Docker internal network เท่านั้น — **ห้ามเปิด port ออก internet เด็ดขาด**

### fail2ban

Config: `/etc/fail2ban/jail.local`

| Setting | Value | หมายเหตุ |
|---------|-------|---------|
| `maxretry` | 3 | SSH attempts ก่อน ban |
| `bantime` | 3600 | Ban 1 ชั่วโมง |
| `findtime` | 600 | นับ attempts ภายใน 10 นาที |
| `backend` | systemd | **Ubuntu 24.04 ต้องใช้ systemd** ไม่ใช่ auto |

```bash
# ดู IP ที่ถูก ban
fail2ban-client status sshd

# Unban IP
fail2ban-client set sshd unbanip <IP>
```

---

## 9. Cert Expiry Monitoring

### Daily Cron Check

ตั้งโดย setup-certbot.sh — check cert expiry ทุกวัน 06:00:

```bash
# ดู log
journalctl -t certcheck --since "7 days ago"
```

### Manual Check

```bash
# ดูวันหมดอายุ cert
openssl x509 -enddate -noout -in /etc/letsencrypt/live/$DOMAIN/cert.pem

# Test renewal (dry-run, ไม่ renew จริง)
certbot renew --dry-run
```

### Post-Go-Live Enhancement

- Setup **Uptime Kuma** → LINE Notify alerts เมื่อ HTTPS check fail
- Target: D+14 หลัง go-live

---

## 10. CI/CD Branch Strategy

```
feature/*  ──→  dev  ──→  uat  ──→  main
                 │         │         │
             local dev   UAT VPS   PROD VPS
             (no deploy) auto-deploy manual-approve
```

### Branch Protection Rules

| Branch | Merge From | Deploy | Approval | Force Push |
|--------|-----------|--------|----------|------------|
| `dev` | `feature/*` | None (CI only) | 1 reviewer | No |
| `uat` | `dev` | Auto → UAT VPS | CI must pass | No |
| `main` | `uat` | Manual → PROD VPS | 1 reviewer + CI | **No** |

### PROD Safety Rules (Non-Negotiable)

1. **UAT First** — ทุก code ต้องผ่าน UAT ก่อน PROD
2. **DB Snapshot ก่อนทุก migration** — `pg_dump` ก่อน `alembic upgrade head`
3. **No force push to main** — revert forward เท่านั้น
4. **Manual approval** — GitHub environment `production` ต้องมี 1 reviewer
5. **Health check = deploy gate** — `/api/health` ต้อง 200 ภายใน 60 วินาที

### GitHub Secrets ที่ต้องตั้ง

| Secret | Value | Used In |
|--------|-------|---------|
| `VPS_SSH_KEY` | SSH private key (ed25519) | deploy-uat, deploy-prod |
| `UAT_HOST` | VPS IP (e.g., `72.62.74.232`) | deploy-uat |
| `PROD_HOST` | VPS IP (e.g., `72.62.247.9`) | deploy-prod |
| `DEPLOY_USER` | `deploy` | deploy-uat, deploy-prod |
| `LINE_NOTIFY_TOKEN` | LINE Notify API token | deploy-uat, deploy-prod |

---

## 11. Gotchas & Ubuntu 24.04 Quirks

### ⚠️ ต้องรู้ก่อนเริ่ม

| # | Gotcha | วิธีแก้ |
|---|--------|--------|
| 1 | **SSH service ชื่อ `ssh` ไม่ใช่ `sshd`** บน Ubuntu 24.04 | ใช้ `systemctl reload ssh` (ไม่ใช่ `systemctl reload sshd`) |
| 2 | **fail2ban ต้องใช้ `backend = systemd`** | ถ้าไม่ตั้ง fail2ban จะไม่ detect SSH failures เพราะ Ubuntu 24.04 ใช้ journald |
| 3 | **certbot ใช้ systemd timer ไม่ใช่ cron** | ไม่ต้องตั้ง cron เอง — `systemctl enable certbot.timer` พอ |
| 4 | **Docker อาจ pre-installed มาแล้ว** | Hostinger Ubuntu 24.04 image มี Docker มาให้ — script ต้อง check ก่อน install |
| 5 | **`DEBIAN_FRONTEND=noninteractive`** ต้องตั้งก่อน apt | ไม่งั้น apt จะ prompt interactive dialog ค้าง script |
| 6 | **docker group ไม่ effective ทันที** | หลัง `usermod -aG docker deploy` ต้อง logout/login ใหม่ |
| 7 | **certbot standalone ต้องการ port 80 ว่าง** | รัน certbot **ก่อน** start nginx container |
| 8 | **`overwrite: true` ลบทุก DNS record** | ใช้ `overwrite: false` เสมอ เว้นแต่จะ reset zone ทั้งหมด |
| 9 | **PermitRootLogin ตั้ง `prohibit-password` ไม่ใช่ `no`** | ช่วง setup ต้องใช้ root key access — เปลี่ยนเป็น `no` หลัง go-live |
| 10 | **certbot dry-run ช้ามาก** (1-3 นาที) | ปกติ — ACME simulation ต้อง round trip กับ Let's Encrypt servers |
| 11 | **certbot lock file** | ถ้า certbot ค้าง ต้อง kill process + ลบ lock: `find /tmp -name ".certbot.lock" -delete` |
| 12 | **CAA record ต้องตั้งก่อน cert issue** | ไม่ได้บังคับ แต่เป็น security best practice — ป้องกัน CA อื่นออก cert ปลอม |
| 13 | **Windows ไม่มี `dig`** | ใช้ `nslookup` หรือ DNS-over-HTTPS: `curl -s "https://dns.google/resolve?name=domain&type=A"` |

### ⚠️ Security Mistakes ห้ามทำ

1. **ห้ามเปิด port PostgreSQL (5432) ออก internet** — ใช้ Docker internal network เท่านั้น
2. **ห้ามเก็บ SSH private key ใน repo** — ใช้ GitHub Secrets
3. **ห้าม force push to main** — revert commit forward เท่านั้น
4. **ห้าม deploy PROD โดยไม่ทำ DB snapshot ก่อน**
5. **ห้ามใช้ `overwrite: true` กับ Hostinger DNS API** โดยไม่ backup zone ก่อน

---

## 12. Quick Reference / Cheat Sheet

### SSH Access

```bash
# Pattern: ssh -i <KEY> <USER>@<IP>
ssh -i ~/.ssh/id_ed25519_hostinger deploy@<UAT_IP>    # Day-to-day
ssh -i ~/.ssh/id_ed25519_hostinger deploy@<PROD_IP>
ssh -i ~/.ssh/id_ed25519_hostinger root@<VPS_IP>      # Emergency only
```

### Docker Commands (on VPS)

```bash
docker ps                              # Running containers
docker logs <container> --tail 50      # View logs
docker stats --no-stream               # Resource usage snapshot
docker compose -f docker-compose.uat.yml up -d   # Start stack
docker compose -f docker-compose.uat.yml down     # Stop stack
docker exec -it postgres psql -U ledgerflow       # DB shell
```

### Hostinger API

```bash
export HOSTINGER_API_TOKEN="your-token"

# VPS list
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  https://developers.hostinger.com/api/vps/v1/virtual-machines | python3 -m json.tool

# Domain portfolio
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  https://developers.hostinger.com/api/domains/v1/portfolio | python3 -m json.tool

# DNS records
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  https://developers.hostinger.com/api/dns/v1/zones/<DOMAIN> | python3 -m json.tool
```

### Health Check

```bash
# From local machine
curl -s https://uat.yourdomain.biz/health
curl -s https://app.yourdomain.biz/api/health

# From VPS (localhost)
curl -sk https://localhost/health
```

### Cert Management

```bash
# Check cert expiry
openssl x509 -enddate -noout -in /etc/letsencrypt/live/$DOMAIN/cert.pem

# Test renewal
certbot renew --dry-run

# Force renewal (if needed)
certbot renew --force-renewal

# List all certs
certbot certificates
```

### Firewall

```bash
ufw status verbose       # Current rules
ufw allow 8080/tcp       # Add rule
ufw delete allow 8080/tcp  # Remove rule
ufw reload               # Apply changes
```

### DNS Verification (from Windows)

```bash
nslookup uat.yourdomain.biz 8.8.8.8
nslookup uat.yourdomain.biz 1.1.1.1
curl -s "https://dns.google/resolve?name=yourdomain.biz&type=CAA"
```

---

## 13. Cost Summary

### Monthly Costs (Estimated)

| Item | Cost/เดือน | หมายเหตุ |
|------|-----------|---------|
| UAT VPS (KVM 2) | ~$10-15 | 2 vCPU, 8 GB RAM |
| PROD VPS (KVM 4) | ~$16-25 | 4 vCPU, 16 GB RAM |
| Demo VPS (KVM 4) | ~$16-25 | Optional — ตัดได้ถ้าไม่ต้อง demo |
| Domain (.biz) | ~$1/เดือน | ($10-15/ปี) |
| SSL (Let's Encrypt) | **$0** | ฟรีตลอด, auto-renew |
| DNS (Hostinger) | **$0** | รวมกับ domain/VPS |
| Cloudflare R2 (backup) | ~$0-5 | Free tier 10 GB/เดือน |
| **Total (2 VPS)** | **~$27-41** | ไม่รวม Demo VPS |
| **Total (3 VPS)** | **~$43-66** | รวม Demo VPS |

### Annual Costs

| Configuration | ต่อปี (ประมาณ) |
|--------------|--------------|
| Minimal (UAT + PROD) | ~$324-492 |
| Full (Demo + UAT + PROD) | ~$516-792 |

> **Tip**: Hostinger มี promo ราคาถูกตอนจ่ายรายปี/2ปี — ลอง check ก่อนซื้อ monthly

---

## Appendix A: Script Execution Order (Copy-Paste Ready)

```bash
# ═══════════════════════════════════════════════════════════
# STEP 1: DNS Setup (ทำจาก local machine)
# ═══════════════════════════════════════════════════════════
export HOSTINGER_API_TOKEN="your-token"
DOMAIN="yourdomain.biz"

# Add A records + CAA
curl -s -X PUT "https://developers.hostinger.com/api/dns/v1/zones/${DOMAIN}" \
  -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "overwrite": false,
    "zone": [
      {"name": "uat", "type": "A", "content": "<UAT_IP>", "ttl": 300},
      {"name": "app", "type": "A", "content": "<PROD_IP>", "ttl": 300},
      {"name": "@", "type": "CAA", "content": "0 issue \"letsencrypt.org\"", "ttl": 3600}
    ]
  }'

# Wait for propagation
sleep 120
nslookup uat.${DOMAIN} 8.8.8.8
nslookup app.${DOMAIN} 8.8.8.8

# ═══════════════════════════════════════════════════════════
# STEP 2: VPS Base Setup (รัน per VPS)
# ═══════════════════════════════════════════════════════════
# UAT
ssh -i ~/.ssh/id_ed25519_hostinger root@<UAT_IP> 'bash -s' < scripts/infra/setup-vps.sh

# PROD (4G swap)
ssh -i ~/.ssh/id_ed25519_hostinger root@<PROD_IP> 'SWAP_SIZE=4G bash -s' < scripts/infra/setup-vps.sh

# ═══════════════════════════════════════════════════════════
# STEP 3: SSL Certificates (รัน per VPS — DNS ต้อง propagate แล้ว)
# ═══════════════════════════════════════════════════════════
# UAT
ssh -i ~/.ssh/id_ed25519_hostinger root@<UAT_IP> \
  'DOMAIN=uat.'"${DOMAIN}"' bash -s' < scripts/infra/setup-certbot.sh

# PROD
ssh -i ~/.ssh/id_ed25519_hostinger root@<PROD_IP> \
  'DOMAIN=app.'"${DOMAIN}"' bash -s' < scripts/infra/setup-certbot.sh

# ═══════════════════════════════════════════════════════════
# STEP 4: nginx Gate Verification (รัน per VPS)
# ═══════════════════════════════════════════════════════════
# UAT
ssh -i ~/.ssh/id_ed25519_hostinger root@<UAT_IP> \
  'DOMAIN=uat.'"${DOMAIN}"' bash -s' < scripts/infra/setup-nginx-gate.sh

# PROD
ssh -i ~/.ssh/id_ed25519_hostinger root@<PROD_IP> \
  'DOMAIN=app.'"${DOMAIN}"' bash -s' < scripts/infra/setup-nginx-gate.sh

# ═══════════════════════════════════════════════════════════
# STEP 5: External Verification (จาก local machine)
# ═══════════════════════════════════════════════════════════
curl -sI http://uat.${DOMAIN}/             # → 301
curl -s  https://uat.${DOMAIN}/health      # → 200 JSON
curl -sI http://app.${DOMAIN}/             # → 301
curl -s  https://app.${DOMAIN}/health      # → 200 JSON

# ═══════════════════════════════════════════════════════════
# STEP 6: DNS Zone Backup
# ═══════════════════════════════════════════════════════════
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  "https://developers.hostinger.com/api/dns/v1/zones/${DOMAIN}" \
  | python3 -m json.tool > infra/dns-zone-backup.txt

echo "✅ Infrastructure ready for Docker Compose deployment"
```

---

## Appendix B: Files Reference

| File | Purpose | เมื่อไหร่ใช้ |
|------|---------|-------------|
| `scripts/infra/setup-vps.sh` | Base OS + Docker + security | Step 2 — VPS แรกเริ่ม |
| `scripts/infra/setup-certbot.sh` | SSL cert issue + auto-renew | Step 3 — หลัง DNS propagate |
| `scripts/infra/setup-nginx-gate.sh` | nginx container + renewal hooks | Step 4 — หลัง cert issue |
| `docs/architecture/vps-architecture.md` | Full architecture topology + sizing | Planning / reference |
| `docs/cicd/pipeline-design.md` | CI/CD branch strategy + deploy steps | TASK-1306 implementation |
| `docs/cicd/prod-safety-rules.md` | PROD safety rules + rollback procedure | Deploy to PROD |
| `docs/infrastructure/bau-support.md` | Day-2 operations (logs, restart, health) | Daily ops |
| `infra/dns-zone-backup.txt` | DNS zone snapshot | Recovery |
| `docs/requirement/phaseII/epic-13/INFRA-PREREQUISITES-CHECKLIST.html` | Interactive progress tracker (browser) | **Human**: เปิดใน browser ดู progress |
| `docs/requirement/phaseII/epic-13/INFRA-PREREQUISITES-RUNBOOK.md` | 7-gate runbook + sign-off table | **AI Agent**: อ่านเพื่อรู้สถานะ gate |
| `docs/requirement/phaseII/epic-13/README-EPIC-13.md` | Task overview + status per task | **AI Agent**: ดูว่า task ไหนเสร็จ/ค้าง |
| `docs/requirement/phaseII/epic-13/EPIC-13-TASKS-DETAIL.md` | Full task specs + acceptance criteria | **AI Agent**: ดู AC ก่อนทำ task |

---

## Appendix C: Timing Expectations

| Step | เวลาจริง | คอขวด |
|------|---------|------|
| VPS สั่งซื้อ | 5-10 นาที | Provisioning |
| DNS propagation | 1-10 นาที | TTL 300s → fast |
| setup-vps.sh | 2-5 นาที | apt upgrade |
| setup-certbot.sh | 1-3 นาที | ACME challenge round trip |
| setup-nginx-gate.sh | 1-2 นาที | Docker image pull |
| certbot dry-run | 1-3 นาที | ACME simulation (ช้ากว่า issue จริง) |
| **Total per VPS** | **~10-20 นาที** | |
| **Total (2 VPS + DNS)** | **~30-45 นาที** | ไม่นับเวลาตัดสินใจ |

---

*Created: 2026-06-21 | Project: LedgerFlow (ai-accounting-copilot) | Epic 13*
*Next: Docker Compose deployment (TASK-1307, TASK-1308)*
