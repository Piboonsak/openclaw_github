# W5-CLAUDE-OCR-PENDING-STALL-FIX-08 — Completion Report

## Doc ID
- **Task:** `docs/requirement/phaseII/W5-CLAUDE-OCR-PENDING-STALL-FIX-08.prompt.json`
- **Tracking tag:** `W5-CLAUDE-OCR-PENDING-STALL-FIX-08`. **Branch:** `dev`.
- **Bug:** HR-07-02B (P0) — uploads succeed, `POST /api/v1/tasks/process-document/{id}` returns task ids, but `GET /api/v1/tasks/{task_id}` stays `pending` with empty stage for 8+ minutes (0 succeeded / 0 failed).

## Commit SHA
- Single commit on `dev` carrying the patch + tests + this report. Resolve: `git log --grep W5-CLAUDE-OCR-PENDING-STALL-FIX-08 -1 --format=%H`.

## Root cause
**Honest finding: the pending-stall could not be reproduced from a repo-code defect. Task registration and the Celery broker/result-backend configuration are functionally correct in the repo; the evidence points at a runtime condition — the celery-worker not consuming the queue on SIT — which Copilot must confirm/fix at the runtime layer.** What was verified and ruled out:

- **Task registration works.** The Codex hypothesis was "task registration / worker binding". Booting the real worker exactly as compose does (`python -m celery -A src.backend.workers.celery_app:celery_app worker`) prints a `[tasks]` banner listing **both** `src.backend.workers.tasks.process_document` and `...extract_coa_pdf`. Stashing the fix and re-running the worker's real registration path (`celery_app.loader.import_default_modules()`) still registered them via `autodiscover_tasks`. So the worker does NOT boot with the task unregistered.
- **Broker / result-backend are consistent.** Both the API and the celery-worker import the same `celery_app.py` and share the same `.env.sit`, so they resolve to the same broker and the same result backend — there is no API-writes-here / worker-reads-there mismatch achievable from the repo config.
- **Image / worker command are correct.** `docker/Dockerfile.backend` (`sit` target) installs requirements and copies the code; the compose `celery-worker` command is a valid worker invocation with `depends_on: redis+postgres healthy`.

Because a task that stayed `pending` with an empty stage for 8 minutes never emitted the `queued` state that `process_document` reports at its top (and `task_track_started=True` would move it to STARTED), the task body never ran — i.e. **no worker consumed the message**, which is a runtime symptom (worker down / crash-looping / broker not reachable from the worker), not a reproducible repo bug.

Two genuine repo-side latent gaps were found and closed so they can never contribute to this class of stall, plus a diagnostic was added to make the actual cause observable instead of a silent forever-`pending`.

## Files changed
- `src/backend/workers/celery_app.py` — add `include=["src.backend.workers.tasks"]`.
- `config/settings.py` — read `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` / `CELERY_TASK_ALWAYS_EAGER` from env.
- `src/backend/app/endpoints.py` — new `GET /api/v1/tasks/diagnostics`.
- `tests/workers/test_celery_registration.py` (new), `tests/api/test_task_diagnostics.py` (new).

## How the pending-stall was addressed
1. **Deterministic task registration (hardening).** `celery_app.py` now passes `include=["src.backend.workers.tasks"]` to `Celery(...)`. The worker is launched with `-A ...celery_app:celery_app`, which imports the app module but not `tasks.py`; registration relied solely on `autodiscover_tasks`. `include` makes Celery import the tasks module deterministically at worker startup — the canonical, reliable registration path — permanently removing "unregistered task → message silently discarded → AsyncResult PENDING forever" as a possible cause.
2. **Honour the Celery env config (real correctness bug).** `.env.sit` sets `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` (a separate result DB) and `CELERY_TASK_ALWAYS_EAGER`, but `settings.py` never read them — so `celery_app.py`'s `getattr(settings, "CELERY_BROKER_URL", ...)` always fell back to `REDIS_URL`, silently ignoring the configured result backend. `settings.py` now reads them explicitly so the API and worker honour the same configured broker/backend from env.
3. **Make the stall diagnosable (surface real evidence instead of silent pending).** New `GET /api/v1/tasks/diagnostics` pings the workers via the Celery control channel and returns `broker_reachable`, `worker_count`, `workers`, and `process_document_registered`. `worker_count == 0` / `broker_reachable == False` is the exact fingerprint of "no worker consuming the queue" — so the Processing screen and SIT proof can tell a downed/miswired worker apart from a task that is merely queued, instead of showing permanent `pending`.

## Evidence that the task lifecycle is observable in local/repro coverage
- Real worker boot registers the tasks (banner shows `process_document` + `extract_coa_pdf`); only the broker connection fails against a non-existent local Redis (expected).
- `GET /api/v1/tasks/diagnostics` against a down broker returns `{"broker_reachable": false, "worker_count": 0, ...}` in ~4s (bounded, never hangs) — the explicit "no worker" signal.
- The HR-07 stage-evidence path (queued/ocr/extract/mapping + elapsed + failed_stage) from commit 2921068 is unchanged and still passes.

## Tests run
- `python -m pytest tests/workers/test_celery_registration.py tests/api/test_task_diagnostics.py tests/workers/test_tasks.py tests/test_pipeline_stage_timeouts.py -q` → **22 passed**.
- New coverage:
  - `test_celery_registration.py::test_worker_boot_registers_tasks_in_isolation` — a fresh subprocess importing ONLY the app module (as the worker does) must end with the tasks registered; this fails on an empty-`include` build that also lacks working autodiscover.
  - `::test_celery_app_includes_tasks_module` — asserts the `include` wiring directly.
  - `::test_settings_honours_celery_env_vars` — settings now reads `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`.
  - `test_task_diagnostics.py` — live workers reported; broker-down flags `worker_count == 0` / `broker_reachable == False`; zero-worker-but-broker-up case; eager short-circuit.
- App import OK; HR-07 timeout/stage-evidence patch (commit 2921068) preserved.

## Residual deploy/runtime proof needed from Copilot
The most likely cause is a runtime worker condition that cannot be reproduced from repo code. On the next SIT deploy, Copilot must:
1. Redeploy `dev` via Openclaw, then hit `GET /api/v1/tasks/diagnostics` with a bearer token. If `worker_count == 0`, the celery-worker is not consuming — inspect `docker compose -f docker/docker-compose.sit.yml ps celery-worker` and `logs celery-worker` for boot errors / broker-connection failures / crash-loop.
2. Confirm the `celery-worker` container is Up (not restarting) and its log shows the `[tasks]` banner + `celery@... ready` + task receipt.
3. Confirm the worker and backend containers share the broker: `.env.sit` `CELERY_BROKER_URL` reachable from the worker container (`redis://redis:6379/0`).
4. Re-run the HR-07-02B probe and confirm tasks leave `pending` and show stage progress (queued → ocr → extract → mapping → review_scan) or explicit failure.

## Next handoff
- Claude does not deploy. After merge, Copilot uses `W5-COPILOT-EXPORT-NORMALIZE-OCR-PROOF-11` to redeploy and prove OCR processing + export normalization on SIT, using the new `/api/v1/tasks/diagnostics` endpoint to pinpoint worker liveness.
- If SIT diagnostics show workers ARE up and consuming yet tasks still stall, hand back a new prompt with the worker logs so the investigation can move to the actual runtime evidence (which was not available in this repo-lane pass).
