# Copilot Instructions — AI Pre-Accounting Copilot

## ⛔ Workspace Governance (Federated-Hybrid CI/CD)

This repo is the **Execution Plane** for `ai-accounting-copilot`. The **Control Plane** is `Piboonsak/Openclaw`.

- **Authority doc:** `D:\01_gitrepo\Openclaw\docs\governance\federated-hybrid-cicd.md` (read before any sprint or deploy task).
- **Deploys** are dispatched ONLY from `Piboonsak/Openclaw/.github/workflows/`. Do NOT add deploy workflows here.
- **Issue routing:** implementation issues → here (with `Refs: Piboonsak/Openclaw#<N>`); governance / sprint / KI / deploy → in `Piboonsak/Openclaw`.
- **Copilot coding agent:** per-repo enable required (KI-075). Assign via **GraphQL only** (REST returns 422 for bots).
- **Sprint closure:** PR merge ≠ done. Done = merge → deploy → health check → close-with-proof → Feedback Report → KI DB update with folder.

## Project Overview

นี่คือ **AI Pre-Accounting Copilot** — platform สำหรับ automated document processing ด้านบัญชี

**Problem Statement:**
- นักบัญชีใช้เวลามากในการรวบรวม สแกน และตรวจสอบเอกสารบัญชี (ใบกำกับ ใบเสร็จ บิล ฯลฯ)
- ความผิดพลาดมนุษย์จากการกรรมการซ้ำ
- Throughput ต่ำและ error rate สูง

**Solution:**
- OCR + LLM (Claude) สำหรับ extraction, classification, validation
- Human-in-the-loop workflow (human review ก่อน export)
- Excel export ที่ ready สำหรับ accounting system integration
- Audit trail สมบูรณ์

## Project Phases

### Phase 1 – Proof of Concept (PoC)
- **Duration:** 1–2 weeks
- **Fee:** ฿55,000 + VAT
- **Deliverable:** 
  - Extraction proof-of-concept (1–2 rounds)
  - Accuracy report
  - Field mapping guide
  - Recommendation for MVP
- **Input:** 200–300 sample documents + field mapping + requirement docs

### Phase 2 – MVP Production
- **Duration:** 4–6 weeks  
- **Fee:** ฿260,000–350,000 + VAT
- **Includes:**
  - Web UI (drag-drop upload)
  - Document auto-classification
  - Field extraction (validation rules: 4 รูป)
  - Human review workflow
  - Excel export + audit trail
  - User management (Admin/Reviewer)
- **Excludes:**
  - Line-item extraction (batch mode)
  - GL integration
  - Custom trainer
  - Managed human review (outsourced)

## Accuracy Targets (Baseline)

| Document Type | Target Accuracy | Note |
|---|---|---|
| ใบกำกับปกติ (เต็ม) | 90–95% | สวนใจเห็นชัด |
| ใบกำกับอย่างย่อย | 85–90% | เล็กลง |
| ใบสำหรับชำระหนี้ (print) | 80–88% | ความคมชัดแตกต่าง |
| ใบสำหรับชำระหนี้ (ลบเลือน) | 50–70% | low-confidence → flag for human |
| Thermal receipt (clear) | No support | ไม่รับบริการ |
| Thermal receipt (faded) | No support | ไม่รับบริการ |
| Handwritten | No support | ไม่รับบริการ |

⚠️ **Fields with low confidence จะถูก flag ให้ human review ก่อน export**

## Tech Stack & Key Decisions

### Backend
- **Language:** Python 3.12
- **Framework:** FastAPI (async) หรือ Django (flexibility)
- **LLM Integration:** Claude API (messages/batch)
- **OCR:** AWS Textract หรือ Tesseract (opensource)
- **Database:** PostgreSQL (document metadata, extraction results)
- **Storage:** S3 หรือ file server (document images + extracted data)

### Frontend
- **Framework:** React 18+ หรือ Next.js 14 (static export)
- **Language:** TypeScript
- **UI:** Tailwind CSS v4
- **Components:** Shadcn/ui หรือ custom Material UI
- **Features:**
  - Drag-drop upload
  - Document preview (PDF/image viewer)
  - Field editor (inline validation)
  - Approval workflow UI
  - Excel export

### ML Pipeline
- **Document Classification:** Claude + few-shot prompts (invoice vs receipt vs bill)
- **Field Extraction:** Claude structured output (using JSON schema)
- **Validation Rules:** 
  - Required fields check
  - Total amount ≠ qty × price + VAT check
  - Vendor master matching (optional add-on)
  - Date format validation

### Deployment
- **Dev:** Docker Compose (backend + postgres + minio/s3)
- **Prod:** ECS/K8s + RDS + S3 (or on-prem equivalent)
- **CI/CD:** GitHub Actions → build → test → deploy (via Openclaw orchestration)

## Key Files & Directories

```
ai-accounting-copilot/
├── src/
│   ├── backend/           # Python API server
│   │   ├── app/          # FastAPI/Django app
│   │   ├── ml/           # OCR + LLM integration
│   │   ├── services/     # Business logic
│   │   └── tests/        # Backend tests
│   └── frontend/         # React TypeScript
│       ├── components/
│       ├── pages/
│       ├── hooks/
│       └── tests/
├── docker/               # Docker configs
├── docs/                 # Architecture, API specs
├── tests/                # Integration tests
├── .github/
│   ├── workflows/        # CI/CD (per-repo only)
│   └── copilot-instructions.md
├── AGENTS.md
├── CLAUDE.md
├── README.md
└── requirements.txt
```

## Coding Standards

### Python (Backend)
- **Version:** Python 3.12
- **Linter:** ruff (check + format)
- **Type checking:** mypy
- **Testing:** pytest + coverage
- **Format:** Black-compatible formatting via ruff
- **No hardcoded:** API keys, credentials, environment-specific paths

### TypeScript (Frontend)
- **Linter:** ESLint + Prettier
- **Type checking:** tsc
- **Testing:** Vitest + React Testing Library
- **Build:** Vite or Next.js
- **No hardcoded:** API URLs (use env vars), credentials

### Commit Message Style
```
feat(api): add document upload endpoint
fix(ml): improve invoice classification accuracy
docs(setup): add OCR configuration guide
test(backend): add extraction validation tests
infra(docker): update postgres image to 16.0
```

## Development Workflow

1. **Branch naming:** `feature/TASK-ID-short-desc` or `fix/TASK-ID-short-desc`
2. **PR size:** Keep PRs under 400 lines of functional code
3. **Testing:** All new endpoints must have tests (80%+ coverage for critical paths)
4. **Documentation:** Update README/docs if adding new APIs or workflows
5. **Review:** At least 1 approval before merge; CI must pass

## Accuracy Testing & Validation

### Phase 1 PoC Validation
- Process 200–300 sample documents
- Measure extraction accuracy by document type
- Identify fields with < 85% accuracy → flag for improvement
- Create field mapping guide (document format → field names)

### Phase 2 MVP Acceptance Criteria
- Extraction accuracy ≥ targets specified in proposal
- Human review workflow tested with real users
- Excel export validated against accounting system format
- Audit trail captures all changes + who made them
- System handles 500+ documents/day without performance degradation

## Monthly Subscription Plans (After Go-Live)

| Plan | Monthly Fee | Pages/month | Overage | Includes |
|------|------------|------------|---------|----------|
| **Starter** | ฿9,000 | 1,000 | ฿8/page | Cloud hosting, OCR/LLM API, bug fixes, email support |
| **Standard** ⭐ | ฿18,000 | 3,000 | ฿6/page | Standard + monthly accuracy report |
| **Pro** | ฿45,000+ | 10,000 | ฿4–5/page | Pro + dedicated support, custom rules |

**Does NOT include:** Managed human review, custom features, GL integration, template changes > 2/month

## When Adding Features

- **New field extraction:** Update accuracy benchmarks in docs
- **New document type:** Run Phase 1 extraction test again
- **Validation rules:** Add to rules engine + test coverage
- **UI changes:** Include before/after screenshots in PR
- **API changes:** Update Swagger/OpenAPI docs

## Known Issues & Workarounds

- **Thermal receipts:** Not supported (too low quality for LLM)
- **Multi-page invoices:** Split into single pages before processing
- **Handwritten fields:** Flag for manual entry (not OCR-able)
- **Low-confidence extractions:** Always require human review before export

## Links & References

- **Proposal details:** See attachments in Openclaw or vault
- **API design:** [Link to Swagger/docs folder]
- **Architecture ADR:** [docs/decisions/]
- **Accuracy benchmarks:** [docs/accuracy-targets.md]
- **Deployment runbook:** `D:\01_gitrepo\Openclaw\docs\cicd/README.md`

