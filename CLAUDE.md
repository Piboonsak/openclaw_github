# Claude Instructions — ai-accounting-copilot

> See `AGENTS.md` in this repo for full instructions.

**AI agent standards (all repos):** `D:\01_gitrepo\ai-instruction\guidelines\AI-AGENT-STANDARDS.md`
**CI/CD procedures (mandatory):** `D:\01_gitrepo\Openclaw\docs\cicd\README.md`
**Project-specific rules:** `.github/copilot-instructions.md`

## ⛔ CI/CD Process Compliance (Non-Negotiable)

ALL AI agents working in this workspace MUST follow the CI/CD process:

- Read `D:\01_gitrepo\Openclaw\docs\cicd\README.md` before any deploy, fix, or debug task
- Never skip procedure steps — follow checklists IN ORDER
- Never stop mid-procedure — complete the full procedure in one session
- Never modify production VPS directly — all changes via Git + GitHub Actions

## Tech Stack Quick Reference

- **Backend:** Python 3.12, FastAPI or Django
- **Frontend:** TypeScript/React
- **ML:** OpenAI/Claude LLM + OCR (Tesseract or AWS Textract)
- **Database:** PostgreSQL
- **Testing:** pytest (backend), Vitest/Jest (frontend)
- **Deployment:** Docker Compose + GitHub Actions

## Before Starting Any Task

1. Read `.github/copilot-instructions.md` for project context
2. Check `docs/ARCHITECTURE.md` (if exists) for system design
3. Read relevant section in `D:\01_gitrepo\Openclaw\docs\cicd\README.md`
4. Understand phase (PoC vs MVP) and current sprint

