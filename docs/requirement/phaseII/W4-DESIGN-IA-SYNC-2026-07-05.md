# W4 Design / IA Sync - SIT End-to-End Delivery Rule

> Date: 2026-07-05
> Status: Active W4 design correction
> Applies to: Epic 0, 8, 9, 10, 11, 12, 13, 14, 15, 16
> Source trigger: manual SIT review found visible UI actions that still behave like prototype-only controls

## 1. Why This Exists

W4 cannot close as a weekly delivery only because one lane, such as Epic 10 Export/Configurator, is route-green. The SIT site now exposes a broader product shell. If a user can see and click a menu item or button, the design documents must say whether that action is real, intentionally deferred, or removed from the SIT review surface.

This document is the bridge between the original Phase II IA and the new W4 SIT end-to-end closure plan.

## 2. New Design Rule

Every visible SIT control must be one of:

| State | Meaning | Allowed in SIT? |
| --- | --- | --- |
| Wired | Calls the real backend/API, handles failure, and survives refresh/re-login where persistence is expected | Yes |
| Disabled / Deferred | Visible but cannot be mistaken as complete; label explains owner or later epic | Yes |
| Hidden | Removed from SIT until it can be honestly reviewed | Yes |
| Fake Success | Shows success toast or optimistic completion without backend success | No |

The banned pattern is: click button -> close drawer/modal -> show success toast -> no persisted state.

## 3. W4 SIT Scope Change

The original roadmap places most Admin UI work in Epic 12 W5-W6. That remains true for the full feature set, but W4 has pulled a minimum Company/User vertical slice forward because the current SIT shell exposes those screens.

Minimum W4 vertical slice:

```text
Login
-> Dashboard shell with current session/company context
-> Companies create/edit persists or is visibly deferred
-> Users create/edit persists or is visibly deferred
-> AP/AR master tabs are separate and honest about import/list readiness
-> Templates / Configurator save/update remains wired
-> Export Quick + Template preview/download remains wired
-> Refresh/re-login proves state where persistence is claimed
```

## 4. Cross-Epic SIT Readiness Matrix

| Epic | SIT role in W4 | W4 rule |
| --- | --- | --- |
| Epic 0 - UX Contract | Defines workflow and API/DB impact | Must update IA/design docs when runtime scope changes |
| Epic 8 - Platform Foundation | DB/auth/storage/runtime services | Must be healthy enough for the proven vertical slice; health 200 alone is not enough |
| Epic 9 - Extraction Accuracy | OCR/extraction pipeline | Upload/review surfaces may use fixture data only if clearly labeled; real processing path remains a later proof if not wired |
| Epic 10 - Template Engine + Configurator | Export and template configuration | Must stay wired to backend preview/download/save/update APIs |
| Epic 11 - Purchase Tax | Template-backed purchase tax export | Can be covered through template/export proof; separate tax-report screens must be disabled/deferred if not wired |
| Epic 12 - Admin UI + Login | Login, dashboard, companies, users | Minimum Company/User persistence is pulled into W4 because those screens are visible |
| Epic 13 - Infrastructure + Deployment | SIT deploy/runtime proof | Must prove actual browser flows and API calls, not only static route markers |
| Epic 14 - Line Item + Inventory | Future CR / Phase II/2 | Keep hidden or clearly disabled unless a W4 PoC surface is intentionally shown |
| Epic 15 - Sales Tax Report | Future CR / Phase II/2 | Keep hidden or clearly disabled unless template export path covers it |
| Epic 16 - Full Dashboard + Monitoring | Future CR / Phase II/2 | Internal/advanced monitoring may be visible only as internal deferred shell |

## 5. IA / Menu Tree Update Requirement

`MENU-TREE-IA.html` is still the visual IA source, but it must be read with this overlay:

- A screen listed in the tree is not automatically approved for clickable SIT.
- If the screen is visible in `/index.html` or `/phase2/prototype`, every primary action needs runtime classification.
- Internal Console, Cost Control, Audit Log, Settings, Epic 14, Epic 15, and Epic 16 surfaces should not look complete in customer-facing SIT unless they are actually wired.
- The IA must not imply that Company/User/Admin actions are done if the current implementation only shows a toast.

## 6. Backlog / Roadmap Update Requirement

The backlog must distinguish:

- Current W4 blockers: visible fake-success actions that prevent SIT close.
- Epic 10 follow-up: clone/delete/row-grouping items that are export/template-specific.
- Epic 12 full scope: richer admin management beyond the minimum W4 vertical slice.
- Phase II/2: Epic 14, 15, 16 surfaces that should be hidden or deferred in SIT until funded and implemented.

## 7. Acceptance Checklist For Design Sync

- `MENU-TREE-IA.html` states the wired/deferred/hidden rule.
- `BACKLOG.md` captures cross-epic clickability cleanup and does not bury it as a normal P2 backlog item.
- `PHASE-II-MASTER-PLAN.md` says weekly delivery means a browser-clickable vertical slice with honest UI state.
- `PHASE-II-EPIC-ROADMAP.md` notes that minimum Epic 12 Company/User work is pulled into W4 SIT closure while full Epic 12 remains W5-W6.
- `W4-EXECUTION-PLAN.md` and `W4-TASK-BOARD.md` remain the execution source for current W4 tasks.

## 8. References

- `W4-SIT-END-TO-END-CLOSURE-PLAN.md`
- `W4-EXECUTION-PLAN.md`
- `W4-TASK-BOARD.md`
- `MENU-TREE-IA.html`
- `BACKLOG.md`
- `PHASE-II-MASTER-PLAN.md`
- `PHASE-II-EPIC-ROADMAP.md`
