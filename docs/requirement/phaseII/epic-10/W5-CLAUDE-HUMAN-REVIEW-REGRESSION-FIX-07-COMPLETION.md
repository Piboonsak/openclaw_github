# W5-CLAUDE-HUMAN-REVIEW-REGRESSION-FIX-07 — Completion Report

## Doc ID
- **Task:** `docs/requirement/phaseII/W5-CLAUDE-HUMAN-REVIEW-REGRESSION-FIX-07.prompt.json`
- **Tracking tag:** `W5-HUMAN-REVIEW-REGRESSION-FIX-07`. **Branch:** `dev`.
- **Source findings:** `docs/requirement/phaseII/W5-HUMAN-REVIEW-REGRESSION-ISSUES-07.md` (human review after `W5-COPILOT-DEPLOY-PROOF-HARDENED-06`).
- **Scope:** the four Claude-owned P0 code/test findings only — HR-07-02, HR-07-03, HR-07-04, HR-07-06. No deploy, no SIT edits, no W5-12 redesign. HR-07-01 (Basic Auth) and HR-07-05 (SIT proof-data cleanup) remain Copilot runtime/deploy items and are **not** closed here.

## Commit SHA
- Single commit on `dev` carrying the patch + tests + this report (governance Action Lock blocks docs-only commits). Resolve the hash: `git log --grep W5-HUMAN-REVIEW-REGRESSION-FIX-07 -1 --format=%H`.

## Human review findings closed
- **HR-07-02 (P0):** Processing still failed after the first successful document; many siblings ended in `SoftTimeLimitExceeded()`.
- **HR-07-03 (P0):** company soft-delete disappeared for the reviewer "System Admin" path.
- **HR-07-04 (P0):** SysAdmin company assignment could not be saved (admin/staff could).
- **HR-07-06 (P0/P1):** Template Configurator blank state still showed demo/static content (`GL เมโทร อีเล็กทริค — Clone of Express GL`).

## Processing timeout and parallel behavior fix (HR-07-02)
Root cause: the LLM provider SDK calls had **no explicit HTTP timeout** (openai/anthropic default ≈ 600s, longer than the task `soft_time_limit`), so one stalled call rode a document straight to the Celery soft limit and, under the frontend's 5-way concurrency, starved the shared worker budget for sibling documents.

Fixes:
- **Explicit provider HTTP timeout (primary).** `config.settings.LLM_HTTP_TIMEOUT_SECONDS` (default 60s) is threaded through `llm_router._build_provider` into both `OpenRouterProvider` (openai client constructor **and** per-request `timeout`) and `AnthropicProvider`. `max_retries` is pinned low (1) so a timeout is not silently retried into a multiple of the budget — the Stage C cascade already provides cross-model/provider fallback.
- **Per-stage circuit breakers.** `run_pipeline` now runs the Stage C cascade and the line-item stage inside `asyncio.wait_for(asyncio.to_thread(...), timeout)` wall clocks (`STAGE_C_STAGE_TIMEOUT_SECONDS` default 240s; `LINE_ITEM_STAGE_TIMEOUT_SECONDS` default 75s). On overrun the pipeline keeps whatever header it has and continues — the document still reaches Review Scan.
- **Line-item extraction is optional / non-blocking.** A timed-out or failing line-item stage records empty/pending rows (`line_item_timed_out`, `error`) and never touches `ctx.status`; header extraction + journal routing complete on their own.
- **Per-stage evidence.** `PipelineContext.stage_history` records `{stage, elapsed_s}` for each stage; `failed_stage` records the stage active at failure. The Celery task result now includes `stage_history`/`failed_stage`/`*_timed_out`, `_report_progress` emits `elapsed_s` in the task meta (so `GET /tasks/{id}` shows which stage a doc is on and for how long), and `build_pipeline_persistence_plan` prefixes `processing_error` with `[<stage>]` so a failed document names its failing stage.

Files: `config/settings.py`, `src/backend/ml/providers/openrouter.py`, `src/backend/ml/providers/anthropic.py`, `src/backend/ml/llm_router.py`, `src/backend/pipeline/orchestrator.py`, `src/backend/workers/tasks.py`, `src/backend/services/document_workflow.py`.

## Company delete / sys_admin fix (HR-07-03)
Root cause: `scripts/seed_data.py` seeded the single bootstrap operator account as `role="admin"`, never `sys_admin`. The frontend correctly (fail-closed) renders company delete only for `sys_admin`, and the backend `DELETE /v1/admin/companies/{id}` correctly requires `require_sys_admin` — so the reviewer's "System Admin" account, being only an `admin`, legitimately saw no delete action.

Fix: the bootstrap operator account is now seeded as a **true `sys_admin`** (create branch + re-seed promotion path), so a redeploy repairs the reviewer path. `sys_admin` is a strict superset of `admin`; admin/staff accounts are still created through the Users admin UI. **Backend enforcement was not weakened** — `require_sys_admin` on delete and the frontend `role === "sys_admin"` gate are unchanged.

Files: `scripts/seed_data.py` (+ regression tests below).

## SysAdmin company assignment fix (HR-07-04)
Root cause: the edit drawer always sent the user's (pre-filled) role in the PUT payload, and `update_user` ran the escalation guard on **every** supplied role. So an admin editing an existing `sys_admin`'s company assignments echoed `role="sys_admin"`, which `_reject_sys_admin_escalation` treated as a forbidden escalation → 403, and the assignment could never be saved.

Fix (defense in depth, access control intact):
- **Backend:** the escalation guard now fires only on a genuine role **change** (`body.role is not None and body.role != user.role`). Re-sending an unchanged role is a no-op; a real staff/admin → `sys_admin` change by a non-sys-admin is still rejected 403.
- **Frontend:** `saveUserDrawer` omits `role` from the PUT payload when it equals the loaded user's role, so an unchanged role is not even sent.

Files: `src/backend/api/users_admin.py`, `src/frontend/main-ux-ui.html`, `src/frontend/index.html`.

## Template Configurator demo cleanup (HR-07-06)
The hardcoded demo subtitle `GL เมโทร อีเล็กทริค — Clone of Express GL · self-service builder mode` was removed from the operational blank state in both HTML files. The header (`#configuratorSubtitle`) now shows a neutral empty state (`ยังไม่ได้เลือก template — …`) and is updated by `updateConfiguratorSubtitle()` to the **real** active template name only after an actual edit/view selection (`openTemplateConfiguratorReal`) or a blank-start (`createBlankTemplateFlow`). The rest of the configurator already used neutral blank states ("No live analysis yet", "No sample uploaded").

Files: `src/frontend/main-ux-ui.html`, `src/frontend/index.html`.

## Tests run
All commands run from repo root on `dev`.

- **New Processing timeout / parallel regression tests** (would fail on pre-fix code):
  - `tests/test_pipeline_stage_timeouts.py` — line-item stage timeout is non-blocking; a slow optional stage on one document does NOT fail a concurrent sibling (batch isolation); Stage C timeout keeps the header; stage_history + failed_stage evidence is captured and surfaced in the persistence plan.
  - `tests/ml/test_provider_timeout.py` — the HTTP timeout is passed to the openai client (constructor + request) and `_build_provider` uses the configured value with a 60s fallback.
- **New role-matrix / seed tests:**
  - `tests/api/test_users_admin_api.py::test_admin_can_edit_sys_admin_company_assignments_without_escalation` (200, was 403), `::test_sys_admin_can_promote_existing_user_to_sys_admin`; existing `::test_admin_cannot_escalate_existing_user_to_sys_admin` still 403.
  - `tests/db/test_seed_data.py::test_bootstrap_admin_user_is_seeded_as_true_sys_admin`.
- **New Playwright regression coverage** (`tests/e2e/w4-sys-admin-visibility-uxui.spec.ts`): sys_admin sees the company delete (ลบ) action; admin/staff do not; Template Configurator blank state contains no `Clone of Express GL` / `เมโทร` demo text.

Results:
- `python -m pytest tests/test_pipeline_stage_timeouts.py tests/ml/test_provider_timeout.py tests/ml/test_line_item_extractor.py tests/test_pipeline.py tests/workers/test_tasks.py -q` → **24 passed**.
- `python -m pytest tests/workers tests/services/test_document_workflow.py tests/services/test_export_dataset.py tests/api/test_export_api.py tests/api/test_users_admin_api.py tests/api/test_companies_admin_api.py tests/api/test_documents_api.py tests/db/test_seed_data.py tests/ml tests/test_pipeline_stage_timeouts.py tests/auth -q` → **149 passed**.
- `node scripts/verify-w4-html-integrity.mjs` → `VERIFY_OK` (index.html == main-ux-ui.html).
- Playwright (static server on `127.0.0.1:8765` with `/static/auth.js` mapped): `w4-sys-admin-visibility-uxui.spec.ts` → **9 passed** (incl. 4 new); `w4-templates-real-uxui.spec.ts` + `w4-admin-crud-uxui.spec.ts` → **12 passed** (no regression).
- Full app import OK; provider/router/orchestrator import OK with the new timeout settings resolved (60/240/75).

## Residual Copilot runtime/deploy follow-up
- **HR-07-01 (Basic Auth):** remove Basic Auth from customer-facing app routes via the Openclaw deploy path so app login is the only visible login. The `deploy/sit-site/nginx-sit-yahwan.conf` / `docker/nginx/nginx-sit.conf` edits in the working tree are Copilot's deploy-lane change, **not** part of this commit.
- **HR-07-05 (SIT proof-data cleanup):** one-time API cleanup of the `W5H06` / `W5 Proof` / `SIT Verify` prefixes and proof-runner `finally`-block cleanup. Optional repo-side proof-runner hardening was intentionally left out of this P0 code-fix commit to keep scope tight; it does not affect app behavior.
- **Re-seed required:** the sys_admin promotion (HR-07-03) only takes effect after `python scripts/seed_data.py` (or the deploy's seed step) runs against SIT — the existing bootstrap account is promoted admin → sys_admin on re-seed.
- **Migration note:** no new migration in this task; migration `013` from W5-12 is still required at deploy (`alembic upgrade head`).

## Next deploy/proof handoff
Claude does not deploy. After this merges to `dev`, Copilot should redeploy `dev` via the Openclaw control plane (run the seed so the operator account becomes sys_admin; `alembic upgrade head`) and prove on SIT:
1. A small batch no longer fails siblings with `SoftTimeLimitExceeded()` after the first success when an optional line-item/provider stage is slow; task evidence shows the last active stage + elapsed.
2. A timed-out/failed optional line-item stage still lets the document reach Review Scan.
3. The reviewer "System Admin" account is a true `sys_admin` and can see and use company delete; admin/staff cannot.
4. An admin (and a sys_admin) can save an existing sys_admin user's company assignments; a non-sys-admin promotion to sys_admin still fails 403.
5. The Template Configurator blank state shows no demo template/runtime content.
6. Then close HR-07-01 (Basic Auth) and HR-07-05 (SIT cleanup) in the Copilot lane, and produce the final W5 proof artifact. **Do not** mark W5 accepted from the earlier partial proof.
