# W4 SIT E2E - Codex Review 02

> Date: 2026-07-05
> Reviewed input: `W4-SIT-E2E-CLAUDE-CODE-FOLLOWUP-02-COMPLETION.md`
> Review stance: code-review, blocker-first
> Decision: **Claude follow-up accepted; proceed to Copilot deploy/live SIT proof**

## Findings

### P0 - `index.html` parity guard is still the remaining deploy gate

`npm run verify:w4-html` still fails:

```text
VERIFY_FAIL: index and main are not byte-identical; parity drift detected
```

This matches the follow-up report and remains the only blocker before deploy-close. It is not a new Claude regression, but Copilot must resolve or resync `src/frontend/index.html` before claiming W4 SIT closure.

References:

- [src/frontend/index.html](D:/01_gitrepo/ai-accounting-copilot/src/frontend/index.html)
- [src/frontend/main-ux-ui.html](D:/01_gitrepo/ai-accounting-copilot/src/frontend/main-ux-ui.html)
- [package.json](D:/01_gitrepo/ai-accounting-copilot/package.json)

### P1 - Live SIT persistence proof is still outstanding

Repo-side wiring is now in place, and focused tests pass, but the real closure still depends on live SIT proof for:

- create/edit Company -> refresh/re-login -> data remains
- create/edit User -> refresh/re-login -> data remains
- AP/AR import/list behavior against the real runtime stack

This is expected Copilot-lane work, not a reason to send Claude back again.

References:

- [src/backend/api/companies_admin.py](D:/01_gitrepo/ai-accounting-copilot/src/backend/api/companies_admin.py)
- [src/backend/api/users_admin.py](D:/01_gitrepo/ai-accounting-copilot/src/backend/api/users_admin.py)
- [tests/api/test_companies_admin_api.py](D:/01_gitrepo/ai-accounting-copilot/tests/api/test_companies_admin_api.py)
- [tests/api/test_users_admin_api.py](D:/01_gitrepo/ai-accounting-copilot/tests/api/test_users_admin_api.py)

### P2 - A few visible non-proof-path controls are still shell/deferred style, but they no longer fake backend success

Spot-checking the accepted surface shows some visible controls still open neutral or warn toasts instead of real workflows, for example:

- topbar avatar/logout stub at [src/frontend/main-ux-ui.html](D:/01_gitrepo/ai-accounting-copilot/src/frontend/main-ux-ui.html:517)
- Company Settings mapping-rule buttons at [src/frontend/main-ux-ui.html](D:/01_gitrepo/ai-accounting-copilot/src/frontend/main-ux-ui.html:1266)

These are not showing false `ok` success anymore, so they are not blocking W4 E2E deploy proof. Copilot should still note them honestly if encountered during live SIT clickthrough.

## Positive Checks

The residual fake-success findings from Review 01 are closed in the accepted follow-up:

- Review Scan `Approve`
- Review Scan `Approve All`
- Review Scan `Flag`
- Review Mapping `Confirm Mapping`
- Processing retry modal

Focused backend/API checks remain healthy:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_companies_admin_api.py tests/api/test_users_admin_api.py -q
# 20 passed

.\.venv\Scripts\python.exe -m pytest tests/auth/test_endpoints.py -q
# 5 passed
```

The frontend/backend route prefix alignment is still correct:

- app mounts API at `/api`
- admin routes are `/v1/admin/...`
- frontend calls `/api/v1/admin/...`

## Required Next Action

Proceed to Copilot with a deploy/live-proof handoff.

Copilot must:

1. make `npm run verify:w4-html` pass by syncing or repairing `src/frontend/index.html`
2. deploy only through the Openclaw control-plane workflow
3. run live SIT clickthrough on `/phase2/prototype` and `/index.html`
4. prove Company/User persistence or visible deferral on the real runtime
5. return PASS/BLOCKED with deployed SHA, workflow URL, route health, browser proof, and residual issues
