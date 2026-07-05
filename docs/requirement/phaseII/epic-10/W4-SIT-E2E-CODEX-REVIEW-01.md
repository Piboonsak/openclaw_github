# W4 SIT E2E - Codex Review 01

> Date: 2026-07-05
> Reviewed input: `W4-SIT-E2E-CLAUDE-CODE-COMPLETION-01.md`
> Review stance: code-review, blocker-first
> Decision: **not deploy-ready yet**; send one Claude follow-up before Copilot deploy

## Findings

### P0 - Residual fake-success controls remain on visible Review screens

`src/frontend/main-ux-ui.html` still contains visible fixture-screen actions that call `showToast(..., 'ok')` without backend persistence:

- Review Scan approve button around line 886: `Approve แล้ว`
- Review Scan approve-all button around line 896: `Approve ทั้งหมดแล้ว`
- Review Mapping confirm button around line 971: `Confirm Mapping แล้ว`

This contradicts the W4 design rule: every visible SIT action must be wired, disabled/deferred, or hidden. The added "Demo data" banners help, but the buttons still claim successful workflow actions. They must be disabled/deferred or wired before Copilot claims W4 SIT E2E closure.

### P0 - `index.html` parity guard still fails

Command:

```powershell
npm run verify:w4-html
```

Result:

```text
VERIFY_FAIL: index and main are not byte-identical; parity drift detected
```

This is already identified as Copilot's lane, but it means Copilot must sync/repair `src/frontend/index.html` before deploy proof. Do not deploy and close from `main-ux-ui.html` only.

### P1 - Live DB proof is still required

The new Company/User backend tests pass locally, but they use fake session doubles rather than a live PostgreSQL session. This is acceptable for repo-side review, but Copilot must prove on SIT:

- create company -> refresh/re-login -> company remains
- create user -> refresh/re-login -> user remains
- AP/AR import/list route works with real DB seed

### P1 - Admin CRUD is single-tenant scoped for W4 SIT only

`companies_admin.py` intentionally uses the first `Tenant` row for create/list behavior. That is acceptable only for the current single-tenant SIT closure assumption. Before UAT/full multi-tenant use, this should filter by `current_user.tenant_id` and avoid cross-tenant reads/writes.

### P2 - Local Playwright rerun needs corrected execution context

Codex rerun of Playwright timed out under the default remote `baseURL`; `--project=chromium` is unavailable because the repo config has no named projects. Claude's reported 16/16 pass should be treated as useful local evidence, but Copilot's live clickthrough remains the real closer.

## Positive Checks

Focused backend tests passed:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_companies_admin_api.py tests/api/test_users_admin_api.py -q
# 20 passed
```

Auth smoke passed:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/auth/test_endpoints.py -q
# 5 passed
```

Route prefix review is correct:

- app mounts API router at `/api`
- admin routers use `/v1/admin/...`
- frontend calls `/api/v1/admin/...`

## Required Next Action

Send `W4-SIT-E2E-CLAUDE-CODE-FOLLOWUP-02.prompt.json` to Claude Code.

Claude should:

1. Remove or defer the residual fake-success controls on Review Scan / Review Mapping / Processing demo modals and any other fixture workflow action still claiming success.
2. Re-run the visible-control audit grep for `showToast(..., 'ok')`.
3. Update the completion report with residual controls closed.
4. Leave `index.html` parity and live SIT deploy to Copilot.

After Claude follow-up passes, Codex can send the Copilot deploy prompt.
