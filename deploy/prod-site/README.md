# Production Deployment — (Not Yet Implemented)

> This file is a placeholder. The production deploy workflow will be created when MVP is ready.

---

## Planned Setup

| Item | Planned Value |
| --- | --- |
| Branch | `main` |
| Domain | TBD (e.g. `aiaccount.yahwan.biz` or custom client domain) |
| Type | Docker (FastAPI + PostgreSQL) |
| Workflow | `deploy-ai-accounting-copilot-prod.yml` (in Piboonsak/Openclaw) |

## Prerequisites Before Production

- [ ] MVP Phase 2 complete and tested
- [ ] PostgreSQL database provisioned (RDS or VPS-local)
- [ ] Production domain DNS configured
- [ ] SSL certificate provisioned
- [ ] Secrets registered in Openclaw repo settings
- [ ] Production `docker-compose.prod.yml` finalized
- [ ] Backup/restore procedure documented
- [ ] Monitoring/alerting configured

## Deploy Command (Future)

```bash
gh workflow run deploy-ai-accounting-copilot-prod.yml \
  --repo Piboonsak/Openclaw \
  -f app_ref=main \
  -f domain=<PRODUCTION_DOMAIN>
```

## Notes

- Production deployment MUST go through Openclaw Control Plane
- All production deploys require risk assessment in PR body
- HIGH/CRITICAL risk deploys require human approval before merge
