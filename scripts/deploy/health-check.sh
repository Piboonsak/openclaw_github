#!/usr/bin/env bash
# health-check.sh — Verify backend health after deployment
# Usage: bash scripts/deploy/health-check.sh [URL] [MAX_RETRIES] [RETRY_INTERVAL] [BASIC_AUTH]
set -euo pipefail

URL="${1:-https://localhost/api/health}"
MAX_RETRIES="${2:-6}"
RETRY_INTERVAL="${3:-5}"
AUTH_CREDENTIALS="${4:-}"

AUTH_ARGS=()
if [[ -n "${AUTH_CREDENTIALS}" ]]; then
  AUTH_ARGS=("-u" "${AUTH_CREDENTIALS}")
fi

echo "Health check: ${URL} (max ${MAX_RETRIES} attempts, ${RETRY_INTERVAL}s interval)"

for i in $(seq 1 "$MAX_RETRIES"); do
  HTTP_CODE=$(curl -sf -k "${AUTH_ARGS[@]}" -o /dev/null -w "%{http_code}" "$URL" 2>/dev/null || echo "000")
  if [[ "$HTTP_CODE" == "200" ]]; then
    BODY=$(curl -sf -k "${AUTH_ARGS[@]}" "$URL" 2>/dev/null || echo "{}")
    echo "Health check PASSED (attempt ${i}/${MAX_RETRIES}): ${BODY}"
    exit 0
  fi
  echo "Attempt ${i}/${MAX_RETRIES}: HTTP ${HTTP_CODE}, retrying in ${RETRY_INTERVAL}s..."
  sleep "$RETRY_INTERVAL"
done

echo "Health check FAILED after ${MAX_RETRIES} attempts: ${URL}"
exit 1
