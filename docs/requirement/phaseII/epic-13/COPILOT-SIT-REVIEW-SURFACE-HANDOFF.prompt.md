# Copilot Handoff — Recover SIT Review Surface For W4 UX Approval

## Context

We cannot complete the 5 UX freeze approvals for W4 until the live SIT review surface is reachable.

Current verified state:

- SIT health is up with Basic Auth:
  - `GET https://sit.yahwan.biz/api/health` -> `200` with auth
  - `GET https://sit.yahwan.biz/api/health/ready` -> `200` with auth
- The current repo contract for the review surface is:
  - `GET /phase2` -> review index
  - `GET /phase2/timeline` -> Phase II timeline
  - `GET /phase2/prototype` -> production-facing main UX/UI review page
  - `GET /prototype` -> redirect alias to `/phase2/prototype`
  - `GET /workflow-demo` -> legacy internal workflow demo

This means runtime/services are green enough, but Copilot must verify that SIT serves the current review-surface contract above from the intended deployment artifact.

## Important routing decision

Use the **SIT control-plane workflow**, not the PoC workflow:

- Correct workflow: `D:\01_gitrepo\Openclaw\.github\workflows\deploy-ai-accounting-copilot-sit.yml`
- Do **not** treat `D:\01_gitrepo\Openclaw\.github\workflows\deploy-ai-accounting-copilot-poc.yml` as the primary target for this SIT fix unless you find hard evidence that SIT traffic is incorrectly pointing to a PoC deployment path.

## Why this is Copilot lane

This task touches:

- Openclaw control-plane workflow
- SIT deployment/runtime verification
- review-surface routing on the deployed environment
- possible branch/ref mismatch in deployed artifact
- possible Nginx/site wiring mismatch on the SIT host

That is infra/deploy/runtime work, so it belongs to Copilot.

## Goal

Make SIT usable for W4 product-owner review by serving the current expected review routes:

- `/phase2`
- `/phase2/prototype`
- `/prototype` -> redirect alias to `/phase2/prototype`

while keeping:

- `/api/health`
- `/api/health/ready`
- Basic Auth edge protection

working.

## Repo evidence to trust

Interface mapping to avoid deploying or validating the wrong surface:

- `src/frontend/ux-ui-prototype.html`
  - role: legacy internal workflow demo
  - expected route: `/workflow-demo`
  - do not use as primary W4 acceptance proof
- `docs/requirement/phaseII/PHASE-II-PROTOTYPE.html`
  - role: requirement/reference prototype
  - expected environment: local/doc review only
  - do not treat as deployed runtime surface
- `src/frontend/main-ux-ui.html`
  - role: production-facing review UI
  - expected routes: `/phase2/prototype` and `/prototype` redirect target
  - this is the file Copilot should protect for SIT review-surface validation
- `src/frontend/index.html`
  - role: static entry/fallback copy
  - expected environment: local/static frontend contexts
  - keep aligned, but do not use it alone as proof that SIT runtime routing is correct

In the app repo, these routes exist locally in code:

- `src/backend/app/main.py`
  - `/prototype`
  - `/workflow-demo`
  - `/phase2`
  - `/phase2/timeline`
  - `/phase2/prototype`
- `/phase2/prototype` serves `src/frontend/main-ux-ui.html`
- `/workflow-demo` serves legacy `src/frontend/ux-ui-prototype.html`

So this is not a missing-feature problem in the current repo snapshot. It is a deployment/runtime/routing mismatch until proven otherwise.

## Suspected causes to investigate

1. SIT deployed the wrong `app_ref` or an older SHA that predates Phase II review routes
2. SIT host is serving a stale build/worktree
3. Nginx/public edge points to the wrong upstream/site config
4. The workflow deploys backend health successfully but not the frontend/static/review surface expected by `main.py` and `src/frontend/main-ux-ui.html`
5. SIT host is serving a different compose/app root than the current `TARGET_ROOT=/opt/ledgerflow`

## Required files to inspect

### Control plane

- `D:\01_gitrepo\Openclaw\.github\workflows\deploy-ai-accounting-copilot-sit.yml`

### App repo deployment/runtime files

- `src/backend/app/main.py`
- `docker/docker-compose.sit.yml`
- `deploy/sit-site/nginx-sit-yahwan.conf`
- `scripts/deploy/deploy-sit.sh`
- `scripts/deploy/smoke-sit.sh`

### Planning / acceptance context

- `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`
- `docs/requirement/phaseII/W4-EXECUTION-PLAN.md`
- `docs/requirement/phaseII/W4-TASK-BOARD.md`
- `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md`

## What to do

1. Confirm the SIT workflow is deploying the intended branch/ref
2. Confirm the deployed app SHA on SIT and compare it with the expected current branch SHA
3. Verify whether `main.py` on the SIT host contains the `/phase2`, `/phase2/prototype`, `/prototype`, and `/workflow-demo` routes
4. Verify the public edge and upstream mapping for SIT
5. Fix the deployment/workflow/runtime mismatch so the live review routes return the expected live status
6. Re-run the SIT deploy/smoke flow if needed
7. Capture concise proof

## Acceptance criteria

1. `GET https://sit.yahwan.biz/api/health` returns `200` with Basic Auth
2. `GET https://sit.yahwan.biz/api/health/ready` returns `200` with Basic Auth
3. `GET https://sit.yahwan.biz/phase2` returns `200` with Basic Auth
4. `GET https://sit.yahwan.biz/phase2/prototype` returns `200` with Basic Auth
5. `GET https://sit.yahwan.biz/prototype` returns a redirect to `/phase2/prototype` or an equivalent `200` review surface with Basic Auth
6. `/phase2` and `/phase2/prototype` are served from the intended current app deployment, not a stale artifact
7. `/workflow-demo` is either reachable for internal reference or intentionally documented as excluded from SIT
8. Basic Auth remains enabled for SIT
9. Output includes the exact root cause and the exact fix applied

## Output format wanted back

Please return:

1. Root cause
2. Files changed
3. Workflow/runtime actions taken
4. Final route status table for:
   - `/phase2`
   - `/phase2/prototype`
   - `/prototype`
   - `/workflow-demo`
   - `/api/health`
   - `/api/health/ready`
5. Any remaining risk

## Credentials handling

- SIT Basic Auth credentials are operator-supplied out of band
- Do not commit, echo, or store plaintext credentials in repo files, workflow logs, or handoff artifacts
