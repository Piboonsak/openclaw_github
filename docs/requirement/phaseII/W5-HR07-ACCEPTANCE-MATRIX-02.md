# W5 HR-07 Acceptance Matrix 02

> Date: 2026-07-12
> Scope: final acceptance gate for human-review regression closure
> Use this after both lanes report back:
> - Claude code fix: `W5-CLAUDE-HUMAN-REVIEW-REGRESSION-FIX-07`
> - Copilot deploy/proof: `W5-COPILOT-HUMAN-REVIEW-DEPLOY-PROOF-08`

## Rules

W5 is **not accepted** unless every P0 row below is `PASS`.

`PARTIAL`, `DEFER`, or `BLOCKED` on any P0 row means:

- do not close W5
- do not say SIT is customer-ready
- do not summarize the run as accepted

## Matrix

| ID | Priority | Owner | What must be true | Required proof artifact | Pass rule | Current state |
| --- | --- | --- | --- | --- | --- | --- |
| HR-07-01 | P0 | Copilot | Browser Basic Auth popup is gone from customer-facing app login path. App login is the only visible login. | Fresh incognito browser screenshot for `/login.html` or `/phase2/prototype`; optional `curl.exe`/network evidence showing no Basic Auth challenge on app route. | `PASS` only if browser popup is absent on live SIT after deploy. Repo-only nginx prep is not enough. | `PARTIAL` from CP-08 prep only |
| HR-07-02A | P0 | Claude + Copilot | Small parallel Processing batch no longer collapses into `SoftTimeLimitExceeded()` after the first success. | Claude completion report + Copilot SIT proof with 4-5 docs, per-doc status evidence, and final task states. | `PASS` only if live SIT proof shows the old collapse pattern is gone. | `DEFER` |
| HR-07-02B | P0 | Claude + Copilot | If a doc still fails, the last failed stage is visible and specific. | Screenshot/API payload showing stage/error detail, not just generic failed badge. | `PASS` only if stage evidence exists in live proof. | `DEFER` |
| HR-07-03 | P0 | Claude + Copilot | True `sys_admin` sees company delete/soft-delete, and non-sys-admin does not. | `/api/v1/auth/me` role evidence + Companies screenshot + delete action result. | `PASS` only if role is proven as `sys_admin` and delete behavior matches policy on live SIT. | `DEFER` |
| HR-07-04 | P0 | Claude + Copilot | SysAdmin company assignment saves and persists after reload. | Edit/save screenshot + reload screenshot + API/UI evidence that company names persist. | `PASS` only if assignment survives reload and no forbidden escalation workaround was used. | `DEFER` |
| HR-07-05A | P0 hygiene | Copilot | Existing W5 test companies are no longer active operational rows. | Cleanup summary JSON with before/after counts + Companies UI screenshot. | `PASS` only if zero active matching companies remain. | `PASS` for active companies from CP-08 prep |
| HR-07-05B | P0 hygiene | Copilot | Existing W5 test users are no longer visible in the default operational user list, not only inactive. | Users UI screenshot after cleanup + exact count/selector used in report. | `PASS` only if visible W5 proof users are gone from the default table or the table explicitly excludes inactive rows by design and that behavior is proven. | `PARTIAL` |
| HR-07-05C | P0 hygiene | Copilot | Future proof runners cleanup narrowly and safely. | Script diff + runner note showing no broad `w5` catch-all or hardcoded credentials. | `PASS` only if selectors are tight and credentials come from env only. | `FAIL REVIEW` on current prep |
| HR-07-06 | P0/P1 | Claude + Copilot | Template Configurator blank state has no demo/static `GL Metro / Clone of Express GL` content. | Blank-state screenshot after deploy; optional DOM/text assertion. | `PASS` only if no demo text appears until real sample/template selection. | `DEFER` |

## Review Notes On Current CP-08 Prep

These are not final acceptance results, but they affect the next Copilot pass:

| Review ID | Severity | Finding | Action before final proof |
| --- | --- | --- | --- |
| CP08-R1 | HIGH | Cleanup script contains hardcoded SIT credential fallback. | Remove hardcoded username/password; require env vars and fail closed if missing. |
| CP08-R2 | HIGH | HR-07-05 was over-claimed as `PASS`; current evidence proves only `active` cleanup, not that test users are gone from the visible UI table. | Downgrade user cleanup to `PARTIAL` until UI proof exists. |
| CP08-R3 | MEDIUM | Cleanup matching for users is too broad because it uses generic `w5` needle. | Narrow selectors to proof-owned prefixes/IDs only. |
| CP08-R4 | MEDIUM | Internal Basic Auth path with `return 404` does not by itself prove that auth challenge still works as intended. | Prove route behavior with browser/curl after deploy instead of claiming repo config is enough. |

## Final Gate

Recommendation can be `ACCEPT W5` only if:

1. `HR-07-01` through `HR-07-06` are all `PASS` where required above.
2. Copilot result report includes summary JSON and screenshots.
3. Claude completion report exists and its commit is actually deployed on SIT.
4. No acceptance row relies on repo-only prep when the row requires live SIT proof.

## Combined Copilot Prompt

- `docs/requirement/phaseII/W5-COPILOT-FINAL-HR07-DEPLOY-PROOF-10.prompt.json`

---

## Superseding Review Note - 2026-07-19

This matrix remains valid for the original HR-07 regression closure, but it is no
longer sufficient by itself to declare W5 customer-ready.

New manual SIT findings from 2026-07-17 are recorded in:

- `docs/requirement/phaseII/W5-HUMAN-REVIEW-REGRESSION-ISSUES-07.md`
- `docs/requirement/phaseII/W5-CODEX-CLOSEOUT-STATUS-2026-07-19.md`

Additional carryover issue IDs: `HR-17-01` through `HR-17-10`.

Final W5/W6 closeout rule:

1. HR-07 rows that are still partial must either be proved closed or explicitly superseded by newer proof.
2. HR-17 P0 rows must be fixed and proved on SIT, or deferred with an honest customer-facing state before the 2026-07-30 review.
3. Do not use a mocked Playwright pass as final proof unless the test also proves it left login and reached the target screen.
