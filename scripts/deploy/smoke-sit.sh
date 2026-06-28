#!/usr/bin/env bash
# smoke-sit.sh — Validate SIT runtime dependencies and readiness.
#
# Usage:
#   SIT_BASIC_AUTH_USER=... SIT_BASIC_AUTH_PASS=... bash scripts/deploy/smoke-sit.sh

set -euo pipefail

SIT_URL="${SIT_URL:-https://sit.yahwan.biz}"
COMPOSE_FILE="${SIT_COMPOSE_FILE:-docker/docker-compose.sit.yml}"
ENV_FILE="${SIT_ENV_FILE:-docker/.env.sit}"
BASIC_AUTH_USER="${SIT_BASIC_AUTH_USER:-}"
BASIC_AUTH_PASS="${SIT_BASIC_AUTH_PASS:-}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: ${ENV_FILE}"
  exit 1
fi

# Compose env-file does not export variables to the host shell.
# Parse env-file key/value pairs safely so host-side commands use the same values.
while IFS='=' read -r key value; do
  [[ "$key" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
  value="${value%%#*}"
  value="${value%\"}"
  value="${value#\"}"
  export "${key}=${value}"
done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE")

if [[ -n "$BASIC_AUTH_USER" && -n "$BASIC_AUTH_PASS" ]]; then
  AUTH_ARG=(-u "${BASIC_AUTH_USER}:${BASIC_AUTH_PASS}")
else
  AUTH_ARG=()
fi

run_compose() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

http_status() {
  local url="$1"
  if [[ "$SIT_URL" == "http://127.0.0.1:8000" ]]; then
    local path="${url#http://127.0.0.1:8000}"
    run_compose exec -T backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000${path}', timeout=10).getcode())"
  else
    curl -sS -k "${AUTH_ARG[@]}" -o /tmp/sit-smoke-body.txt -w "%{http_code}" "$url"
  fi
}

echo "[1/7] API liveness: ${SIT_URL}/api/health"
STATUS="$(http_status "${SIT_URL}/api/health")"
if [[ "$STATUS" != "200" ]]; then
  echo "Expected 200, got ${STATUS}"
  cat /tmp/sit-smoke-body.txt || true
  exit 1
fi

echo "[2/7] API readiness: ${SIT_URL}/api/health/ready"
STATUS="$(http_status "${SIT_URL}/api/health/ready")"
if [[ "$STATUS" != "200" ]]; then
  echo "Expected 200, got ${STATUS}"
  cat /tmp/sit-smoke-body.txt || true
  exit 1
fi

echo "[3/7] PostgreSQL connectivity"
run_compose exec -T postgres pg_isready -U "${POSTGRES_USER:-ledgerflow}" -d "${POSTGRES_DB:-ledgerflow_sit}" >/dev/null

echo "[4/7] Redis connectivity"
run_compose exec -T redis redis-cli ping | grep -q PONG

echo "[5/7] MinIO health"
run_compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('http://minio:9000/minio/health/live', timeout=5)"

echo "[6/7] Celery worker ping"
run_compose exec -T celery-worker python -c "from src.backend.workers.celery_app import celery_app; import sys; resp = celery_app.control.ping(timeout=2); print(resp); sys.exit(0 if resp else 1)"

echo "[7/7] Export endpoint smoke (route availability)"
STATUS="$(http_status "${SIT_URL}/api/v1/companies")"
if [[ "$STATUS" != "200" && "$STATUS" != "401" && "$STATUS" != "403" ]]; then
  echo "Unexpected status from /api/v1/companies route: ${STATUS}"
  cat /tmp/sit-smoke-body.txt || true
  exit 1
fi

echo "SIT smoke checks passed"
