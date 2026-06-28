# Production Deployment Safety Rules

> **TASK-1305** | Created: 2026-06-21 | Owner: DevOps
> **Applies to**: All deployments to `app.bwcacc.biz` (PROD VPS `72.62.247.9`)

---

## Non-Negotiable Rules

### 1. UAT First — Always

No code reaches PROD without passing through UAT first.

- Branch flow enforces this: `feature/* → dev → uat → main`
- Environment mapping:
  - `dev` promotion gate: SIT VPS `76.13.210.250` (`sit.yahwan.biz`)
  - `uat`: UAT VPS `72.62.74.232` (`uat.bwcacc.biz`)
  - `main`: PROD VPS `72.62.247.9` (`app.bwcacc.biz`)
- SIT (`sit.yahwan.biz`) must pass deploy + smoke checks before UAT is considered safe
- PRs to `main` can only come from `uat` branch
- If a hotfix bypasses UAT, it must be backported to `uat` within 24 hours

### 1.1 SIT Promotion Gate (TASK-1306A)

SIT gate must be green before UAT promotion:

1. SIT runtime deployed with real services (PostgreSQL, Redis, MinIO, Celery, Alembic)

1. SIT smoke checks pass: `/api/health`, `/api/health/ready`, DB, Redis, storage, Celery

1. SIT feature-flow test passes on real runtime (not dry run): execute core UI/API feature actions end-to-end, verify data write/read in PostgreSQL, verify Redis cache hit/update in request path, and verify MinIO object write/read for real artifacts

1. SIT remains internal-only (Basic Auth enabled, noindex header, only 80/443 exposed)

Promotion chain:

`CI pass -> SIT deploy pass -> SIT smoke pass -> SIT feature pass -> UAT deploy allowed -> PROD deploy allowed`

### 2. DB Snapshot Before Every Migration

Every PROD deploy runs `pg_dump` **before** `alembic upgrade head`.

```bash
docker exec postgres pg_dump -U ledgerflow ledgerflow_prod \
  | gzip > /backup/db/pre-deploy-$(date +%Y%m%d_%H%M%S).sql.gz
```

- Snapshot must complete successfully before migration starts
- Deploy workflow aborts if snapshot fails
- Retained minimum 7 days

### 3. No Force Push to main

Branch protection rule: force push disabled on `main`.

- Revert commits forward (create revert commit), don't rewrite history
- If history is corrupted, escalate to DevOps Lead

### 4. Manual Approval Required

GitHub environment `production` requires 1 reviewer approval.

- Reviewer must verify UAT testing is complete
- Reviewer must check the PR diff (especially migrations)
- Approval expires after 24 hours — re-approval needed if not deployed

### 5. Health Check is the Deploy Gate

Deploy is only successful if `/api/health` returns `200` within 60 seconds.

- If health check fails → automatic rollback
- If health check times out → manual investigation required
- Never mark a deploy "successful" without a passing health check

---

## Migration Safety

### Destructive Migration Checklist

Before merging any migration that drops columns, tables, or changes types:

- [ ] Is this migration reversible? (has `downgrade()` function)
- [ ] Has it been tested on UAT with production-like data volume?
- [ ] Is there a pre-deploy snapshot strategy?
- [ ] Can the old code still work if we rollback code but not the migration?
- [ ] Have you documented the rollback procedure for this specific migration?

### Multi-Step Migrations

For breaking schema changes, use the expand-contract pattern:

1. **Deploy 1**: Add new column (nullable), deploy code that writes to both
2. **Deploy 2**: Backfill data, deploy code that reads from new column
3. **Deploy 3**: Drop old column

---

## Rollback Decision Tree

```
Deploy failed?
    │
    ├── Health check failed immediately?
    │       → Auto-rollback (workflow handles it)
    │
    ├── Works initially, fails after minutes/hours?
    │       → Manual rollback:
    │       → 1. docker compose down
    │       → 2. git checkout <previous-commit>
    │       → 3. Restore DB if migration ran
    │       → 4. docker compose up -d
    │
    └── Data corruption detected?
            → 1. docker compose down
            → 2. Restore from pre-deploy snapshot
            → 3. git checkout <previous-commit>
            → 4. docker compose up -d
            → 5. Page DevOps Lead immediately
```

---

## Emergency Contacts

| Severity | Action | Who |
|----------|--------|-----|
| P1 — Site down | Rollback immediately, notify team | DevOps Lead |
| P2 — Feature broken | Assess impact, rollback if critical | DevOps Lead |
| P3 — Non-critical bug | Fix forward in next deploy | Developer |

---

*Ref: `docs/cicd/pipeline-design.md` for full pipeline design*
