# PoC Deployment — poc-aiaccount.yahwan.biz

Docker-based FastAPI deployment for user-trial.

---

## Deploy Command

```bash
gh workflow run deploy-ai-accounting-copilot-poc.yml \
  --repo Piboonsak/Openclaw \
  -f app_ref=poc \
  -f domain=poc-aiaccount.yahwan.biz
```

## Workflow Inputs

| Input | Default | Description |
| --- | --- | --- |
| `app_ref` | `poc` | Branch/tag/SHA in YAHWAN-SHOP/ai-accounting-copilot |
| `domain` | `poc-aiaccount.yahwan.biz` | Domain served by Nginx |
| `poc_url` | `https://poc-aiaccount.yahwan.biz` | Public URL for post-deploy smoke tests |
| `target_root` | `/opt/aiacc-poc` | Remote app root directory |

## Infrastructure

| Item | Value |
| --- | --- |
| VPS IP | `76.13.210.250` |
| Container name | `aiacc-poc-api` |
| Internal port | `8000` (mapped to host `127.0.0.1:18080`) |
| Nginx vhost | `/etc/nginx/conf.d/poc-aiaccount.conf` |
| App root | `/opt/aiacc-poc` |
| Data volumes | `rules/`, `cache/`, `uploads/`, `exports/` under app root |
| Docker Compose | `deploy/poc-site/docker-compose.poc.yml` |
| Env file template | `deploy/poc-site/.env.poc.example` |

## Runtime Dependencies

The Docker image is built from `docker/Dockerfile.backend` using root `requirements.txt`.
Key PDF processing libs that MUST be in `requirements.txt`:

- `pypdf` — native PDF text extraction
- `pypdfium2` — PDF page rendering to image for OCR fallback
- `paddleocr` / `pytesseract` — OCR engines

## Health Check

```bash
curl -s https://poc-aiaccount.yahwan.biz/health
# Expected: {"status":"ok"}

curl -s https://poc-aiaccount.yahwan.biz/api/health
# Expected: {"status":"ok",...}
```

## Post-Deploy Verification

The workflow automatically runs Playwright smoke tests (`tests/e2e/poc-smoke.spec.ts`) that verify:

1. Health endpoints respond 200
2. `/prototype` page loads with correct title
3. Core workflow DOM elements render (6 step items)
4. CSS served with correct `text/css` MIME type

## HTTPS / SSL Certificate

Certbot is auto-managed by the deploy workflow:

```bash
certbot --nginx --cert-name poc-aiaccount.yahwan.biz \
  -d poc-aiaccount.yahwan.biz --non-interactive --agree-tos -m admin@yahwan.biz
```

Certificate is stored at `/etc/letsencrypt/live/poc-aiaccount.yahwan.biz/`.

## Environment Variables

See `.env.poc.example` in this folder. Key variables:

- `APP_ENV=poc-user-trial`
- `STAGE_C_PROVIDER=openrouter`
- `OCR_ENGINE=tesseract`
- `OPENROUTER_API_KEY` — injected by workflow from Openclaw secrets
- `ANTHROPIC_API_KEY` — injected by workflow from Openclaw secrets

## Rollback

```bash
gh workflow run deploy-ai-accounting-copilot-poc.yml \
  --repo Piboonsak/Openclaw \
  -f app_ref=<KNOWN_GOOD_COMMIT_SHA>
```

## Known Issues

| Issue | Solution |
| --- | --- |
| CSS not loading (MIME error) | Ensure `href="/static/ux-ui-prototype.css"` in HTML |
| Certificate CN mismatch | Deploy workflow forces `certbot --cert-name` rebinding |
| `pypdf` missing in Docker | Must be in root `requirements.txt` (not just local venv) |
| Playwright timeout on GHA | Tests use retry helpers with 60s timeout per navigation |

## Files in This Folder

- `.env.poc.example` — Template environment variables
- `docker-compose.poc.yml` — Docker Compose service definition
- `nginx-poc-aiaccount.conf` — Nginx reverse-proxy vhost config
