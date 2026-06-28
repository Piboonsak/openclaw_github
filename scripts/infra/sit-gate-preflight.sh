#!/usr/bin/env bash
set -euo pipefail

# Read-only preflight for SIT/UAT/PROD promotion gates.
# This script does not mutate infra state; it only validates required inputs.

TARGET_HOST="${1:-${SIT_HOST:-}}"
TARGET_URL="${2:-${SIT_URL:-}}"

if [[ -z "${TARGET_HOST}" || -z "${TARGET_URL}" ]]; then
  echo "Usage: SIT_HOST=<host> SIT_URL=<url> $0"
  echo "   or: $0 <host> <url>"
  exit 1
fi

echo "[preflight] target host: ${TARGET_HOST}"
echo "[preflight] target url : ${TARGET_URL}"

echo "[preflight] checking DNS resolution"
if ! getent ahostsv4 "${TARGET_HOST}" >/dev/null 2>&1; then
  echo "ERROR: host does not resolve from this runner: ${TARGET_HOST}"
  exit 1
fi

echo "[preflight] checking HTTPS health endpoint availability"
if ! curl -kfsS "${TARGET_URL}/api/health" >/dev/null; then
  echo "ERROR: unable to reach ${TARGET_URL}/api/health"
  exit 1
fi

echo "[preflight] checking HTTPS readiness endpoint availability"
if ! curl -kfsS "${TARGET_URL}/api/health/ready" >/dev/null; then
  echo "ERROR: unable to reach ${TARGET_URL}/api/health/ready"
  exit 1
fi

echo "[preflight] success"
