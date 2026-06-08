#!/bin/bash
# check_scope.sh -- Compatibility shim. Forwards to scripts/gates/check_scope.py.
# The state-aware enforcement (forbidden paths hard-fail + per-task allowed_scope)
# lives in scripts/gates/check_scope.py.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python}"

exec "$PYTHON" "$SCRIPT_DIR/gates/check_scope.py" "$@"

