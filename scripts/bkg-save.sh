#!/usr/bin/env bash
# Save a Best-Known-Good copy of the running OpenClaw config on the VPS.
# - Copies /data/.openclaw/openclaw.json into /data/openclaw-config-archive/
# - Names snapshot: bkg-{YYYYMMDD-HHmmss}-{short-sha}.json
# - Updates symlink: bkg-latest.json -> newest snapshot
# - Rotates snapshots, keeping the 10 most recent

set -euo pipefail

CONFIG_PATH="/data/.openclaw/openclaw.json"
ARCHIVE_DIR="/data/openclaw-config-archive"
LATEST_LINK="${ARCHIVE_DIR}/bkg-latest.json"

# Prefer provided short SHA; fall back to repo HEAD if available.
SHORT_SHA="${SHORT_SHA:-${GITHUB_SHA:-}}"
if [[ -z "$SHORT_SHA" ]]; then
  for repo in /data/openclaw_github /docker/openclaw-sgnl /docker/openclaw; do
    if git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      SHORT_SHA="$(git -C "$repo" rev-parse --short HEAD 2>/dev/null || true)"
      [[ -n "$SHORT_SHA" ]] && break
    fi
  done
fi
SHORT_SHA="${SHORT_SHA:0:7}"
if [[ -z "$SHORT_SHA" ]]; then
  echo "WARN: Unable to determine short SHA, defaulting to 'unknown'" >&2
  SHORT_SHA="unknown"
fi

if [[ ! -f "$CONFIG_PATH" ]]; then
  echo "ERROR: Config not found at $CONFIG_PATH" >&2
  exit 1
fi

mkdir -p "$ARCHIVE_DIR"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BKG_FILE="${ARCHIVE_DIR}/bkg-${TIMESTAMP}-${SHORT_SHA}.json"

cp "$CONFIG_PATH" "$BKG_FILE"
ln -sfn "$BKG_FILE" "$LATEST_LINK"

# Rotate snapshots: keep newest 10, delete older ones.
mapfile -t snapshots < <(
  find "$ARCHIVE_DIR" -maxdepth 1 -type f -name "bkg-*.json" -printf '%T@ %p\n' \
    | sort -nr \
    | awk '{print $2}'
)

if ((${#snapshots[@]} > 10)); then
  for old in "${snapshots[@]:10}"; do
    rm -f "$old"
  done
fi

echo "Saved BKG snapshot: $BKG_FILE"
echo "Updated symlink: $LATEST_LINK -> $BKG_FILE"
