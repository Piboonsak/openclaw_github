# VPS Architecture Design — LedgerFlow (ai-accounting-copilot)

> **TASK-1301** | Created: 2026-06-21 | Owner: DevOps
> **Decision**: Hostinger VPS all-in (compute + DB + storage on VPS)

---

## 1. Infrastructure Inventory

### 1.1 VPS Fleet

| Role | VPS ID | Plan | vCPU | RAM | Disk | IP (v4) | Hostname | DC | OS | Created |
|------|--------|------|------|-----|------|---------|----------|----|----|---------|
| **PoC/Demo** | 1414058 | KVM 4 | 4 | 16 GB | 200 GB | `76.13.210.250` | srv1414058.hstgr.cloud | 21 | Ubuntu 24.04 LTS | 2026-02-22 |
| **UAT** | 1772060 | KVM 2 | 2 | 8 GB | 100 GB | `72.62.74.232` | srv1772060.hstgr.cloud | 21 | Ubuntu 24.04 LTS | 2026-06-20 |
| **PROD** | 1772174 | KVM 4 | 4 | 16 GB | 200 GB | `72.62.247.9` | srv1772174.hstgr.cloud | 21 | Ubuntu 24.04 LTS | 2026-06-20 |

- All VPS in **Data Center 21** (Singapore region) — low latency for Thai users
- SSH key: `C:\Users\HP Probook 440 G8\.ssh\id_ed25519_hostinger`

### 1.2 Domain Portfolio

| Domain | Registrar | Type | Expires | Assigned Role |
|--------|-----------|------|---------|---------------|
| `bwcacc.biz` | Hostinger | Purchased (1yr) | 2027-06-20 | **Primary domain** — subdomains for all environments |
| `bwcacc.tech` | Hostinger | Free (VPS bonus) | 2027-06-20 | Reserved — UAT VPS hostname alias |
| `bwcacc.cloud` | Hostinger | Free (VPS bonus) | 2027-06-20 | Reserved — PROD VPS hostname alias |
| `bwcacc.com` | Squarespace | Purchased (5yr) | ~2031 | Reserved — future brand migration target |
| `bwcacc.net` | TBD | Purchased (1yr) | ~2027 | Reserved |

### 1.3 DNS Record Map (bwcacc.biz)

| Subdomain | Type | Target | TTL | Environment |
|-----------|------|--------|-----|-------------|
| `demo.bwcacc.biz` | A | `76.13.210.250` | 300 | PoC/Demo |
| `uat.bwcacc.biz` | A | `72.62.74.232` | 300 | UAT |
| `app.bwcacc.biz` | A | `72.62.247.9` | 300 | Production |
| `@` | CAA | `0 issue "letsencrypt.org"` | 3600 | All |

---

## 2. Service Topology

Each VPS runs the same service stack via Docker Compose, differing only in resource limits and configuration.

```
                         Internet
                            |
                       [Cloudflare]  (future: CDN + WAF)
                            |
                     +--------------+
                     |    nginx     |  :80 → redirect :443
                     |  (SSL term)  |  :443 → proxy_pass
                     +--------------+
                            |
              +-------------+-------------+
              |                           |
     +--------+--------+        +--------+--------+
     |     backend      |        |   celery-worker  |
     |    (FastAPI)     |        | (background jobs) |
     |   uvicorn/       |        |   OCR, LLM,      |
     |   gunicorn       |        |   PDF processing  |
     +--------+---------+        +--------+---------+
              |                           |
     +--------+---------+       +---------+--------+
     |                  |       |                  |
+----+----+      +------+------+           +-------+------+
| postgres |      |    redis    |           |    minio     |
| (data)   |      |  (broker +  |           | (S3 storage) |
|          |      |   cache)    |           |              |
+----------+      +-------------+           +--------------+
```

### 2.1 Service Descriptions

| Service | Image | Role | Port (internal) |
|---------|-------|------|-----------------|
| **nginx** | `nginx:1.27-alpine` | SSL termination, reverse proxy, static files | 80, 443 |
| **backend** | Custom Dockerfile | FastAPI app — API endpoints, auth, business logic | 8000 |
| **celery-worker** | Same as backend | Async tasks — OCR, LLM extraction, PDF processing | — |
| **celery-beat** | Same as backend | Task scheduler — periodic jobs, report generation | — |
| **postgres** | `postgres:16-alpine` | Primary database — documents, users, companies | 5432 |
| **redis** | `redis:7-alpine` | Celery broker + result backend + session cache | 6379 |
| **minio** | `minio/minio:latest` | S3-compatible object storage — uploaded documents, exports | 9000, 9001 |

---

## 3. Resource Sizing

### 3.1 UAT (KVM 2: 2 vCPU, 8 GB RAM, 100 GB Disk)

Target workload: internal testing, 1-5 concurrent users, ~100 docs/day

| Service | CPU Limit | Memory Limit | Memory Reserve | Justification |
|---------|-----------|-------------|----------------|---------------|
| nginx | 0.25 | 128 MB | 64 MB | Low traffic, SSL termination only |
| backend | 0.5 | 1 GB | 512 MB | FastAPI + uvicorn, light load |
| celery-worker | 0.5 | 1.5 GB | 512 MB | OCR + LLM calls, memory-intensive |
| celery-beat | 0.1 | 128 MB | 64 MB | Scheduler only, minimal load |
| postgres | 0.5 | 2 GB | 1 GB | Small dataset, needs buffer pool |
| redis | 0.1 | 256 MB | 128 MB | Broker + small cache |
| minio | 0.25 | 512 MB | 256 MB | Object storage, low throughput |
| **Total** | **2.2** | **5.5 GB** | **2.5 GB** | ~69% RAM, headroom for OS + swap |

Swap: 2 GB file — covers memory spikes during OCR processing.

### 3.2 PROD (KVM 4: 4 vCPU, 16 GB RAM, 200 GB Disk)

Target workload: 10-50 concurrent users, 10K-20K docs/month

| Service | CPU Limit | Memory Limit | Memory Reserve | Justification |
|---------|-----------|-------------|----------------|---------------|
| nginx | 0.25 | 256 MB | 128 MB | Moderate traffic, SSL + rate limiting |
| backend | 1.0 | 2 GB | 1 GB | Gunicorn 4 workers, concurrent requests |
| celery-worker | 1.0 | 3 GB | 1.5 GB | Heavy OCR + LLM, multiple concurrent tasks |
| celery-beat | 0.1 | 128 MB | 64 MB | Scheduler only |
| postgres | 1.5 | 4 GB | 2 GB | Larger dataset, complex queries, indexing |
| redis | 0.25 | 512 MB | 256 MB | Higher broker throughput + cache |
| minio | 0.5 | 1 GB | 512 MB | More document storage I/O |
| **Total** | **4.6** | **10.9 GB** | **5.5 GB** | ~68% RAM, headroom for OS + backup jobs |

Swap: 4 GB file — covers burst workloads + pg_dump memory.

### 3.3 Disk Layout

| Path | UAT | PROD | Purpose |
|------|-----|------|---------|
| `/` (OS + Docker) | ~30 GB | ~40 GB | OS, Docker images, containers |
| `/var/lib/docker/volumes/` | ~40 GB | ~100 GB | PostgreSQL data, MinIO objects |
| `/backup/db/` | ~10 GB | ~30 GB | Local pg_dump backups (7-day retention) |
| `/var/log/` | ~5 GB | ~10 GB | Logs (rotation: 10MB x 5 per container) |
| **Free** | ~15 GB | ~20 GB | Buffer |

---

## 4. Network Architecture

### 4.1 Port Mapping

| Port | Protocol | Source | Destination | Purpose |
|------|----------|--------|-------------|---------|
| 22 | TCP | Whitelisted IPs only | VPS | SSH management |
| 80 | TCP | Public | nginx container | HTTP → HTTPS redirect |
| 443 | TCP | Public | nginx container | HTTPS (TLS 1.2+) |
| 8000 | TCP | nginx (internal) | backend container | API proxy |
| 5432 | TCP | Docker network only | postgres container | Database |
| 6379 | TCP | Docker network only | redis container | Broker/cache |
| 9000 | TCP | Docker network only | minio container | S3 API |
| 9001 | TCP | Docker network only | minio container | MinIO Console |

### 4.2 Docker Networks

```
ledgerflow-net (bridge, internal)
├── nginx          ← only service with host port binding (80, 443)
├── backend        ← talks to postgres, redis, minio
├── celery-worker  ← talks to postgres, redis, minio
├── celery-beat    ← talks to redis
├── postgres       ← NO external port
├── redis          ← NO external port
└── minio          ← NO external port
```

### 4.3 Firewall Rules (UFW)

```bash
# Default: deny incoming, allow outgoing
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (restrict to known IPs in production)
ufw allow 22/tcp

# Allow HTTP/HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Enable
ufw enable
```

---

## 5. Environment Separation Strategy

### 5.1 Configuration Isolation

| Aspect | Demo (PoC) | UAT | PROD |
|--------|-----------|-----|------|
| Compose file | `docker-compose.yml` | `docker-compose.uat.yml` | `docker-compose.prod.yml` |
| Env file | `.env` | `.env.uat` | `.env.prod` |
| DB name | `ledgerflow_dev` | `ledgerflow_uat` | `ledgerflow_prod` |
| Debug mode | ON | ON | **OFF** |
| App server | uvicorn (1 worker) | uvicorn (2 workers) | gunicorn (4 workers) |
| Log level | DEBUG | DEBUG | **WARNING** |
| Domain | `demo.bwcacc.biz` | `uat.bwcacc.biz` | `app.bwcacc.biz` |
| SSL | Optional | Let's Encrypt | Let's Encrypt |
| Backup | None | Daily (local) | Every 6h (local + R2 offsite) |
| Restart policy | no | on-failure | always |
| Resource limits | None | Soft limits | **Hard limits** |

### 5.2 Branch → Environment Mapping

```
feature/* ──→ dev branch ──→ (local dev only)
                  │
                  ▼
              uat branch ──→ deploy to UAT VPS (72.62.74.232)
                  │              uat.bwcacc.biz
                  ▼
             main branch ──→ deploy to PROD VPS (72.62.247.9)
                                 app.bwcacc.biz
```

### 5.3 Domain Strategy

**Primary domain**: `bwcacc.biz` (all active subdomains here)

**Reserved domains** (DNS redirect or parked):

| Domain | Strategy | When to activate |
|--------|----------|------------------|
| `bwcacc.com` | Keep parked on Squarespace. Set up 301 redirect to `app.bwcacc.biz` when ready | Post-launch brand migration |
| `bwcacc.net` | Park. Optional 301 redirect to primary | If needed |
| `bwcacc.tech` | Map to UAT VPS as alternative hostname | Optional — if `uat.bwcacc.biz` insufficient |
| `bwcacc.cloud` | Map to PROD VPS as alternative hostname | Optional — if `app.bwcacc.biz` insufficient |

---

## 6. Volume Mount Strategy

### 6.1 Named Volumes (Docker-managed)

| Volume Name | Service | Container Path | Purpose |
|-------------|---------|----------------|---------|
| `pg_data` | postgres | `/var/lib/postgresql/data` | Database files |
| `redis_data` | redis | `/data` | Redis persistence (AOF) |
| `minio_data` | minio | `/data` | Uploaded documents, exports |

### 6.2 Bind Mounts (Host-managed)

| Host Path | Service | Container Path | Purpose |
|-----------|---------|----------------|---------|
| `/opt/ledgerflow/nginx/certs/` | nginx | `/etc/letsencrypt/` | SSL certificates (certbot) |
| `/opt/ledgerflow/nginx/conf.d/` | nginx | `/etc/nginx/conf.d/` | nginx config |
| `/opt/ledgerflow/logs/` | all | `/var/log/app/` | Centralized log directory |
| `/backup/db/` | postgres (via script) | — | pg_dump output (cron, not container mount) |

---

## 7. Security Architecture

| Layer | Measure | Status |
|-------|---------|--------|
| Network | UFW: only 22/80/443 open | TASK-1309 |
| SSH | Key-only auth, root disabled, fail2ban | TASK-1303 |
| DNS | CAA record: only Let's Encrypt can issue certs | Done |
| TLS | Let's Encrypt certs, auto-renew, HTTP→HTTPS redirect | TASK-1304 |
| Docker | Internal network, no external DB/Redis/MinIO ports | TASK-1307/1308 |
| App | `.env` files not in git, secrets via env vars | Convention |
| Backup | pg_dump every 6h, offsite to Cloudflare R2 | TASK-1310 |
| Monitoring | Disk alert at 80%, cert expiry check, health endpoint | TASK-1311 |

---

## 8. Capacity Planning

### 8.1 Current Estimates

| Metric | UAT Target | PROD Target |
|--------|-----------|-------------|
| Concurrent users | 1-5 | 10-50 |
| Documents/month | ~500 | 10,000-20,000 |
| Average document size | 200 KB | 200 KB |
| DB size (1 year) | ~2 GB | ~20 GB |
| Object storage (1 year) | ~5 GB | ~50 GB |
| Backup storage (local) | ~5 GB | ~20 GB |

### 8.2 Scaling Triggers

| Trigger | Threshold | Action |
|---------|-----------|--------|
| CPU sustained > 80% for 1 hour | Monitor via `docker stats` | Upgrade to next KVM tier |
| RAM sustained > 85% | Monitor via `docker stats` | Increase swap or upgrade tier |
| Disk > 80% used | LINE alert | Clean old backups, upgrade disk |
| Response time p95 > 3s | Health check monitoring | Profile + optimize or scale |
| Documents/month > 20K | Business metric | Consider dedicated worker VPS |

---

## Appendix A: Quick Reference

### SSH Access

```bash
# Demo/PoC
ssh -i ~/.ssh/id_ed25519_hostinger root@76.13.210.250

# UAT
ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.74.232

# PROD
ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.247.9
```

### Hostinger API

```bash
# List VPS
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  https://developers.hostinger.com/api/vps/v1/virtual-machines

# List domains
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  https://developers.hostinger.com/api/domains/v1/portfolio

# DNS records
curl -s -H "Authorization: Bearer $HOSTINGER_API_TOKEN" \
  https://developers.hostinger.com/api/dns/v1/zones/bwcacc.biz
```
