#!/usr/bin/env bash
# scripts/check-bot.sh
# One-shot health check for the OpenClaw bot deployment.
#
# Usage:
#   bash scripts/check-bot.sh [OPTIONS]
#
# Options:
#   --json              Machine-readable JSON output
#   --container NAME    Docker container name (default: openclaw-sgnl-openclaw-1)
#   --port PORT         Gateway port to probe (default: 18789)
#   --host HOST         Gateway host          (default: localhost)
#   -h, --help          Show this help message
#
# Exit codes:
#   0  All checks passed
#   1  One or more checks failed

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
CONTAINER_NAME="${OPENCLAW_CONTAINER:-openclaw-sgnl-openclaw-1}"
GATEWAY_PORT="${OPENCLAW_GATEWAY_PORT:-18789}"
GATEWAY_HOST="${OPENCLAW_GATEWAY_HOST:-localhost}"
JSON_OUTPUT=false
LOG_LINES=10

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --json)            JSON_OUTPUT=true ;;
    --container)       CONTAINER_NAME="$2"; shift ;;
    --port)            GATEWAY_PORT="$2"; shift ;;
    --host)            GATEWAY_HOST="$2"; shift ;;
    -h|--help)
      sed -n '2,14p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
  shift
done

# ── Result tracking ───────────────────────────────────────────────────────────
PASS_COUNT=0
FAIL_COUNT=0
declare -A RESULTS   # name → pass|fail
declare -A DETAILS   # name → detail string

record() {
  local name="$1"
  local status="$2"   # pass | fail
  local detail="$3"
  RESULTS["$name"]="$status"
  DETAILS["$name"]="$detail"
  if [[ "$status" == "pass" ]]; then
    PASS_COUNT=$(( PASS_COUNT + 1 ))
  else
    FAIL_COUNT=$(( FAIL_COUNT + 1 ))
  fi
}

# Print a single check result line (skipped when --json)
print_check() {
  local name="$1"
  local status="${RESULTS[$name]}"
  local detail="${DETAILS[$name]}"
  if [[ "$status" == "pass" ]]; then
    printf "${GREEN}  PASS${NC}  %-28s %s\n" "$name" "$detail"
  else
    printf "${RED}  FAIL${NC}  %-28s %s\n" "$name" "$detail"
  fi
}

# ── Check 1: Container status ─────────────────────────────────────────────────
check_container() {
  local state
  state=$(docker inspect --format='{{.State.Status}}' "$CONTAINER_NAME" 2>/dev/null || true)
  state="${state//[$'\t\r\n ']}"  # strip whitespace
  state="${state:-not-found}"
  if [[ "$state" == "running" ]]; then
    record "container_status" "pass" "container=$CONTAINER_NAME state=running"
  else
    record "container_status" "fail" "container=$CONTAINER_NAME state=${state}"
  fi
}

# ── Check 2: Port binding ─────────────────────────────────────────────────────
check_port() {
  local bound=false
  # Check with ss (preferred) then netstat, then /proc/net/tcp
  if command -v ss &>/dev/null; then
    if ss -ltnp 2>/dev/null | grep -q ":${GATEWAY_PORT}[[:space:]]"; then
      bound=true
    fi
  elif command -v netstat &>/dev/null; then
    if netstat -ltnp 2>/dev/null | grep -q ":${GATEWAY_PORT}[[:space:]]"; then
      bound=true
    fi
  fi
  # Fallback: attempt TCP connect
  if ! $bound && command -v nc &>/dev/null; then
    if nc -z -w2 "$GATEWAY_HOST" "$GATEWAY_PORT" &>/dev/null; then
      bound=true
    fi
  fi

  if $bound; then
    record "port_binding" "pass" "port=${GATEWAY_PORT} is bound"
  else
    record "port_binding" "fail" "port=${GATEWAY_PORT} not bound"
  fi
}

# ── Check 3: Health endpoint ──────────────────────────────────────────────────
check_health_endpoint() {
  local url="http://${GATEWAY_HOST}:${GATEWAY_PORT}/health"
  local http_code
  if command -v curl &>/dev/null; then
    http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 5 "$url" 2>/dev/null) || http_code="000"
    if [[ "$http_code" == "200" ]]; then
      record "health_endpoint" "pass" "GET ${url} → HTTP ${http_code}"
    else
      record "health_endpoint" "fail" "GET ${url} → HTTP ${http_code} (expected 200)"
    fi
  else
    record "health_endpoint" "fail" "curl not available"
  fi
}

# ── Check 4: Process check ────────────────────────────────────────────────────
check_process() {
  local proc_count
  # Look for the gateway node process inside the container
  if ! docker exec "$CONTAINER_NAME" true &>/dev/null 2>&1; then
    record "gateway_process" "fail" "cannot exec into container (is it running?)"
    return
  fi
  if docker exec "$CONTAINER_NAME" sh -c "ps aux 2>/dev/null | grep -q '[n]ode.*gateway'" 2>/dev/null; then
    proc_count=$(docker exec "$CONTAINER_NAME" sh -c \
      "ps aux 2>/dev/null | grep -c '[n]ode.*gateway'" 2>/dev/null)
    record "gateway_process" "pass" "openclaw gateway process running (count=${proc_count})"
  else
    record "gateway_process" "fail" "no gateway process found inside container"
  fi
}

# ── Check 5: Memory / CPU ─────────────────────────────────────────────────────
check_resources() {
  local stats
  stats=$(docker stats --no-stream --format \
    "{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" \
    "$CONTAINER_NAME" 2>/dev/null || echo "")
  if [[ -n "$stats" ]]; then
    local cpu mem_usage mem_pct
    cpu=$(echo "$stats" | cut -f1)
    mem_usage=$(echo "$stats" | cut -f2)
    mem_pct=$(echo "$stats" | cut -f3)
    record "resources" "pass" "cpu=${cpu} mem=${mem_usage} (${mem_pct})"
  else
    record "resources" "fail" "could not retrieve container stats"
  fi
}

# ── Check 6: Log tail ─────────────────────────────────────────────────────────
check_logs() {
  local tmpfile logs
  tmpfile=$(mktemp) || { record "log_tail" "fail" "failed to create temp file"; LOG_CONTENT=""; return; }
  if docker logs --tail "${LOG_LINES}" "$CONTAINER_NAME" > "$tmpfile" 2>&1; then
    logs=$(cat "$tmpfile")
    rm -f "$tmpfile"
    record "log_tail" "pass" "last ${LOG_LINES} log lines retrieved"
    LOG_CONTENT="$logs"
  else
    rm -f "$tmpfile"
    record "log_tail" "fail" "docker logs failed (container not running?)"
    LOG_CONTENT=""
  fi
}

# ── JSON helpers ──────────────────────────────────────────────────────────────
# json_escape <string>  — emit a JSON-safe escaped string (no surrounding quotes)
# Uses jq when available; falls back to pure-bash escaping per RFC 8259.
json_escape() {
  if command -v jq &>/dev/null; then
    # jq outputs a JSON string with surrounding quotes; strip them with -r + wrap trick
    printf '%s' "$1" | jq -Rsc . | sed 's/^"\(.*\)"$/\1/'
  else
    local s="$1"
    s="${s//\\/\\\\}"       # backslashes first
    s="${s//\"/\\\"}"       # double-quotes
    s="${s//$'\t'/\\t}"     # tab
    s="${s//$'\r'/\\r}"     # carriage return
    s="${s//$'\n'/\\n}"     # newline
    printf '%s' "$s"
  fi
}
check_container
check_port
check_health_endpoint
check_process
check_resources
check_logs

# ── JSON output ───────────────────────────────────────────────────────────────
if $JSON_OUTPUT; then
  # Build JSON without requiring jq
  printf '{\n'
  printf '  "overall": "%s",\n' "$([ $FAIL_COUNT -eq 0 ] && echo pass || echo fail)"
  printf '  "pass": %d,\n' "$PASS_COUNT"
  printf '  "fail": %d,\n' "$FAIL_COUNT"
  printf '  "checks": {\n'
  FIRST=true
  for name in container_status port_binding health_endpoint gateway_process resources log_tail; do
    $FIRST || printf ',\n'
    FIRST=false
    printf '    "%s": {"status": "%s", "detail": "%s"}' \
      "$name" "${RESULTS[$name]}" "$(json_escape "${DETAILS[$name]}")"
  done
  printf '\n  },\n'
  printf '  "log_tail": "%s"\n' "$(json_escape "${LOG_CONTENT:-}")"
  printf '}\n'
  [ $FAIL_COUNT -eq 0 ] && exit 0 || exit 1
fi

# ── Human-readable output ─────────────────────────────────────────────────────
printf "\n${BLUE}╔═══════════════════════════════════════════════════════╗${NC}\n"
printf "${BLUE}║         OpenClaw Bot Health Check                     ║${NC}\n"
printf "${BLUE}╚═══════════════════════════════════════════════════════╝${NC}\n\n"

printf "  Container : %s\n" "$CONTAINER_NAME"
printf "  Gateway   : %s:%s\n\n" "$GATEWAY_HOST" "$GATEWAY_PORT"

printf "${YELLOW}Checks:${NC}\n"
for name in container_status port_binding health_endpoint gateway_process resources log_tail; do
  print_check "$name"
done

printf "\n${YELLOW}Last %d log lines:${NC}\n" "$LOG_LINES"
if [[ -n "${LOG_CONTENT:-}" ]]; then
  echo "$LOG_CONTENT" | sed 's/^/  /'
else
  echo "  (no logs)"
fi

printf "\n"
if [[ $FAIL_COUNT -eq 0 ]]; then
  printf "${GREEN}  ✓ All %d checks passed${NC}\n\n" "$PASS_COUNT"
else
  printf "${RED}  ✗ %d/%d checks failed${NC}\n\n" "$FAIL_COUNT" "$(( PASS_COUNT + FAIL_COUNT ))"
fi

[ $FAIL_COUNT -eq 0 ] && exit 0 || exit 1
