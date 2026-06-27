# Secrets required in Piboonsak/Openclaw repo

Go to: github.com/Piboonsak/Openclaw -> Settings -> Secrets -> Actions

- [ ] BWCACC_UAT_HOST = 72.62.74.232
- [ ] BWCACC_PROD_HOST = 72.62.247.9
- [ ] BWCACC_DEPLOY_USER = deploy
- [ ] BWCACC_VPS_SSH_KEY = (private key: ~/.ssh/id_ed25519_hostinger)
- [ ] BWCACC_LINE_CHANNEL_ACCESS_TOKEN = (copy from YAHWAN-SHOP secrets)
- [ ] BWCACC_LINE_USER_ID = (copy from YAHWAN-SHOP secrets)

Note: OPENROUTER_API_KEY and ANTHROPIC_API_KEY already exist in Openclaw.

## Verification commands (run after setting secrets)

gh secret list -R Piboonsak/Openclaw | grep BWCACC

## After Openclaw deploy confirmed working

- [ ] Remove BWCACC_* secrets from YAHWAN-SHOP/ai-accounting-copilot (if they exist)
- [ ] Verify: gh secret list -R YAHWAN-SHOP/ai-accounting-copilot shows no SSH_KEY or VPS_HOST
