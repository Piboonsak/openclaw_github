---
name: aiacc-clearcache
scope: ai-accounting-copilot
version: 2026-06-10
---

# /aiacc-clearcache

Run the cache-reset skill for this repository.

## Required Actions
1. Clear these folders:
- `src/backend/ml/cache`
- `src/backend/services/cache`
- `tmp/stage_c_images`
2. Use command:
```powershell
.\scripts\clear-cache.ps1
```
3. If user asks restart in same command, run:
```powershell
.\scripts\clear-cache.ps1 -RestartServer
curl.exe -sS http://127.0.0.1:8000/api/health
```
4. Report back:
- Cleared folders
- Restart status
- Health endpoint result (if restart requested)

## Guardrails
- Do not delete non-cache business data.
- Keep operation scoped to listed folders only.
