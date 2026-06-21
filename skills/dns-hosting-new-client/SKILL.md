---
name: dns-hosting-new-client
description: Onboard a new customer domain to DNS and hosting — external DNS first, transfer later if needed
scope: infra
version: 1.0.0
---

# DNS Hosting New Client

## When to Use This Skill

Use when onboarding a new client's domain to Hostinger DNS and VPS hosting. Covers DNS setup, SSL issuance, and health verification.

## Step-by-Step Workflows

See sections below: Decision Tree, External Domain Onboarding, SSL and Health.

## Output Checklist

- [ ] DNS records created (A + CAA)
- [ ] Propagation verified on 8.8.8.8 and 1.1.1.1
- [ ] SSL certs issued and auto-renew configured
- [ ] HTTP → HTTPS redirect working
- [ ] /health and /api/health returning 200

## Purpose

Reusable runbook for onboarding a new customer domain to DNS and hosting with minimal risk.
This skill prevents confusion between domain transfer and external DNS onboarding.

## Core Rule

Transfer domain is optional and usually unnecessary for go-live.
Use external-domain DNS onboarding first unless business explicitly requires registrar consolidation.

## Decision Tree

1. If customer already owns a domain and go-live is time-sensitive:
- Keep registrar where it is.
- Update nameservers to DNS provider target.
- Add domain as external domain DNS zone in hosting panel.
- Create required records and verify propagation.

2. If customer has no domain yet:
- Register new domain at preferred registrar (Hostinger is fine for cost).
- Configure DNS and hosting immediately.

3. If customer wants registrar consolidation or lower renewal cost over time:
- Plan domain transfer as a separate activity.
- Confirm 60-day lock, unlock state, and EPP code readiness.

## External Domain Onboarding (Recommended Path)

1. Registrar panel
- Update nameservers to target DNS provider.
- Record timestamp of NS change.

2. Hosting panel
- Add external domain to portfolio.
- Open DNS zone editor for that domain.

3. Apply baseline records
- A demo -> PoC IP (TTL 300)
- A uat -> UAT VPS IP (TTL 300)
- A app -> PROD VPS IP (TTL 300)
- CAA @ -> 0 issue "letsencrypt.org" (TTL 3600)

4. Verify propagation
- Resolve NS on 8.8.8.8 and 1.1.1.1
- Resolve A/CAA on both resolvers
- Continue only when resolvers agree

5. SSL and health
- Issue certbot certs on target hosts
- Verify HTTP -> HTTPS redirect
- Verify /health and /api/health

## Hostinger-Specific Notes

- Domain transfer page and external domain page are different flows.
- 60-day lock applies to transfer only, not external DNS management.
- If API returns Domain not found, external domain was not added to that account yet.

## Troubleshooting Checklist

1. NS changed but DNS writes fail:
- Confirm domain exists in external-domain list in hPanel.
- Wait for resolver convergence if SERVFAIL appears.

2. UI says custom nameservers in registrar DNS page:
- Expected behavior.
- Record edits must happen in the nameserver target provider, not registrar UI.

3. API can write another domain but not target domain:
- Account scope mismatch or missing external-domain onboarding.

## Deliverables Per Client

- DNS ownership map (registrar, nameservers, zone owner)
- Record set with TTL policy
- Verification evidence (resolver outputs)
- SSL issuance evidence
- Rollback plan (TTL 300 and previous values)

## Quick Commands

```bash
# Nameserver checks
nslookup -type=ns example.com 8.8.8.8
nslookup -type=ns example.com 1.1.1.1

# Record checks
dig @1.1.1.1 app.example.com +short
dig @8.8.8.8 app.example.com +short
dig +short CAA example.com

# HTTPS checks
curl -I https://app.example.com/health
curl -I https://uat.example.com/health
```

## Anti-Pattern To Avoid

Do not start from transfer-domain flow when the goal is immediate DNS control.
It adds lock-policy dependencies and delays delivery.
