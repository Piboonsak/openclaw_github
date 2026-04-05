---
name: session-memory
description: "Save session context to memory when /new or /reset command is issued, or automatically after every N messages"
homepage: https://docs.openclaw.ai/automation/hooks#session-memory
metadata:
  {
    "openclaw":
      {
        "emoji": "💾",
        "events": ["command:new", "command:reset", "message:sent"],
        "requires": { "config": ["workspace.dir"] },
        "install": [{ "id": "bundled", "kind": "bundled", "label": "Bundled with OpenClaw" }],
      },
  }
---

# Session Memory Hook

Automatically saves session context to your workspace memory when you issue `/new` or `/reset`, or after every N sent messages when `every` is configured.

## What It Does

When you run `/new` or `/reset` to start a fresh session, or when the auto-save threshold is reached:

1. **Finds the previous session** - Uses the pre-reset session entry to locate the correct transcript
2. **Extracts conversation** - Reads the last N user/assistant messages from the session (default: 15, configurable)
3. **Generates descriptive slug** - Uses LLM to create a meaningful filename slug based on conversation content
4. **Saves to memory** - Creates a new file at `<workspace>/memory/YYYY-MM-DD-slug.md`
5. **Sends confirmation** - Notifies you with the file path

## Output Format

Memory files are created with the following format:

```markdown
# Session: 2026-01-16 14:30:00 UTC

- **Session Key**: agent:main:main
- **Session ID**: abc123def456
- **Source**: telegram
```

## Filename Examples

The LLM generates descriptive slugs based on your conversation:

- `2026-01-16-vendor-pitch.md` - Discussion about vendor evaluation
- `2026-01-16-api-design.md` - API architecture planning
- `2026-01-16-bug-fix.md` - Debugging session
- `2026-01-16-1430.md` - Fallback timestamp if slug generation fails

## Requirements

- **Config**: `workspace.dir` must be set (automatically configured during onboarding)

The hook uses your configured LLM provider to generate slugs, so it works with any provider (Anthropic, OpenAI, etc.).

## Configuration

The hook supports optional configuration:

| Option     | Type   | Default | Description                                                                          |
| ---------- | ------ | ------- | ------------------------------------------------------------------------------------ |
| `messages` | number | 15      | Number of user/assistant messages to include in the memory file                      |
| `every`    | number | 0       | Auto-save after every N sent messages (0 = disabled; requires `message:sent` events) |

Example configuration:

```json
{
  "hooks": {
    "internal": {
      "entries": {
        "session-memory": {
          "enabled": true,
          "messages": 25,
          "every": 10
        }
      }
    }
  }
}
```

### Auto-save behaviour

When `every` is set to a positive integer, the hook listens to `message:sent` events and increments a per-session counter. Once the counter reaches the configured value, a memory snapshot is written (tagged `source: auto-save`) and the counter resets to zero. The counter is in-memory only, so it resets when the gateway restarts — this is intentional; it avoids saving duplicate snapshots across restarts.

Auto-save is **disabled by default** (`every: 0`). Set it to a positive number to enable it:

```json
{ "every": 10 }
```

The hook automatically:

- Uses your workspace directory (`~/.openclaw/workspace` by default)
- Uses your configured LLM for slug generation
- Falls back to timestamp slugs if LLM is unavailable

## Disabling

To disable this hook:

```bash
openclaw hooks disable session-memory
```

Or remove it from your config:

```json
{
  "hooks": {
    "internal": {
      "entries": {
        "session-memory": { "enabled": false }
      }
    }
  }
}
```
