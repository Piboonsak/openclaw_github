# W6 Execution Handoff - 2026-07-19

> Purpose: next-step work split after committing W5 closeout evidence and the W6 decision bundle.
> Customer review target: 2026-07-30.

## Current Decision

W6 is a closeout sprint. Do not start broad new scope until the HR-17 P0 customer-visible gaps are fixed, proved, hidden, or explicitly deferred.

Primary source:

- `docs/requirement/phaseII/W6-CLOSEOUT-DECISION-BUNDLE-2026-07-19.md`

## Step Order

| Step | Owner | Prompt | Outcome |
| --- | --- | --- | --- |
| 1 | Claude | `W6-CLAUDE-P0-PRODUCT-CLOSEOUT-01.prompt.json` | Product/UI fixes for Export, Review Scan, Companies, Template Configurator, Upload match, and tests |
| 2 | Copilot | `W6-COPILOT-SIT-PROOF-02.prompt.json` | Deploy through Openclaw and prove the W6 P0 path on live SIT |
| 3 | Codex | `W6-CODEX-QA-ACCEPTANCE-03.prompt.json` | Review reports, update close/defer status, and prepare customer-safe review script |

## Non-Negotiables For All Lanes

- Align UX/UI to `src/frontend/main-ux-ui.html`.
- Keep `src/frontend/index.html` in parity if the static fallback is still used.
- Use `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` for Export and Template Configurator behavior.
- Export must remain full-page: select documents -> select mode/template -> adjust columns/data inline -> preview -> download.
- Do not leave fake-click controls. Wire, hide, or label deferred.
- E2E proof must show the page leaves login and reaches the target screen.

## W6 P0 Completion Rule

Each P0 item must end as exactly one of:

- `Done + SIT proof`
- `Deferred + customer-safe wording`
- `Hidden from customer-visible SIT`

No ambiguous "looks done but not proved" item may remain before the 2026-07-30 customer review.
