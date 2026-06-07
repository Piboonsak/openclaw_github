# D7: Backend-Frontend Integration API Architecture

**Status:** Open Design Decision  
**Epic:** 5 (Core Parser) — Integration layer  
**Aligned with:** Master Roadmap Week 2 (Day 8-10), VPS Hostinger deployment  
**Domain:** `demo-aiaccount.yahwan.biz` → production: `app.aiaccount.yahwan.biz`

---

## 1. Network Topology & DNS Layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Hostinger VPS  (76.13.210.250)                                             │
│  OS: Ubuntu 22.04 / Debian 12                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │  Nginx (Host-level reverse proxy + TLS termination)              │       │
│  │  Port 80/443 → Certbot Let's Encrypt auto-renew                 │       │
│  │                                                                  │       │
│  │  server_name: app.aiaccount.yahwan.biz                           │       │
│  │    /           → frontend:3000 (React SPA)                       │       │
│  │    /api/       → backend:8000  (FastAPI)                         │       │
│  │    /ws/        → backend:8000  (WebSocket for processing status) │       │
│  │    /storage/   → minio:9000    (pre-signed redirect, optional)   │       │
│  │                                                                  │       │
│  │  server_name: demo-aiaccount.yahwan.biz                          │       │
│  │    /           → /var/www/demo-aiaccount (static prototype)      │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                             │
│  ┌─────────────────────── Docker Compose Network ───────────────────┐       │
│  │                                                                  │       │
│  │  frontend:3000 ←── React (Vite build, served by nginx-alpine)    │       │
│  │       ↕ /api proxy (in dev: Vite proxy; in prod: host Nginx)     │       │
│  │  backend:8000  ←── FastAPI (uvicorn, --workers 2)                │       │
│  │       ↕                                                          │       │
│  │  postgres:5432 ←── PostgreSQL 16                                 │       │
│  │  redis:6379    ←── Redis 7 (task queue + cache)                  │       │
│  │  minio:9000    ←── S3-compatible storage                         │       │
│  │  worker        ←── Celery worker (OCR + LLM async tasks)         │       │
│  │                                                                  │       │
│  └──────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### DNS Records (Hostinger DNS panel)

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | `app.aiaccount` | `76.13.210.250` | 3600 |
| A | `demo-aiaccount` | `76.13.210.250` | 3600 |
| CNAME | `api.aiaccount` | `app.aiaccount.yahwan.biz` | 3600 |

> **Decision**: Use path-based routing (`/api/`) over subdomain routing to avoid extra TLS certs and CORS complexity.

---

## 2. TLS / Certificate Strategy

```bash
# Initial setup (one-time on VPS)
certbot --nginx \
  -d app.aiaccount.yahwan.biz \
  -d demo-aiaccount.yahwan.biz \
  --non-interactive --agree-tos -m admin@yahwan.biz

# Auto-renewal via systemd timer (certbot default)
# Verify: systemctl list-timers | grep certbot
```

- **Protocol:** TLS 1.2+ only (Nginx `ssl_protocols TLSv1.2 TLSv1.3;`)
- **HSTS:** Enabled with `max-age=31536000`
- **Certificate:** Let's Encrypt (auto-renew every 60 days)

---

## 3. API Architecture — Endpoint Contract

### Base URLs

| Environment | Frontend | API |
|---|---|---|
| **Local Dev** | `http://localhost:3000` | `http://localhost:8000/api` |
| **SIT (VPS)** | `https://app.aiaccount.yahwan.biz` | `https://app.aiaccount.yahwan.biz/api` |
| **Demo** | `https://demo-aiaccount.yahwan.biz` | N/A (static only) |

### API Versioning

```
/api/v1/...
```

Single version for PoC/MVP. Version bump only on breaking changes.

---

## 4. REST API Endpoints (Mapped to UI Steps)

### Step 1: Upload

| Method | Endpoint | Purpose | Request | Response |
|--------|----------|---------|---------|----------|
| `POST` | `/api/v1/documents/upload` | Upload batch of files | `multipart/form-data` (files[] + company_id) | `{ batch_id, files: [{id, filename, status}] }` |
| `GET` | `/api/v1/companies` | List companies for selector | — | `[{id, name, tax_id}]` |
| `POST` | `/api/v1/documents/upload/validate-taxid` | Pre-check TaxID on file | `{file_id, detected_taxid}` | `{match: bool, expected, detected}` |

### Step 2: Select / Confirm Queue

| Method | Endpoint | Purpose | Request | Response |
|--------|----------|---------|---------|----------|
| `GET` | `/api/v1/batches/{batch_id}/files` | Get file list with status | — | `[{id, filename, size, taxid_match, selected}]` |
| `PATCH` | `/api/v1/batches/{batch_id}/files` | Update selection | `{file_ids: [], action: "select"|"deselect"|"remove"}` | `{updated: int}` |

### Step 3: Processing (Async Pipeline)

| Method | Endpoint | Purpose | Request | Response |
|--------|----------|---------|---------|----------|
| `POST` | `/api/v1/batches/{batch_id}/process` | Start processing | `{file_ids: []}` | `{job_id, status: "queued"}` |
| `GET` | `/api/v1/jobs/{job_id}/status` | Poll job status | — | `{status, progress, files: [{id, stages: {ocr, classify, extract, map_coa}}]}` |
| `WS` | `/ws/v1/jobs/{job_id}` | Real-time progress stream | — | Server-sent events per file/stage |

#### Processing Stages (per file):

```json
{
  "file_id": "uuid",
  "stages": {
    "ocr":      {"status": "done", "duration_ms": 1200},
    "classify": {"status": "done", "result": "invoice", "confidence": 0.97},
    "extract":  {"status": "running", "progress": 0.6},
    "map_coa":  {"status": "pending"}
  }
}
```

### Step 4: Scan Review (Header Fields)

| Method | Endpoint | Purpose | Request | Response |
|--------|----------|---------|---------|----------|
| `GET` | `/api/v1/batches/{batch_id}/extractions` | List all extractions | `?status=pending_review` | `[{file_id, doc_type, confidence, fields, flags}]` |
| `GET` | `/api/v1/documents/{doc_id}/extraction` | Single extraction detail | — | `{fields, confidence_scores, validation_errors, preview_url}` |
| `GET` | `/api/v1/documents/{doc_id}/preview` | PDF/image preview URL | — | `{url: "pre-signed S3 URL", pages: 1}` |
| `PUT` | `/api/v1/documents/{doc_id}/extraction` | Update fields (human edit) | `{fields: {invoice_date, seller_tax_id, ...}}` | `{validated: bool, errors: []}` |
| `POST` | `/api/v1/documents/{doc_id}/approve-header` | Approve header fields | — | `{status: "header_approved"}` |
| `POST` | `/api/v1/batches/{batch_id}/approve-all-headers` | Bulk approve | `{file_ids: []}` | `{approved: int, failed: int}` |

#### Extraction Fields Schema (Step 4 form fields):

```json
{
  "invoice_date": "2026-01-15",
  "invoice_number": "INV-2605-001",
  "seller_tax_id": "0105559654321",
  "seller_name": "บริษัท เมโทรอิเล็คทริค จำกัด",
  "buyer_tax_id": "0105559123456",
  "buyer_name": "บริษัท ยะวัน เทค จำกัด",
  "net_amount": 10000.00,
  "vat_amount": 700.00,
  "wht_rate": 3,
  "wht_amount": 300.00,
  "discount": 0.00,
  "gross_amount": 10400.00
}
```

### Step 5: COA Mapping Review

| Method | Endpoint | Purpose | Request | Response |
|--------|----------|---------|---------|----------|
| `GET` | `/api/v1/batches/{batch_id}/vouchers` | List voucher journal entries | — | `[{doc_id, voucher_no, lines: [{account_code, account_name, dr, cr}]}]` |
| `GET` | `/api/v1/companies/{company_id}/coa` | Get COA dropdown options | — | `[{code, name, type}]` |
| `PUT` | `/api/v1/documents/{doc_id}/voucher` | Update COA mapping | `{lines: [{account_code, dr, cr}]}` | `{balanced: bool, total_dr, total_cr}` |
| `POST` | `/api/v1/documents/{doc_id}/confirm-mapping` | Confirm mapping (trains model) | — | `{status: "mapping_confirmed"}` |
| `POST` | `/api/v1/batches/{batch_id}/confirm-all-mappings` | Bulk confirm | — | `{confirmed: int}` |

### Step 6: Export

| Method | Endpoint | Purpose | Request | Response |
|--------|----------|---------|---------|----------|
| `POST` | `/api/v1/batches/{batch_id}/export` | Generate export file | `{format: "csv", columns: [...], preset: "express_gl"}` | `{export_id, download_url}` |
| `GET` | `/api/v1/exports/{export_id}/download` | Download generated file | — | `application/octet-stream` (CSV) |
| `GET` | `/api/v1/exports/{export_id}/preview` | Preview first N rows | `?rows=6` | `{headers: [...], rows: [[...]]}` |

### Settings / Admin

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/v1/companies` | List companies |
| `POST` | `/api/v1/companies` | Create company |
| `PUT` | `/api/v1/companies/{id}` | Update company |
| `POST` | `/api/v1/companies/{id}/coa/import` | Import COA from CSV |
| `GET` | `/api/v1/companies/{id}/coa` | Get COA list |
| `POST` | `/api/v1/auth/login` | Login |
| `POST` | `/api/v1/auth/logout` | Logout |
| `GET` | `/api/v1/auth/me` | Current user |

### Health & Utility

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/v1/health` | Readiness check |
| `GET` | `/api/v1/health/ready` | Deep health (DB + Redis + Storage) |

---

## 5. Authentication & Security

### Auth Flow (Session-based for PoC, JWT upgrade for MVP)

```
Frontend                          Backend
   │                                 │
   │── POST /api/v1/auth/login ─────▶│  Verify credentials
   │◀── Set-Cookie: session_id ──────│  Create session in Redis
   │                                 │
   │── GET /api/v1/documents ────────▶│  Validate session cookie
   │   (Cookie: session_id)          │
   │◀── 200 OK + data ──────────────│
```

### Security Headers (Nginx)

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:;" always;
add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
```

### CORS Policy

```python
# FastAPI CORS (only needed for local dev; in prod Nginx handles same-origin)
origins = [
    "http://localhost:3000",       # Vite dev server
    "http://localhost:5173",       # Vite alt port
]
# Production: same-origin (no CORS needed — path-based routing)
```

### Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| `/api/v1/auth/login` | 5 | 1 min |
| `/api/v1/documents/upload` | 20 | 1 min |
| `/api/v1/batches/*/process` | 5 | 1 min |
| General API | 100 | 1 min |

---

## 6. WebSocket Protocol (Real-time Processing Updates)

```
Client connects:  ws://app.aiaccount.yahwan.biz/ws/v1/jobs/{job_id}

Server sends events:
{
  "event": "stage_update",
  "file_id": "uuid",
  "stage": "ocr",
  "status": "done",
  "duration_ms": 1200,
  "timestamp": "2026-06-05T10:30:00Z"
}

{
  "event": "job_complete",
  "summary": {
    "total": 12,
    "success": 11,
    "failed": 1,
    "duration_ms": 35000
  }
}
```

**Fallback:** If WebSocket unavailable, client polls `GET /api/v1/jobs/{job_id}/status` every 3 seconds.

---

## 7. File Upload Strategy

### Upload Flow

```
Browser                    Nginx                   Backend                 MinIO/S3
  │                          │                       │                       │
  │── POST /upload ──────────▶│── proxy_pass ─────────▶│                       │
  │   (multipart, 50MB max)  │   client_max_body 50m  │                       │
  │                          │                       │── PUT object ─────────▶│
  │                          │                       │◀── 200 OK ────────────│
  │◀── 201 {batch_id} ──────│◀──────────────────────│                       │
```

### Nginx Config for Upload

```nginx
location /api/v1/documents/upload {
    client_max_body_size 50m;
    proxy_pass http://backend:8000;
    proxy_request_buffering off;  # Stream to backend
    proxy_read_timeout 120s;
}
```

### Storage Layout (MinIO/S3)

```
bucket: ai-accounting-{env}/
├── {company_id}/
│   ├── uploads/
│   │   └── {batch_id}/
│   │       ├── {file_id}.pdf
│   │       └── {file_id}.jpg
│   ├── cache/
│   │   └── {sha256}/
│   │       ├── ocr_output.json
│   │       ├── extraction_output.json
│   │       └── journal_output.json
│   └── exports/
│       └── {export_id}/
│           └── Express-Journal.csv
```

---

## 8. Nginx Production Config

```nginx
# /etc/nginx/conf.d/app-aiaccount.conf

upstream backend {
    server 127.0.0.1:8000;
    keepalive 32;
}

upstream frontend {
    server 127.0.0.1:3000;
}

server {
    listen 80;
    server_name app.aiaccount.yahwan.biz;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name app.aiaccount.yahwan.biz;

    # TLS (managed by Certbot)
    ssl_certificate /etc/letsencrypt/live/app.aiaccount.yahwan.biz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.aiaccount.yahwan.biz/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # API routes → Backend
    location /api/ {
        proxy_pass http://backend/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Connection "";

        # Upload size
        client_max_body_size 50m;
        proxy_read_timeout 120s;
    }

    # WebSocket → Backend
    location /ws/ {
        proxy_pass http://backend/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400s;
    }

    # Frontend SPA → React container
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # SPA fallback
        proxy_intercept_errors on;
        error_page 404 = /index.html;
    }

    # Static assets caching
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        proxy_pass http://frontend;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

---

## 9. Docker Compose — Production Stack

```yaml
# docker/docker-compose.prod.yml
version: '3.8'

services:
  backend:
    image: ghcr.io/yahwan-shop/ai-accounting-backend:${TAG:-latest}
    container_name: aiaccount-api
    restart: unless-stopped
    environment:
      STAGE: production
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASS}@postgres:5432/ai_accounting
      REDIS_URL: redis://redis:6379/0
      STORAGE_PROVIDER: minio
      STORAGE_ENDPOINT: http://minio:9000
      STORAGE_BUCKET: ai-accounting-prod
      STORAGE_ACCESS_KEY: ${MINIO_ACCESS_KEY}
      STORAGE_SECRET_KEY: ${MINIO_SECRET_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      LLM_MODEL: claude-haiku-4-20250414
      SECRET_KEY: ${SECRET_KEY}
      ALLOWED_ORIGINS: https://app.aiaccount.yahwan.biz
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - internal

  worker:
    image: ghcr.io/yahwan-shop/ai-accounting-backend:${TAG:-latest}
    container_name: aiaccount-worker
    restart: unless-stopped
    command: celery -A src.worker worker --loglevel=info --concurrency=2
    environment:
      DATABASE_URL: postgresql://${DB_USER}:${DB_PASS}@postgres:5432/ai_accounting
      REDIS_URL: redis://redis:6379/0
      STORAGE_PROVIDER: minio
      STORAGE_ENDPOINT: http://minio:9000
      STORAGE_BUCKET: ai-accounting-prod
      STORAGE_ACCESS_KEY: ${MINIO_ACCESS_KEY}
      STORAGE_SECRET_KEY: ${MINIO_SECRET_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      LLM_MODEL: claude-haiku-4-20250414
    depends_on:
      - backend
      - redis
    networks:
      - internal

  frontend:
    image: ghcr.io/yahwan-shop/ai-accounting-frontend:${TAG:-latest}
    container_name: aiaccount-ui
    restart: unless-stopped
    ports:
      - "127.0.0.1:3000:80"
    networks:
      - internal

  postgres:
    image: postgres:16-alpine
    container_name: aiaccount-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASS}
      POSTGRES_DB: ai_accounting
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER}"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal

  redis:
    image: redis:7-alpine
    container_name: aiaccount-cache
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal

  minio:
    image: minio/minio:latest
    container_name: aiaccount-storage
    restart: unless-stopped
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_ACCESS_KEY}
      MINIO_ROOT_PASSWORD: ${MINIO_SECRET_KEY}
    volumes:
      - minio_data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - internal

volumes:
  pg_data:
  minio_data:

networks:
  internal:
    driver: bridge
```

---

## 10. Frontend API Client Architecture

```typescript
// src/frontend/src/api/client.ts

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

interface ApiResponse<T> {
  data: T;
  error?: { code: string; message: string };
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl;
  }

  // Step 1: Upload
  async uploadDocuments(companyId: string, files: File[]): Promise<ApiResponse<Batch>> {
    const formData = new FormData();
    formData.append('company_id', companyId);
    files.forEach(f => formData.append('files', f));
    return this.post('/documents/upload', formData);
  }

  // Step 3: Start Processing
  async startProcessing(batchId: string, fileIds: string[]): Promise<ApiResponse<Job>> {
    return this.post(`/batches/${batchId}/process`, { file_ids: fileIds });
  }

  // Step 3: WebSocket connection for real-time updates
  connectJobStream(jobId: string, onEvent: (e: JobEvent) => void): WebSocket {
    const wsUrl = `${this.baseUrl.replace('http', 'ws').replace('/api/v1', '/ws/v1')}/jobs/${jobId}`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (msg) => onEvent(JSON.parse(msg.data));
    return ws;
  }

  // Step 4: Extraction review
  async getExtraction(docId: string): Promise<ApiResponse<Extraction>> {
    return this.get(`/documents/${docId}/extraction`);
  }

  async updateExtraction(docId: string, fields: ExtractionFields): Promise<ApiResponse<ValidationResult>> {
    return this.put(`/documents/${docId}/extraction`, { fields });
  }

  async approveHeader(docId: string): Promise<ApiResponse<void>> {
    return this.post(`/documents/${docId}/approve-header`);
  }

  // Step 5: COA Mapping
  async getVouchers(batchId: string): Promise<ApiResponse<Voucher[]>> {
    return this.get(`/batches/${batchId}/vouchers`);
  }

  async getCOA(companyId: string): Promise<ApiResponse<COAEntry[]>> {
    return this.get(`/companies/${companyId}/coa`);
  }

  async updateVoucher(docId: string, lines: VoucherLine[]): Promise<ApiResponse<BalanceCheck>> {
    return this.put(`/documents/${docId}/voucher`, { lines });
  }

  // Step 6: Export
  async generateExport(batchId: string, config: ExportConfig): Promise<ApiResponse<ExportResult>> {
    return this.post(`/batches/${batchId}/export`, config);
  }

  // Generic methods...
  private async get<T>(path: string): Promise<ApiResponse<T>> { /* ... */ }
  private async post<T>(path: string, body?: any): Promise<ApiResponse<T>> { /* ... */ }
  private async put<T>(path: string, body: any): Promise<ApiResponse<T>> { /* ... */ }
}

export const api = new ApiClient(BASE_URL);
```

---

## 11. Request/Response Data Flow per UI Step

```
┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐     ┌────────┐
│ Step 1 │────▶│ Step 2 │────▶│ Step 3 │────▶│ Step 4 │────▶│ Step 5 │────▶│ Step 6 │
│Upload  │     │Select  │     │Process │     │Scan Rev│     │Map Rev │     │Export  │
└────────┘     └────────┘     └────────┘     └────────┘     └────────┘     └────────┘
    │               │              │              │              │              │
    ▼               ▼              ▼              ▼              ▼              ▼
POST /upload   GET /batch/    POST /process   GET /extract   GET /vouchers  POST /export
               files          WS /jobs/{id}   PUT /extract   PUT /voucher   GET /download
                                              POST /approve  POST /confirm
```

### State Machine (Document Lifecycle)

```
UPLOADED → QUEUED → PROCESSING → EXTRACTED → HEADER_APPROVED → MAPPING_CONFIRMED → EXPORTED
                         │
                         ▼ (on error)
                      FAILED
```

---

## 12. Error Contract

All errors follow a consistent schema:

```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "Net amount + VAT does not equal gross amount",
    "details": {
      "field": "gross_amount",
      "expected": 10700.00,
      "actual": 10400.00
    },
    "request_id": "req_abc123",
    "timestamp": "2026-06-05T10:30:00Z"
  }
}
```

### Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `AUTH_REQUIRED` | 401 | Missing or invalid session |
| `FORBIDDEN` | 403 | Insufficient role |
| `NOT_FOUND` | 404 | Resource not found |
| `VALIDATION_FAILED` | 422 | Business rule violation |
| `UPLOAD_TOO_LARGE` | 413 | File exceeds 50MB |
| `RATE_LIMITED` | 429 | Too many requests |
| `PROCESSING_FAILED` | 500 | OCR/LLM pipeline error |
| `SERVICE_UNAVAILABLE` | 503 | Downstream service down |

---

## 13. Environment Variables (.env template)

```env
# .env.production (stored in VPS, NOT in git)
STAGE=production
SECRET_KEY=<random-64-char>
DB_USER=aiaccount
DB_PASS=<strong-password>
ANTHROPIC_API_KEY=sk-ant-xxx
MINIO_ACCESS_KEY=<minio-user>
MINIO_SECRET_KEY=<minio-pass>
ALLOWED_ORIGINS=https://app.aiaccount.yahwan.biz
```

---

## 14. Deployment Sequence (GitHub Actions → VPS)

```
Developer pushes to main
    ↓
GitHub Actions (in Piboonsak/Openclaw)
    ├── Build backend Docker image → ghcr.io
    ├── Build frontend Docker image → ghcr.io
    └── Deploy to VPS via SSH
         ├── docker compose pull
         ├── docker compose up -d
         ├── Wait for health checks
         └── Report status
```

### Health Check Endpoints

```bash
# Liveness (is the process running?)
curl https://app.aiaccount.yahwan.biz/api/v1/health
# → {"status": "ok", "version": "0.1.0"}

# Readiness (are dependencies connected?)
curl https://app.aiaccount.yahwan.biz/api/v1/health/ready
# → {"status": "ok", "db": "connected", "redis": "connected", "storage": "connected"}
```

---

## 15. Decision Log

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| D7-1 | Path-based routing (`/api/`) vs subdomain | Simpler TLS, no CORS, single cert | **Decided** |
| D7-2 | Session cookies vs JWT | Session simpler for PoC; JWT for mobile later | **Decided: Session** |
| D7-3 | WebSocket vs SSE for processing | WS = bidirectional, SSE = simpler; use WS with SSE fallback | **Decided: WS + poll fallback** |
| D7-4 | Celery vs Python-RQ for async tasks | Celery more mature, supports priorities | **Decided: Celery** |
| D7-5 | Single Docker Compose vs separate services | Single compose for PoC VPS simplicity | **Decided: Single Compose** |
| D7-6 | MinIO vs local filesystem | MinIO = S3 compatible, portable to cloud later | **Decided: MinIO** |

---

## 16. Next Steps

1. **Implement** `src/api/routes/` with FastAPI router structure matching §4
2. **Create** frontend API client module (`src/frontend/src/api/`)
3. **Configure** Nginx prod config on VPS
4. **Set up** DNS A record for `app.aiaccount.yahwan.biz`
5. **Create** GitHub Actions workflow for Docker build + deploy (in Openclaw)
6. **Test** end-to-end flow: upload → process → review → export

---

*Last Updated: 2026-06-05*  
*Owner: Backend + DevOps Lead*  
*Refs: MASTER-ROADMAP.md, EPIC-5-HOWTO-DESIGN-DISCUSSION.html*
