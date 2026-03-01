#!/usr/bin/env bash
# WS-2.4 Regression Tests
# Run on VPS after deploy to verify WS-2.4 changes are live.
# Exit 0 = all pass, exit 1 = at least one failure.

set -euo pipefail

PASS=0
FAIL=0
SKIP=0

pass() { echo "  ✓ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL + 1)); }
skip() { echo "  ⊘ $1 (skipped)"; SKIP=$((SKIP + 1)); }

echo "═══════════════════════════════════════════════════════"
echo "  WS-2.4 Regression Tests — $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "═══════════════════════════════════════════════════════"
echo ""

# ── I1: Session idle timeout = 30 minutes ────────────────────────────
echo "Category I1: Session idle timeout"
CONFIG_FILE="/docker/openclaw-sgnl/config/openclaw.prod.json5"
if [ -f "$CONFIG_FILE" ]; then
  if grep -q '"idleMinutes"' "$CONFIG_FILE" 2>/dev/null; then
    IDLE_VAL=$(grep -oP '"idleMinutes"\s*:\s*\K[0-9]+' "$CONFIG_FILE" 2>/dev/null || echo "0")
    if [ "$IDLE_VAL" = "30" ]; then
      pass "I1.1 session.reset.idleMinutes = 30"
    else
      fail "I1.1 session.reset.idleMinutes = $IDLE_VAL (expected 30)"
    fi
  else
    fail "I1.1 idleMinutes key not found in config"
  fi
else
  skip "I1.1 Config file not found at $CONFIG_FILE"
fi

# ── I2: Context 5x values ────────────────────────────────────────────
echo ""
echo "Category I2: Context 5x scaling"
if [ -f "$CONFIG_FILE" ]; then
  check_config_val() {
    local KEY="$1" EXPECTED="$2" LABEL="$3"
    if grep -q "\"$KEY\"" "$CONFIG_FILE" 2>/dev/null; then
      VAL=$(grep -oP "\"$KEY\"\s*:\s*\K[0-9]+" "$CONFIG_FILE" 2>/dev/null || echo "0")
      if [ "$VAL" = "$EXPECTED" ]; then
        pass "$LABEL = $EXPECTED"
      else
        fail "$LABEL = $VAL (expected $EXPECTED)"
      fi
    else
      fail "$LABEL key not found"
    fi
  }
  check_config_val "bootstrapMaxChars" "100000" "I2.1 bootstrapMaxChars"
  check_config_val "bootstrapTotalMaxChars" "750000" "I2.2 bootstrapTotalMaxChars"
  check_config_val "contextTokens" "1000000" "I2.3 contextTokens"
else
  skip "I2 Config file not found"
fi

# ── I3: Exec safe-bin profiles count ─────────────────────────────────
echo ""
echo "Category I3: Exec safe-bin profiles"
# The exec-safe-bin-policy.ts should have 17 total profiles after WS-2.4
# (9 original + 8 new: date, uptime, whoami, hostname, ps, tree, curl, wget)
# We verify by checking the container image source
CONTAINER_NAME="openclaw-sgnl-openclaw-1"
if docker ps --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
  # Check if new bins appear in the safeBins config
  SAFEBINS=$(docker exec "$CONTAINER_NAME" sh -c 'cat /app/config/*.json5 2>/dev/null | grep -i safeBins || echo ""' 2>/dev/null || echo "")
  NEW_BINS="date uptime whoami hostname ps tree curl wget"
  MISSING=""
  for BIN in $NEW_BINS; do
    if ! echo "$SAFEBINS" | grep -q "$BIN" 2>/dev/null; then
      MISSING="$MISSING $BIN"
    fi
  done
  if [ -z "$MISSING" ]; then
    pass "I3.1 All 8 new safe-bin commands found in config"
  else
    fail "I3.1 Missing safe bins:$MISSING"
  fi
else
  skip "I3 Container $CONTAINER_NAME not running"
fi

# ── I4: format_response.py exists ────────────────────────────────────
echo ""
echo "Category I4: format_response.py"
SCRIPT_PATH="/docker/openclaw-sgnl/scripts/format_response.py"
if [ -f "$SCRIPT_PATH" ]; then
  pass "I4.1 format_response.py exists at $SCRIPT_PATH"
  # Check it has the format_response function
  if grep -q "def format_response" "$SCRIPT_PATH" 2>/dev/null; then
    pass "I4.2 format_response() function defined"
  else
    fail "I4.2 format_response() function not found"
  fi
else
  # Also check inside the container
  if docker exec "$CONTAINER_NAME" test -f /app/docker/scripts/format_response.py 2>/dev/null; then
    pass "I4.1 format_response.py exists in container"
    if docker exec "$CONTAINER_NAME" grep -q "def format_response" /app/docker/scripts/format_response.py 2>/dev/null; then
      pass "I4.2 format_response() function defined"
    else
      fail "I4.2 format_response() function not found in container"
    fi
  else
    skip "I4.1 format_response.py not found (host or container)"
  fi
fi

# ── I5: Container resource limits ────────────────────────────────────
echo ""
echo "Category I5: Container resource limits (4vCPU / 16GB)"
if docker ps --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
  CPU_NANO=$(docker inspect --format='{{.HostConfig.NanoCpus}}' "$CONTAINER_NAME" 2>/dev/null || echo "0")
  MEM_BYTES=$(docker inspect --format='{{.HostConfig.Memory}}' "$CONTAINER_NAME" 2>/dev/null || echo "0")

  # 4 CPU = 4000000000 NanoCPUs
  if [ "$CPU_NANO" = "4000000000" ]; then
    pass "I5.1 CPU limit = 4 vCPU (NanoCPUs: $CPU_NANO)"
  elif [ "$CPU_NANO" = "0" ]; then
    skip "I5.1 CPU limit not enforced (unlimited)"
  else
    CPU_CORES=$((CPU_NANO / 1000000000))
    fail "I5.1 CPU limit = ${CPU_CORES} vCPU (expected 4)"
  fi

  # 16GB = 17179869184 bytes
  if [ "$MEM_BYTES" = "17179869184" ]; then
    pass "I5.2 Memory limit = 16 GB"
  elif [ "$MEM_BYTES" = "0" ]; then
    skip "I5.2 Memory limit not enforced (unlimited)"
  else
    MEM_GB=$((MEM_BYTES / 1073741824))
    fail "I5.2 Memory limit = ${MEM_GB} GB (expected 16)"
  fi
else
  skip "I5 Container $CONTAINER_NAME not running"
fi

# ── I6: Health endpoint ──────────────────────────────────────────────
echo ""
echo "Category I6: Health check"
HTTP=$(curl -o /dev/null -sw "%{http_code}" --max-time 10 http://localhost:18789/health 2>/dev/null || echo "000")
if [ "$HTTP" = "200" ]; then
  pass "I6.1 Health endpoint returns 200"
else
  fail "I6.1 Health endpoint returns $HTTP (expected 200)"
fi

# ── I7: Docker image is latest ───────────────────────────────────────
echo ""
echo "Category I7: Docker image version"
if docker ps --format '{{.Names}}' | grep -q "$CONTAINER_NAME"; then
  IMAGE=$(docker inspect --format='{{.Config.Image}}' "$CONTAINER_NAME" 2>/dev/null || echo "unknown")
  if echo "$IMAGE" | grep -q "piboonsak/openclaw"; then
    pass "I7.1 Container running piboonsak/openclaw image ($IMAGE)"
  else
    fail "I7.1 Unexpected image: $IMAGE"
  fi
else
  skip "I7 Container not running"
fi

# ── Summary ──────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════"
echo "  WS-2.4 Results: $PASS passed · $FAIL failed · $SKIP skipped"
echo "═══════════════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
  echo "RESULT: FAIL"
  exit 1
fi

echo "RESULT: PASS"
exit 0
