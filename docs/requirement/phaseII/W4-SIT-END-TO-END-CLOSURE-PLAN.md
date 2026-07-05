# W4 SIT End-to-End Closure Plan

> Date: 2026-07-05
> Purpose: pivot W4 from week-based completion to a usable SIT vertical slice
> Use with: `W4-EXECUTION-PLAN.md`, `W4-TASK-BOARD.md`, `MENU-TREE-IA.html`, Epic 10, Epic 12, and Epic 13 docs
> Design sync: `W4-DESIGN-IA-SYNC-2026-07-05.md`

## 1. Position

The current W4 export/configurator lane is close-ready for its own surface, but the product is not yet SIT-ready as an end-to-end weekly delivery.

Manual SIT review found that important application paths still behave like prototypes:

- Add Company opens a drawer and shows a toast, but does not create persisted data.
- Add User opens a drawer and shows a toast, but does not create persisted data.
- Company detail COA/AP/AR actions still include toast-only controls.
- Some proof reports validated route reachability and marker presence, but not the full user journey with persisted state.

W4 should therefore finish as a real vertical slice, not as a set of isolated weekly checkboxes.

## 2. W4 SIT Definition Of Done

W4 is not done until SIT can prove these conditions with a real browser session and live backend services:

1. User can log in on SIT.
2. User can create or edit a Company and see the change after refresh/re-login.
3. User can create or edit a User and see the change after refresh/re-login.
4. User can import or list AP/AR master data separately for a company, or the UI clearly disables/defer-labels any action not yet implemented.
5. User can create/update a Template Configurator setup and preview it.
6. User can run Quick Export and Template Export through backend endpoints.
7. `index.html` and `/phase2/prototype` do not contradict each other.
8. A SIT clickthrough test records the actual journey, not only static markers.

If any item is intentionally out of scope, the UI must say so clearly and the W4 board must park it with an owner. Silent toast-only success is not acceptable for SIT.

## 3. Critical Vertical Slice For W4

This is the smallest useful end-to-end slice to finish inside W4:

```text
Login
-> Dashboard shell loads with current user/company context
-> Companies: create/edit company persists
-> Users: create/edit user persists with role/company assignment
-> Templates: create/update template from configurator persists
-> Export: Quick Export and Template Export preview/download via backend
-> Refresh/re-login proves persisted state
```

The Admin CRUD portion is Epic 12 by roadmap, but it must be pulled into W4 as a minimal SIT closure slice because the current product shell exposes Companies and Users in the main navigation. A visible navigation item that only shows a toast is a failed weekly delivery, even if the export lane itself is working.

## 4. Scope Split

### Must Finish In W4 SIT

| Area | Minimum W4 behavior | Source |
| --- | --- | --- |
| Login/session | Login works, auth header attached, logout clears session | Epic 12 `TASK-1201` |
| Company CRUD | List/create/edit company persists and reloads | Epic 12 `TASK-1203`, API contract |
| User CRUD | List/create/edit user persists and reloads | Epic 12 `TASK-1204`, API contract |
| AP/AR master | Vendor and Customer tabs are separate; import/list works or is visibly deferred | `TASK-1207`, BL-011 |
| Template Configurator | 3 tabs usable; save/update/template preview works | Epic 10 `TASK-1003` |
| Export | Quick/Template export use real backend preview/download | Epic 10 `TASK-1006` |
| SIT proof | Browser clickthrough plus backend/log proof | Epic 13/Openclaw CI/CD |

### May Park After W4 If Explicit

| Area | Park condition |
| --- | --- |
| Template delete | May remain deferred only if the delete button is disabled or labeled as unavailable, not fake-success toast |
| Template clone | May remain deferred only if clearly marked or excluded from W4 proof |
| Row-grouping strategy | Parked as schema decision; disabled design reference is acceptable |
| Full PDF COA import | Park unless needed for the W4 demo company |
| Full dashboard analytics | Park if dashboard is clearly a summary shell and not the proof target |

## 5. Workstreams

### Lane A - Admin CRUD Vertical Slice

Owner: Codex or Claude Code

Goal: replace toast-only admin actions with real API-backed behavior.

Tasks:

1. Confirm existing backend reality:
   - `GET /api/v1/companies`
   - `POST /api/v1/companies/sync`
   - master import routes for vendor/customer
   - whether user CRUD endpoints exist or must be added
2. Implement or wire minimal Company create/edit:
   - read current list from backend
   - save create/edit through backend
   - refresh list from backend
3. Implement or wire minimal User create/edit:
   - if backend user CRUD exists, wire it
   - if backend user CRUD does not exist, add the smallest authenticated API slice needed for SIT
4. Replace fake success toasts with:
   - real success only after API success
   - visible error on API failure
   - disabled/deferred labels for unimplemented actions

Acceptance:

- Create company -> refresh -> company still appears.
- Create user -> refresh -> user still appears.
- Failed API calls do not show success.

### Lane B - AP/AR Master Data SIT Slice

Owner: Codex or Claude Code

Goal: make the existing AP and AR tabs honest and useful enough for SIT.

Tasks:

1. Wire AP tab to vendor master routes where available.
2. Wire AR tab to customer master routes where available.
3. Use sample files:
   - `private_data/poc/Comp_1/APAR/AP-CCSS.csv`
   - `private_data/poc/Comp_1/APAR/AR-CCSS.csv`
4. If full import UI cannot close inside W4, disable the import buttons and add visible "pending backend/API wiring" state.

Acceptance:

- AP and AR are separate.
- At least list/import path is proven or explicitly parked.
- No fake success toast for AP/AR import.

### Lane C - Export/Configurator Completion Guard

Owner: Codex

Goal: keep the already-fixed Epic 10 path from regressing while admin work is added.

Tasks:

1. Keep `verify:w4-html` passing.
2. Keep Quick Export backend null-template checks passing.
3. Keep Configurator tab click tests passing.
4. Add one end-to-end smoke that starts from navigation, not direct DOM markers only.

Acceptance:

- Existing W4 export/configurator tests still pass.
- SIT clickthrough covers actual clicks and network calls.

### Lane D - SIT Deploy And Runtime Proof

Owner: Copilot

Goal: deploy only after lanes A-C pass locally, then prove the live runtime.

Tasks:

1. Deploy through Openclaw only.
2. Check public edge and internal runtime.
3. Run credentialed browser clickthrough.
4. Capture route/API status and failed network calls.

Acceptance:

- Live SIT proof includes screenshot/video/log or equivalent evidence.
- Report distinguishes "route 200" from "user flow works".

## 6. Execution Order For W4

### Step 0 - Stop Overclaiming

Update status wording:

- Say "Epic 10 export/configurator close-ready" only for that lane.
- Do not say "SIT complete" until Company/User/Admin flows are real or visibly deferred.

### Step 1 - Truth Audit

Run a focused audit of every visible navigation item:

| Screen | Must classify as |
| --- | --- |
| Dashboard | wired / shell / deferred |
| Companies | wired / shell / deferred |
| Company Detail COA | wired / shell / deferred |
| Company Detail AP | wired / shell / deferred |
| Company Detail AR | wired / shell / deferred |
| Users | wired / shell / deferred |
| Templates | wired / shell / deferred |
| Export | wired / shell / deferred |

Any button that says success without API success is a blocker or must be disabled.

### Step 2 - Implement Minimal Admin Slice

Finish Company and User create/edit persistence before another SIT close claim.

### Step 3 - Prove Export/Configurator Still Works

Re-run local focused tests and update the clickthrough script.

### Step 4 - Deploy To SIT

Use Openclaw control-plane workflow.

### Step 5 - SIT End-to-End Clickthrough

Required live path:

```text
Login
-> Dashboard
-> Companies
-> Add Company
-> Refresh/re-login
-> Users
-> Add User
-> Refresh/re-login
-> Templates / Configurator
-> Save or update template
-> Export
-> Quick Export preview/download
-> Template Export preview/download
```

## 7. Agent Routing

| Lane | Owner | Output |
| --- | --- | --- |
| Admin CRUD implementation | Claude Code or Codex | Company/User persistence and tests |
| Export/configurator guard | Codex | regression tests and clickthrough checklist |
| Deploy/runtime proof | Copilot | Openclaw workflow + live SIT report |
| Status/customer wording | Codex | W4 closeout wording that does not overclaim |

## 8. Closeout Rule

W4 can only be called complete when the final report says:

```text
SIT end-to-end vertical slice: PASS
Company CRUD: PASS or visibly deferred with owner
User CRUD: PASS or visibly deferred with owner
AP/AR master flow: PASS or visibly deferred with owner
Export/Configurator: PASS
No fake success toast remains in the proven path
```

Anything less is a partial lane close, not W4 SIT closure.
