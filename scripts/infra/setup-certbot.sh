#!/usr/bin/env bash
# setup-certbot.sh — Idempotent SSL certificate setup for LedgerFlow
# TASK-1304: DNS delegation + Certbot SSL
#
# Usage (from laptop):
#   # UAT
#   ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.74.232 \
#     'DOMAIN=uat.bwcacc.biz bash -s' < scripts/infra/setup-certbot.sh
#
#   # PROD
#   ssh -i ~/.ssh/id_ed25519_hostinger root@72.62.247.9 \
#     'DOMAIN=app.bwcacc.biz bash -s' < scripts/infra/setup-certbot.sh
#
# Idempotent: safe to re-run — skips already-completed steps.
# Uses --standalone mode (no nginx dependency).

set -euo pipefail

# ── Config ────────────────────────────────────────────────
DOMAIN="${DOMAIN:?'DOMAIN env var required (e.g. uat.bwcacc.biz)'}"
EMAIL="${EMAIL:-admin@yahwan.biz}"
LOG_PREFIX="[setup-certbot]"

log()  { echo "$LOG_PREFIX $*"; }
ok()   { echo "$LOG_PREFIX ✅ $*"; }
skip() { echo "$LOG_PREFIX ⏭️  $* (already done)"; }

log "Starting SSL setup on $(hostname) for $DOMAIN — $(date -Iseconds)"

# ── 1. Install certbot ───────────────────────────────────
log "1/4 Install certbot"
if command -v certbot &>/dev/null; then
    skip "certbot already installed: $(certbot --version 2>&1)"
else
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq certbot
    ok "certbot installed: $(certbot --version 2>&1)"
fi

# ── 2. Issue certificate ─────────────────────────────────
log "2/4 Issue certificate for $DOMAIN"
CERT_DIR="/etc/letsencrypt/live/$DOMAIN"
if [ -d "$CERT_DIR" ] && [ -f "$CERT_DIR/fullchain.pem" ]; then
    skip "Certificate exists: $CERT_DIR"
    openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -subject -enddate 2>/dev/null || true
else
    # Standalone mode: certbot starts its own HTTP server on port 80
    # Port 80 must be free (no nginx/apache running)
    certbot certonly --standalone \
        --cert-name "$DOMAIN" \
        -d "$DOMAIN" \
        --non-interactive \
        --agree-tos \
        -m "$EMAIL" \
        --no-eff-email
    ok "Certificate issued for $DOMAIN"
fi

# ── 3. Verify certificate ────────────────────────────────
log "3/4 Verify certificate"
if [ -f "$CERT_DIR/fullchain.pem" ]; then
    EXPIRY=$(openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -enddate | cut -d= -f2)
    SUBJECT=$(openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -subject | sed 's/.*CN = //')
    ok "Certificate valid: CN=$SUBJECT, expires=$EXPIRY"
else
    echo "$LOG_PREFIX ❌ Certificate file not found at $CERT_DIR/fullchain.pem"
    exit 1
fi

# ── 4. Auto-renew setup ──────────────────────────────────
log "4/4 Auto-renew configuration"

# certbot installs a systemd timer by default on Ubuntu 24.04
if systemctl is-enabled certbot.timer &>/dev/null; then
    skip "certbot.timer already enabled"
    systemctl status certbot.timer --no-pager 2>/dev/null | head -5 || true
else
    systemctl enable certbot.timer
    systemctl start certbot.timer
    ok "certbot.timer enabled"
fi

# Test auto-renew (dry-run)
log "Running renew dry-run..."
certbot renew --dry-run 2>&1 | tail -3
ok "Auto-renew dry-run passed"

# ── Summary ──────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  SSL Setup Complete — $(hostname)"
echo "════════════════════════════════════════════════════════"
echo "  Domain:     $DOMAIN"
echo "  Cert:       $CERT_DIR/fullchain.pem"
echo "  Key:        $CERT_DIR/privkey.pem"
echo "  Expires:    $EXPIRY"
echo "  Auto-renew: $(systemctl is-enabled certbot.timer 2>/dev/null || echo 'manual')"
echo "════════════════════════════════════════════════════════"
echo ""
echo "Docker nginx mount (for docker-compose.yml):"
echo "  volumes:"
echo "    - /etc/letsencrypt:/etc/letsencrypt:ro"
echo ""
