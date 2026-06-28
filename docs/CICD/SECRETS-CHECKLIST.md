# Secrets required in Piboonsak/Openclaw repo

Go to: github.com/Piboonsak/Openclaw -> Settings -> Secrets -> Actions

This file is the authoritative checklist for deploy/control-plane secrets.
For SIT execution order and blocker context, use:

- `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md`

- [x] BWCACC_UAT_HOST = 72.62.74.232
- [x] BWCACC_PROD_HOST = 72.62.247.9
- [x] BWCACC_SIT_HOST = 76.13.210.250
- [x] BWCACC_DEPLOY_USER = deploy
- [x] BWCACC_VPS_SSH_KEY = (private key: ~/.ssh/id_ed25519_hostinger)
- [x] BWCACC_LINE_CHANNEL_ACCESS_TOKEN = (copy from YAHWAN-SHOP secrets)
- [x] BWCACC_LINE_USER_ID = (copy from YAHWAN-SHOP secrets)
- [x] BWCACC_SIT_BASIC_AUTH_USER = (SIT edge auth user)
- [x] BWCACC_SIT_BASIC_AUTH_PASS = (SIT edge auth password)

Note: OPENROUTER_API_KEY and ANTHROPIC_API_KEY already exist in Openclaw.

SIT-specific planning and reuse/new-secret policy:

- `docs/requirement/phaseII/epic-13/sit-env-setup-plan.md`

## Secret policy by type

### Reuse from Openclaw when already valid

- `BWCACC_VPS_SSH_KEY`
- `BWCACC_DEPLOY_USER`
- `BWCACC_LINE_CHANNEL_ACCESS_TOKEN`
- `BWCACC_LINE_USER_ID`

### Must exist for SIT specifically

- `BWCACC_SIT_HOST`
- `BWCACC_SIT_BASIC_AUTH_USER`
- `BWCACC_SIT_BASIC_AUTH_PASS`

### Must not be committed here

These remain environment-local on the VPS/runtime side:

- app secret keys
- database passwords / connection strings
- MinIO root or access secrets
- runtime LLM provider keys not intentionally centralized

If a required SIT secret cannot be reused safely, create a new SIT-specific secret and raise it explicitly before deploy.

## Verification commands (run after setting secrets)

gh secret list -R Piboonsak/Openclaw | grep BWCACC

## After Openclaw deploy confirmed working

- [x] Remove BWCACC_* secrets from YAHWAN-SHOP/ai-accounting-copilot (if they exist)
- [x] Verify: gh secret list -R YAHWAN-SHOP/ai-accounting-copilot shows no SSH_KEY or VPS_HOST
