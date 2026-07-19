# W5 Human Review Regression Issues 07

> Date: 2026-07-12
> Source: Human review after `W5-COPILOT-DEPLOY-PROOF-HARDENED-06`
> SIT target: `https://sit.yahwan.biz`
> Status: **not accepted for W5 closure**

## Decision

The hardened W5 deploy is not accepted as customer-ready yet.

Copilot proved the Openclaw deploy and basic health checks, but the human review found product-blocking regressions on the live SIT surface:

- Browser Basic Auth still creates a double-login experience.
- Processing still fails after the first successful document and many documents end in `SoftTimeLimitExceeded()`.
- Company delete disappeared for the reviewer path.
- SysAdmin company assignment cannot be saved.
- SIT proof data was left behind.
- Template Configurator still exposes demo/static content.

These must be treated as W5 P0 regression issues. Do not close W5 from the earlier proof report.

## Corrected Processing Diagnosis

This is **not** primarily a "current upload scope" issue.

The latest screenshot shows a deeper Processing pipeline problem:

- One document reached Review Scan successfully.
- Multiple other documents in the same run failed with `SoftTimeLimitExceeded()`.
- The UI shows only a small number of running tasks while many rows are already failed.
- The user's expected behavior is closer to the earlier PoC/UAT behavior, where a small batch finishes in under about one minute.

Repo evidence shows the frontend already tries to process documents concurrently:

- `src/frontend/main-ux-ui.html:6134` defines `MAX_CONCURRENT_PROCESSING = 5`.
- `src/frontend/main-ux-ui.html:6322` starts worker-style concurrent processing.
- `src/frontend/index.html` mirrors the same production-facing static copy.

So the next fix should focus on backend/runtime processing reliability:

- Add explicit provider HTTP timeouts.
- Add stage-level circuit breakers.
- Ensure line-item extraction failures/timeouts are non-blocking when header extraction and mapping can still complete.
- Persist enough per-stage progress/error evidence to know whether a task died in OCR, header extraction, Stage C, line-item extraction, mapping, or persistence.
- Add regression tests that simulate parallel documents and a slow/hung provider call.

## Findings

| ID | Severity | Owner | Symptom | Evidence | Required fix |
| --- | --- | --- | --- | --- | --- |
| HR-07-01 | P0 | Copilot runtime + Claude repo guard | Browser Basic Auth popup still appears before app login, creating two login prompts. | Human screenshot at `sit.yahwan.biz/login.html`; repo config has `auth_basic` in `deploy/sit-site/nginx-sit-yahwan.conf` and `docker/nginx/nginx-sit.conf`. | Remove Basic Auth from customer-facing app routes through the approved Openclaw deploy path, or restrict it to non-app internal routes only. App login must be the only visible login. |
| HR-07-02 | P0 | Claude | Processing is faster than before but still fails/stalls; many documents hit `SoftTimeLimitExceeded()` after the first success. | Human screenshot shows Review Scan has one processed document, while Processing table shows many failed rows with `SoftTimeLimitExceeded()`. | Patch provider/stage timeouts, make line-item extraction non-blocking, add per-stage evidence, and add parallel-processing regression tests. |
| HR-07-03 | P0 | Claude | Company delete button disappeared in SIT. This is a red flag because CI/proof should catch permission-sensitive UI regressions. | Human screenshot shows Companies table actions only `แก้ไข` and `ตั้งค่า`; delete button absent. Code currently renders delete only when `state.currentUser.role === "sys_admin"`. | Ensure the seeded reviewer System Admin path is truly `sys_admin`; sys_admin must see and use delete/soft-delete. Add UI/API regression coverage. |
| HR-07-04 | P0 | Claude | SysAdmin user cannot add or save assigned companies, while admin/staff can. | Human screenshots show SysAdmin row and company assignment drawer with save action; save path does not persist correctly. | Fix edit payload/role-escalation behavior so company assignment can be saved for allowed users without accidentally triggering forbidden sys_admin escalation. Add role-matrix tests. |
| HR-07-05 | P0 hygiene | Copilot proof runner + optional Claude script hardening | Test companies/users remain visible on SIT after proof. | Human screenshots show `W5H06...`, `W5 Proof...`, `SIT Verify...` rows still present. Proof scripts create these rows. | Proof runners must cleanup in `finally` or produce an explicit cleanup artifact. One-time SIT cleanup should remove/deactivate known W5 test prefixes through API, not direct DB edits. |
| HR-07-06 | P0/P1 | Claude | Template Configurator still shows demo/static content. | Human screenshot shows `GL เมโทร อีเล็กทริค - Clone of Express GL` and runtime demo state. Repo has hardcoded demo text in `src/frontend/main-ux-ui.html` and `src/frontend/index.html`. | Remove demo/static content from operational blank states. Template Configurator should show no selected sample/template until real data is chosen or uploaded. Add regression check that blank state has no demo text. |

## Source Pointers

Processing:

- `src/frontend/main-ux-ui.html:6134`
- `src/frontend/main-ux-ui.html:6322`
- `src/backend/workers/tasks.py`
- `src/backend/ml/providers/openrouter.py`
- `src/backend/ml/llm_router.py`
- `src/backend/ml/line_item_extractor.py`

Login / Basic Auth:

- `deploy/sit-site/nginx-sit-yahwan.conf`
- `docker/nginx/nginx-sit.conf`

Companies and users:

- `src/frontend/main-ux-ui.html:4718`
- `src/frontend/main-ux-ui.html:5025`
- `src/frontend/main-ux-ui.html:5041`
- `src/backend/api/companies_admin.py`
- `src/backend/api/users_admin.py`
- `src/backend/auth/dependencies.py`

Template Configurator:

- `src/frontend/main-ux-ui.html:1379`
- `src/frontend/index.html:1379`
- `src/backend/services/export_job.py`

Proof cleanup:

- `scripts/live_proof_w5_deploy_hardened_06.js`
- `scripts/live_proof_w5_deploy_hardened_06.ps1`
- `scripts/live_proof_w5_batch_deploy_sit_03.js`

## Acceptance Criteria

W5 can move back to deploy/proof only after:

1. Processing a small batch does not fail the remaining documents with `SoftTimeLimitExceeded()` when the first document succeeds.
2. Timeout or LLM/provider failure in optional line-item extraction does not prevent a document from reaching Review Scan when header extraction is available.
3. Per-stage evidence identifies the last stage for failures.
4. System Admin on SIT can see and use the company delete action.
5. SysAdmin user company assignment saves correctly for allowed roles and fails clearly for forbidden roles.
6. Operational Template Configurator blank state no longer shows demo template names or demo runtime content.
7. Proof scripts either clean up W5-created data or report a cleanup artifact.
8. Browser Basic Auth is removed from the app login path through Openclaw deploy, leaving app login as the only visible login.

## Routing

Claude Code should fix the repo-owned product/code/test issues:

- HR-07-02 Processing timeout/circuit breaker/stage evidence.
- HR-07-03 Company delete visibility and regression coverage.
- HR-07-04 SysAdmin company assignment.
- HR-07-06 Template Configurator demo/static cleanup.
- Optional repo-side hardening for proof cleanup scripts if it does not require direct SIT edits.

Copilot should own runtime/deploy proof after Claude merges:

- HR-07-01 Openclaw deploy config/proof for browser Basic Auth removal.
- HR-07-05 one-time SIT cleanup and proof-run cleanup verification.
- Final SIT proof that closes all HR-07 issues with screenshots and summary JSON.

Copilot deploy/proof prompt:

- `docs/requirement/phaseII/W5-COPILOT-HUMAN-REVIEW-DEPLOY-PROOF-08.prompt.json`

Acceptance matrix:

- `docs/requirement/phaseII/W5-HR07-ACCEPTANCE-MATRIX-02.md`

Copilot clean-lane follow-up prompt:

- `docs/requirement/phaseII/W5-COPILOT-CLEAN-LANE-FOLLOWUP-09.prompt.json`

---

## Human Review Addendum - 2026-07-17 SIT Review

> Source: manual product-owner review on `https://sit.yahwan.biz/` dated 2026-07-17.
> Planning decision: do not hide these under the older HR-07 closure. Treat them
> as the W6 carryover list that must be triaged before the 2026-07-30 customer
> review. Items marked P0 must either be fixed and proved on SIT, or explicitly
> deferred with an honest customer-safe label.

### UX/UI Baseline To Preserve

All W6 implementation prompts must name these source files so the UI does not drift:

- `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md` - frozen Export / Template Configurator UX decision record.
- `src/frontend/main-ux-ui.html` - production-facing review surface for `/phase2/prototype`.
- `src/frontend/index.html` - static/fallback copy that must stay in parity with `main-ux-ui.html`.
- `src/frontend/ux-ui-prototype.html` and `src/frontend/ux-ui-prototype.css` - legacy workflow demo/reference surface.
- `docs/requirement/phaseII/PHASE-II-PROTOTYPE.html` - reference-only prototype material.

Instruction for agents: align layout, tab behavior, table styling, and workflow order
with the existing production-facing UX. Do not replace full-page export/configurator
flows with modal-first flows. Do not leave clickable controls that are only visual;
either wire them, disable them with a precise deferred label, or hide them from the
customer-facing path.

### New Findings

| ID | Area | Priority | Owner | Status for W6 | Finding | Required fix / proof |
| --- | --- | --- | --- | --- | --- | --- |
| HR-17-01 | Upload | P0 | Claude + Copilot proof | Carry to W6 | Upload no longer gives the PoC-style first-pass company match by Tax ID, so the user cannot quickly confirm the document was loaded into the correct company. | Restore a tax-id match hint during upload/processing: compare seller/buyer tax IDs from OCR/extraction with the selected company, show match/mismatch/unknown, and prove with at least one matching and one non-matching sample. Check PoC references before redesigning. |
| HR-17-02 | Review Scan | P0 | Claude | Carry to W6 | Party fields are incomplete: seller name is visible but seller tax ID is missing; buyer tax ID is visible but buyer name is missing. | Review Scan must show seller name, seller tax ID, buyer name, and buyer tax ID together when extracted. Missing fields must be clearly marked as missing, not silently omitted. Add field-level regression coverage. |
| HR-17-03 | Review Scan / line item confidence | P1 | Claude | Carry to W6 | Line-item confidence feels miscalibrated across real files: `03062026131758.pdf` and `03062026131731.pdf` look over-confident for non-product/service-like rows, while `03062026131708.pdf` / invoice `IV260225-056` is a strong correct extraction but shows low 69 percent confidence. | Calibrate confidence display separately from extraction correctness. Add `03062026131708.pdf` / `IV260225-056` as a golden positive sample tag in the implementation commit/report. Review service/labor/non-product row labeling. |
| HR-17-04 | Review Scan / line-item confirmation | P0 | Claude | Carry to W6 | The line-item logic is useful, but the user cannot explicitly confirm individual line items, reject/unconfirm a bad item, or have Approve All approve line items too. | Add per-line confirm/reject/unconfirm controls. `Approve All` must include confirmable line items or clearly ask before doing so. Export must only include confirmed lines unless a deliberate override is added. |
| HR-17-05 | Export | P0 | Claude | Carry to W6 | Export cannot select individual documents; there is no per-row select control and no select-all control. | Add per-document checkboxes plus Select All / clear selection to the full-page Export flow, preserving the UX freeze design. Export preview/download must pass selected `document_ids` and prove selected-only output on SIT. |
| HR-17-06 | Export / Excel compatibility | P1 | Claude | Carry to W6 | CSV date values are technically formatted, but Excel auto-interprets them incorrectly when opened directly. | Provide an Excel-safe path: default to XLSX where possible, or add a template transform/export option that preserves dates as intended for Express/Excel. Prove by opening/import-shape evidence, not only raw CSV text. |
| HR-17-07 | Companies / COA / AP / AR / Product Master | P0 | Claude | Carry to W6 | Master-data tabs have inconsistent UX and do not show complete lists comfortably. COA, AP Vendor Master, AR Customer Master, and Product Master need consistent search, load more/pagination, add, delete/deactivate, and import behavior. | Normalize these tabs to one table pattern: search bar, count, load more/page controls, add/import, edit, delete/deactivate where backend permits. Prove each tab with > page-size data and search. |
| HR-17-08 | Template Configurator | P0 | Claude | Carry to W6 | Template Mode controls (`Flat Document`, `Flatten Row`, `Grouped Summary`) appear as UI only and cannot be used / are not backed by behavior. | Either wire mode selection through the template model/export dataset behavior, or remove/disable with a precise deferred label. No customer-facing fake controls. |
| HR-17-09 | Template Configurator | P0 | Claude | Carry to W6 | Manual Template Configurator flow from the PoC/reference design appears missing or buried. | Restore the manual fallback flow alongside upload-driven inference: create/edit columns, source fields, transforms, encoding, preview, and save/update. Align with `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`; do not replace it with schema-heavy UX. |
| HR-17-10 | QA / agent test quality | P0 process | Codex + all agents | Carry to W6 | Automated proof has been too optimistic; human review keeps finding issues after test packs pass. | Add a W6 test-quality gate: every claimed fix must include at least one negative/regression test that would fail on the observed human issue, plus live SIT proof for user-facing P0s. Mocked tests must verify the page actually leaves login and reaches the target screen. |

### Immediate W6 Triage Rule

Before opening new W6 feature work, close or explicitly defer:

1. `HR-17-05` Export document selection.
2. `HR-17-04` line-item confirm/reject and Approve All behavior.
3. `HR-17-02` Review Scan party fields.
4. `HR-17-07` master-data table consistency for COA/AP/AR/Product.
5. `HR-17-08` / `HR-17-09` Template Configurator fake-control/manual-flow gap.

`HR-17-03`, `HR-17-06`, and `HR-17-10` can run in parallel but must not be lost:
they directly affect customer confidence on 2026-07-30.
