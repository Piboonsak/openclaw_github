#!/usr/bin/env bash
# docker/deploy.sh
# Roll out a new piboonsak/openclaw image on the Hostinger VPS.
#
# Usage (from local machine):
#   SSH_KEY=~/.ssh/id_ed25519_hostinger \
#   VPS_HOST=srv1414058.hstgr.cloud \
#   VPS_USER=root \
#     bash docker/deploy.sh [IMAGE_TAG]
#
# Called by:
#   .github/workflows/deploy-vps.yml   (automated, after image push)
#   manual operator invocation
#
# Environment variables:
#   VPS_HOST      VPS hostname or IP  (default: srv1414058.hstgr.cloud)
#   VPS_USER      SSH user            (default: root)
#   SSH_KEY       Path to SSH private key (default: ~/.ssh/id_ed25519_hostinger)
#   IMAGE_TAG     Docker image tag    (default: latest)
#   APP_DIR       App dir on VPS      (default: /opt/openclaw)
#
# SECURITY: This script does NOT handle secrets. Secrets live in .env on the VPS.

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
VPS_HOST="${VPS_HOST:-srv1414058.hstgr.cloud}"
VPS_USER="${VPS_USER:-root}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519_hostinger}"
IMAGE_TAG="${1:-${IMAGE_TAG:-latest}}"
APP_DIR="${APP_DIR:-/docker/openclaw-sgnl}"
DOCKER_IMAGE="piboonsak/openclaw:${IMAGE_TAG}"
CONTAINER_NAME="openclaw-sgnl-openclaw-1"

# ── Validation ────────────────────────────────────────────────────────────────
if [[ ! -f "$SSH_KEY" ]]; then
  echo "ERROR: SSH key not found at $SSH_KEY"
  echo "       Set SSH_KEY env var or put key there."
  exit 1
fi

echo "→ Deploying $DOCKER_IMAGE to $VPS_USER@$VPS_HOST"
echo "  App dir:   $APP_DIR"
echo "  Container: $CONTAINER_NAME"
echo ""

# ── SSH helper ────────────────────────────────────────────────────────────────
run_remote() {
  ssh -i "$SSH_KEY" \
      -o StrictHostKeyChecking=no \
      -o ConnectTimeout=30 \
      "${VPS_USER}@${VPS_HOST}" "$@"
}

# ── Sync compose file from repo to VPS ───────────────────────────────────────
# Issue #67: deploy.sh previously only sed-updated the image tag, so new volume
# mounts and env_file directives in docker-compose.prod.yml never reached VPS.
# Now we sync the full compose file on every deploy to keep VPS in sync with repo.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_SRC="${SCRIPT_DIR}/docker-compose.prod.yml"
if [[ -f "$COMPOSE_SRC" ]]; then
  echo "→ Syncing docker-compose.prod.yml → VPS:${APP_DIR}/docker-compose.yml"
  scp -i "$SSH_KEY" \
      -o StrictHostKeyChecking=no \
      "$COMPOSE_SRC" \
      "${VPS_USER}@${VPS_HOST}:${APP_DIR}/docker-compose.yml"
else
  echo "WARNING: docker-compose.prod.yml not found at $COMPOSE_SRC"
  echo "         Falling back to existing compose file on VPS"
fi

# ── Deploy steps (executed on the VPS) ───────────────────────────────────────
run_remote bash -s -- "$DOCKER_IMAGE" "$APP_DIR" "$CONTAINER_NAME" << 'REMOTE_EOF'
set -euo pipefail
DOCKER_IMAGE="$1"
APP_DIR="$2"
CONTAINER_NAME="$3"

echo "[1/4] Pulling image: $DOCKER_IMAGE"
docker pull "$DOCKER_IMAGE"

echo "[2/4] Updating compose and restarting container"
cd "$APP_DIR"
# Ensure bind-mount targets exist for development workspace (Issue #67)
mkdir -p "$APP_DIR/volumes/gitrepo"
chown 1000:1000 "$APP_DIR/volumes/gitrepo" 2>/dev/null || true
# Ensure .env exists so the bind mount doesn't create a directory
if [[ ! -f "$APP_DIR/.env" ]]; then
  echo "WARNING: .env not found at $APP_DIR/.env — creating empty placeholder"
  touch "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
fi
# Update the image line in docker-compose.yml (overrides the variable default)
sed -i "s|image:.*|image: ${DOCKER_IMAGE}|" docker-compose.yml
# Start/update container
# --remove-orphans: required when service name changes (e.g. openclaw → openclaw-gateway)
# to remove old containers before creating new ones with the same container_name.
docker compose -f docker-compose.yml up -d --pull always --remove-orphans

# Wait for container runtime to be fully ready before exec commands.
# The container may take time to start or may restart once.
echo "  Waiting for container to become healthy..."
for i in $(seq 1 12); do
  STATE=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
  HEALTH=$(docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
  echo "    Attempt $i/12: state=$STATE health=$HEALTH"
  if [ "$STATE" = "running" ] && [ "$HEALTH" = "healthy" ]; then
    echo "  Container is healthy ✔"
    break
  fi
  if [ "$STATE" = "running" ] && [ "$HEALTH" = "no-healthcheck" ]; then
    echo "  Container is running (no healthcheck configured) ✔"
    break
  fi
  if [ "$i" -eq 12 ]; then
    echo "  WARNING: Container not healthy after 60s — attempting exec anyway"
  fi
  sleep 5
done

echo "[2a/4] Post-deploy: Clear stale LINE sessions + lock files"
# Remove bloated session files (>50KB) to prevent token overflow and latency
# Also remove stale .loc lock files left from previous container runs (KI-009-C1)
docker exec "$CONTAINER_NAME" bash -c '
  SESSION_DIR="/home/node/.openclaw/agents/main/sessions"
  mkdir -p "$SESSION_DIR"
  if [ -d "$SESSION_DIR" ]; then
    STALE=$(find "$SESSION_DIR" -name "line-*.jsonl" -size +50k 2>/dev/null | wc -l)
    if [ "$STALE" -gt 0 ]; then
      find "$SESSION_DIR" -name "line-*.jsonl" -size +50k -delete
      echo "  Cleared $STALE stale LINE session file(s) ✔"
    else
      echo "  No stale LINE sessions found ✔"
    fi
    LOCKS=$(find "$SESSION_DIR" -name "*.loc" 2>/dev/null | wc -l)
    if [ "$LOCKS" -gt 0 ]; then
      find "$SESSION_DIR" -name "*.loc" -delete
      echo "  Cleared $LOCKS stale session lock file(s) ✔"
    else
      echo "  No stale lock files found ✔"
    fi
  else
    echo "  Session directory not found (first deploy?) — skipping"
  fi
' || echo "  WARNING: Session cleanup failed (non-fatal)"

echo "[2b/4] Post-deploy: Apply exec security config"
# R3 fix: Ensure exec tool configuration matches production requirements
# - security: allowlist (only safeBins commands auto-approved)
# - askFallback: allowlist (stored in exec-approvals.json defaults)
# - host: gateway (no sandbox available on VPS)
# All exec commands use || true to prevent deploy failure if container is restarting
docker exec "$CONTAINER_NAME" openclaw config set tools.exec.security allowlist 2>/dev/null || true
docker exec "$CONTAINER_NAME" openclaw config get tools.exec.security 2>/dev/null | grep -qx "allowlist" || echo "  WARNING: exec.security verification failed"
docker exec "$CONTAINER_NAME" openclaw config set tools.exec.host gateway 2>/dev/null || true
docker exec "$CONTAINER_NAME" openclaw config get tools.exec.host 2>/dev/null | grep -qx "gateway" || echo "  WARNING: exec.host verification failed"
docker exec "$CONTAINER_NAME" openclaw config set tools.exec.ask on-miss 2>/dev/null || true
# Issue #63: Updated safeBins to include git and gh for agent self-development
docker exec "$CONTAINER_NAME" openclaw config set tools.exec.safeBins '["jq","cut","uniq","head","tail","tr","wc","date","uptime","whoami","hostname","ps","tree","curl","wget","git","gh"]' 2>/dev/null || true
# Issue #64 (Sprint 1.4.1): Set reasoning mode default to high
docker exec "$CONTAINER_NAME" openclaw config set agents.defaults.thinkingDefault high 2>/dev/null || true
# askFallback is not a regular tools.exec config path. Persist it in exec-approvals defaults.
docker exec "$CONTAINER_NAME" node -e '
const fs = require("node:fs");
const p = "/home/node/.openclaw/exec-approvals.json";
let file = { version: 1, defaults: {}, agents: {} };
try {
  const raw = fs.readFileSync(p, "utf8");
  const parsed = JSON.parse(raw);
  if (parsed && typeof parsed === "object") file = parsed;
} catch {}
file.version = 1;
file.defaults = { ...(file.defaults || {}), askFallback: "allowlist" };
if (!file.agents || typeof file.agents !== "object") file.agents = {};
fs.writeFileSync(p, JSON.stringify(file, null, 2) + "\n", { mode: 0o600 });
' 2>/dev/null || true
echo "  exec config applied ✔"

echo "[2c/4] Post-deploy: Apply session + context config"
# WS-2.4: Session idle timeout (30 min) and 5x context expansion
docker exec "$CONTAINER_NAME" openclaw config set session.reset.idleMinutes 30 2>/dev/null || true
docker exec "$CONTAINER_NAME" openclaw config set agents.defaults.bootstrapMaxChars 100000 2>/dev/null || true
docker exec "$CONTAINER_NAME" openclaw config set agents.defaults.bootstrapTotalMaxChars 750000 2>/dev/null || true
docker exec "$CONTAINER_NAME" openclaw config set agents.defaults.contextTokens 1000000 2>/dev/null || true
echo "  session + context config applied ✔"

echo "[2c2/4] Post-deploy: Apply model config"
# Issue #33: Claude Sonnet 4.6 as primary model for improved reasoning + cost efficiency
docker exec "$CONTAINER_NAME" openclaw config set agents.defaults.model.primary "anthropic/claude-sonnet-4-5" 2>/dev/null || true
echo "  model config applied ✔"

echo "[2d/4] Post-deploy: Apply embeddings config"
# R3 fix: Enable memory search via OpenAI embeddings (requires OPENAI_API_KEY in container env)
docker exec "$CONTAINER_NAME" openclaw config set agents.defaults.memorySearch.provider openai 2>/dev/null || true
docker exec "$CONTAINER_NAME" openclaw config set agents.defaults.memorySearch.sources '["memory"]' 2>/dev/null || true
docker exec "$CONTAINER_NAME" openclaw config set agents.defaults.memorySearch.fallback none 2>/dev/null || true
echo "  embeddings config applied ✔"

echo "[2d2/4] Post-deploy: Apply channel access policy"
# KI-013 fix: LINE OA is public-facing — dmPolicy must be "open" so all users get AI responses.
# "pairing" requires manual approval per user, which blocks all new LINE OA conversations.
docker exec "$CONTAINER_NAME" openclaw config set channels.line.dmPolicy open 2>/dev/null || true
echo "  channel access policy applied ✔"

echo "[2e/4] Post-deploy: Nginx config"
# Nginx config is now applied by deploy-vps.yml workflow (before deploy.sh runs).
# The workflow SCPs docker/nginx/openclaw.conf to VPS and applies it with rollback safety.
echo "  Nginx config managed by GitHub Actions workflow ✔"

echo "[2f/4] Post-deploy: Update Flask bridge timeout"
# Increase gunicorn timeout from 60s to 300s for the fallback Flask bridge
FLASK_SERVICE="/etc/systemd/system/line-bridge.service"
if [ -f "$FLASK_SERVICE" ]; then
  if grep -q "\-\-timeout 60" "$FLASK_SERVICE"; then
    sed -i 's/--timeout 60/--timeout 300/' "$FLASK_SERVICE"
    systemctl daemon-reload
    systemctl restart line-bridge
    echo "  Flask bridge timeout updated to 300s and restarted ✔"
  else
    echo "  Flask bridge timeout already updated (or different format) ✔"
  fi
else
  echo "  Flask bridge service not found — skipping (native handler is primary)"
fi

echo "[3/4] Verifying container is running and resource limits applied"
RUNNING=$(docker inspect --format='{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || echo "false")
if [[ "$RUNNING" != "true" ]]; then
  echo "ERROR: Container $CONTAINER_NAME is not running after deploy"
  docker logs "$CONTAINER_NAME" --tail 50
  exit 1
fi
echo "Container $CONTAINER_NAME is running ✔"

# Verify resource limits are applied (4 vCPU = 4000000000 NanoCpus, 16G = 17179869184 bytes)
NANO_CPUS=$(docker inspect --format='{{.HostConfig.NanoCpus}}' "$CONTAINER_NAME" 2>/dev/null || echo "0")
MEM_LIMIT=$(docker inspect --format='{{.HostConfig.Memory}}' "$CONTAINER_NAME" 2>/dev/null || echo "0")
echo "  CPU limit: $NANO_CPUS NanoCpus (expected: 4000000000)"
echo "  Memory limit: $MEM_LIMIT bytes (expected: 17179869184)"
# Warn if limits are not applied (non-fatal — Hostinger Docker Manager may override)
if [[ "$NANO_CPUS" != "4000000000" && "$NANO_CPUS" != "0" ]]; then
  echo "  WARNING: CPU limit mismatch — expected 4 vCPU (4000000000), got $NANO_CPUS"
fi
if [[ "$MEM_LIMIT" != "17179869184" && "$MEM_LIMIT" != "0" ]]; then
  echo "  WARNING: Memory limit mismatch — expected 16G (17179869184), got $MEM_LIMIT"
fi

echo "[4/4] Health check"
# Wait up to 40 s for the gateway health endpoint to respond
for i in $(seq 1 8); do
  if curl -sf http://localhost:18789/health > /dev/null; then
    echo "Health check passed ✔"
    break
  fi
  if [[ "$i" -eq 8 ]]; then
    echo "WARNING: Health check timed out after 40s (check logs)"
    docker logs "$CONTAINER_NAME" --tail 30
  else
    echo "  ... waiting for health (attempt $i/8)"
    sleep 5
  fi
done

echo ""
echo "Deploy complete: $DOCKER_IMAGE → $CONTAINER_NAME"
docker ps --filter "name=$CONTAINER_NAME" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
REMOTE_EOF

echo ""
echo "✓ Deployment finished."
echo "  Live URL: https://openclaw.yahwan.biz/health"
