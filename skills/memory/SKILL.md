---
name: memory
description: "Maintain persistent agent memory across sessions. Use when: recording or retrieving VPS connection details, Docker config, port mappings, operational procedures, or known issues; updating MEMORY.md after infrastructure changes; bootstrapping a fresh session with infrastructure context. Also triggered by: 'remember this connection', 'update memory', 'what do you know about <host>', 'save this for later'."
---

# Persistent Memory Management

OpenClaw auto-loads `MEMORY.md` (and `memory.md`) from the agent workspace at every session start, so anything written there survives restarts.

## Workspace path

```
~/.openclaw/workspace/MEMORY.md          # primary
~/.openclaw/workspace/memory/YYYY-MM-DD.md  # dated daily notes
```

> If `OPENCLAW_PROFILE` is set the workspace is `~/.openclaw/workspace-<profile>/`.

## When to read

- At session start, scan for relevant sections before answering infrastructure questions.
- Search with `memory_search` tool first; fall back to reading the file directly when the tool is unavailable.

## When to write

Write to `MEMORY.md` after any of the following:

- Learning a new VPS/server address, SSH key path, or credential location
- Mapping a new port, container name, or service endpoint
- Completing an operational procedure worth repeating
- Discovering a known issue or workaround
- User explicitly says "remember this" or "save this"

**Append, never overwrite.** Keep entries dated and concise.

---

## Required sections in MEMORY.md

Use these exact headings so the memory search index can locate them reliably.

````markdown
## Connections

| Name            | Host / Address           | User | Key / Auth            | Notes                          |
| --------------- | ------------------------ | ---- | --------------------- | ------------------------------ |
| VPS (main)      | 203.0.113.10             | root | ~/.ssh/id_ed25519_vps | VPS (replace with actual host) |
| Container shell | openclaw-sgnl-openclaw-1 | —    | via docker exec       | Signal gateway                 |

SSH shortcut: `ssh -i "~/.ssh/id_ed25519_vps" root@203.0.113.10`

## Config

| Key              | Value                         | Where |
| ---------------- | ----------------------------- | ----- |
| Gateway config   | /data/.openclaw/openclaw.json | VPS   |
| Docker compose   | /data/docker-compose.yml      | VPS   |
| OpenClaw profile | default                       | VPS   |

## Port Mappings

| Service          | Internal | External | Host |
| ---------------- | -------- | -------- | ---- |
| OpenClaw gateway | 18789    | 18789    | VPS  |
| NGINX            | 80/443   | 80/443   | VPS  |

## Procedures

### Restart gateway (VPS)

```bash
pkill -9 -f openclaw-gateway || true
nohup openclaw gateway run --bind loopback --port 18789 --force \
  > /tmp/openclaw-gateway.log 2>&1 &
```
````

### Verify gateway is up

```bash
ss -ltnp | rg 18789
tail -n 120 /tmp/openclaw-gateway.log
openclaw channels status --probe
```

### Update OpenClaw on VPS

```bash
sudo npm i -g openclaw@latest
```

## Known Issues

| Date | Issue               | Workaround / Status |
| ---- | ------------------- | ------------------- |
| —    | (add as discovered) | —                   |

````

---

## Updating memory

Patch only the relevant section — do not regenerate the whole file.

To insert a new row into an existing Markdown table, locate the last row of the target table and append after it. Example using `awk`:

```bash
# Append a new row to the Connections table
awk '/^\| Container shell/{print; print "| Pi node | 192.168.1.42 | pi | ~/.ssh/id_ed25519 | local LAN |"; next}1' \
  ~/.openclaw/workspace/MEMORY.md > /tmp/MEMORY.md.tmp \
  && mv /tmp/MEMORY.md.tmp ~/.openclaw/workspace/MEMORY.md
````

For simpler appends at the bottom of a section, use the `write` tool to splice the new entry into the correct table boundary.

## Daily notes

For session-scoped notes that don't belong in the long-term file, write to the dated daily file instead:

```bash
DATED=~/.openclaw/workspace/memory/$(date +%Y-%m-%d).md
mkdir -p "$(dirname "$DATED")"
echo "## $(date +%H:%M) — <summary>" >> "$DATED"
echo "<details>" >> "$DATED"
```

Daily files are also indexed and searched, but they are not loaded verbatim at session start.
