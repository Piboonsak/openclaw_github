# W5-CLAUDE-TASK-DIAGNOSTICS-ROUTE-SHADOW-FIX-09 — Completion Report

## Doc ID
- **Task:** `docs/requirement/phaseII/W5-CLAUDE-TASK-DIAGNOSTICS-ROUTE-SHADOW-FIX-09.prompt.json`
- **Tracking tag:** `W5-CLAUDE-TASK-DIAGNOSTICS-ROUTE-SHADOW-FIX-09`. **Branch:** `dev`.
- **Bug:** HR-07-02C (P1 proof-lane blocker) — `GET /api/v1/tasks/diagnostics` returned the generic task-status payload (`{task_id:"diagnostics", status:"pending", ...}`) instead of the diagnostics object, failing Gate 12 even though the celery-worker was up and consuming.

## Commit SHA
- Single commit on `dev` carrying the patch + tests + this report. Resolve: `git log --grep W5-CLAUDE-TASK-DIAGNOSTICS-ROUTE-SHADOW-FIX-09 -1 --format=%H`.

## Root cause
FastAPI matches routes in **declaration order**. The diagnostics endpoint added in fix 08 (`GET /v1/tasks/diagnostics`) was declared **after** the dynamic `GET /v1/tasks/{task_id}` route, so a request to `/v1/tasks/diagnostics` was captured by `{task_id}` as `task_id="diagnostics"` and served by `get_task_status` — returning `{"task_id":"diagnostics","status":"pending","stage":null,"result":null}` instead of the diagnostics object. This was a pure route-ordering bug; the Celery worker/runtime (confirmed up + registered + ready by Copilot Gate 12) was never the problem here.

Reproduced deterministically: with the pre-fix order (`{task_id}` first), `GET /v1/tasks/diagnostics` → `{'task_id': 'diagnostics', 'status': 'pending', 'stage': None, 'result': None}` (shadowed). With the fix, the same request returns the diagnostics object.

## Files changed
- `src/backend/app/endpoints.py` — moved `get_task_diagnostics` (`/v1/tasks/diagnostics`) to be declared **before** `get_task_status` (`/v1/tasks/{task_id}`), with a guard comment against re-reordering.
- `tests/api/test_task_diagnostics.py` — added routing-level regression tests (via `TestClient` over the real router) that exercise route matching, not just the handler function.

## Route fix implemented
- The static `/v1/tasks/diagnostics` route is now declared immediately before the dynamic `/v1/tasks/{task_id}` route in `endpoints.py`, so FastAPI matches the literal path first. Verified against the assembled app: route order is `['/api/v1/tasks/diagnostics', '/api/v1/tasks/{task_id}', '/api/v1/tasks/process-document/{document_id}']` — diagnostics precedes `{task_id}`.
- A comment on the diagnostics route documents the ordering requirement so it is not accidentally moved back.
- The diagnostics response shape from fix 08 (`eager`, `process_document_registered`, `broker_reachable`, `worker_count`, `workers`) is unchanged. The task-status endpoint is unchanged for real task ids.

## Tests run
- `python -m pytest tests/api/test_task_diagnostics.py -q` → **6 passed**.
- The prior fix-08 tests called the handler function directly (bypassing routing), so they did NOT catch the shadow. New routing-level tests close that gap:
  - `test_diagnostics_route_is_not_shadowed_by_task_id` — `GET /v1/tasks/diagnostics` returns the diagnostics object (`worker_count`/`broker_reachable`/`workers`), NOT the `{task_id:"diagnostics", stage:...}` task-status payload. This assertion FAILS on the pre-fix declaration order (demonstrated: pre-fix returns `{'task_id':'diagnostics','status':'pending',...}`).
  - `test_real_task_id_still_resolves_to_task_status` — `GET /v1/tasks/{uuid}` still returns exactly `{task_id, status, stage, result}` with no diagnostics keys (no regression).
- Full app import OK; assembled-app route order verified.

## Next handoff
- Claude does not deploy. After merge, **Copilot must rerun `W5-COPILOT-SIT-DIAGNOSTICS-GATE-12`** and confirm `GET /api/v1/tasks/diagnostics` returns the diagnostics object with `worker_count >= 1` on SIT.
- Only if Gate 12 passes should Copilot proceed to `W5-COPILOT-OCR-LIVE-PROOF-13` and `W5-COPILOT-EXPORT-NORMALIZE-LIVE-PROOF-14`.
