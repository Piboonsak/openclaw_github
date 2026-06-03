# Development Setup Guide

## Prerequisites

- **Python 3.12+**
- **Node.js 18+** (pnpm preferred)
- **PostgreSQL 15+**
- **Docker & Docker Compose** (optional, but recommended)
- **Git**

## Option 1: Docker Compose (Recommended)

### 1. Clone & Navigate
```bash
cd d:\01_gitrepo\ai-accounting-copilot
```

### 2. Set up Environment
```bash
# Copy example env
copy .env.example .env

# Edit .env with your settings (Claude API key, etc.)
notepad .env
```

### 3. Start Services
```bash
# Build and start all containers
docker-compose -f docker/docker-compose.dev.yml up --build

# In background (detached mode)
docker-compose -f docker/docker-compose.dev.yml up -d

# View logs
docker-compose -f docker/docker-compose.dev.yml logs -f backend
docker-compose -f docker/docker-compose.dev.yml logs -f frontend

# Stop services
docker-compose -f docker/docker-compose.dev.yml down
```

### 4. Access Applications
- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs
- **Database:** localhost:5432 (copilot / dev_password)
- **Redis:** localhost:6379

---

## Option 2: Local Development (Manual)

### Backend Setup

#### 1. Python Virtual Environment
```bash
# Create virtual env
python -m venv venv

# Activate
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

#### 3. Database Setup
```bash
# Create PostgreSQL database
createdb -U postgres ai_accounting

# Run migrations (if using Alembic)
alembic upgrade head
```

#### 4. Environment Variables
```bash
# Create .env file
copy .env.example .env

# Edit with your settings
# Key variables:
# DATABASE_URL=postgresql://user:password@localhost:5432/ai_accounting
# CLAUDE_API_KEY=sk-...
# ENVIRONMENT=development
```

#### 5. Start Backend
```bash
# Run with auto-reload
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or using standard Python
python manage.py runserver  # if using Django
```

Backend will be available at: **http://localhost:8000**

### Frontend Setup

#### 1. Install Dependencies
```bash
cd src/frontend
pnpm install
# or: npm install
```

#### 2. Environment Variables
```bash
# Create .env.local
echo REACT_APP_API_URL=http://localhost:8000 > .env.local
```

#### 3. Start Dev Server
```bash
pnpm dev
# or: npm run dev
```

Frontend will be available at: **http://localhost:3000**

---

## Option 3: Production Deployment (Cloud WebApp Hosting)

This option is for real customer usage where Accountant, Manager, and Owner access the system from their own PCs via HTTPS.

### 1. Recommended Production Topology

1. Frontend hosted on cloud web hosting/CDN
2. Backend API hosted on cloud compute (container service)
3. Managed PostgreSQL for application data
4. Object storage for uploaded files and generated exports
5. HTTPS termination via load balancer or reverse proxy

### 2. Production Environment Variables

Configure environment variables in production secret store (not in source files):

```bash
ENVIRONMENT=production
API_BASE_URL=https://<your-domain>
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<db>
CLAUDE_API_KEY=<secret>
STORAGE_BUCKET=<bucket-name>
EXPORT_MODE=manual_or_auto
```

### 3. HTTPS and Domain

1. Bind application to company domain (for example `app.company.com`)
2. Install valid TLS certificate
3. Redirect HTTP to HTTPS
4. Enable HSTS and secure cookies

### 4. User Access Validation

Verify these user journeys on production URL:

1. Accountant uploads local files from own PC via browser
2. Manager views review queue and approval status
3. Owner views summary dashboard and export status

---

## Option 4: On-Prem Express Account Integration

This option connects cloud output CSV with Express Account installed on office on-prem server.

### Mode A: Manual CSV Transfer

1. Accountant clicks export CSV from Step 6
2. CSV is downloaded to local PC
3. User copies CSV to office import location
4. Express Account operator imports file

### Mode B: Assisted Auto Sync (Optional)

1. Cloud app generates CSV to integration endpoint/shared transfer area
2. Office sync service receives file into Express import folder
3. Scheduled import job executes on Express server
4. Import status is logged for reconciliation

### On-Prem Server Checklist

1. Prepare dedicated import folder on office server
2. Restrict access rights for import folder
3. Define file naming policy and archive policy
4. Define retry and failure handling process
5. Keep import logs (timestamp, filename, status, operator/service)

### Office Network Checklist

1. Allow outbound HTTPS from user PCs to cloud webapp
2. For auto sync, allow secure route between cloud integration point and office gateway (VPN/IP allowlist)
3. Validate DNS and certificate trust on all user PCs
4. Test upload and import with sample CSV before go-live

---

## Testing

### Backend Tests
```bash
# Run all tests
pytest tests/

# With coverage report
pytest tests/ --cov=src/backend --cov-report=html

# Run specific test file
pytest tests/test_extraction.py -v

# Run with markers
pytest -m unit  # only unit tests
pytest -m integration  # only integration tests
```

### Frontend Tests
```bash
cd src/frontend

# Run all tests
pnpm test

# With coverage
pnpm test:coverage

# Watch mode
pnpm test --watch
```

---

## Code Quality

### Python
```bash
# Lint with ruff
ruff check src/

# Auto-format
ruff format src/

# Type checking
mypy src/backend

# All checks together
ruff check src/ && mypy src/backend && pytest tests/
```

### TypeScript
```bash
cd src/frontend

# ESLint
pnpm lint

# Type check
pnpm typecheck

# Format
pnpm format
```

---

## Project Structure Walkthrough

```
ai-accounting-copilot/
├── src/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── main.py           # FastAPI app entry point
│   │   │   ├── models.py         # SQLAlchemy models (Document, Extraction, etc.)
│   │   │   ├── schemas.py        # Pydantic models for API requests/responses
│   │   │   └── api/
│   │   │       ├── documents.py  # Document endpoints
│   │   │       ├── extractions.py # Extraction endpoints
│   │   │       └── auth.py       # Auth endpoints
│   │   ├── ml/
│   │   │   ├── ocr.py            # OCR (Tesseract/Textract)
│   │   │   ├── classifier.py     # Document classification (Claude)
│   │   │   ├── extractor.py      # Field extraction (Claude)
│   │   │   └── validator.py      # Validation rules engine
│   │   ├── services/
│   │   │   ├── document.py       # Document business logic
│   │   │   ├── extraction.py     # Extraction processing
│   │   │   ├── audit.py          # Audit logging
│   │   │   └── export.py         # Excel export
│   │   └── tests/
│   │       ├── test_api.py
│   │       ├── test_ml.py
│   │       └── test_services.py
│   │
│   └── frontend/
│       ├── src/
│       │   ├── components/       # React components (Upload, Review, etc.)
│       │   ├── pages/            # Page components
│       │   ├── hooks/            # Custom hooks
│       │   ├── services/         # API client
│       │   ├── types/            # TypeScript types
│       │   └── App.tsx           # Root component
│       ├── public/               # Static files
│       ├── tests/                # Frontend tests
│       └── package.json
│
├── docker/
│   ├── docker-compose.dev.yml    # Development environment
│   ├── Dockerfile.backend
│   └── Dockerfile.frontend
│
├── docs/
│   ├── ARCHITECTURE.md           # System design
│   ├── SETUP.md                  # This file
│   ├── API.md                    # API documentation
│   └── ACCURACY.md               # Accuracy benchmarks
│
├── tests/                        # Integration tests
├── .github/workflows/            # CI/CD pipelines
├── AGENTS.md
├── CLAUDE.md
├── README.md
└── requirements.txt
```

---

## Troubleshooting

### PostgreSQL Connection Error
```
Error: could not translate host name "postgres" to address

Solution:
- If using Docker: ensure postgres service is running
- If local: check DATABASE_URL in .env
- Verify postgres is running: psql -U postgres -l
```

### Python Package Not Found
```
Solution:
- Activate venv: source venv/bin/activate
- Reinstall: pip install -r requirements.txt
```

### Frontend API Connection Error
```
Error: API request failed (CORS error, 404, etc.)

Solution:
- Ensure backend is running on port 8000
- Check REACT_APP_API_URL in .env.local
- Check browser console for actual error
```

### Docker Port Already in Use
```
Solution:
docker ps  # list running containers
docker stop <container_id>  # stop conflicting container
# or change port in docker-compose.dev.yml
```

---

## Next Steps

1. **Read ARCHITECTURE.md** for system design overview
2. **Check API.md** for endpoint documentation
3. **Run tests** to verify setup: `pytest tests/`
4. **Start developing!** Pick a task from GitHub Issues

---

Last Updated: 2026-06-02
