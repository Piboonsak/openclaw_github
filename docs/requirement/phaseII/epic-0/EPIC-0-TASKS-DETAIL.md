# Epic 0 — UX Contract & Workflow Freeze: Tasks Detail

> **Epic Goal**: Lock workflow, interaction, API, and DB impact before deep DB implementation.
> **Duration**: W0 / W1 Day 0 | **Critical Path**: Yes
> **Baseline Date**: 2026-06-20

---

## TASK-001: PoC UX Click Audit + Interaction Inventory

**Owner**: Product / UX + Backend Dev
**Risk**: LOW
**Duration**: ~0.5 day
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-5 (evidence required)

### Purpose

The Phase II prototype currently communicates the intended workflow, but many controls are mock-only. Before DB design, every visible action must be classified so the backend does not model behavior that will be removed or miss behavior that users actually need.

### What exists today

- Deployed prototype: `https://poc-aiaccount.yahwan.biz/phase2/prototype`
- Local prototype: `docs/requirement/phaseII/PHASE-II-PROTOTYPE.html`
- IA document: `docs/requirement/phaseII/MENU-TREE-IA.html`
- Playwright exists in repo and can run browser-based checks

### What to build

1. **Click audit** — run Playwright against the deployed PoC prototype on desktop and mobile.
2. **Action inventory** — list every visible CTA / button / tab / modal trigger by screen.
3. **Classification** — mark each action as `MVP`, `mock-only`, `disable`, or `Phase II/2`.
4. **Blocker list** — identify UX blockers that prevent user-friendly testing.
5. **Evidence** — include Playwright result summary and manual notes.

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docs/requirement/phaseII/epic-0/UX-CLICK-AUDIT.md` | Audit results + action inventory |
| Optional | `tests/e2e/phase2-prototype-audit.spec.ts` | Repeatable click audit for prototype |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_001_1 | All sidebar screens are listed with visible primary actions | manual review |
| ac_001_2 | Each visible action has one classification: `MVP`, `mock-only`, `disable`, `Phase II/2` | manual review |
| ac_001_3 | Mobile navigation behavior is documented | Playwright mobile viewport |
| ac_001_4 | Dead primary actions are identified | Playwright click audit |
| ac_001_5 | Audit includes DB impact notes where relevant | manual review |

### Governance fields

```json
{
  "task_id": "TASK-001",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docs/**", "tests/e2e/**"],
  "forbidden_scope": [".env*", "src/backend/db/**", "src/frontend/**"],
  "max_loops": 3,
  "escalation_policy": "stop"
}
```

---

## TASK-002: MVP Workflow State Machine Freeze

**Owner**: Product / Backend Dev
**Risk**: MEDIUM
**Duration**: ~0.5-1 day
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-10 (wrong-fix retry loop)

### Purpose

DB design depends on workflow states. Freeze the minimum viable state machine before changing ORM models, especially batch and document transitions across Upload, Processing, Review Scan, Review Mapping, and Export.

### What exists today

- `Document.status` exists as a generic string in `src/backend/db/models.py`
- `JournalVoucher.status` exists as a generic string
- `documents.batch_id` exists as a UUID field but there is no first-class batch table
- IA states mention `uploaded`, `processing`, `review_scan`, `exported`

### What to build

1. **Batch states** — define upload batch lifecycle: `draft`, `uploading`, `processing`, `review_scan`, `review_mapping`, `ready_export`, `exported`, `failed`, `archived`.
2. **Document states** — define per-document lifecycle and allowed transitions.
3. **Review states** — define scan approval, flags, mapping confirmation, force confirm rules.
4. **Role guards** — define what Staff and Admin can do at each transition.
5. **Edge states** — define encrypted PDF, OCR failed, extraction failed, unbalanced voucher, skipped export.

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docs/requirement/phaseII/epic-0/WORKFLOW-STATE-MACHINE.md` | Frozen state machine + transitions |
| Modify | `docs/requirement/phaseII/PHASE-II-EPIC-ROADMAP.md` | Link Epic 0 gate |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_002_1 | Batch states and document states are separately defined | manual review |
| ac_002_2 | Every state has allowed next states | manual review |
| ac_002_3 | Staff/Admin role guards are documented | manual review |
| ac_002_4 | Error states are included | manual review |
| ac_002_5 | State names are reused by TASK-003 DB impact contract | manual review |

### Governance fields

```json
{
  "task_id": "TASK-002",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docs/**"],
  "forbidden_scope": [".env*", "src/backend/db/**"],
  "max_loops": 3,
  "escalation_policy": "human"
}
```

---

## TASK-003: DB Impact Contract for Workflow Entities

**Owner**: Backend Dev
**Risk**: MEDIUM
**Duration**: ~0.5-1 day
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-5 (evidence required), PP-11 (business logic mismatch)

### Purpose

Translate UX workflow into DB implications before modifying schema. This prevents adding tables too early or encoding unstable prototype behavior into migrations.

### What exists today

- Core ORM models exist: Tenant, Company, User, Document, Extraction, JournalVoucher, JournalLine, ChartOfAccount, AccountMappingRule, ExportTemplate, ApiUsage, BudgetLimit, AuditLog, DataRetentionPolicy
- Missing likely workflow entities: batch, field correction, document flag, export job/history, template version, review assignment

### What to build

1. **Entity decision matrix** — decide whether each workflow concept is a table, JSONB field, enum/status, or Phase II/2.
2. **Proposed DB deltas** — list candidate tables and fields with purpose.
3. **No-go list** — explicitly list UX ideas not supported in Phase II/1 DB.
4. **Migration order** — define which changes must land before `TASK-801A` and what must wait for `TASK-801B`.
5. **Compatibility check** — preserve PoC file-cache transition where Epic 8 needs dual-mode write.

### Candidate DB additions

| Entity | Purpose | Expected Phase |
|--------|---------|----------------|
| `DocumentBatch` | Upload session, workflow aggregate, progress summary | II/1 |
| `DocumentReview` | Scan approval, mapping confirmation, reviewer metadata | II/1 |
| `DocumentFlag` | Human flag reason/comment/status | II/1 |
| `FieldCorrection` | Field-level human edits with old/new values | II/1 |
| `ExportJob` | Export run, selected docs, template used, status | II/1 |
| `ExportFile` | Generated file metadata + storage key | II/1 |
| `TemplateVersion` | Template draft/published history | II/1 or II/2 |
| `ReviewAssignment` | Explicit reviewer assignment/locking | II/2 unless required |

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docs/requirement/phaseII/epic-0/DB-IMPACT-CONTRACT.md` | Entity decision matrix + proposed schema deltas |
| Optional | `docs/requirement/phaseII/epic-8/EPIC-8-TASKS-DETAIL.md` | Annotate `TASK-801A` / `TASK-801B` with approved state names |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_003_1 | Each UX workflow concept maps to table, field, JSONB, or deferred scope | manual review |
| ac_003_2 | Candidate schema additions include purpose and owner screen | manual review |
| ac_003_3 | Migration order is clear for Epic 8 | manual review |
| ac_003_4 | Existing models are not changed until contract is accepted | git diff |
| ac_003_5 | Contract explicitly calls out what is deferred to Phase II/2 | manual review |

### Governance fields

```json
{
  "task_id": "TASK-003",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docs/**"],
  "forbidden_scope": [".env*", "src/backend/db/**", "alembic/**"],
  "max_loops": 3,
  "escalation_policy": "human"
}
```

---

## TASK-004: Prototype Interaction Patch Scope

**Owner**: UX / Frontend Dev
**Risk**: MEDIUM
**Duration**: ~0.5-1 day
**Closes pain points**: PP-3 (details encoded), PP-5 (evidence required), PP-8 (scope locked)

### Purpose

Patch only prototype interactions that block UX validation. This is not a full UI rewrite. The goal is to let the client and developer click through the MVP flow without confusing dead controls.

### What exists today

- Desktop sidebar navigation works
- Mobile sidebar is hidden with no replacement navigation
- Several primary CTAs are toast-only or dead
- Admin screens contain future-scope controls that look clickable

### What to build

1. **Mobile nav decision** — add minimal mobile nav or explicitly declare desktop-only prototype.
2. **Primary CTA behavior** — make MVP CTAs navigate/open modal/update visible state.
3. **Non-MVP controls** — disable or label future-scope controls.
4. **Template tabs/settings tabs** — ensure tabs visibly switch panels.
5. **Review controls** — make back/next, flag, approve, confirm, export preview behavior understandable.

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `docs/requirement/phaseII/PHASE-II-PROTOTYPE.html` | Patch prototype blockers only |
| Optional | `docs/requirement/phaseII/MENU-TREE-IA.html` | Update IA if scope changes |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_004_1 | Main MVP flow can be clicked end-to-end without dead primary CTA | Playwright/manual |
| ac_004_2 | Mobile behavior is either usable or explicitly desktop-only | Playwright/manual |
| ac_004_3 | Non-MVP controls are visibly disabled or scoped as future | manual review |
| ac_004_4 | No console errors after prototype patch | Playwright |
| ac_004_5 | Patch does not introduce backend/API dependencies | manual review |

### Governance fields

```json
{
  "task_id": "TASK-004",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docs/requirement/phaseII/PHASE-II-PROTOTYPE.html", "docs/requirement/phaseII/MENU-TREE-IA.html", "tests/e2e/**"],
  "forbidden_scope": [".env*", "src/backend/**", "alembic/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-005: API / Route Contract for Phase II Screens

**Owner**: Backend Dev + Frontend Dev
**Risk**: MEDIUM
**Duration**: ~0.5-1 day
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-4 (no mock integration)

### Purpose

Define the data contract each screen needs before implementing DB CRUD and endpoints. The contract should be small enough for Phase II/1 but complete enough that screens do not need fake state.

### What exists today

- Prototype is static HTML
- PoC endpoints mostly read file-cache data
- No formal API contract for Phase II screens

### What to build

1. **Route list** — define MVP routes for auth, company selector, batches, documents, reviews, templates, exports, users, audit.
2. **Payload shape** — define request/response fields for each route.
3. **Screen mapping** — map each route to prototype screen(s).
4. **Error contract** — define standard error response and user-facing messages.
5. **Pagination/filtering** — define minimal list filters for batch/document/audit/export screens.

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docs/requirement/phaseII/epic-0/API-ROUTE-CONTRACT.md` | Route list + payload shapes |
| Optional | `docs/requirement/phaseII/epic-8/EPIC-8-TASKS-DETAIL.md` | Link routes needed by `TASK-801A`, `TASK-801B`, `TASK-803`, `TASK-805` |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_005_1 | Every MVP screen has required API routes listed | manual review |
| ac_005_2 | Batch/document/review/export payloads include IDs and status fields | manual review |
| ac_005_3 | API contract includes company scoping and user role assumptions | manual review |
| ac_005_4 | Error payloads cover upload, OCR, extraction, review, export failures | manual review |
| ac_005_5 | Contract identifies endpoints that can remain mock-only in Phase II/1 | manual review |

### Governance fields

```json
{
  "task_id": "TASK-005",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docs/**"],
  "forbidden_scope": [".env*", "src/backend/**", "alembic/**"],
  "max_loops": 3,
  "escalation_policy": "human"
}
```

---

## TASK-006: Epic 8 Handoff Checklist + Sign-Off

**Owner**: Tech Lead / Backend Dev
**Risk**: LOW
**Duration**: ~0.5 day
**Closes pain points**: PP-5 (evidence required), PP-8 (scope locked), PP-16 (go-live evidence)

### Purpose

Convert Epic 0 decisions into an actionable handoff for Epic 8 so DB work can start without reopening UX decisions every time a missing state appears.

### What exists today

- Epic 8 assumes DB integration can start immediately
- UX review found workflow entities that need decisions first
- Existing roadmap does not yet include Epic 0 as a gate

### What to build

1. **Handoff checklist** — list decisions required before `TASK-801A` starts and what `TASK-801B` depends on.
2. **Epic 8 annotations** — identify which `TASK-801A` / `TASK-801B` / `TASK-802` assumptions changed.
3. **Sign-off block** — explicit approve/defer decisions for schema-impacting UX concepts.
4. **Risk note** — identify what happens if Epic 0 is skipped.
5. **Next work package** — define the first DB implementation slice.

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `docs/requirement/phaseII/epic-0/EPIC-8-HANDOFF-CHECKLIST.md` | Gate checklist before DB work |
| Modify | `docs/requirement/phaseII/PHASE-II-EPIC-ROADMAP.md` | Add Epic 0 checkpoint |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_006_1 | Checklist names all decisions required before `TASK-801A` and `TASK-801B` | manual review |
| ac_006_2 | DB implementation slice is clearly scoped | manual review |
| ac_006_3 | Deferred UX features are listed | manual review |
| ac_006_4 | Roadmap reflects Epic 0 gate | manual review |
| ac_006_5 | Stakeholder can approve the handoff in one review session | manual review |

### Governance fields

```json
{
  "task_id": "TASK-006",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["docs/**"],
  "forbidden_scope": [".env*", "src/backend/**", "alembic/**"],
  "max_loops": 3,
  "escalation_policy": "stop"
}
```
