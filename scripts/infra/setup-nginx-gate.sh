#!/usr/bin/env bash
# setup-nginx-gate.sh — Deploy minimal nginx for Gate 4/6/7 verification
# Usage: ssh root@<VPS_IP> 'DOMAIN=uat.bwcacc.biz bash -s' < scripts/infra/setup-nginx-gate.sh
# Requires: DOMAIN env var (uat.bwcacc.biz or app.bwcacc.biz)
set -euo pipefail

# ── Validation ───────────────────────────────────────────────
if [[ -z "${DOMAIN:-}" ]]; then
  echo "ERROR: DOMAIN env var required (e.g. DOMAIN=uat.bwcacc.biz)"
  exit 1
fi

CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"
NGINX_CONF_DIR="/opt/ledgerflow/nginx/conf.d"
NGINX_CONTAINER="nginx-gate"

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
fail()  { echo -e "\033[1;31m[FAIL]\033[0m  $*"; exit 1; }

# ── Step 1: Verify prerequisites ─────────────────────────────
info "Step 1/5: Checking prerequisites"

[[ -f "${CERT_DIR}/fullchain.pem" ]] || fail "SSL cert not found: ${CERT_DIR}/fullchain.pem"
[[ -f "${CERT_DIR}/privkey.pem" ]]   || fail "SSL key not found: ${CERT_DIR}/privkey.pem"
docker version &>/dev/null                || fail "Docker not available"
ok "Certs found, Docker ready"

# ── Step 2: Create nginx config ──────────────────────────────
info "Step 2/5: Writing nginx config for ${DOMAIN}"

mkdir -p "${NGINX_CONF_DIR}"

cat > "${NGINX_CONF_DIR}/default.conf" <<NGINX_EOF
# Minimal nginx config for Gate 4/6/7 verification
# Domain: ${DOMAIN}
# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)

# HTTP → HTTPS redirect
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

# HTTPS with SSL termination
server {
    listen 443 ssl;
    server_name ${DOMAIN};

    ssl_certificate     /etc/letsencrypt/live/${DOMAIN}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${DOMAIN}/privkey.pem;

    # SSL hardening
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Static health endpoint (replaced by backend proxy in TASK-1307)
    location /health {
        default_type application/json;
        return 200 '{"status":"healthy","service":"nginx-gate","domain":"${DOMAIN}"}';
    }

    location /api/health {
        default_type application/json;
        return 200 '{"status":"healthy","version":"pre-deploy","services":{"nginx":"running","database":"pending","redis":"pending","minio":"pending"}}';
    }

    # Root — placeholder
    location / {
        default_type text/html;
        return 200 '<html><body><h1>LedgerFlow — ${DOMAIN}</h1><p>Infrastructure gate check passed. Application deploy pending.</p></body></html>';
    }
}
NGINX_EOF

ok "Config written to ${NGINX_CONF_DIR}/default.conf"

# ── Step 3: Stop existing container if running ───────────────
info "Step 3/5: Managing nginx container"

if docker ps -a --format '{{.Names}}' | grep -q "^${NGINX_CONTAINER}$"; then
    warn "Removing existing ${NGINX_CONTAINER} container"
    docker rm -f "${NGINX_CONTAINER}" &>/dev/null || true
fi

# ── Step 4: Start nginx container ────────────────────────────
info "Step 4/5: Starting nginx container"

docker run -d \
    --name "${NGINX_CONTAINER}" \
    --restart unless-stopped \
    -p 80:80 \
    -p 443:443 \
    -v /etc/letsencrypt:/etc/letsencrypt:ro \
    -v "${NGINX_CONF_DIR}":/etc/nginx/conf.d:ro \
    nginx:1.27-alpine

sleep 3

# Verify container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${NGINX_CONTAINER}$"; then
    echo "--- Container logs ---"
    docker logs "${NGINX_CONTAINER}" 2>&1 | tail -20
    fail "nginx container failed to start"
fi

# Verify nginx config
docker exec "${NGINX_CONTAINER}" nginx -t 2>&1
ok "nginx container running, config test passed"

# ── Step 5: Setup certbot renewal hooks ──────────────────────
info "Step 5/5: Configuring certbot renewal hooks"

RENEWAL_CONF="/etc/letsencrypt/renewal/${DOMAIN}.conf"
if [[ -f "${RENEWAL_CONF}" ]]; then
    # Remove existing hook lines if any
    sed -i '/^pre_hook/d' "${RENEWAL_CONF}"
    sed -i '/^post_hook/d' "${RENEWAL_CONF}"

    # Add hooks under [renewalparams] section
    if grep -q '^\[renewalparams\]' "${RENEWAL_CONF}"; then
        sed -i '/^\[renewalparams\]/a pre_hook = docker stop '"${NGINX_CONTAINER}"' || true\npost_hook = docker start '"${NGINX_CONTAINER}"' || true' "${RENEWAL_CONF}"
        ok "Certbot renewal hooks configured (stop/start nginx around renewal)"
    else
        warn "No [renewalparams] section found in ${RENEWAL_CONF}, hooks not added"
    fi
else
    warn "Renewal config not found at ${RENEWAL_CONF}, hooks not added"
fi

# ── Verification ─────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════"
echo "  Gate Verification for ${DOMAIN}"
echo "═══════════════════════════════════════════════════"

echo ""
echo "Gate 4 — nginx -t:"
docker exec "${NGINX_CONTAINER}" nginx -t 2>&1 && ok "PASS" || fail "FAIL"

echo ""
echo "Gate 6 — HTTP → HTTPS redirect:"
REDIRECT=$(curl -sI -o /dev/null -w "%{http_code}" "http://localhost/" 2>/dev/null || echo "000")
if [[ "$REDIRECT" == "301" ]]; then
    ok "PASS — HTTP returns 301"
else
    warn "HTTP returned ${REDIRECT} (expected 301)"
fi

echo ""
echo "Gate 6 — HTTPS /health:"
HEALTH=$(curl -sk "https://localhost/health" 2>/dev/null || echo "")
if echo "$HEALTH" | grep -q '"status":"healthy"'; then
    ok "PASS — /health returns healthy"
    echo "  Response: ${HEALTH}"
else
    warn "FAIL — /health response: ${HEALTH}"
fi

echo ""
echo "Gate 6 — HTTPS /api/health:"
API_HEALTH=$(curl -sk "https://localhost/api/health" 2>/dev/null || echo "")
if echo "$API_HEALTH" | grep -q '"status":"healthy"'; then
    ok "PASS — /api/health returns healthy"
    echo "  Response: ${API_HEALTH}"
else
    warn "FAIL — /api/health response: ${API_HEALTH}"
fi

echo ""
echo "Gate 6 — certbot renewal hooks:"
if [[ -f "${RENEWAL_CONF}" ]] && grep -q "pre_hook" "${RENEWAL_CONF}"; then
    ok "PASS — hooks configured in ${RENEWAL_CONF}"
else
    warn "Hooks not verified"
fi

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Container: docker ps --filter name=${NGINX_CONTAINER}"
echo "  Logs:      docker logs ${NGINX_CONTAINER}"
echo "  Config:    cat ${NGINX_CONF_DIR}/default.conf"
echo "═══════════════════════════════════════════════════"
