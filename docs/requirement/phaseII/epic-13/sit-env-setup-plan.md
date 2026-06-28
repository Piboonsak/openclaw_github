# SIT Environment Setup Plan

> **Epic**: 13 — Infrastructure + Deployment
> **Purpose**: Primary execution document for `dev -> SIT` environment readiness
> **Status**: Gate passed
> **Last updated**: 2026-06-29

---

## 1. Scope

This document is the source of truth for preparing and operating the SIT environment at `sit.yahwan.biz`.

Included:

- DNS and public resolution requirements
- TLS/certificate requirements
- Network and firewall requirements
- Reverse proxy / Basic Auth / noindex edge rules
- Secret reuse vs new secret creation policy
- Control-plane workflow prerequisites
- SIT smoke / readiness / evidence gates
- Current blockers and exit criteria

Excluded:

- Application feature refactors unrelated to SIT infra readiness
- UAT/PROD deployment steps already documented elsewhere, except where they define the SIT baseline pattern

---

## 2. Baseline Reference

SIT must follow the same proven infrastructure control pattern already used by UAT/PROD:

1. VPS reachable by SSH with hardened baseline
2. DNS resolves from public resolvers before runtime checks begin
3. TLS certificate matches target hostname
4. Only edge ports are public
5. Runtime dependencies stay internal to Docker network
6. Deploy orchestration is dispatched from Openclaw control plane

Reference documents:

- [INFRA-PREREQUISITES-RUNBOOK.md](INFRA-PREREQUISITES-RUNBOOK.md)
- [pipeline-design.md](../../../cicd/pipeline-design.md)
- [sit-runtime-evidence-checklist.md](../../../cicd/sit-runtime-evidence-checklist.md)
- [SECRETS-CHECKLIST.md](../../../CICD/SECRETS-CHECKLIST.md)

---

## 3. SIT Target Mapping

| Item | Value |
| --- | --- |
| Branch gate | `dev` |
| SIT hostname | `sit.yahwan.biz` |
| SIT target host | `76.13.210.250` |
| Runtime location | `/opt/ledgerflow` |
| Canonical dispatch repo | `Piboonsak/Openclaw` |
| Canonical dispatch workflow | `deploy-ai-accounting-copilot-sit.yml` |

## 3.1 Latest green evidence

| Item | Value |
| --- | --- |
| Final green run | `Piboonsak/Openclaw` Actions run `28332426427` |
| Final conclusion | `success` |
| Evidence artifact | `aiacc-sit-evidence-<run_number>` from run `28332426427` |
| Gate outcome | `dev -> uat` promotion gate satisfied |

Branch flow remains:

`feature/* -> dev -> uat -> main`

Promotion rule:

`CI pass -> SIT deploy pass -> SIT smoke pass -> SIT feature/runtime evidence pass -> UAT allowed`

---

## 4. Required Controls

### 4.1 DNS

Required condition:

- `sit.yahwan.biz` must resolve publicly to `76.13.210.250`
- verify against authoritative/public resolvers before smoke execution

Required verification:

```powershell
Resolve-DnsName sit.yahwan.biz -Type A -Server 8.8.8.8
Resolve-DnsName sit.yahwan.biz -Type A -Server 1.1.1.1
nslookup sit.yahwan.biz 8.8.8.8
nslookup sit.yahwan.biz 1.1.1.1
```

Exit criteria:

- both public resolvers return `76.13.210.250`

### 4.2 TLS / Certificate

Required condition:

- valid certificate for `sit.yahwan.biz`
- no hostname mismatch
- renewal path documented

Required verification:

```bash
curl -I https://sit.yahwan.biz
openssl s_client -connect sit.yahwan.biz:443 -servername sit.yahwan.biz
```

Exit criteria:

- HTTPS handshake succeeds
- certificate CN/SAN includes `sit.yahwan.biz`

### 4.3 Network / Firewall

Required condition:

- public exposure limited to 80/443 when edge is enabled
- `5432`, `6379`, `9000`, `9001` not publicly reachable

Required verification:

```bash
ssh <deploy-user>@76.13.210.250 "ss -ltnp | grep -E ':(5432|6379|9000|9001)\\b' || true"
curl -I https://sit.yahwan.biz
```

Exit criteria:

- `80/443` open only if intended
- internal service ports closed or filtered externally

### 4.4 Edge Security

Required condition:

- Basic Auth required for SIT edge access
- `X-Robots-Tag: noindex` enabled
- unauthorized request receives `401`

Required verification:

```bash
curl -I https://sit.yahwan.biz/api/health
curl -I -u "$USER:$PASS" https://sit.yahwan.biz/api/health
```

Exit criteria:

- unauthenticated response is `401`
- authenticated response reaches application

---

## 5. Secret Strategy

### 5.1 Reuse from Openclaw

These may be reused from Openclaw when already present and valid:

| Secret | Purpose | Source |
| --- | --- | --- |
| `BWCACC_VPS_SSH_KEY` | SSH access from workflow to VPS | Openclaw Actions secrets |
| `BWCACC_DEPLOY_USER` | remote deploy user | Openclaw Actions secrets |
| `BWCACC_LINE_CHANNEL_ACCESS_TOKEN` | deploy notification | Openclaw Actions secrets |
| `BWCACC_LINE_USER_ID` | deploy notification target | Openclaw Actions secrets |
| `OPENROUTER_API_KEY` | backend runtime LLM access | Openclaw Actions secrets |
| `OPENAI_API_KEY` | backend runtime LLM access | Openclaw Actions secrets |

### 5.2 Must Exist for SIT Specifically

These are required for SIT execution and must be created if missing:

| Secret | Purpose | Reuse allowed |
| --- | --- | --- |
| `BWCACC_SIT_HOST` | SIT target host/IP | yes if already defined correctly |
| `BWCACC_SIT_BASIC_AUTH_USER` | SIT Basic Auth username | yes if policy-approved |
| `BWCACC_SIT_BASIC_AUTH_PASS` | SIT Basic Auth password | yes if policy-approved |

### 5.3 Must Remain Environment-Local

These must not be committed and should stay in VPS-side `.env.sit` or equivalent runtime secret source:

- application secret keys
- database password / connection string
- MinIO root/user secrets
- LLM provider runtime keys only if not centrally managed by the control-plane workflow

Rule:

- if a required SIT runtime secret cannot be reused safely from Openclaw, create a new SIT-specific secret and raise it explicitly before deploy

---

## 6. Execution Order

1. Confirm VPS baseline and SSH access
2. Confirm/create DNS record for `sit.yahwan.biz`
3. Confirm TLS certificate for `sit.yahwan.biz`
4. Confirm firewall and public port policy
5. Confirm Openclaw secrets coverage
6. Provision `.htpasswd` for SIT edge auth
7. Run control-plane SIT workflow dispatch
8. Verify deploy, smoke, readiness, and runtime evidence
9. Attach evidence before allowing `dev -> uat`

---

## 7. Evidence Gate

Required proof before UAT promotion:

1. SIT deploy log
2. migration success proof
3. seed success proof
4. `/api/health` = 200
5. `/api/health/ready` = 200
6. PostgreSQL / Redis / MinIO runtime proof
7. Celery ping proof
8. DB write/read proof from same SIT run
9. Redis cache activity proof
10. MinIO object write/read proof
11. unauthorized Basic Auth challenge proof
12. public port exposure proof
13. Openclaw workflow run URL

Reference checklist:

- [sit-runtime-evidence-checklist.md](../../../cicd/sit-runtime-evidence-checklist.md)

---

## 8. Gate outcome and resolved blockers

| Item | Resolution | Outcome |
| --- | --- | --- |
| DNS for `sit.yahwan.biz` | validated during SIT rollout | resolved |
| SIT certificate state | HTTPS gate and smoke path passed on final run | resolved |
| SIT Openclaw secrets coverage | workflow now injects required runtime keys and auth values | resolved |
| readiness `503` | fixed by env/key injection and MinIO endpoint correction | resolved |
| intermittent SSH preflight timeout | fixed by environment user correction + bounded SSH retry | resolved |
| network evidence tool mismatch | fixed by replacing runner `nmap` usage with host-side `ss` probe | resolved |

No active SIT blockers remain for `dev -> uat` promotion.

## 9. Lessons learned from SIT rollout

1. A green local/manual SSH path does not guarantee GitHub runner reachability. Control-plane workflows must treat SSH as retryable infrastructure, not as a single-shot assumption.
2. Runtime secrets used by backend readiness must be injected on the actual deploy path. A correct `.env.example` is not enough if the live workflow never writes the values.
3. URL-shaped configuration matters at runtime. For MinIO/storage settings, `http://minio:9000` is valid while `minio:9000` breaks backend dependency initialization.
4. Evidence steps are part of the gate, not optional reporting. If evidence commands are brittle, the environment still fails promotion even when the app is healthy.

## 10. UAT/PROD prevention checklist

Before first UAT and PROD rollout using the same control-plane pattern:

1. Assert deploy user, host, and SSH key path explicitly per environment; do not inherit SIT assumptions blindly.
2. Validate runtime LLM/storage/auth env coverage before deploy by checking the control-plane workflow inputs/secrets map, not just repo templates.
3. Validate container healthchecks against the actual image contents; avoid `wget`/`curl` assumptions unless the image guarantees them.
4. Validate endpoint variables in example env files and rewritten env files use the exact format expected by backend code.
5. Keep evidence probes minimal and portable: prefer SSH + `ss`, `curl`, and `docker compose exec` over extra runner packages.
6. Treat `/api/health/ready` as the promotion authority; if it returns `503`, block promotion and capture backend/dependency diagnostics immediately.

---

## 11. Decision Rules

1. Do not treat SIT as optional if `dev -> uat` promotion depends on it.
2. Do not run smoke against public SIT URL until DNS and TLS are verified.
3. Do not assume secrets can be reused; document each reuse explicitly.
4. Raise missing runtime secrets instead of hardcoding placeholder values into committed files.

---

## 12. Follow-on Document Changes

The following documents should reference this file as the SIT execution plan:

- [EPIC-13-TASKS-DETAIL.md](EPIC-13-TASKS-DETAIL.md)
- [INFRA-PREREQUISITES-RUNBOOK.md](INFRA-PREREQUISITES-RUNBOOK.md)
- [SECRETS-CHECKLIST.md](../../../CICD/SECRETS-CHECKLIST.md)
