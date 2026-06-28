#!/usr/bin/env bash
# deploy-sit.sh — Deploy LedgerFlow SIT stack on a VPS host.
#
# Expected run location: /opt/ledgerflow (repo root on VPS)
# Usage:
#   SIT_BRANCH=dev bash scripts/deploy/deploy-sit.sh

set -euo pipefail

SIT_BRANCH="${SIT_BRANCH:-dev}"
SIT_URL="${SIT_URL:-https://sit.yahwan.biz}"
COMPOSE_FILE="docker/docker-compose.sit.yml"
ENV_FILE="docker/.env.sit"
HTPASSWD_FILE="/opt/ledgerflow/secrets/sit/.htpasswd"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing ${ENV_FILE}. Copy docker/.env.sit.example and fill required values."
  exit 1
fi

if [[ ! -f "$HTPASSWD_FILE" ]]; then
  echo "Missing ${HTPASSWD_FILE}. Create Basic Auth file before deploy."
  exit 1
fi

run_compose() {
  docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"
}

echo "=== SIT Deploy: checkout ${SIT_BRANCH} ==="
git fetch origin "$SIT_BRANCH"
git checkout "$SIT_BRANCH"
git pull --ff-only origin "$SIT_BRANCH"

echo "=== SIT Deploy: build images ==="
run_compose build backend frontend celery-worker

echo "=== SIT Deploy: start dependencies ==="
run_compose up -d postgres redis minio

echo "=== SIT Deploy: run migrations ==="
run_compose run --rm backend python -m alembic upgrade head

echo "=== SIT Deploy: seed anonymized SIT data ==="
run_compose run --rm backend python scripts/seed_sit.py

echo "=== SIT Deploy: start app services ==="
run_compose up -d backend frontend celery-worker nginx

echo "=== SIT Deploy: wait for app boot (30s) ==="
sleep 30

echo "=== SIT Deploy: smoke test ==="
SIT_COMPOSE_FILE="$COMPOSE_FILE" SIT_ENV_FILE="$ENV_FILE" SIT_URL="$SIT_URL" \
  bash scripts/deploy/smoke-sit.sh

echo "SIT deploy completed: ${SIT_URL}"
