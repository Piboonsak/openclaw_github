#!/usr/bin/env bash
# scripts/regression-check.sh — NongKung agent capability regression runner.
#
# Runs the regression test suite in tests/regression/ and reports pass/fail.
# Designed to be called from CI after a deploy step.
#
# Exit codes:
#   0 — all regression tests passed
#   1 — one or more tests failed (or an unexpected error occurred)
#
# Usage:
#   bash scripts/regression-check.sh
#   bash scripts/regression-check.sh --reporter=verbose   (extra vitest args passed through)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

SEPARATOR="══════════════════════════════════════════════════════"

echo "$SEPARATOR"
echo "  NongKung Regression Check — $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "$SEPARATOR"
echo ""

# Ensure node_modules are present before running.
if [[ ! -d "node_modules" ]]; then
  echo "[regression-check] node_modules not found — installing dependencies..." >&2
  pnpm install --frozen-lockfile
fi

EXTRA_ARGS=("$@")

echo "[regression-check] Running: vitest run --config vitest.regression.config.ts ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}"
echo ""

START_TIME="$SECONDS"

if pnpm exec vitest run --config vitest.regression.config.ts "${EXTRA_ARGS[@]}"; then
  ELAPSED=$((SECONDS - START_TIME))
  echo ""
  echo "$SEPARATOR"
  echo "  ✓ All NongKung regression tests passed (${ELAPSED}s)"
  echo "$SEPARATOR"
  exit 0
else
  ELAPSED=$((SECONDS - START_TIME))
  echo ""
  echo "$SEPARATOR"
  echo "  ✗ NongKung regression tests FAILED (${ELAPSED}s)" >&2
  echo "  Review the output above to identify failing capability tests." >&2
  echo "$SEPARATOR"
  exit 1
fi
