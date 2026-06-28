# Epic 13 W2 Execution Prompt (UI-First, Guarded)

Use this prompt when executing W2 infra tasks in ai-accounting-copilot.
This version is designed to prevent unsafe assumptions by requiring operator inputs in UI before execution.

## 1) Required Reading (must be loaded before actions)
- docs/requirement/phaseII/epic-13/EPIC-13-TASKS-DETAIL.md
- docs/requirement/phaseII/epic-13/INFRA-PREREQUISITES-RUNBOOK.md
- docs/requirement/phaseII/epic-13/sit-env-setup-plan.md
- docs/CICD/design-control-cicd-process.md
- docs/CICD/INCIDENTS.md

## 2) Hard Rules
- Never SSH to VPS for mutations. Allowed path is local edit -> commit -> push -> GitHub Actions.
- Never add deploy workflows in this repo. Deploy hub is Piboonsak/Openclaw.
- Do not modify already completed files listed in Epic 13 W2 scope lock.
- For Task 4 workflow cleanup: hard-block deletion until Openclaw UAT success evidence is provided.
- Any UAT/PROD plan refresh must incorporate the completed SIT rollout lessons in `sit-env-setup-plan.md` sections `8-10` before changing deploy assumptions.

## 2.1 Latest SIT rollout snapshot

- SIT runtime gate passed on 2026-06-28 via Openclaw Actions run `28332426427`
- Planning assumptions must now treat `TASK-1306A` as complete and must preserve the proven fixes:
  - retryable SSH preflight
  - control-plane runtime key injection
  - URL-form MinIO/storage endpoints
  - dependency-light evidence probes

## 3) Scope Lock and Conflict Resolution

### 3.1 W2 in-scope tasks
- Task 1: env templates + gitignore policy checks
- Task 2: pre-commit python detection fix
- Task 3: housekeeping scripts
- Task 4: migration preparation artifacts only (no workflow removal yet)

### 3.2 Explicit out-of-scope
- src/backend app entrypoint
- auth implementation
- Alembic migrations
- DB backup automation requiring missing R2 credentials
- go-live execution runbooks

### 3.3 Task 1 scope correction (resolved)
Previous governance used forbidden_scope: [".env*", "src/**"], which conflicts with required outputs.
Use this corrected policy for Task 1 only:

```json
{
  "task_id": "TASK-1307/TASK-1308-gap",
  "risk_tier": "LOW",
  "allowed_scope": [
    "docker/.env.prod.example",
    "docker/.env.uat.example",
    "docker/.env.dev",
    ".gitignore"
  ],
  "forbidden_scope": [
    "src/**",
    "docker/.env.prod",
    "docker/.env.uat"
  ],
  "max_loops": 5
}
```

## 4) Pre-Run UI Form (mandatory)
Execution must stop unless all required fields pass validation.

```json
{
  "formId": "epic13-w2-prerun",
  "version": "2026-06-27",
  "sections": [
    {
      "id": "execution",
      "title": "Execution Mode",
      "fields": [
        {
          "key": "mode",
          "type": "select",
          "required": true,
          "options": ["dry-run", "apply"],
          "default": "dry-run"
        },
        {
          "key": "tasks",
          "type": "multiselect",
          "required": true,
          "options": ["task1", "task2", "task3", "task4"],
          "min": 1
        }
      ]
    },
    {
      "id": "repo_state",
      "title": "Repository Safety",
      "fields": [
        {
          "key": "target_repo",
          "type": "select",
          "required": true,
          "options": ["YAHWAN-SHOP/ai-accounting-copilot"]
        },
        {
          "key": "target_branch",
          "type": "text",
          "required": true,
          "default": "dev"
        },
        {
          "key": "working_tree_clean",
          "type": "checkbox",
          "required": true
        }
      ]
    },
    {
      "id": "task1_inputs",
      "title": "Task 1 Inputs",
      "fields": [
        {
          "key": "allowlist_confirmed",
          "type": "checkbox",
          "required": true,
          "showIfTaskSelected": "task1"
        },
        {
          "key": "placeholder_only_confirmed",
          "type": "checkbox",
          "required": true,
          "showIfTaskSelected": "task1"
        },
        {
          "key": "gitignore_policy_confirmed",
          "type": "checkbox",
          "required": true,
          "showIfTaskSelected": "task1"
        }
      ]
    },
    {
      "id": "task2_inputs",
      "title": "Task 2 Inputs",
      "fields": [
        {
          "key": "shell_target",
          "type": "select",
          "required": true,
          "options": ["bash-compatible"],
          "showIfTaskSelected": "task2"
        },
        {
          "key": "windows_python_fallback_confirmed",
          "type": "checkbox",
          "required": true,
          "showIfTaskSelected": "task2"
        }
      ]
    },
    {
      "id": "task3_inputs",
      "title": "Task 3 Inputs",
      "fields": [
        {
          "key": "disk_threshold_percent",
          "type": "number",
          "required": true,
          "default": 80,
          "min": 1,
          "max": 99,
          "showIfTaskSelected": "task3"
        },
        {
          "key": "upload_staging_dir",
          "type": "text",
          "required": false,
          "default": "/opt/ledgerflow/uploads/staging",
          "showIfTaskSelected": "task3"
        },
        {
          "key": "notify_fallback_mode",
          "type": "select",
          "required": true,
          "options": ["log-only-if-missing", "fail-if-missing"],
          "default": "log-only-if-missing",
          "showIfTaskSelected": "task3"
        }
      ]
    },
    {
      "id": "task4_inputs",
      "title": "Task 4 Inputs",
      "fields": [
        {
          "key": "migration_phase",
          "type": "select",
          "required": true,
          "options": ["activation-prep-only", "cleanup-enabled"],
          "default": "activation-prep-only",
          "showIfTaskSelected": "task4"
        },
        {
          "key": "openclaw_uat_evidence_url",
          "type": "text",
          "required": false,
          "showIfTaskSelected": "task4"
        },
        {
          "key": "openclaw_uat_run_id",
          "type": "text",
          "required": false,
          "showIfTaskSelected": "task4"
        }
      ]
    },
    {
      "id": "approvals",
      "title": "Approvals",
      "fields": [
        {
          "key": "uat_policy",
          "type": "select",
          "required": true,
          "options": ["no-manual-approval-but-gated"],
          "default": "no-manual-approval-but-gated"
        },
        {
          "key": "prod_manual_approval_confirmed",
          "type": "checkbox",
          "required": true
        }
      ]
    }
  ]
}
```

## 5) Gate Engine (blockers)
The run must stop immediately if any rule below is true.

1. Task 1 selected and `allowlist_confirmed` is false.
2. Task 1 selected and target file set includes any of:
   - docker/.env.prod
   - docker/.env.uat
   - any src/** path
3. Task 4 selected with `migration_phase=cleanup-enabled` and either evidence URL or run ID is missing.
4. Task 4 selected and Openclaw UAT health proof is missing (`curl https://uat.bwcacc.biz/api/health = 200` evidence not attached).
5. Any PROD-related action selected while `prod_manual_approval_confirmed` is false.
6. Repo working tree is not clean.

## 6) Task Execution Constraints

### Task 1 (env templates)
- Create or update only:
  - docker/.env.prod.example
  - docker/.env.uat.example
  - docker/.env.dev
  - .gitignore
- Use placeholder values only. Never place real secrets.

### Task 2 (INC-2026-06-24-001)
- Modify only:
  - .githooks/pre-commit
  - docs/CICD/INCIDENTS.md
- Required change:
  - detect python or python3 via `command -v`
  - replace all `python script.py` to `$PYTHON script.py`
  - add Resolution section with date and commit SHA placeholder

### Task 3 (housekeeping)
- Create only:
  - scripts/infra/housekeeping.sh
  - scripts/infra/setup-housekeeping-cron.sh
- Script requirements:
  - `set -euo pipefail`
  - idempotent cron install
  - disk alert threshold configurable

### Task 4 (migration activation prep)
- Create only:
  - scripts/infra/post-push-hook.sh.template
  - docs/CICD/SECRETS-CHECKLIST.md
- Do not remove deploy workflows in this stage.

## 7) Done Definition (W2, evidence-backed)
For each item, attach evidence.

1. docker/.env.prod.example exists (file path + diff)
2. docker/.env.uat.example exists (file path + diff)
3. docker/.env.dev exists (file path + diff)
4. .gitignore patterns enforced (diff shows exact lines)
5. .githooks/pre-commit detects python or python3 (diff + quick command output)
6. docs/CICD/INCIDENTS.md has Resolution (date + commit placeholder)
7. scripts/infra/housekeeping.sh exists and is executable-safe
8. scripts/infra/setup-housekeeping-cron.sh exists and idempotent logic present
9. scripts/infra/post-push-hook.sh.template exists with header: copy to .git/hooks/post-push
10. docs/CICD/SECRETS-CHECKLIST.md exists
11. .github/workflows/bwcacc-deploy-uat.yml and .github/workflows/bwcacc-deploy-prod.yml still exist (until Openclaw evidence gate passes)

## 8) Operator Output Template
At run start, print:

- selected tasks
- mode
- passed gates summary
- blocked gates (if any)
- proceed or abort decision

At run end, print:

- changed files list
- acceptance criteria mapping
- evidence list
- pending blocked actions (if any)
