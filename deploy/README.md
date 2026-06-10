# Deploy — AI Pre-Accounting Copilot

Quick-reference for deploying each environment.  
All production/PoC deploys are triggered from the **Control Plane** (`Piboonsak/Openclaw`).

> **Full CI/CD process & quality gates:** See [`docs/CICD/design-control-cicd-process.md`](../docs/CICD/design-control-cicd-process.md)

---

## Environment Matrix

| Env | Branch | Domain | Type | Workflow |
| --- | --- | --- | --- | --- |
| **demo** | `demo` | `demo-aiaccount.yahwan.biz` | Static HTML/CSS | `deploy-ai-accounting-copilot-demo.yml` |
| **poc** | `poc` | `poc-aiaccount.yahwan.biz` | Docker (FastAPI) | `deploy-ai-accounting-copilot-poc.yml` |
| **prod** | `main` | TBD | Docker (FastAPI) | TBD (MVP) |

---

## Quick Deploy Commands

### Demo (static prototype)

```bash
gh workflow run deploy-ai-accounting-copilot-demo.yml \
  --repo Piboonsak/Openclaw \
  -f app_ref=demo
```

### PoC (Docker API + UI)

```bash
gh workflow run deploy-ai-accounting-copilot-poc.yml \
  --repo Piboonsak/Openclaw \
  -f app_ref=poc \
  -f domain=poc-aiaccount.yahwan.biz
```

### Production

> Not yet implemented. Will be created when MVP is ready.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│  Control Plane: Piboonsak/Openclaw                          │
│  └── .github/workflows/deploy-ai-accounting-copilot-*.yml   │
│       • Holds VPS secrets (SSH key, API keys)               │
│       • Triggers deploy via workflow_dispatch                │
│       • Runs post-deploy smoke tests (Playwright)           │
└────────────────────────┬────────────────────────────────────┘
                         │ git clone + SCP/Docker
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  VPS: 76.13.210.250                                         │
│  ├── /var/www/demo-aiaccount  (demo: static HTML/CSS)       │
│  ├── /opt/aiacc-poc           (poc: Docker app)             │
│  └── /etc/nginx/conf.d/       (per-domain vhost configs)    │
└─────────────────────────────────────────────────────────────┘
```

---

## Docker & Dependencies

The Dockerfile (`docker/Dockerfile.backend`) copies and installs **root `requirements.txt`**.  
Any runtime Python dependency (e.g. `pypdf`, `pypdfium2`) MUST be declared there.

```text
docker/Dockerfile.backend
  └── COPY requirements.txt .
  └── RUN pip install -r requirements.txt
```

`config/requirements.txt` is a lighter local-dev alternative and should stay in sync.

---

## Secrets (managed in Openclaw repo settings)

| Secret | Used by |
| --- | --- |
| `VPS_HOST` | All deploy workflows |
| `VPS_USER` | All deploy workflows |
| `VPS_SSH_KEY` / `DEPLOY_SSH_PRIVATE_KEY` | SSH to VPS |
| `GH_TOKEN` | Clone private repo branches |
| `OPENROUTER_API_KEY` | PoC runtime |
| `ANTHROPIC_API_KEY` | PoC runtime (optional) |

---

## Per-Environment Details

- [**demo-site/README.md**](demo-site/README.md) — Static demo deployment
- [**poc-site/README.md**](poc-site/README.md) — PoC Docker deployment
- [**prod-site/README.md**](prod-site/README.md) — Production (placeholder)

---

## Rollback

All environments: redeploy a known-good commit by specifying `app_ref`:

```bash
# Example: rollback PoC to a specific commit
gh workflow run deploy-ai-accounting-copilot-poc.yml \
  --repo Piboonsak/Openclaw \
  -f app_ref=<COMMIT_SHA>
```

No direct VPS mutation is allowed. All changes flow through Git + GitHub Actions.
