# CI/CD Incident Log

This file stores small but recurring incidents that can block delivery flow.
Use this as a quick operational reference before commit and deploy.

## INC-2026-06-24-001: pre-commit fails because `python` is not found

- Date: 2026-06-24
- Scope: local commit in `ai-accounting-copilot`
- Symptom:
  - `.githooks/pre-commit: line 17: python: command not found`
  - commit blocked even when code changes are valid

### Root Cause

The pre-commit hook calls `python` directly, but some Windows setups only have `python3` or a virtual environment interpreter path and do not expose `python` in PATH.

### Impact

- Blocks normal commit flow.
- Increases risk of bypassing checks with `--no-verify`.

### Prevention (recommended)

1. Ensure Python launcher or executable is available from shell:
   - `python --version`
2. If command is missing, install/repair Python and enable PATH integration.
3. Activate the project virtual environment before commit:
   - PowerShell: `.venv\Scripts\Activate.ps1`
4. Re-test hook path resolution before real commit:
   - `python --version`
   - `git commit --allow-empty -m "chore: hook precheck"` (then reset if needed)

### Safe Fallback (when delivery is blocked)

Use only for urgent unblock after manual verification of changed files:

1. Validate changes manually (`git diff`, smoke checks, lint/tests if available).
2. Commit with:
   - `git commit --no-verify -m "<message>"`
3. Record the bypass in PR/issue notes with reason:
   - `pre-commit blocked by missing python path`
4. Fix environment immediately after release window.

### Owner Action Items

1. Update hook scripts to support both `python` and `python3` detection on Windows.
2. Add a short bootstrap check in contributor setup docs:
   - `python --version`
   - `where python`

### Resolution (2026-06-27)

Updated .githooks/pre-commit to detect python OR python3 using `command -v`.
Fix committed in: [commit SHA]
