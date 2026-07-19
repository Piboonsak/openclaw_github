# W6 Closeout Decision Bundle - 2026-07-19

> Source of truth for W6 planning after the 2026-07-17 human SIT review.
> Customer review target: 2026-07-30.

## Decision

W5 is not accepted as fully closed. W6 must be treated as a closeout sprint for customer-review readiness, not as a broad new-feature week.

The W6 rule is:

- Finish and prove customer-visible P0 items on SIT before claiming UAT/customer readiness.
- If an item cannot be finished this week, explicitly mark it deferred with owner, risk, and customer-facing wording.
- Do not leave UI controls that look clickable but are not wired. They must be wired, hidden, or visibly deferred.
- Keep UX/UI aligned to the existing production-facing design in `src/frontend/main-ux-ui.html`; keep `src/frontend/index.html` in parity when that static fallback is still used.

## Execution Handoff

Use `docs/requirement/phaseII/W6-EXECUTION-HANDOFF-2026-07-19.md` to dispatch the next W6 steps:

- Claude product fix prompt: `docs/requirement/phaseII/W6-CLAUDE-P0-PRODUCT-CLOSEOUT-01.prompt.json`
- Copilot SIT proof prompt: `docs/requirement/phaseII/W6-COPILOT-SIT-PROOF-02.prompt.json`
- Codex QA/acceptance prompt: `docs/requirement/phaseII/W6-CODEX-QA-ACCEPTANCE-03.prompt.json`

## Input Docs Included In W6

These planning files must be read together when assigning or accepting W6 work:

| File | W6 use |
| --- | --- |
| `docs/requirement/phaseII/PHASE-II-EPIC-ROADMAP.md` | Epic-level status and W6 closeout scope |
| `docs/requirement/phaseII/PHASE-II-MASTER-PLAN.md` | Delivery rule and customer-review gate |
| `docs/requirement/phaseII/PHASE-II-TIMELINE.html` | Week-by-week status visible to stakeholders |
| `docs/requirement/phaseII/BACKLOG.md` | Backlog items reopened or promoted by HR-17 |
| `docs/requirement/phaseII/MENU-TREE-IA.html` | Visible screen/control contract |
| `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` | Frozen Export and Template Configurator UX |
| `docs/requirement/phaseII/W5-HUMAN-REVIEW-REGRESSION-ISSUES-07.md` | Human review issue log including HR-17 addendum |
| `docs/requirement/phaseII/W5-CODEX-CLOSEOUT-STATUS-2026-07-19.md` | Current W5 proof/defer status |

## UX/UI Source Map

| Surface | Role |
| --- | --- |
| `src/frontend/main-ux-ui.html` | Production-facing SIT review surface, served at `/phase2/prototype` |
| `src/frontend/index.html` | Static/fallback copy that must stay in parity with `main-ux-ui.html` |
| `src/frontend/ux-ui-prototype.html` and `src/frontend/ux-ui-prototype.css` | Legacy workflow demo/design reference, served at `/workflow-demo` |
| `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` | Frozen UX decision source for Export and Template Configurator |

## W6 P0 Closeout Board

| ID | Source | Area | W6 outcome required |
| --- | --- | --- | --- |
| W6-P0-01 | HR-17-05 | Export | Per-document row selection, Select All, selected-count/total, and selected-doc export proof on SIT |
| W6-P0-02 | HR-17-04 | Review Scan / Line Items | Line-item approve/reject/unconfirm controls and Approve All includes line items |
| W6-P0-03 | HR-17-02 | Review Scan | Seller name + seller tax ID + buyer name + buyer tax ID are visible, editable, and included in audit/commit payload |
| W6-P0-04 | HR-17-07 | Companies | COA, AP Vendor Master, AR Customer Master, and Product Master share consistent search/load more/add/edit/delete or deactivate behavior |
| W6-P0-05 | HR-17-08/09 | Template Configurator | Template Mode controls are either wired for Flat Document, Flatten Row, Grouped Summary or disabled with honest labels; manual config fallback from PoC is restored or clearly reachable |
| W6-P0-06 | HR-17-01 | Upload | PoC-style company Tax ID matching/check is restored or replaced with an explicit company-match warning before upload commit |
| W6-P0-07 | HR-17-06 | Export CSV | Date output is proved Excel-safe with client import steps, not only raw CSV text inspection |
| W6-P0-08 | HR-17-10 | QA Gate | Add/repair tests so at least one automated check reproduces a human-found issue and proves navigation left login before passing |

## W6 P1 Parallel Work

| ID | Source | Area | W6 handling |
| --- | --- | --- | --- |
| W6-P1-01 | HR-17-03 | Confidence calibration | Tag `03062026131708.pdf` / invoice `IV260225-056` as a golden positive line-item sample and review confidence scaling for overconfident non-product/labor rows |
| W6-P1-02 | W5 proof gap | Product Master tests | Repair Playwright bootstrap so Product Master UX proof reaches the target screen instead of timing out at login |
| W6-P1-03 | W5 proof gap | Export/Line-item E2E | Repair static auth mapping or test setup so W5 export-lineitem Playwright proof is not inconclusive |

## Acceptance Gate Before Customer Review

Before the 2026-07-30 customer review, the team must produce one of these for every W6 P0 item:

- `Done + SIT proof`: screenshot/test/API evidence, with file or commit reference.
- `Deferred + wording`: why it is not finished, when it will be done, and what customer-facing wording to use.
- `Hidden`: removed from customer-visible SIT until it is safe to show.

No item should remain in an ambiguous "looks done but not proved" state.
