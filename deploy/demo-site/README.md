# Demo Deployment — demo-aiaccount.yahwan.biz

Static HTML/CSS prototype deployment (no Docker, no API backend).

---

## Deploy Command

```bash
gh workflow run deploy-ai-accounting-copilot-demo.yml \
  --repo Piboonsak/Openclaw \
  -f app_ref=demo
```

## Workflow Inputs

| Input | Default | Description |
| --- | --- | --- |
| `app_ref` | `demo` | Branch/tag/SHA in YAHWAN-SHOP/ai-accounting-copilot |

## Infrastructure

| Item | Value |
| --- | --- |
| VPS IP | `76.13.210.250` |
| Web root | `/var/www/demo-aiaccount` |
| Nginx vhost | `/etc/nginx/conf.d/demo-aiaccount.conf` |
| Nginx config source | `deploy/demo-site/nginx-demo-aiaccount.conf` |
| Content | `src/frontend/ux-ui-prototype.html` + `ux-ui-prototype.css` |

## What Gets Deployed

The workflow SCPs two static files to the web root:

1. `src/frontend/ux-ui-prototype.html` → served as `index.html`
2. `src/frontend/ux-ui-prototype.css` → served alongside

Nginx serves these directly (no proxy, no Docker).

## Health Check

```bash
curl -sI https://demo-aiaccount.yahwan.biz/ | grep "HTTP/"
# Expected: HTTP/2 200
```

## Post-Deploy Verification

The workflow runs Playwright checks:

1. Page loads with expected title
2. Main UI elements render (topbar, stepper, action buttons)
3. No console errors
4. Screenshot artifact uploaded

## Rollback

```bash
gh workflow run deploy-ai-accounting-copilot-demo.yml \
  --repo Piboonsak/Openclaw \
  -f app_ref=<KNOWN_GOOD_COMMIT_SHA>
```

## Local Deploy Script (Alternative)

A PowerShell script is available for manual deployment from a developer laptop:

```powershell
.\deploy\demo-site\deploy-demo.ps1
```

Requires SSH key at `~/.ssh/id_ed25519_hostinger`.

## Files in This Folder

- `deploy-demo.ps1` — Local PowerShell deploy script
- `nginx-demo-aiaccount.conf` — Nginx static-site vhost config
