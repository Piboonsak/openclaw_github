# W5-CODEX-HUMAN-REVIEW-FUNCTIONAL-FIX-02 — Completion Report

## Doc ID
- **Source task:** `docs/requirement/phaseII/W5-CLAUDE-HUMAN-REVIEW-FUNCTIONAL-FIX-02.prompt.json`
- **Executed by:** Codex, while Claude Code was usage-limited
- **Tracking tag:** `W5-HUMAN-REVIEW-FUNCTIONAL-FIX-02`
- **Branch:** `dev`

## Commit SHA
- Included in implementation commit `feat(ui): add W5 human review functional fixes`; final SHA is recorded in the Codex handoff/final status after commit and push.

## Human Review Findings Closed
- **W5-USER-01:** Users screen now has a real soft-deactivate action using the existing `PUT /api/v1/admin/users/{id}` contract with `is_active=false`.
- **W5-USER-02:** User company assignment display no longer falls back to raw UUIDs; missing companies render as a clear missing-company label.
- **W5-USER-03:** Existing sys_admin grant support is preserved and now renders a distinct SysAdmin badge in the Users table.
- **W5-COMPANY-02:** Mapping Rules DOCX preview now supports removing unwanted/duplicate rows before confirm; removed rows are not sent to `/mapping-rules/confirm`.
- **W5-TEMPLATE-01:** `+ สร้าง Template ใหม่` now opens the manual blank Template Configurator path; sample upload remains a helper path, not the only entry point.

## Files Changed
- `src/frontend/main-ux-ui.html`
- `src/frontend/index.html`
- `tests/e2e/w4-admin-crud-uxui.spec.ts`
- `tests/e2e/w4-coa-mapping-rules-uxui.spec.ts`
- `tests/e2e/w4-export-uxui.spec.ts`
- `docs/requirement/phaseII/epic-10/W5-CODEX-HUMAN-REVIEW-FUNCTIONAL-FIX-02-COMPLETION.md`

## Behavior Before vs After
- Before: Users could be created/edited/reset, but there was no visible deactivate action; company assignment fallback could expose IDs.
- After: Users can be deactivated from the table; inactive state reloads from the existing API path; unresolved company IDs show a human-safe missing-company label.
- Before: Mapping Rules DOCX AI preview could be edited but not pruned before save.
- After: Each preview row has a Remove action and the confirm payload contains only the remaining reviewed rows.
- Before: The Template create CTA redirected users into sample-file analysis, making upload feel mandatory.
- After: The Template create CTA starts a blank configurator/edit path; users may still choose Auto-detect from Sample File separately.

## Tests Run
- `npx.cmd playwright test tests/e2e/w4-admin-crud-uxui.spec.ts -g "deactivates users" --workers=1 --reporter=line` — **1 passed**
- `npx.cmd playwright test tests/e2e/w4-coa-mapping-rules-uxui.spec.ts -g "Mapping Rules DOCX" --workers=1 --reporter=line` — **1 passed**
- `npx.cmd playwright test tests/e2e/w4-export-uxui.spec.ts -g "Create Template starts" --workers=1 --reporter=line` — **1 passed**
- `npx.cmd playwright test tests/e2e/w4-admin-crud-uxui.spec.ts tests/e2e/w4-coa-mapping-rules-uxui.spec.ts tests/e2e/w4-export-uxui.spec.ts -g "deactivates users|Mapping Rules DOCX|Create Template starts" --workers=1 --reporter=line` — **3 passed**
- `npm.cmd run verify:w4-html` — **passed**

Local test note: the frontend HTML loads `/static/auth.js`; the updated Playwright specs intercept that asset and serve `src/frontend/auth.js` during local static tests, so no temporary static shim is left in the repo.

## Residual Risks
- **W5-USER-04:** First-login/admin credential flow was not changed in this pass; it still needs live SIT proof with the documented test account.
- **W5-COMPANY-01:** COA PDF Thai glyph repair was not changed in this pass; existing COA preview row removal remains available, but text normalization requires a separate backend/service pass.
- **W5-EXPORT-01 / W5-12:** Export real scanned-data path and line-item-enabled company flow remain open and should be split into their own implementation task.

## Next Copilot Proof Required
- Do not deploy only this slice unless a live review is urgent.
- Preferred next step: batch deploy W5 Processing POC parity (`5836bd6`) plus this W5 functional fix after commit/push, then run one SIT proof pack covering:
  - Users create SysAdmin, display company names, deactivate user, reload inactive state.
  - Mapping Rules DOCX import, remove duplicate row, confirm only remaining row.
  - Templates manual create opens blank Configurator; sample upload remains optional helper.
  - Processing stage tracker from W5-01 still works on live SIT.
