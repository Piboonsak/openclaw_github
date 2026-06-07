# Epic 1 — Orchestration & AI Agent Governance (Redesigned)

> **Source spec**: `D:\01_gitrepo\AI-Dev-Factory\docs\factory-gap-closure-governance.html`
> **Goal**: Make AI agents capable of running the full `ai-accounting-copilot` PoC development to completion — **without runaway loops, fake completions, scope creep, or token burn**.
> **Control surface**:
> - Issues: <https://github.com/YAHWAN-SHOP/ai-accounting-copilot/issues>
> - Project board: <https://github.com/orgs/YAHWAN-SHOP/projects/1/views/2>

---

## Why this redesign

The original Epic 1 (3 tasks, ~80 lines each) only covered loop detection + evidence + pre-commit. The AI-Dev-Factory governance spec proves that is **not enough** — agents still produced fake completions, scope creep, wrong-fix loops, and token explosions until **all 4 security layers + questionnaire intake + model-tier routing** are in place.

This redesign keeps the **same 3 task IDs** (TASK-101/102/103) but rescopes each to deliver one full **governance layer** of the factory model, end-to-end. After Epic 1, every other epic (2–7) is automatically governed.

### The 12 pain points → which task closes each

| # | Pain point | Closed by | Mechanism | Status target |
|---|------------|-----------|-----------|---------------|
| 1 | Context loss on long tasks | **101** | `.agent/state/<id>.json` external memory | CI-enforced |
| 2 | Forgetting requirements | **101** | Issue template → `acceptance_criteria[]` in state | CI-enforced |
| 3 | Skipping details | **101** | AC must encode every detail; missing AC = no work | Prompt + lint |
| 4 | Fake/mock integration | **102** | `check_evidence.py` requires real `docker compose` / `pytest` raw log | CI-enforced |
| 5 | Fake "done" | **102** | No evidence → PR blocked | CI-enforced |
| 6 | Plan-only commits (token burn) | **103** | `min_action_check.py` + pre-commit hook | CI-enforced |
| 7 | Cannot resume after crash | **101** | State persisted every loop; `max_loops=5` exits cleanly | Prompt + state |
| 8 | Scope creep (edits wrong files) | **102** | `check_scope.sh` blocks PRs touching `forbidden_scope` | CI-enforced |
| 9 | PR looks done but doesn't run | **102/103** | Full gate pipeline `ruff → mypy → scope → pytest → evidence → hdr` | CI-enforced |
| 10 | Wrong-fix loop (retry-same-bug) | **103** | `classify_failure.py` → narrow fix scope, escalate on dangerous classes | CI-enforced |
| 11 | Wide-context token burn on fix | **103** | Fix-agent context = `error_log + changed_files` only (model_policy) | Policy + dispatcher |
| 12 | Human bottleneck on every PR | **102** | `hdr_gate.py` auto-merges LOW/MED, routes HIGH to human | CI-enforced |

**Result after Epic 1**: every pain point is closed by a hard gate or an enforceable policy — no pain point left at "prompt-only".

---

## TASK-101 — Governance State + Questionnaire Intake

**Owner**: DevOps / Governance · **Risk**: MEDIUM · **Duration**: ~2 days · **Closes pain points**: 1, 2, 3, 7

### Purpose

Give every task a single source of truth — a state file derived from a structured issue (the "questionnaire"). The state file is what every gate, every agent, and the project board read from.

### Deliverables

```
.agent/
├── README.md                            # explains the governance model
├── state/
│   ├── _schema.json                     # JSON Schema (draft-2020-12)
│   └── TASK-<ID>.json                   # one per active task
├── evidence/<TASK-ID>/                  # raw outputs (see TASK-102)
└── logs/<TASK-ID>/                      # agent loop logs (no commits)

.github/
├── ISSUE_TEMPLATE/
│   ├── task-intake.yml                  # the questionnaire (Q1–Q8)
│   └── blocker.yml                      # for status=BLOCKED reporting
└── workflows/
    └── intake-sync.yml                  # issue → .agent/state/<id>.json

scripts/
├── agent_state.py                       # CLI: init / update / get / lock
└── intake_to_state.py                   # parse issue body → state file
```

### State file schema (authoritative)

```jsonc
{
  "task_id": "TASK-501",                 // matches issue title prefix
  "issue_url": "https://github.com/.../issues/123",
  "project_item_id": "PVTI_xxx",         // GitHub Projects v2 node id
  "status": "PENDING|IN_PROGRESS|REVIEW_READY|BLOCKED|DONE",
  "risk_tier": "LOW|MEDIUM|HIGH|CRITICAL",
  "model_tier": "tier-1-opus|tier-2a-copilot|tier-2b-sonnet|tier-3-gemini",
  "allowed_scope": ["src/backend/ml/**", "tests/ml/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/payments/**", "migrations/**", "config/secrets/**"],
  "acceptance_criteria": [
    { "id": "ac_ocr_runs", "desc": "Tesseract returns text for sample PDF", "test": "test_ocr_runs_on_sample" },
    { "id": "ac_conf_score", "desc": "Output includes per-field confidence", "test": "test_confidence_attached" }
  ],
  "max_loops": 5,
  "run_count": 0,
  "last_action": "init",
  "last_modified_files": [],
  "blocker_reason": null,
  "escalation_policy": "human|ai-debate|stop",
  "created_at": "2026-06-06T00:00:00Z",
  "updated_at": "2026-06-06T00:00:00Z"
}
```

### Issue template (the questionnaire — Q1–Q8)

`.github/ISSUE_TEMPLATE/task-intake.yml` is a GitHub Issue Form that produces a deterministic markdown body. `scripts/intake_to_state.py` regex-parses it into the state file on `issues.opened` / `issues.edited`.

Required fields map 1:1 to the state schema:

| Form field | State field | Validated by |
|------------|-------------|--------------|
| `task_id` (prefix in title) | `task_id` | regex `^TASK-\d{3}` |
| `risk_tier` (dropdown) | `risk_tier` | enum |
| `model_tier` (dropdown) | `model_tier` | enum |
| `allowed_scope` (checkbox + free text) | `allowed_scope[]` | glob syntax |
| `forbidden_scope` (checkbox + free text) | `forbidden_scope[]` | glob syntax |
| `acceptance_criteria` (textarea, one row per AC: `id ‖ desc ‖ test_fn`) | `acceptance_criteria[]` | min 1 row, `test_fn` must match `^test_\w+` |
| `max_loops` (number) | `max_loops` | default 5, max 10 |
| `escalation_policy` (dropdown) | `escalation_policy` | enum |

**Hard rule**: a PR linked to an issue whose state file fails schema validation is **blocked at the gate** (TASK-102).

### Project Board automation

GitHub Projects v2 board `YAHWAN-SHOP/projects/1` columns = state machine values.

| Column | Trigger to enter | Set by |
|--------|------------------|--------|
| Backlog | Issue created without `status:ready` label | Manual |
| Ready | Label `status:ready` added | Triager |
| In Progress | `copilot[bot]` assigned OR branch `task-<id>/*` pushed | `intake-sync.yml` |
| Review Ready | PR opened + all gates green | `agent_gate.yml` (TASK-102) |
| Blocked | State `status=BLOCKED` OR label `blocked` | `agent_gate.yml` / agent |
| Done | PR merged + close-with-proof comment posted | Merge workflow |

`intake-sync.yml` uses the GraphQL API (REST returns 422 for bot assigns — KI-075 lesson) to:
1. Move the project item to the right column on state transitions.
2. Apply / sync labels: `risk:<tier>`, `model:<tier>`, `status:<state>`.
3. Reject the issue (auto-comment + remove `status:ready`) if the questionnaire is incomplete.

### Acceptance Criteria (TASK-101 itself)

| ID | Condition | Test |
|----|-----------|------|
| `ac_schema_valid` | `.agent/state/_schema.json` validates a sample state file | `test_state_schema_validates` |
| `ac_init_state` | `python scripts/agent_state.py init TASK-999` creates a valid file | `test_init_creates_valid_state` |
| `ac_intake_parse` | Issue body with all 8 fields → correct state JSON | `test_intake_parses_all_fields` |
| `ac_intake_reject` | Issue body missing AC → script exits 1 + comments on issue | `test_intake_rejects_missing_ac` |
| `ac_loop_limit` | `run_count >= max_loops` → `is_blocked()` returns True | `test_max_loops_blocks` |
| `ac_resume` | New agent reading state at `run_count=3` continues from `last_action` | `test_resume_from_state` |
| `ac_project_sync` | State transition `IN_PROGRESS → REVIEW_READY` moves project card | `test_project_card_moves` (uses `gh` CLI mock) |

### Definition of Done

- `python scripts/agent_state.py --help` works
- A sample issue created via the template produces a valid state file within 30 s
- Project board reflects state changes within 1 min
- `pytest tests/governance/test_state.py -q` → all green
- `.agent/README.md` documents the full lifecycle with an example

---

## TASK-102 — Four-Layer Gate Pipeline (CI Side)

**Owner**: DevOps / Governance · **Risk**: HIGH · **Duration**: ~3 days · **Closes pain points**: 4, 5, 8, 9, 12

### Purpose

Implement the 4 security layers from §6 of the spec as **CI hard gates** running in a single workflow `agent_gate.yml`. Every PR must pass all four or it cannot be merged.

| Layer | Script | Blocks on |
|-------|--------|-----------|
| **A — Scope Lock** | `scripts/gates/check_scope.sh` | Any file in `forbidden_scope` or outside `allowed_scope` |
| **B — Evidence Lock** | `scripts/gates/check_evidence.py` | Missing evidence OR AC bound to a test that didn't show PASSED |
| **C — Risk Router (HDR)** | `scripts/gates/hdr_gate.py` | HIGH/CRITICAL PR without `approved-by-human` label |
| **D — Quality Pipeline** | inline (ruff, mypy, pytest) | Lint / type / test failure |

### Deliverables

```
scripts/gates/
├── check_scope.sh                       # Layer A
├── check_evidence.py                    # Layer B (with AC↔test binding)
├── hdr_gate.py                          # Layer C
└── _common.py                           # shared: read state, find task_id from PR

.github/workflows/
└── agent_gate.yml                       # orchestrates A+B+C+D on every PR

tests/gates/
├── test_check_scope.py
├── test_check_evidence.py
└── test_hdr_gate.py
```

### Layer A — `check_scope.sh`

```
# Input:  PR diff vs base branch + .agent/state/<task_id>.json
# Output: exit 0 if every changed file ∈ allowed_scope AND ∉ forbidden_scope
#         exit 1 with file-by-file reason otherwise
```

- `task_id` resolved from PR title prefix or branch name `task-<id>/*`.
- Globs evaluated with `fnmatch` (Python implementation) — bash wraps it.
- Always-forbidden defaults applied even if `forbidden_scope` empty: `.env*`, `**/secrets/**`, `**/private_data/commercial/**`.

### Layer B — `check_evidence.py` (with AC↔test binding)

Evidence file required at `.agent/evidence/<TASK-ID>/evidence.md`. Must contain three sections:

```markdown
## Commands Executed
$ pytest tests/ml/test_ocr.py -v
$ docker compose -f docker/docker-compose.dev.yml run --rm backend pytest tests/integration/

## Raw Output
<verbatim stdout/stderr>

## Acceptance Criteria
- [x] ac_ocr_runs (test_ocr_runs_on_sample) — PASSED
- [x] ac_conf_score (test_confidence_attached) — PASSED
```

Validation logic:

1. All three sections present and non-empty → else fail.
2. For each AC with a `test` field in the state file:
   - Grep `Raw Output` for `<test_fn> .* PASSED` (pytest verbose format) → else fail with `AC <id> not bound to a passing test`.
3. Integration AC (id starts with `int_`) additionally requires a `docker` line in `Commands Executed`.
4. Backward-compat: AC without a `test` field → fall back to section-presence check (so docs-only tasks still work).

### Layer C — `hdr_gate.py` (Human Decision Router)

```
# Reads PR file list + state.risk_tier
# Forces HIGH/CRITICAL: must carry label `approved-by-human`
# Auto-bumps risk to HIGH if PR touches any of:
#   - src/backend/auth/**, src/backend/payments/**
#   - migrations/**, config/openclaw.prod.json5
#   - .github/workflows/** (gate self-modification)
# Outputs sticky PR comment with classification + reason
```

### Layer D — Quality pipeline

In `agent_gate.yml`:

```yaml
- ruff check src/ scripts/ tests/
- mypy scripts/ src/backend --ignore-missing-imports
- pytest -q --maxfail=1
- bash scripts/gates/check_scope.sh
- python scripts/gates/check_evidence.py
- python scripts/gates/hdr_gate.py
```

Workflow uses `concurrency: gate-${{ github.event.pull_request.number }}` so re-runs cancel stale checks.

### Acceptance Criteria (TASK-102 itself)

| ID | Condition | Test |
|----|-----------|------|
| `ac_scope_forbids_env` | PR touching `.env.local` → `check_scope` exit 1 | `test_scope_blocks_env` |
| `ac_scope_allows_in_scope` | PR only inside `allowed_scope` → exit 0 | `test_scope_allows_in_scope` |
| `ac_evidence_missing_blocks` | No `## Raw Output` section → exit 1 | `test_evidence_missing_blocks` |
| `ac_evidence_ac_binding` | AC test name not found in raw output → exit 1 | `test_ac_binding_enforced` |
| `ac_evidence_backward_compat` | AC without `test` field → section check still works | `test_backward_compat` |
| `ac_hdr_high_needs_label` | HIGH PR without `approved-by-human` → exit 1 | `test_hdr_high_needs_label` |
| `ac_hdr_auto_bump_auth` | PR touching `src/backend/auth/` auto-bumps to HIGH | `test_hdr_auto_bump_auth` |
| `ac_workflow_runs_all` | `agent_gate.yml` runs ruff→mypy→pytest→A→B→C in order | `test_workflow_order` (workflow lint) |

### Definition of Done

- All four layers callable locally: `bash scripts/run_gates.sh <task_id>` simulates the full CI run.
- Sample failing PR demonstrates each gate blocking with a clear comment.
- `agent_gate.yml` runs in <90 s on this repo's typical PR.

---

## TASK-103 — Local Enforcement + Failure Classifier + Model Policy

**Owner**: DevOps / Governance · **Risk**: MEDIUM · **Duration**: ~2 days · **Closes pain points**: 6, 9 (local), 10, 11

### Purpose

Stop bad commits **before they reach CI** (saves CI minutes and token cost), and when CI does fail, classify the failure so the fix-agent gets a **narrow** retry scope instead of the whole repo.

### Deliverables

```
scripts/
├── min_action_check.py                  # Layer D from spec — pre-commit
├── classify_failure.py                  # categorizes CI logs → narrow fix scope
├── run_gates.sh                         # local mirror of agent_gate.yml
└── hooks/
    └── pre-commit                       # calls min_action_check + ruff --diff

config/
├── model-policy.yaml                    # tier routing (already exists — extend)
└── failure-categories.yaml              # regex → category map

.github/workflows/
└── classify-on-failure.yml              # on gate failure → run classifier → comment on PR

tests/
├── test_min_action.py
└── test_classify_failure.py
```

### `min_action_check.py` (Layer D — Action Lock)

```
# Input:  git diff --cached --name-only
# Pass if at least one staged file matches:
#   src/**, tests/**, scripts/**, config/**, docker/**
# Fail if everything staged is in:
#   .agent/logs/**, **/*.md (notes only), .agent/state/** (without code)
# Override: state file has status=BLOCKED AND evidence has "## Blocker" section
```

Installed by `scripts/install_hooks.sh`:

```bash
git config core.hooksPath scripts/hooks
```

### `classify_failure.py` (Pain point #10 + #11)

Reads a CI log (stdin or `--log <path>`) and emits JSON:

```json
{
  "category": "syntax|lint|type|unit_test|integration_test|docker|webhook_replay|hmac_signature|migration|schema|permission_auth|unclear",
  "escalate_to_human": true,
  "suggested_fix_scope": ["src/backend/ml/extractor.py", "tests/ml/test_extractor.py"],
  "evidence_excerpt": "FAILED tests/ml/test_extractor.py::test_field_extract - AssertionError: ..."
}
```

Rules loaded from `config/failure-categories.yaml` (auditable, not buried in code):

| Category | Regex (example) | Escalate? | Fix scope hint |
|----------|-----------------|-----------|----------------|
| `syntax` | `SyntaxError:` | no | file from traceback |
| `lint` | `^[^\s]+\.py:\d+:\d+: [A-Z]\d+` | no | files in lint output |
| `type` | `error: .* \[(arg-type\|assignment\|attr-defined)\]` | no | files in mypy output |
| `unit_test` | `FAILED tests/` | no | failing test file + module under test |
| `integration_test` | `FAILED tests/integration/` | no | failing test file + service module |
| `docker` | `Cannot connect to the Docker daemon` / compose exit | no | `docker/**` |
| `migration` | `alembic.util.exc\|InvalidMigration` | **yes** | n/a (human) |
| `hmac_signature` | `hmac\|signature.*mismatch` | **yes** | n/a |
| `permission_auth` | `403\|401\|PermissionDenied` | **yes** | n/a |
| `unclear` | (fallback) | **yes** | n/a |

Wired by `classify-on-failure.yml` (runs on `workflow_run: agent_gate.yml: completed: failure`). Posts a sticky PR comment:

```
🤖 Failure Classifier
category: unit_test
escalate_to_human: false
fix_scope:
  - src/backend/ml/extractor.py
  - tests/ml/test_extractor.py
👉 Fix-agent context will be limited to these files (~5K tokens vs 200K).
```

### `config/model-policy.yaml` (extends existing)

```yaml
tiers:
  tier-1-opus:        { model: claude-opus-4.7, use: [architecture, rca, high_risk_review], max_calls_per_sprint: 3 }
  tier-2a-copilot:    { model: github-copilot, use: [code, bugfix, tests, refactor], cost_per_call: 0 }     # default for ALL coding
  tier-2b-sonnet:     { model: claude-sonnet-4.6, use: [log_analysis, classify, evidence_check], context_policy: changed_files_plus_error_only }
  tier-3-gemini:      { model: gemini-flash, use: [docs, changelog, issue_classification] }

hard_rules:
  free_models_for_gates: forbidden
  llm_can_final_merge_high_risk: false
  hard_gates: [ruff, mypy, pytest, check_scope, check_evidence, hdr_gate, min_action]
```

### Acceptance Criteria (TASK-103 itself)

| ID | Condition | Test |
|----|-----------|------|
| `ac_min_plan_only_rejected` | Staged only `.agent/logs/x.log` → exit 1 | `test_plan_only_rejected` |
| `ac_min_real_change_passes` | Staged `src/foo.py + tests/test_foo.py` → exit 0 | `test_real_change_passes` |
| `ac_min_blocked_override` | `status=BLOCKED` + evidence has `## Blocker` → exit 0 | `test_blocked_override` |
| `ac_cf_migration_escalates` | log contains `alembic.util.exc` → `escalate_to_human=true` | `test_migration_escalates` |
| `ac_cf_hmac_escalates` | log contains `hmac` → `escalate_to_human=true` | `test_hmac_escalates` |
| `ac_cf_type_no_escalate` | mypy error → `escalate=false`, scope = mypy files | `test_type_no_escalate` |
| `ac_cf_unit_scope` | pytest fail → scope = test file + module under test | `test_unit_scope` |
| `ac_cf_unknown_escalates` | unrecognized pattern → escalate (fail-safe) | `test_unknown_escalates` |
| `ac_policy_loads` | `model-policy.yaml` validates against its schema | `test_policy_valid` |
| `ac_hooks_installed` | `git config core.hooksPath` == `scripts/hooks` after install script | `test_hooks_installed` |

### Definition of Done

- `bash scripts/run_gates.sh <task_id>` produces the same verdict as CI in <30 s.
- A deliberately bad commit (only `.md` changes) is blocked locally.
- Failure classifier posts a comment on a sample failing PR within 1 min of CI completion.

---

## Cross-task wiring (how the 3 tasks compose)

```
                  ┌────────────────────────┐
   Issue (Form)──▶│  TASK-101              │
                  │  intake_to_state.py    │──┐
                  └────────────────────────┘  │
                                              ▼
                                   .agent/state/<id>.json  ◀── single source of truth
                                              │
       ┌──────────────────────────────────────┴──────────────────────────────────┐
       │                                                                         │
       ▼                                                                         ▼
┌─────────────────────────┐                                       ┌──────────────────────────┐
│  TASK-103 (LOCAL)       │                                       │  TASK-102 (CI)           │
│  pre-commit:            │                                       │  agent_gate.yml:         │
│   • min_action_check    │   ───── git push ─────▶              │   A. check_scope.sh      │
│  on CI failure:         │                                       │   B. check_evidence.py   │
│   • classify_failure    │   ◀──── narrow scope ─────            │   C. hdr_gate.py         │
└─────────────────────────┘                                       │   D. ruff+mypy+pytest    │
                                                                  └──────────────────────────┘
                                                                            │
                                                                            ▼
                                                                ┌──────────────────────────┐
                                                                │  Project Board update    │
                                                                │  In Progress → Review    │
                                                                │  Ready  /  Blocked       │
                                                                └──────────────────────────┘
```

---

## Execution order (within Epic 1)

```
Day 1 AM:  TASK-101 schema + agent_state.py + issue template
Day 1 PM:  TASK-101 intake-sync.yml + project board automation
Day 2:     TASK-102 layers A, B, C + agent_gate.yml
Day 3 AM:  TASK-103 min_action_check + pre-commit
Day 3 PM:  TASK-103 classify_failure + classify-on-failure.yml
Day 3 EOD: End-to-end smoke test using a real seed issue (TASK-501 OCR)
```

After Day 3, Epic 5 (Core Parser) becomes the first real consumer — every TASK-5xx issue is created via the questionnaire, dispatched to Copilot Agent (tier-2a, $0), and merged only when all 4 gates are green.

---

## Definition of Done (Epic 1)

- [ ] All three task ACs above pass (`pytest tests/governance -q` green)
- [ ] One seed issue (TASK-501) flows end-to-end: questionnaire → state file → project card → Copilot PR → 4 gates pass → auto-merge → board moves to Done
- [ ] One deliberately bad PR is blocked at each of the 4 layers in turn (recorded in `.agent/evidence/EPIC-1/`)
- [ ] `docs/AGENT-SKILL-CATALOG.md` updated with the new gate scripts
- [ ] `AGENTS.md` references the questionnaire and points agents at `.agent/README.md`

---

*Last updated: 2026-06-06 · Spec source: AI-Dev-Factory `factory-gap-closure-governance.html`*
