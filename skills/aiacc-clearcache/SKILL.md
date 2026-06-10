---
name: aiacc-clearcache
description: 'Clear AI accounting pipeline caches safely and optionally restart local API server.'
scope: ai-accounting-copilot
version: 2026-06-10
---

# Skill: AIACC Clear Cache

## Purpose
Reset OCR/extraction/journal cache artifacts to force clean recomputation and avoid stale outputs.

## When to Use This Skill
- When extraction output appears stale after prompt/rule changes.
- When journal output still reflects previous runs.
- Before rerunning benchmark or verification scripts that depend on fresh cache state.

## Cache Folders To Clear
- src/backend/ml/cache
- src/backend/services/cache
- tmp/stage_c_images

## Standard Command
```powershell
.\scripts\clear-cache.ps1
```

## With Server Restart
```powershell
.\scripts\clear-cache.ps1 -RestartServer
curl.exe -sS http://127.0.0.1:8000/api/health
```

## Step-by-Step Workflows

### 1) Clear Cache Only
1. Run `.\scripts\clear-cache.ps1`.
2. Confirm all cache folders report `CLEARED|...` lines.

### 2) Clear Cache and Restart API
1. Run `.\scripts\clear-cache.ps1 -RestartServer`.
2. Verify API health with `curl.exe -sS http://127.0.0.1:8000/api/health`.

## Expected Output
- `CLEARED|src/backend/ml/cache`
- `CLEARED|src/backend/services/cache`
- `CLEARED|tmp/stage_c_images`
- optional server stop/start lines when `-RestartServer` is used.

## Output Checklist
- All target cache directories are cleared.
- No non-cache business data is touched.
- If restart mode is used, API health endpoint responds successfully.
