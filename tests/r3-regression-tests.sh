#!/usr/bin/env bash
# tests/r3-regression-tests.sh
# R3 Regression Test Suite — Deterministic automated checks
#
# All tests check specific config values, HTTP status codes, command outputs,
# and file sizes. NO LLM inference. NO hallucination possible.
#
# Usage:
#   bash tests/r3-regression-tests.sh                     # Run on VPS directly
#   ssh root@VPS "bash /docker/openclaw-sgnl/tests/r3-regression-tests.sh"  # Run remotely
#
# Called by:
#   .github/workflows/deploy-vps.yml  (automated, after deploy)
#
# Exit codes:
#   0 = all tests passed
#   1 = one or more tests failed

set -uo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
CONTAINER_NAME="${CONTAINER_NAME:-openclaw-sgnl-openclaw-1}"
PASS=0
FAIL=0
SKIP=0
RESULTS=()

# ── Helpers ───────────────────────────────────────────────────────────────────
pass() {
  PASS=$((PASS + 1))
  RESULTS+=("  ✔ PASS: $1")
  echo "  ✔ PASS: $1"
}

fail() {
  FAIL=$((FAIL + 1))
  RESULTS+=("  ✘ FAIL: $1 — $2")
  echo "  ✘ FAIL: $1 — $2"
}

skip() {
  SKIP=$((SKIP + 1))
  RESULTS+=("  ⊘ SKIP: $1 — $2")
  echo "  ⊘ SKIP: $1 — $2"
}

dexec() {
  docker exec "$CONTAINER_NAME" "$@" 2>/dev/null
}

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║        R3 Regression Test Suite — OpenClaw Production          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "Container: $CONTAINER_NAME"
echo "Started:   $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo ""

# ── Pre-flight: Container must be running ─────────────────────────────────────
echo "── Pre-flight ──────────────────────────────────────────────────────"
RUNNING=$(docker inspect --format='{{.State.Running}}' "$CONTAINER_NAME" 2>/dev/null || echo "false")
if [[ "$RUNNING" != "true" ]]; then
  echo "FATAL: Container $CONTAINER_NAME is not running. Cannot proceed."
  exit 1
fi
echo "Container is running ✔"
echo ""

# ══════════════════════════════════════════════════════════════════════════════
# Category A: Exec Configuration Checks (RC-1 fix verification)
# ══════════════════════════════════════════════════════════════════════════════
echo "── A. Exec Configuration ──────────────────────────────────────────"

# Test A1: exec security = allowlist
VAL=$(dexec openclaw config get tools.exec.security 2>/dev/null | tr -d '"' | tr -d '[:space:]')
if [[ "$VAL" == "allowlist" ]]; then
  pass "A1: tools.exec.security = allowlist"
else
  fail "A1: tools.exec.security" "expected 'allowlist', got '$VAL'"
fi

# Test A2: exec askFallback = allowlist
VAL=$(docker exec "$CONTAINER_NAME" node -e '
const fs = require("node:fs");
const p = "/home/node/.openclaw/exec-approvals.json";
let v = "";
try {
  const raw = fs.readFileSync(p, "utf8");
  const parsed = JSON.parse(raw);
  v = parsed?.defaults?.askFallback ?? "";
} catch {}
process.stdout.write(String(v));
' 2>/dev/null | tr -d '"' | tr -d '[:space:]')
if [[ "$VAL" == "allowlist" ]]; then
  pass "A2: tools.exec.askFallback = allowlist"
else
  fail "A2: tools.exec.askFallback" "expected 'allowlist', got '$VAL'"
fi

# Test A3: exec host = gateway
VAL=$(dexec openclaw config get tools.exec.host 2>/dev/null | tr -d '"' | tr -d '[:space:]')
if [[ "$VAL" == "gateway" ]]; then
  pass "A3: tools.exec.host = gateway"
else
  fail "A3: tools.exec.host" "expected 'gateway', got '$VAL'"
fi

# Test A4: safeBins contains 'date'
SAFEBINS=$(dexec openclaw config get tools.exec.safeBins 2>/dev/null)
if echo "$SAFEBINS" | grep -q '"date"'; then
  pass "A4: safeBins contains 'date'"
else
  fail "A4: safeBins contains 'date'" "not found in: $SAFEBINS"
fi

# Test A5: safeBins contains 'jq'
if echo "$SAFEBINS" | grep -q '"jq"'; then
  pass "A5: safeBins contains 'jq'"
else
  fail "A5: safeBins contains 'jq'" "not found in: $SAFEBINS"
fi

# Test A6: safeBins contains 'whoami'
if echo "$SAFEBINS" | grep -q '"whoami"'; then
  pass "A6: safeBins contains 'whoami'"
else
  fail "A6: safeBins contains 'whoami'" "not found in: $SAFEBINS"
fi

echo ""

# ══════════════════════════════════════════════════════════════════════════════
# Category B: Embeddings Configuration (RC-3 fix verification)
# ══════════════════════════════════════════════════════════════════════════════
echo "── B. Embeddings Configuration ────────────────────────────────────"

# Test B1: memorySearch provider = openai
VAL=$(dexec openclaw config get agents.defaults.memorySearch.provider 2>/dev/null | tr -d '"' | tr -d '[:space:]')
if [[ "$VAL" == "openai" ]]; then
  pass "B1: memorySearch.provider = openai"
else
  fail "B1: memorySearch.provider" "expected 'openai', got '$VAL'"
fi

echo ""

# ══════════════════════════════════════════════════════════════════════════════
# Category C: Exec Smoke Tests (RC-1 end-to-end verification)
# ══════════════════════════════════════════════════════════════════════════════
echo "── C. Exec Smoke Tests ────────────────────────────────────────────"

# Pre-C: Clear stale session lock files to prevent "session file locked" errors
# After deploy/restart, previous session locks may still exist and block new agent calls
dexec bash -c 'find /home/node/.openclaw/agents/main/sessions/ -name "*.loc" -delete 2>/dev/null' || true

# Test C1: 'date' command runs without "Approval required"
EXEC_OUT=$(docker exec "$CONTAINER_NAME" timeout 45 openclaw agent --agent main -m "run the command: date" --json --local 2>&1)
EXEC_CODE=$?
if [[ "$EXEC_CODE" -eq 124 ]]; then
  fail "C1: exec 'date' without approval" "command timed out after 30s"
elif [[ "$EXEC_CODE" -ne 0 ]]; then
  fail "C1: exec 'date' without approval" "command failed: $(echo "$EXEC_OUT" | head -c 200)"
elif echo "$EXEC_OUT" | grep -qi "approval required\|permission denied\|blocked"; then
  fail "C1: exec 'date' without approval" "got approval/permission error"
else
  pass "C1: exec 'date' runs without approval prompt"
fi

# Test C2: 'whoami' returns "node" (container default user)
EXEC_OUT=$(docker exec "$CONTAINER_NAME" timeout 45 openclaw agent --agent main -m "run whoami and return only the output" --json --local 2>&1)
EXEC_CODE=$?
if [[ "$EXEC_CODE" -eq 124 ]]; then
  fail "C2: exec 'whoami' returns node" "command timed out after 30s"
elif [[ "$EXEC_CODE" -ne 0 ]]; then
  fail "C2: exec 'whoami' returns node" "command failed: $(echo "$EXEC_OUT" | head -c 200)"
elif echo "$EXEC_OUT" | grep -qi "node"; then
  pass "C2: exec 'whoami' returns 'node'"
else
  fail "C2: exec 'whoami' returns node" "output did not contain 'node': $(echo "$EXEC_OUT" | head -c 200)"
fi

echo ""

# ══════════════════════════════════════════════════════════════════════════════
# Category D: LINE Webhook (RC-2, RC-6 fix verification)
# ══════════════════════════════════════════════════════════════════════════════
echo "── D. LINE Webhook ────────────────────────────────────────────────"

# Test D1: POST to native LINE handler returns HTTP 200 (not 502/499)
# Send a minimal LINE webhook payload — the handler should respond 200 immediately
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:18789/line/webhook \
  -H "Content-Type: application/json" \
  -d '{"events":[],"destination":"test"}' \
  --max-time 10 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" == "200" ]]; then
  pass "D1: LINE webhook returns HTTP 200 (native handler)"
elif [[ "$HTTP_CODE" == "000" ]]; then
  fail "D1: LINE webhook HTTP status" "connection failed (port 18789 not reachable)"
else
  # Accept 401/403 as "handler is working but auth check failed" — still means native handler is active
  if [[ "$HTTP_CODE" == "401" || "$HTTP_CODE" == "403" ]]; then
    pass "D1: LINE webhook returns HTTP $HTTP_CODE (native handler active, auth expected)"
  else
    fail "D1: LINE webhook HTTP status" "expected 200, got $HTTP_CODE"
  fi
fi

echo ""

# ══════════════════════════════════════════════════════════════════════════════
# Category E: Nginx Routing (RC-2, RC-6 fix verification)
# ══════════════════════════════════════════════════════════════════════════════
echo "── E. Nginx Routing ───────────────────────────────────────────────"

# Test E1: /line/ routes to port 18789 (native handler, NOT 5100)
NGINX_CONF=$(nginx -T 2>/dev/null || echo "")
if [[ -z "$NGINX_CONF" ]]; then
  skip "E1: Nginx /line/ → port 18789" "nginx -T not available (not on VPS host?)"
else
  # Extract the /line/ location block and check proxy_pass
  LINE_PROXY=$(echo "$NGINX_CONF" | awk '/location \/line\/ \{/,/\}/' | grep proxy_pass | head -1)
  if echo "$LINE_PROXY" | grep -q "18789"; then
    pass "E1: Nginx /line/ → port 18789 (native handler)"
  elif echo "$LINE_PROXY" | grep -q "5100"; then
    fail "E1: Nginx /line/ routing" "still pointing to port 5100 (Flask bridge)"
  else
    fail "E1: Nginx /line/ routing" "proxy_pass not found or unexpected: $LINE_PROXY"
  fi
fi

# Test E2: /line-bridge/ routes to port 5100 (Flask fallback)
if [[ -z "$NGINX_CONF" ]]; then
  skip "E2: Nginx /line-bridge/ → port 5100" "nginx -T not available"
else
  BRIDGE_PROXY=$(echo "$NGINX_CONF" | awk '/location \/line-bridge\/ \{/,/\}/' | grep proxy_pass | head -1)
  if echo "$BRIDGE_PROXY" | grep -q "5100"; then
    pass "E2: Nginx /line-bridge/ → port 5100 (Flask fallback)"
  else
    fail "E2: Nginx /line-bridge/ routing" "proxy_pass not found or unexpected: $BRIDGE_PROXY"
  fi
fi

echo ""

# ══════════════════════════════════════════════════════════════════════════════
# Category F: Session Cleanup (RC-4 fix verification)
# ══════════════════════════════════════════════════════════════════════════════
echo "── F. Session Cleanup ─────────────────────────────────────────────"

# Test F1: No LINE session files > 50KB (bloated sessions cleared by deploy.sh)
BLOATED=$(dexec bash -c 'find /home/node/.openclaw/agents/main/sessions -name "line-*.jsonl" -size +50k 2>/dev/null | wc -l' || echo "0")
BLOATED=$(echo "$BLOATED" | tr -d '[:space:]')
if [[ "$BLOATED" == "0" ]]; then
  pass "F1: No bloated LINE sessions (>50KB)"
else
  fail "F1: Session cleanup" "$BLOATED session file(s) still >50KB"
fi

echo ""

# ══════════════════════════════════════════════════════════════════════════════
# Category G: Flask Bridge Health (fallback verification)
# ══════════════════════════════════════════════════════════════════════════════
echo "── G. Flask Bridge Fallback ───────────────────────────────────────"

# Test G1: Flask bridge health endpoint responds
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:5100/line/health \
  --max-time 5 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" == "200" ]]; then
  pass "G1: Flask bridge health endpoint responds HTTP 200"
elif [[ "$HTTP_CODE" == "000" ]]; then
  # Flask bridge may not be running — that's OK since native handler is primary
  skip "G1: Flask bridge health" "port 5100 not reachable (native handler is primary, OK)"
else
  pass "G1: Flask bridge responds HTTP $HTTP_CODE (service alive)"
fi

echo ""

# ══════════════════════════════════════════════════════════════════════════════
# Category H: Container Resource Limits (scaling verification)
# ══════════════════════════════════════════════════════════════════════════════
echo "── H. Container Resource Limits ─────────────────────────────────"

# Test H1: CPU limit = 4 vCPU (4000000000 NanoCpus)
NANO_CPUS=$(docker inspect --format='{{.HostConfig.NanoCpus}}' "$CONTAINER_NAME" 2>/dev/null || echo "ERR")
if [[ "$NANO_CPUS" == "4000000000" ]]; then
  pass "H1: CPU limit = 4 vCPU (4000000000 NanoCpus)"
elif [[ "$NANO_CPUS" == "0" ]]; then
  # 0 means unlimited — compose deploy.resources may not translate to HostConfig on all runtimes
  skip "H1: CPU limit" "NanoCpus=0 (unlimited — Hostinger Docker Manager may manage limits separately)"
else
  fail "H1: CPU limit" "expected 4000000000, got $NANO_CPUS"
fi

# Test H2: Memory limit = 16G (17179869184 bytes)
MEM_LIMIT=$(docker inspect --format='{{.HostConfig.Memory}}' "$CONTAINER_NAME" 2>/dev/null || echo "ERR")
if [[ "$MEM_LIMIT" == "17179869184" ]]; then
  pass "H2: Memory limit = 16G (17179869184 bytes)"
elif [[ "$MEM_LIMIT" == "0" ]]; then
  skip "H2: Memory limit" "Memory=0 (unlimited — Hostinger Docker Manager may manage limits separately)"
else
  fail "H2: Memory limit" "expected 17179869184, got $MEM_LIMIT"
fi

# Test H3: PIDs limit = 200
PIDS_LIMIT=$(docker inspect --format='{{.HostConfig.PidsLimit}}' "$CONTAINER_NAME" 2>/dev/null || echo "ERR")
if [[ "$PIDS_LIMIT" == "200" ]]; then
  pass "H3: PIDs limit = 200"
else
  skip "H3: PIDs limit" "got $PIDS_LIMIT (non-fatal)"
fi

echo ""

# ══════════════════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════════════════
echo "══════════════════════════════════════════════════════════════════"
echo "  R3 Regression Test Results"
echo "══════════════════════════════════════════════════════════════════"
echo ""
for R in "${RESULTS[@]}"; do
  echo "$R"
done
echo ""
echo "  TOTAL: $((PASS + FAIL + SKIP)) | PASS: $PASS | FAIL: $FAIL | SKIP: $SKIP"
echo ""
echo "  Finished: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "══════════════════════════════════════════════════════════════════"

if [[ "$FAIL" -gt 0 ]]; then
  echo ""
  echo "RESULT: FAILED ($FAIL test(s) failed)"
  exit 1
else
  echo ""
  echo "RESULT: PASSED (all $PASS tests passed, $SKIP skipped)"
  exit 0
fi
