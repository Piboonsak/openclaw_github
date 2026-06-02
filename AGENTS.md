# ai-accounting-copilot — AI Agent Instructions

> Auto-loaded by Claude, Copilot, Cursor, and other AI agents.
> For cross-repo standards: `D:\01_gitrepo\ai-instruction\guidelines\AI-AGENT-STANDARDS.md`
> For CI/CD procedures (mandatory): `D:\01_gitrepo\Openclaw\docs\cicd\README.md`
> **For workspace governance (Federated-Hybrid CI/CD model):** `D:\01_gitrepo\Openclaw\docs\governance\federated-hybrid-cicd.md`
> **📍 Path Resolution:** `D:\01_gitrepo\...` = laptop paths. On VPS/CI, use `gh api` or repo-relative paths. See `Piboonsak/Openclaw` → `data/orchestration/repo-path-map.json`

---

## ⛔ CI/CD Process Compliance (Non-Negotiable)

ALL AI agents MUST follow the CI/CD process for any deploy, fix, or debug task:

- Read `D:\01_gitrepo\Openclaw\docs\cicd\README.md` before starting
- Never skip procedure steps — follow checklists IN ORDER
- **Never stop mid-procedure** — complete the full procedure in one session
- Never modify production VPS directly — all changes via Git + GitHub Actions

---

## ⛔ Federated-Hybrid Workspace Rule (Authority)

This repo is the **Execution Plane** for `ai-accounting-copilot`. The **Control Plane** is `Piboonsak/Openclaw`.

- **Production deploys** are dispatched ONLY from `Piboonsak/Openclaw/.github/workflows/`. Do NOT add deploy workflows here.
- **Per-repo CI** (lint/typecheck/build/test) lives in `.github/workflows/` of THIS repo.
- **Issue routing:**
  - Implementation issues confined to this repo → open here, with body containing `Refs: Piboonsak/Openclaw#<governance-issue>` and `Sprint: X.Y` and `Risk: LOW|MEDIUM|HIGH|CRITICAL`.
  - Governance / sprint / cross-repo / KI issues → open in `Piboonsak/Openclaw`.
- **Copilot coding agent:** must be enabled by repo owner UI (KI-075). Run the precheck before dispatching to a new sprint. Assign via **GraphQL only** (REST returns 422).
- **Sprint closure:** PR merge ≠ done. Done = merge → Openclaw deploy → health check → close-with-proof → Feedback Report (in Openclaw) → KI DB update with folder.

Full RACI / risk-tier gate / KI-075 precheck → `D:\01_gitrepo\Openclaw\docs\governance\federated-hybrid-cicd.md`.

---

## What This Repo Is

`ai-accounting-copilot` is a **Human-in-the-Loop AI platform for pre-accounting document processing**.

**Core Use Case:**
- OCR + LLM extraction of accounting documents (invoices, receipts, bills)
- Document classification, field extraction, validation
- Human review workflow with audit trail
- Excel export for accounting system integration

**Tech Stack:**
- **Backend:** Python 3.12 + FastAPI/Django
- **Frontend:** TypeScript/React (web UI)
- **ML Pipeline:** OCR (Tesseract/AWS Textract) + Claude LLM
- **Database:** PostgreSQL (document metadata, extraction results)
- **Deployment:** Docker Compose + Nginx

See `.github/copilot-instructions.md` for project-specific rules.

---

## Project Phases

| Phase | Duration | Fee | Deliverable |
|-------|----------|-----|-------------|
| **Phase 1 – PoC** | 1–2 weeks | ฿55,000 | Extraction proof-of-concept, accuracy report, field mapping guide |
| **Phase 2 – MVP** | 4–6 weeks | ฿260,000–350,000 | Web UI, document classification, field extraction, human review workflow, Excel export, user management |

---

## Commit Conventions

- `feat(api):` — new API endpoints
- `feat(ui):` — new UI features/components
- `fix(core):` — bug fixes in core logic
- `docs(project):` — documentation updates
- `infra(docker):` — Docker/deployment changes
- `test(unit):` — unit test additions
- Never commit secrets, tokens, or real credentials.

---

## Key Files & Directories

| Path | Purpose |
|------|---------|
| `src/backend/` | Python FastAPI/Django application |
| `src/frontend/` | React web application |
| `src/ml/` | OCR pipeline, LLM integration, extraction logic |
| `docker/` | Docker & Compose configs |
| `.github/workflows/` | CI/CD pipelines (per-repo only) |
| `docs/` | Architecture, API specs, runbooks |
| `tests/` | Unit & integration tests |
| `.github/copilot-instructions.md` | Project-specific AI guidelines |

---

## Development Commands

| Command | Purpose |
|---------|---------|
| `pnpm install` / `pip install -r requirements.txt` | Install dependencies |
| `pnpm dev` / `python manage.py runserver` | Start dev server |
| `pnpm build` / `python setup.py build` | Build project |
| `pnpm test` / `pytest` | Run tests |
| `pnpm lint` | Lint code (ESLint/Ruff) |
| `docker-compose up` | Start all services (dev) |

---

## Sprint & Issue Management

- **Issue board:** GitHub Issues in this repo
- **Sprint tracking:** Linked to `Piboonsak/Openclaw` for governance
- **Risk classification:** LOW / MEDIUM / HIGH / CRITICAL (required in PR body)
- **Acceptance criteria:** Always include in issue description

---

## Related Repositories

| Repo | Role |
|------|------|
| `Piboonsak/Openclaw` | Control Plane (governance, CI/CD, sprints) |
| `Piboonsak/ai-instruction` | AI guidelines & prompt templates |
| `YAHWAN-SHOP/yahwan_website` | Template reference |
| `YAHWAN-SHOP/AI-Dev-Factory` | Gate & policy reference |

---

## Helpful Links

- **AI Standards:** `D:\01_gitrepo\ai-instruction\guidelines\AI-AGENT-STANDARDS.md`
- **Connection Details:** `D:\01_gitrepo\Openclaw\docs\connection.md`
- **CI/CD Index:** `D:\01_gitrepo\Openclaw\docs\cicd\README.md`
- **Federated-Hybrid Model:** `D:\01_gitrepo\Openclaw\docs\governance\federated-hybrid-cicd.md`

