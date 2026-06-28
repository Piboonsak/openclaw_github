# nginx environment configs

This directory keeps one edge config per environment so SIT, UAT, and PROD can stay isolated while still sharing the same reverse-proxy pattern.

| File | Environment | Notes |
| --- | --- | --- |
| `nginx-sit.conf` | SIT | Basic Auth gate, `noindex`, proxies to the SIT runtime stack |
| `nginx-uat.conf` | UAT | Standard UAT reverse proxy |
| `nginx-prod.conf` | Production | Production-hardened reverse proxy |

SIT-specific behavior:

- Hostname: `sit.yahwan.biz`
- TLS termination happens at the edge
- Basic Auth is required before app routes are reachable
- `X-Robots-Tag: noindex, nofollow, noarchive` is sent on the SIT host
- App traffic proxies to the internal `frontend` and `backend` containers on the SIT compose network

Related runtime files:

- `docker/docker-compose.sit.yml`
- `docker/.env.sit.example`
- `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md`
