# `.agent/` — Governance State, Evidence, and Templates

This directory is the **single source of truth** for AI-agent governance on every
`TASK-<ID>` worked in this repository. It is consumed by:

- Pre-commit hooks (`.githooks/pre-commit`)
- CI gate scripts (`scripts/gates/*`)
- Intake automation (`scripts/intake_to_state.py`, `.github/workflows/intake-sync.yml`)
- Governance watchdogs (`scripts/governance/*`)

## Layout

```text
.agent/
├── README.md                 # This file
├── definitions/              # Per-agent role definitions (Markdown)
├── state/
│   ├── _schema.json          # JSON Schema for TASK-<ID>.json
│   └── TASK-<ID>.json        # One file per active task (see schema)
├── evidence/
│   └── TASK-<ID>/
│       └── evidence.md       # Required by check_evidence.py
├── templates/
│   └── high-risk-advisory.md # 3-provider review template for HIGH/CRITICAL
└── logs/                     # Agent run logs (not committed if noisy)
```

## State lifecycle (`.agent/state/TASK-<ID>.json`)

```text
PENDING ──► IN_PROGRESS ──► REVIEW_READY ──► DONE ──► VERIFIED
              │
              └──► BLOCKED (requires evidence.md `## Blocker` section)
```

Fields (full schema in [`state/_schema.json`](state/_schema.json)):

| Field                 | Required | Notes                                                    |
| --------------------- | -------- | -------------------------------------------------------- |
| `task_id`             | yes      | `TASK-<ID>` (regex `^TASK-[A-Z0-9-]+$`)                  |
| `status`              | yes      | Lifecycle state above                                    |
| `risk_tier`           | yes      | `LOW`/`MEDIUM`/`HIGH`/`CRITICAL`                         |
| `model_tier`          | yes      | One of the tiers in `config/model-policy.yaml`           |
| `allowed_scope`       | yes      | Glob list — files the agent MAY modify                   |
| `forbidden_scope`     | yes      | Glob list — files the agent MUST NOT modify              |
| `acceptance_criteria` | yes      | List of `{id, desc, test?}` — drives evidence binding    |
| `max_loops`           | yes      | Cap on `run_count` (default 5, max 20)                   |
| `run_count`           | yes      | Incremented by the agent runner on each loop             |
| `escalation_policy`   | yes      | `human` / `ai-debate` / `stop`                           |

## Evidence contract (`.agent/evidence/TASK-<ID>/evidence.md`)

Every PR must include an evidence file with **all three** sections non-empty:

```markdown
## Commands Executed
$ pytest tests/test_ocr.py -v
$ docker compose run --rm backend pytest ...

## Raw Output
<verbatim stdout/stderr — must contain `<test_fn> ... PASSED` for each AC>

## Acceptance Criteria
- [x] ac_ocr_runs (test_ocr_runs_on_sample) -- PASSED
- [x] ac_conf_score (test_confidence_attached) -- PASSED
```

Rules enforced by `scripts/gates/check_evidence.py`:

1. All three sections present and non-empty.
2. Every AC line that names a `test` must have a matching `<test_fn> .* PASSED` in **Raw Output**.
3. AC id prefix `int_` requires at least one `docker` command in **Commands Executed**.
4. AC without `test` falls back to section-presence validation only (backward-compat).

## Forbidden paths (global)

Sourced from [`config/model-policy.yaml`](../config/model-policy.yaml) under
`safety.forbidden_paths`. The scope gate merges this list with each task's
`forbidden_scope` and **hard-fails** any match (no skip-list, no override).

Current global forbidden globs:

- `private_data/**` — customer PoC data
- `samples/sample_documents/**` — partner samples
- `**/*.key`, `**/*.pem` — private keys
- `**/.env*` — environment secrets

## Bypass policy

The label `bypass:governance` (HIGH/CRITICAL only) is **auto-expired** by
[`scripts/governance/expire_bypass_label.py`](../scripts/governance/expire_bypass_label.py)
after **24 hours**. The expiry job (`.github/workflows/governance-watch.yml`)
runs hourly and posts an audit comment when it removes a stale label.

## Local enforcement

`.githooks/pre-commit` runs:

1. `npm run validate:agents-skills` (agent/skill Markdown validation)
2. `python scripts/min_action_check.py` (block plan-only commits)

Install once per clone:

```pwsh
node scripts/setup-git-hooks.mjs
```

## CLI

```pwsh
# Validate a state file against the schema
python scripts/agent_state.py validate .agent/state/TASK-501.json

# Initialise a new state file
python scripts/agent_state.py init TASK-501 `
    --risk MEDIUM --model tier-2a-copilot `
    --allowed "src/ocr/**" --allowed "tests/test_ocr.py" `
    --forbidden "private_data/**"

# Read a single field
python scripts/agent_state.py get TASK-501 allowed_scope
```
