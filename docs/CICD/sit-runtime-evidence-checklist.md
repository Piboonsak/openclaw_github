# SIT Runtime Evidence Checklist (TASK-1306A)

Use this checklist before opening/merging the TASK-1306A PR.

## Control-plane compliance

- Canonical deploy dispatch path: `Piboonsak/Openclaw/.github/workflows/deploy-openclaw-github-private-secrets.yml`
- Execution-plane workflow in this repo is mirror/break-glass only.
- Attach Openclaw run URL that performed SIT/UAT gate dispatch.

## Branch and environment mapping

- Branch flow: `feature/* -> dev -> uat -> main`
- SIT gate target: `sit.yahwan.biz` (`76.13.210.250`)
- UAT target: `uat.bwcacc.biz` (`72.62.74.232`)
- PROD target: `app.bwcacc.biz` (`72.62.247.9`)

## Required runtime proof

1. SIT deploy real run log

- Command: `bash scripts/deploy/deploy-sit.sh`
- Evidence: migration success + seed success in output.

1. SIT smoke real run log

- Command: `bash scripts/deploy/smoke-sit.sh`
- Evidence: all 7 checks passed.

1. SIT feature-flow real run evidence

- Run at least one core feature flow end-to-end via UI/API on SIT
- Evidence: PostgreSQL write/read proof from same test run
- Evidence: Redis cache hit/update proof from request path
- Evidence: MinIO object write/read proof for upload/export artifact

1. Basic Auth proof

- Command: `curl -I https://sit.yahwan.biz/api/health`
- Expected: `401 Unauthorized` without credentials.

1. Closed service ports proof (external check)

- Expected closed externally: `5432`, `6379`, `9000`, `9001`
- Suggested command: `nmap -Pn sit.yahwan.biz -p 5432,6379,9000,9001`
- Evidence: all listed ports are filtered/closed.

## PR scope guard (TASK-1306A)

Allowed areas:

- `docker/**`
- `scripts/deploy/**`
- `scripts/seed_sit.py`
- `samples/sit/**`
- `docs/cicd/**`
- `docs/requirement/phaseII/epic-13/**`
- `.github/workflows/bwcacc-deploy-uat.yml` (mirror compliance notes only)

Do not include unrelated W3 template/UX/docs or app logic formatting changes.
