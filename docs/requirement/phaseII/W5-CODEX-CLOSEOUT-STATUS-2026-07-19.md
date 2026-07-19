# W5 Codex Closeout Status - 2026-07-19

> Purpose: reconcile W5 proof results, 2026-07-17 human SIT review findings, and
> the W6 carryover list before the 2026-07-30 customer review.
> SIT target checked: `https://sit.yahwan.biz/`

---

## Decision

W5 should be treated as **functionally not closed yet**, but ready to move into a
W6 closeout sprint with a strict finish/defer rule.

The right plan for this week:

1. Finish the Export / Review Scan / Template Configurator P0 gaps first.
2. Defer anything not customer-critical into W6 with an honest label.
3. Keep the existing UX shape; do not let follow-up agents redesign the flow.
4. Require tests that prove the human-found issue, not only happy-path mocks.

---

## UX/UI Source Map

Use these files when implementing or reviewing W6 work:

| File | Role |
| --- | --- |
| `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` | Frozen UX decision record for Export and Template Configurator. |
| `src/frontend/main-ux-ui.html` | Production-facing review surface served by `/phase2/prototype`. |
| `src/frontend/index.html` | Static/fallback copy; must stay in parity with `main-ux-ui.html`. |
| `src/frontend/ux-ui-prototype.html` | Legacy workflow demo/reference surface. |
| `src/frontend/ux-ui-prototype.css` | Legacy demo styling reference. |
| `docs/requirement/phaseII/PHASE-II-PROTOTYPE.html` | Reference-only prototype material, not route proof. |

Agent instruction for W6 prompts:

- Align with the existing production-facing UX.
- Preserve the full-page Export flow from the UX freeze.
- Do not introduce modal-first field pickers for Export.
- Do not leave clickable UI-only controls. Wire them, hide them, or show a precise deferred state.
- Keep table patterns consistent across COA, AP, AR, Product Master, and Template Configurator.

---

## Verification Run - 2026-07-19

### Live SIT read-only check

Read-only route checks from this workstation:

| Route | Result |
| --- | --- |
| `https://sit.yahwan.biz/api/health` | `200` |
| `https://sit.yahwan.biz/api/health/ready` | `200` |
| `https://sit.yahwan.biz/phase2/prototype` | `200` |

Scope note: this confirms the live route/health surface is reachable now. It does
not prove the full browser workflow, document processing, or export behavior.

### Local backend/service tests

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/api/test_export_api.py tests/services/test_export_dataset.py tests/services/test_master_data_import.py tests/services/test_product_master_import.py tests/api/test_master_import_api.py tests/api/test_product_master_api.py tests/test_pipeline_stage_timeouts.py tests/ml/test_line_item_extractor.py -q
```

Result: **54 passed**.

Covered:

- export API and dataset shape
- export company access guard
- AP/AR master import/list search and pagination service behavior
- Product Master import/list service/API behavior
- pipeline stage timeout behavior
- line-item extractor behavior

### Local UI checks

Command:

```powershell
node scripts/verify-w4-html-integrity.mjs
```

Result: **PASS** (`VERIFY_OK`) - `index.html` and `main-ux-ui.html` parity is intact.

Command:

```powershell
npx.cmd playwright test tests/e2e/w4-coa-mapping-rules-uxui.spec.ts --workers=1 --reporter=line
```

Result: **6 passed**.

Covered:

- COA tab loads backend data
- COA CSV/YAML import
- COA PDF async extraction/review table
- Mapping Rules manual add
- Mapping Rules DOCX review/delete/confirm

Command:

```powershell
npx.cmd playwright test tests/e2e/w4-product-master-uxui.spec.ts --workers=1 --reporter=line
```

Result: **2 failed** before reaching Product Master assertions.

Observed reason:

- The spec stayed on the login screen and timed out waiting for `companiesStatus`.
- This is a test harness/login bootstrap gap, not proof that Product Master UI is correct.
- The failure supports `HR-17-10`: mocked tests must prove the page actually leaves login and reaches the target screen.

Command:

```powershell
npx.cmd playwright test tests/e2e/w5-export-lineitem-uxui.spec.ts --workers=1 --reporter=line
```

Result: **timeout / inconclusive**.

Observed reason:

- The spec comments require a local `/static/auth.js` mapping, but the W5 spec does not route that asset the way other specs do.
- Treat this as a verification gap, not a W5 pass.

---

## W5 Status By Area

| Area | Current status | Decision for W6 |
| --- | --- | --- |
| SIT route/health | Green by read-only check on 2026-07-19. | Keep as baseline; still require functional proof after fixes. |
| Processing / OCR stall | Improved. Previous proof showed 4 docs reached `review_scan` with no `SoftTimeLimitExceeded`; engineering decision remains Conditional Go until soak. | Run short soak or keep Conditional Go wording. |
| Export real OCR-backed rows | Partially proved by W5 proof 14: 4 OCR-produced documents exported as 4 document rows. | Do not reopen this unless regression appears. Add document selection and Excel-safe date handling. |
| Line-item review/export | Implemented in repo, but 2026-07-17 review found missing per-line confirm/reject behavior and Approve All does not approve line items. | W6 P0. Must prove enable_stock flow end to end on SIT. |
| Review Scan party fields | Human review found seller/buyer name/tax-id display gaps. | W6 P0. |
| Upload company Tax ID match | PoC behavior appears missing from current SIT. | W6 P0/P1 depending on scope, but should be visible before customer review. |
| COA/Mapping Rules | Local regression suite passes for core COA/mapping behavior. Thai glyph issue still open from earlier W5 notes. | W6 carryover for glyph normalization and table consistency. |
| AP/AR/Product Master tables | Service/API tests pass for list/search/pagination. Human review says UI needs consistent search/load more/add/delete. Product Master Playwright is inconclusive due login harness gap. | W6 P0 UX consistency pass. |
| Template Configurator | Blank-state demo cleanup was previously proved, but 2026-07-17 review found Template Mode fake controls and missing manual flow. | W6 P0. Restore/wire or defer visibly. |
| Test quality | Current automated tests are not trustworthy enough for customer-facing closure by themselves. | W6 P0 process gate. |

---

## W6 Carryover Board

| ID | Priority | Owner | Status | Target outcome |
| --- | --- | --- | --- | --- |
| W6-01 | P0 | Claude | Open | Export per-document selection + Select All, selected-only preview/download. |
| W6-02 | P0 | Claude | Open | Line-item per-row confirm/reject/unconfirm; Approve All includes line items or prompts clearly. |
| W6-03 | P0 | Claude | Open | Review Scan shows seller name/tax ID and buyer name/tax ID consistently. |
| W6-04 | P0 | Claude | Open | Template Configurator mode controls wired or honestly deferred; manual configuration flow restored. |
| W6-05 | P0 | Claude | Open | COA/AP/AR/Product Master table UX consistency: search, load more/page, add/import, edit, delete/deactivate. |
| W6-06 | P0 | Copilot | Open | SIT proof after W6 fixes: Upload -> Processing -> Review Scan -> Review Mapping -> Export, with selected documents. |
| W6-07 | P1 | Claude | Open | Upload Tax ID company-match hint restored from PoC behavior. |
| W6-08 | P1 | Claude | Open | Excel-safe date export behavior. |
| W6-09 | P1 | Claude | Open | Line-item confidence calibration; tag `03062026131708.pdf` / `IV260225-056` as a golden correct sample. |
| W6-10 | P1 | Claude | Open | COA Thai glyph normalization. |
| W6-11 | P0 process | Codex + all agents | Open | Test-quality gate: every claimed fix has a failing-before/passing-after test and live SIT proof where required. |

---

## Customer Review Rule For 2026-07-30

Before customer review, the demo path must avoid unproved surfaces.

Minimum acceptable demo path:

1. Login to `/phase2/prototype`.
2. Select one known company.
3. Upload/process a small known document set.
4. Review Scan: show party fields and line-item decision controls.
5. Review Mapping: confirm mapping rows.
6. Export: select documents, preview, download, and explain date/export format behavior.

Anything not complete must be shown as an honest deferred state, not as a clickable
control that does nothing.

---

## W6 Decision Bundle Link

W6 planning and acceptance are now centralized in:

- `docs/requirement/phaseII/W6-CLOSEOUT-DECISION-BUNDLE-2026-07-19.md`

The bundle explicitly includes these overview/control files in the W6 decision set:

- `docs/requirement/phaseII/MENU-TREE-IA.html`
- `docs/requirement/phaseII/BACKLOG.md`
- `docs/requirement/phaseII/PHASE-II-TIMELINE.html`
- `docs/requirement/phaseII/PHASE-II-MASTER-PLAN.md`
- `docs/requirement/phaseII/PHASE-II-EPIC-ROADMAP.md`
