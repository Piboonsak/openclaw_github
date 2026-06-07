# EPIC-1-DESIGN-new — Organized Prompts

> ใช้ทีละ prompt ตามลำดับ หรือ ส่ง P0+P1 ก่อนแล้วต่อเป็นรายหัวข้อ
> ไฟล์ target: `docs/PoC/plan/epic-1/EPIC-1-DESIGN-new.html`

---

## P0 — Master Context (ส่งก่อนทุก prompt ถ้าเริ่ม session ใหม่)

```
You are building a single-file HTML design document for Epic 1 of the ai-accounting-copilot project.

Project:
- Repo: YAHWAN-SHOP/ai-accounting-copilot (branch: develop)
- Epic 1 goal: Set up AI agent governance so Copilot can develop the AI Pre-Accounting Copilot PoC
  end-to-end without runaway loops, fake "done", scope creep, or token burn.
- GitHub Issues: https://github.com/YAHWAN-SHOP/ai-accounting-copilot/issues
- Project board: https://github.com/orgs/YAHWAN-SHOP/projects/1/views/2

Epic 1 has 4 tasks:
  TASK-101  Governance State + MCP Intake          (pain points 1–5)
  TASK-102  Four-Layer CI Gate Pipeline            (pain points 6–11)
  TASK-103  Local Enforcement + Failure Classifier (pain points 12–14)
  TASK-104  PR to Production Closure Loop          (pain points 15–18)

Total: 18 pain points closed, 4 days, $0 coding cost (Copilot flat-rate).

Operating mode: Users work from VS Code + NongKung + GitHub MCP/GraphQL.
GitHub Issue UI is optional. All scripts/workflows are *design targets* — they do not exist yet.
```

---

## P1 — HTML Design System & CSS Theme

```
Create a dark-theme single-file HTML document with these design system rules:

CSS variables:
  --bg:#0f172a  --panel:#111827  --panel-2:#1f2937  --text:#e5e7eb
  --muted:#94a3b8  --ok:#22c55e  --warn:#f59e0b  --bad:#ef4444
  --accent:#38bdf8  --line:#334155  --chip:#0b3a4a

Font: "IBM Plex Sans Thai", "Segoe UI", Tahoma (body) + "IBM Plex Mono", Consolas (code/pre)

Required CSS classes:
  .wrap          max-width 1180px centered, padding 24px 16px 80px
  .hero          dark gradient card with box-shadow for the title section
  .card          --panel background, --line border, 12px radius, 16px padding
  .grid.col2     responsive 2-column grid (single column < 860px)
  .grid.col3     responsive 3-column grid
  .chip          pill label, --chip background, --accent border
  .kpi           auto-fit grid of stat boxes (panel-2 bg)
  .flow-box      monospace pre-formatted code/diagram box, dashed blue border
  .mermaid-wrap  container for Mermaid diagrams, same dashed blue border
  .tag-101/102/103/104   colored task tags
  .tag-risk-h/m/l        colored risk tags
  .pill-ok/warn/bad      tiny status badges
  .legend / .dot         color legend row
  details/summary        collapsible sections, open state uses --accent border
  .footer                muted small text, top border

Include: <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js">
Initialize mermaid with theme:"dark" and background "#0b1220" in DOMContentLoaded.
```

---

## P2 — Hero Section + §0 What Changed

```
Add to the HTML:

1. HERO section (.hero class) containing:
   - h1: "Epic 1 — AI Agent Governance"
   - Subtitle (muted): Repo + source spec paths
   - Summary paragraph explaining the goal
   - Chips: MCP-first intake | State file source of truth | GraphQL project sync |
             Policy-based assignment | Close-with-proof | 18/18 pain points | $0 default
   - KPI grid (4 boxes): "4 days / Day 1–4 of Week 1" | "4 tasks / TASK-101/102/103/104" |
     "18/18 / Pain points closed" | "$0 / coding / Copilot flat-rate"
   - Footer links to Issues and Project board

2. §0 "What changed in this design" (.card):
   - Explain: operating mode is VS Code + NongKung + MCP/GraphQL, not GitHub UI
   - Clarify: task-intake.yml, intake-sync.yml, intake_to_state.py are DESIGN TARGETS (not yet in repo)
   - Explain: added TASK-104 to close 6 new deploy/verify pain points → 18 total
   - Explain: Layer C upgraded from Human Decision Router to AI Decision Router (verdict: ตรง/ไม่ตรง)
```

---

## P3 — §1 End-to-End Operating Model (Mermaid Diagram)

```
Add §1 "End-to-end operating model" with a Mermaid flowchart inside .mermaid-wrap.

The flow must show:
  Human in VS Code/NongKung
    → AI drafts Q1–Q8
    → Human confirms scope + AC? (decision node)
      → no: Keep issue status:draft
      → yes: GitHub MCP/GraphQL create or update issue
    → GitHub issue body (same contract as task-intake.yml)
    → intake-sync.yml
    → .agent/state/TASK-ID.json
    → policy_dispatch.py reads model-policy.yaml
    → Move Projects v2 status (board)
    → ready + budget + KI-075 ok? (decision)
      → yes: GraphQL assign copilot[bot]
      → no: Ready for Trial / needs-human
    → Agent PR
    → agent_gate.yml
    → merge → deploy → health → closed-with-proof

Use flowchart TD layout, curve:"basis", htmlLabels:true.
```

---

## P4 — §2 Pain Points Table (18 rows)

```
Add §2 "18 Pain Points → Which Task Closes Each" with:
- A legend row: green dot = CI-enforced hard gate | yellow dot = Policy/prompt + state
- A table with columns: # | Pain point | Closed by (tag) | Mechanism | Status (pill)

All 18 rows:
1   Context loss on long tasks              TASK-101  .agent/state/<id>.json external memory              policy
2   Forgetting requirements                 TASK-101  Issue form → acceptance_criteria[]                  hard gate
3   Skipping details / guessing scope       TASK-101  Q1-Q8 form rejects issues missing AC or scope       hard gate
4   Cannot resume after crash               TASK-101  State persisted every loop; max_loops=5             policy
5   Wrong model tier (cost blowout)         TASK-101  model-policy.yaml routes every task to tier         policy
6   Human bottleneck on every PR            TASK-102  check_hdr_review.py auto-handles LOW/MEDIUM         hard gate
7   Scope creep (wrong files touched)       TASK-102  check_scope.sh blocks forbidden_scope               hard gate
8   Fake/mock integration                   TASK-102  check_evidence.py requires docker raw log            hard gate
9   Fake "done" / no test output            TASK-102  No evidence → PR blocked                             hard gate
10  PR looks done but doesn't run           TASK-102  ruff + mypy + pytest in agent_gate.yml               hard gate
11  Business logic mismatch (code ≠ intent) TASK-102  Layer C AI review: verdict ตรง/ไม่ตรง               hard gate
12  Plan-only commits (token burn)          TASK-103  min_action_check.py + pre-commit                     hard gate
13  Wrong-fix loop                          TASK-103  classify_failure.py narrows fix scope                hard gate
14  Wide-context token burn on fix          TASK-103  Fix-agent context = error + changed_files            policy
15  PR merged but not deployed              TASK-104  Deploy gate dispatches on merge                      hard gate
16  Deploy succeeded but not healthy        TASK-104  /health check required before VERIFIED               hard gate
17  Issue closed without proof              TASK-104  close-with-proof comment required                    hard gate
18  Repeat failures (no KI fingerprint)     TASK-104  KI fingerprint update on failure + incident issue    policy
```

---

## P5 — §3 TASK-101: MCP Intake + Governance State

```
Add §3 TASK-101 "Governance State + MCP Intake" with the following sub-sections:

Header info: Owner: DevOps/Governance | Risk: MEDIUM | Duration: ~2 days | Closes: pain points 1–5

1. Purpose paragraph: intake system that creates validated issue → state file → labels → board → assignment

2. Deliverables (monospace tree):
   .agent/ state/_schema.json + TASK-<ID>.json, evidence/, templates/high-risk-advisory.md, logs/
   .github/ ISSUE_TEMPLATE/task-intake.yml + blocker.yml, workflows/intake-sync.yml
   scripts/ agent_state.py, intake_to_state.py, governance/policy_dispatch.py, project_graphql.py, assign_copilot.py
   tests/governance/ test_state.py, test_intake.py, test_policy_dispatch.py

3. "Actual workflow — no GitHub UI required" table (6 steps):
   Step 1 | Human      | Says task in VS Code e.g. "create TASK-501 OCR extraction" | No code edits yet
   Step 2 | AI         | Drafts Q1–Q8 from user request, epic HTML, repo paths, model-policy.yaml | Must not silently finalize scope or AC
   Step 3 | Human      | Confirms or edits scope + acceptance criteria | If not confirmed, keep status:draft
   Step 4 | MCP/GraphQL| Creates issue with deterministic Q1-Q8 markdown body | If API fails, do not assign agent
   Step 5 | intake-sync| Parses issue, writes state JSON, syncs labels and board column | Invalid state removes status:ready
   Step 6 | policy dispatcher | Reads policy and assigns Copilot only when ready | HIGH/CRITICAL routes to human approval

4. "Q1–Q8 ownership" table:
   task_id          | Yes         | User text or next ID           | Only if generated
   risk_tier        | Yes         | Policy, files, labels, phase   | Yes for HIGH/CRITICAL
   model_tier       | Yes         | Policy routing                 | Only for cost/risk exception
   allowed_scope    | Draft only  | Epic docs + repo paths         | YES (required)
   forbidden_scope  | Draft only  | Policy defaults + sensitive    | YES (required)
   acceptance_criteria | Draft only | User intent + epic/task spec | YES (required)
   max_loops        | Yes         | Default 5, max 10              | No unless overridden
   escalation_policy| Yes         | Risk and category              | Yes for bypass/deploy/security

5. State file JSON schema (pre block, full example with all fields)

6. Issue template validation table (form field → state field → validated by)

7. Hard rule note: PR linked to issue whose state fails schema → BLOCKED at gate

8. Five <details> collapsibles (collapsed by default):
   a. "Design code: task-intake.yml" — full YAML for GitHub Issue Form with Q1-Q8
   b. "Design code: MCP issue body contract" — markdown body example
   c. "Design code: intake_to_state.py" — parse_issue_body() function
   d. "Design code: MCP / GraphQL policy dispatch" — dispatch() function
   e. "Design code: intake-sync.yml" — full workflow YAML

9. "Project Board automation" table:
   Backlog → Ready → In Progress → Review Ready → Blocked → Done (when each column is entered + who sets it)

   Note at bottom: assigning Copilot uses GraphQL only (REST returns 422 — KI-075 lesson)

10. Acceptance Criteria table (7 rows: ac_schema_valid, ac_init_state, ac_intake_parse,
    ac_intake_reject, ac_loop_limit, ac_resume, ac_project_sync)
```

---

## P6 — §4 TASK-102: Four-Layer CI Gate + AI Decision Router

```
Add §4 TASK-102 "Four-Layer CI Gate Pipeline" with:

Header info: Owner: DevOps/Governance | Risk: HIGH | Duration: ~3 days | Closes: pain points 6–11

Purpose: implement 4 layers as CI hard gates in agent_gate.yml; every PR must pass all four.

Four cards in .grid.col2 layout:

LAYER A — Scope Lock (check_scope.sh):
  Input: PR diff vs base + state file
  Output: exit 0 if every changed file is in allowed_scope AND not in forbidden_scope
          exit 1 with per-file reason otherwise
  Note: always-forbidden defaults: .env*, **/secrets/**, **/private_data/commercial/**

LAYER B — Evidence Lock with AC→test binding (check_evidence.py):
  Requires .agent/evidence/<TASK-ID>/evidence.md with 3 sections:
    ## Commands Executed  — must include actual command lines
    ## Raw Output         — verbatim stdout/stderr
    ## Acceptance Criteria — [x] ac_id (test_fn_name) — PASSED for each AC
  Rule: for each AC with "test" field, grep Raw Output for <test_fn> .* PASSED
  Integration ACs (id int_*) must have a docker command line

LAYER C — AI Decision Router (HDR+AI Review):
  Files: scripts/gates/check_hdr_review.py + .github/prompts/hdr-review.prompt.md
  Input: PR diff + state.acceptance_criteria[] + state.risk_tier
  AI reviewer MUST output strict JSON:
    {
      "verdict": "ตรง|ไม่ตรง",
      "business_logic_summary": "...",
      "code_logic_summary": "...",
      "mismatches": ["..."],
      "risk_final": "LOW|MEDIUM|HIGH|CRITICAL",
      "next_action": "approve|request_changes|escalate_human"
    }
  Hard rules:
    1) verdict = ไม่ตรง → gate FAIL + label needs-rework + request-changes comment
    2) risk_final HIGH/CRITICAL → require approved-by-human label
    3) typo/no-business-impact → AI handles directly (no human needed)
  Note: goal is AI reviews what AI should review; human only for business risk.

LAYER D — Quality Pipeline (inline in agent_gate.yml):
  ruff check src/ scripts/ tests/
  mypy scripts/ src/backend --ignore-missing-imports
  pytest -q --maxfail=1
  bash scripts/gates/check_scope.sh
  python scripts/gates/check_evidence.py
  python scripts/gates/check_hdr_review.py
  Uses concurrency: gate-PR# to cancel stale runs.

Implementation checklist table (7 rows):
  1  check_scope.sh              ~60 LOC
  2  check_evidence.py           ~150 LOC
  3  hdr-review.prompt.md        ~80 LOC
  4  check_hdr_review.py         ~140 LOC  (calls AI, validates JSON, fails on ไม่ตรง)
  5  agent_gate.yml              workflow with 4 jobs
  6  Branch protection on main   (GitHub Settings)
  7  tests/governance/test_gates.py  ~260 LOC

Acceptance Criteria table (8 rows: scope blocks env, scope allows in-scope, evidence missing blocks,
AC binding enforced, backward compat, hdr AI review runs, mismatch blocks, workflow order)
```

---

## P7 — §5 TASK-103: Local Enforcement + Failure Classifier + Model Policy

```
Add §5 TASK-103 "Local Enforcement + Failure Classifier + Model Policy" with:

Header info: Owner: DevOps/Governance | Risk: MEDIUM | Duration: ~2 days | Closes: pain points 12–14

Purpose: stop bad commits before CI; when CI fails, narrow the fix scope for the fix-agent.

Deliverables tree:
  scripts/ min_action_check.py, classify_failure.py, run_gates.sh, hooks/pre-commit
  config/ model-policy.yaml, failure-categories.yaml
  .github/workflows/ classify-on-failure.yml

Two cards side by side (.grid.col2):

Card 1 — min_action_check.py (Action Lock):
  Pass if at least one staged file matches: src/**, tests/**, scripts/**, config/**, docker/**
  Fail if everything staged is in: .agent/logs/**, **/*.md (notes only), .agent/state/** (without code)
  Override: state.status=BLOCKED AND evidence has '## Blocker' section

Card 2 — classify_failure.py output example:
  JSON with: category, escalate_to_human, suggested_fix_scope[], evidence_excerpt

Failure categories table (10 rows):
  syntax, lint, type, unit_test, integration_test, docker → escalate: NO
  migration, hmac_signature, permission_auth, unclear → escalate: YES (fail-safe)

Model tier policy (config/model-policy.yaml) as pre block:
  tier-1-opus:     claude-opus-4.7  | architecture, rca, high_risk_review | max 3/sprint
  tier-2a-copilot: github-copilot   | code, bugfix, tests, refactor | cost $0 (DEFAULT for all coding)
  tier-2b-sonnet:  claude-sonnet-4.6 | log_analysis, classify, evidence_check | context = changed_files+error
  tier-3-gemini:   gemini-flash      | docs, changelog, issue_classification
  hard_rules: free_models_for_gates: forbidden; llm_can_final_merge_high_risk: false

Acceptance Criteria table (10 rows)
```

---

## P8 — §5.5 TASK-104: PR to Production Closure Loop

```
Add §5.5 TASK-104 "PR to Production Closure Loop" with:

Header info: Owner: DevOps/Governance | Risk: MEDIUM | Duration: ~1 day | Closes: pain points 15–18

Purpose: close the lifecycle after PR — deploy gate, health check, close-with-proof, KI fingerprint.

Flow diagram (.flow-box):
  PR opened → gates pass → merge → deploy dispatch → /health → state=VERIFIED → closed-with-proof
  Failure → incident issue + revert when needed + KI fingerprint update

Deliverables tree:
  .github/workflows/ closure-loop.yml
  scripts/governance/ close_with_proof.py, expire_bypass_label.py, check_project_board_mapping.py

Acceptance Criteria table (6 rows):
  ac_deploy_dispatches    Merge on main triggers deploy workflow within 60s
  ac_health_required      /health must return 200 before state=VERIFIED
  ac_close_with_proof     State=VERIFIED → close issue + comment with deploy SHA + health URL
  ac_revert_on_failure    Health fail → incident issue opened + revert PR created
  ac_bypass_expires       bypass:governance label > 24h → removed + audit comment
  ac_board_mapping_check  Column rename detected and alerted within 1 daily run
```

---

## P9 — §6 Execution Order + §7 Definition of Done

```
Add §6 "Execution Order (4 Days)" with a .flow-box showing:
  Day 1 AM   TASK-101  schema + agent_state.py + issue template
  Day 1 PM   TASK-101  intake-sync.yml + policy_dispatch + GraphQL board/assign
  Day 2      TASK-102  layers A, B, C (AI review) + agent_gate.yml + branch protection
  Day 3 AM   TASK-103  min_action_check + pre-commit hook
  Day 3 PM   TASK-103  classify_failure + classify-on-failure.yml + model-policy.yaml
  Day 4      TASK-104  closure-loop.yml + close_with_proof + expire_bypass + board_mapping
  Day 4 EOD  End-to-end smoke test: TASK-501 OCR seed issue full lifecycle

Follow with a paragraph: after Day 4, Epic 5 (Core Parser) becomes the first real consumer.
Every TASK-5xx issue is created via MCP/GraphQL, dispatched to Copilot Agent (tier-2a, $0),
and merged only when all 4 gates are green and health check passes.

Add §7 "Definition of Done (Epic 1)" as a bulleted list:
- pytest tests/governance -q green
- Seed issue TASK-501 flows end-to-end (all steps listed)
- One bad PR blocked at each of the 4 layers in turn
- Bypass labels auto-expire within 24 hours with audit comments
- Board mapping check catches renamed/missing project columns
- HIGH/CRITICAL tasks require approved-by-human label before merge
- docs/AGENT-SKILL-CATALOG.md updated with new gate scripts
- AGENTS.md references the questionnaire and points agents at .agent/README.md
```

---

## P10 — §7.5 Fast Pilot Readiness

```
Add §7.5 "Fast Pilot Readiness — ทำแค่นี้รอดไหม?" with:

Opening paragraph: รอดสำหรับ PoC เร่งด่วนได้ ถ้าเปิด 3 guardrails บังคับทันที
และยอมให้ส่วนที่เหลือเป็น shadow mode ชั่วคราว.
ไม่รอดถ้าปล่อยให้ bypass, issue intake, หรือ board automation เป็น manual ล้วน.

"Minimum guardrails ที่ต้อง active ตั้งแต่วันแรก" table (3 rows):
  Forbidden paths   | Hard fail for private_data/**, .env*, secrets, commercial data | Customer data / secrets leak into PR
  Evidence required | Every PR needs raw output or manual proof bound to AC           | AI says done without running anything
  Bypass expires    | bypass:governance expires after 24h with audit comment          | Temporary bypass becomes permanent default

"อะไรยังติดเยอะ" — two side-by-side cards (.grid.col2):

Card HIGH FRICTION (red border, dark red background):
  - task-intake.yml and intake-sync.yml are not created yet
  - MCP issue body must match the Issue Form contract exactly
  - Copilot assignment needs GraphQL and KI-075 precheck
  - Projects v2 column rename breaks automation unless mapping is checked daily
  - Workflow state commits must avoid trigger loops

Card LOW FRICTION (green border, dark green background):
  - Keep governance code isolated in .agent/, scripts/governance/, scripts/gates/
  - Let AI draft Q1-Q8, but require human confirmation for scope + AC
  - Hard fail forbidden paths and missing evidence immediately
  - Run HDR/AI business review in shadow mode until false positives are understood

"Rollout switchboard" table (4 rows):
  Day 0   shadow  All gates comment, forbidden paths hard fail            Seed issue parses into state
  Day 1   hard    Scope + evidence block merge                            One good PR passes, one bad PR blocks
  Day 2   mixed   HDR+AI comments; HIGH/CRITICAL requires human          False positives reviewed
  Day 3+  hard    Full gate + board sync + assignment + closure loop      TASK-501 verified close-with-proof

Warning text (amber color, bold): shadow mode is calibration only. Production-ready Epic 1 means
state sync, evidence gate, board mapping, bypass expiry, and close-with-proof are all enforced.
```

---

## P11 — §8 Practical Add-ons + Footer

```
Add §8 "Practical Add-ons Already Scaffolded" with a table (4 rows):

File | Purpose | Mode
.agent/templates/high-risk-advisory.md
  | 3-provider AI advisory template for HIGH/CRITICAL PRs (Provider A/B/C + cross-provider summary + merge gate)
  | Manual / PR comment

scripts/governance/expire_bypass_label.py
  | Expire stale bypass:governance labels after 24h; --dry-run flag; pagination supported
  | Hourly GitHub Actions

scripts/governance/check_project_board_mapping.py
  | Verify Project #1 Status column names/order; --allow-extra flag; org or user owner via GraphQL
  | Daily GitHub Actions

.github/workflows/governance-watch.yml
  | Runs bypass expiry (hourly) and board mapping check (daily)
  | GitHub Actions cron

Add footer (.footer) with:
  Updated: 2026-06-07
  Note: after sign-off, TASK-101/102/103/104 will be opened as GitHub issues via the new
  questionnaire template (self-bootstrapping).
```

---

## P12 — Assembly Instructions (สั่ง AI ประกอบไฟล์สมบูรณ์)

```
Combine everything from P0–P11 into a single file:
  docs/PoC/plan/epic-1/EPIC-1-DESIGN-new.html

Rules:
1. Do NOT use external CSS frameworks (Tailwind, Bootstrap). All CSS is inline in <style>.
2. Use IBM Plex Sans Thai from Google Fonts (optional link tag) OR fallback to Segoe UI.
3. Include Mermaid from CDN: https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js
4. All <details> sections are CLOSED by default (default behavior, no JS needed).
5. The file must render correctly with no JS errors in a browser without internet.
   (Mermaid diagrams may fail without CDN but should not throw errors.)
6. Section order:
   Hero → §0 → §1 → §2 → §3 (TASK-101) → §4 (TASK-102) → §5 (TASK-103) →
   §5.5 (TASK-104) → §6 → §7 → §7.5 → §8 → Footer
7. Each h2 section heading uses the format:
   <h2><span class="sn">§N</span> Title</h2>
8. All Thai text must render correctly (UTF-8 charset declared in head).
9. Target file size: 40–55 KB. If larger, move long code blocks inside <details>.
10. Do NOT split into multiple files or use iframes.
```

---

## Quick Reference: สิ่งที่ต้องระวังเป็นพิเศษ

| จุดเสี่ยง | วิธีป้องกัน |
|---|---|
| Mermaid syntax พัง | ใช้ `flowchart TD` + `htmlLabels:true` เสมอ; หลีก`{}` ใน node labels |
| `<details>` ไม่ collapse | อย่า set `open` attribute ถ้าต้องการ default closed |
| CSS `--variable` ไม่ inherited | declare ทั้งหมดใน `:root{}` เท่านั้น |
| Thai font ไม่ render | charset=utf-8 + IBM Plex Sans Thai เป็น first font choice |
| file ใหญ่เกิน → context limit | ย้าย YAML/Python code blocks ทั้งหมดเข้า `<details>` |
| `${{ secrets.X }}` ใน pre block | escape เป็น `$&#123;&#123; secrets.X &#125;&#125;` ใน HTML entity |
