/**
 * Session memory hook handler
 *
 * Saves session context to memory when /new or /reset command is triggered,
 * or automatically after every N messages when `every` is configured.
 * Creates a new dated memory file with LLM-generated slug.
 */

import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { resolveAgentWorkspaceDir } from "../../../agents/agent-scope.js";
import type { OpenClawConfig } from "../../../config/config.js";
import { loadConfig } from "../../../config/config.js";
import { resolveStateDir } from "../../../config/paths.js";
import { loadSessionStore, resolveStorePath } from "../../../config/sessions.js";
import { createSubsystemLogger } from "../../../logging/subsystem.js";
import { resolveAgentIdFromSessionKey } from "../../../routing/session-key.js";
import { resolveHookConfig } from "../../config.js";
import type { HookHandler } from "../../hooks.js";
import { generateSlugViaLLM } from "../../llm-slug-generator.js";
import { findPreviousSessionFile, getRecentSessionContentWithResetFallback } from "./transcript.js";

// In-memory counter for auto-save: tracks message count per session key since last save.
// Node.js is single-threaded; the gateway serialises execution per session lane, so this
// map does not need a mutex or atomic operations.
const autoSaveCounters = new Map<string, number>();

/** @internal For testing only. Resets all auto-save counters. */
export function _resetAutoSaveCountersForTest(): void {
  autoSaveCounters.clear();
}

const log = createSubsystemLogger("hooks/session-memory");

type SaveSessionMemoryParams = {
  sessionKey: string;
  sessionFile: string | undefined;
  sessionId: string;
  cfg: OpenClawConfig | undefined;
  now: Date;
  source: string;
  hookConfig: Record<string, unknown> | undefined;
  workspaceDir: string;
};

/**
 * Core save logic: writes session context to a dated memory file.
 * Used by both the /new|/reset command handler and the auto-save path.
 */
async function saveMemoryEntry(params: SaveSessionMemoryParams): Promise<void> {
  const { sessionKey, sessionFile, sessionId, cfg, now, source, hookConfig, workspaceDir } = params;

  const memoryDir = path.join(workspaceDir, "memory");
  await fs.mkdir(memoryDir, { recursive: true });

  const dateStr = now.toISOString().split("T")[0]; // YYYY-MM-DD

  // Read message count from hook config (default: 15)
  const messageCount =
    typeof hookConfig?.messages === "number" && hookConfig.messages > 0 ? hookConfig.messages : 15;

  let slug: string | null = null;
  let sessionContent: string | null = null;

  if (sessionFile) {
    // Get recent conversation content, with fallback to rotated reset transcript.
    sessionContent = await getRecentSessionContentWithResetFallback(sessionFile, messageCount);
    log.debug("Session content loaded", {
      length: sessionContent?.length ?? 0,
      messageCount,
    });

    // Avoid calling the model provider in unit tests; keep hooks fast and deterministic.
    const isTestEnv =
      process.env.OPENCLAW_TEST_FAST === "1" ||
      process.env.VITEST === "true" ||
      process.env.VITEST === "1" ||
      process.env.NODE_ENV === "test";
    const allowLlmSlug = !isTestEnv && hookConfig?.llmSlug !== false;

    if (sessionContent && cfg && allowLlmSlug) {
      log.debug("Calling generateSlugViaLLM...");
      slug = await generateSlugViaLLM({ sessionContent, cfg });
      log.debug("Generated slug", { slug });
    }
  }

  // If no slug, use timestamp
  if (!slug) {
    const timeSlug = now.toISOString().split("T")[1].split(".")[0].replace(/:/g, "");
    slug = timeSlug.slice(0, 4); // HHMM
    log.debug("Using fallback timestamp slug", { slug });
  }

  // Create filename with date and slug
  const filename = `${dateStr}-${slug}.md`;
  const memoryFilePath = path.join(memoryDir, filename);
  log.debug("Memory file path resolved", {
    filename,
    path: memoryFilePath.replace(os.homedir(), "~"),
  });

  // Format time as HH:MM:SS UTC
  const timeStr = now.toISOString().split("T")[1].split(".")[0];

  // Build Markdown entry
  const entryParts = [
    `# Session: ${dateStr} ${timeStr} UTC`,
    "",
    `- **Session Key**: ${sessionKey}`,
    `- **Session ID**: ${sessionId}`,
    `- **Source**: ${source}`,
    "",
  ];

  // Include conversation content if available
  if (sessionContent) {
    entryParts.push("## Conversation Summary", "", sessionContent, "");
  }

  const entry = entryParts.join("\n");

  await fs.writeFile(memoryFilePath, entry, "utf-8");
  log.debug("Memory file written successfully");

  const relPath = memoryFilePath.replace(os.homedir(), "~");
  log.info(`Session context saved to ${relPath}`);
}

/**
 * Resolve an absolute session file path from a potentially relative path stored in the
 * session store. When sessions are written by older versions the path may be relative to
 * the agent's sessions directory.
 */
function resolveAbsoluteSessionFile(sessionFile: string, agentId: string): string {
  if (path.isAbsolute(sessionFile)) {
    return sessionFile;
  }
  const sessionsDir = path.join(
    resolveStateDir(process.env, os.homedir),
    "agents",
    agentId,
    "sessions",
  );
  return path.join(sessionsDir, sessionFile);
}

/**
 * Resolve session file and cfg for a session key by loading the session store.
 * Used by the auto-save path where context does not carry these values.
 */
function resolveSessionFileFromStore(sessionKey: string): {
  cfg: OpenClawConfig;
  sessionFile: string | undefined;
  sessionId: string | undefined;
} {
  const cfg = loadConfig();
  const agentId = resolveAgentIdFromSessionKey(sessionKey);
  const storePath = resolveStorePath(cfg.session?.store, { agentId });
  const store = loadSessionStore(storePath);
  const entry = store[sessionKey.toLowerCase()] ?? store[sessionKey];
  if (!entry) {
    log.debug("Session entry not found in store for auto-save", { sessionKey, storePath });
  }
  return {
    cfg,
    sessionFile: entry?.sessionFile,
    sessionId: entry?.sessionId,
  };
}

/**
 * Handle auto-save on message:sent events.
 * Increments the per-session counter and triggers a save when the `every` threshold is reached.
 */
async function handleAutoSave(event: Parameters<HookHandler>[0]): Promise<void> {
  if (event.type !== "message" || event.action !== "sent") {
    return;
  }

  // Load config to check if auto-save is configured for this hook.
  // Use a best-effort sync load; skip auto-save if config is unavailable.
  let cfg: OpenClawConfig;
  try {
    cfg = loadConfig();
  } catch {
    return;
  }

  const hookConfig = resolveHookConfig(cfg, "session-memory");
  const everyMessages =
    typeof hookConfig?.every === "number" && hookConfig.every > 0 ? hookConfig.every : 0;

  // Auto-save disabled if `every` is not set or zero.
  if (everyMessages <= 0) {
    return;
  }

  const sessionKey = event.sessionKey;
  if (!sessionKey) {
    return;
  }

  // Increment counter for this session key.
  const current = (autoSaveCounters.get(sessionKey) ?? 0) + 1;
  if (current < everyMessages) {
    autoSaveCounters.set(sessionKey, current);
    return;
  }

  // Threshold reached — delete key (avoids accumulating stale entries) and run save.
  autoSaveCounters.delete(sessionKey);

  log.debug("Auto-save threshold reached", { sessionKey, every: everyMessages });

  const agentId = resolveAgentIdFromSessionKey(sessionKey);
  const workspaceDir = resolveAgentWorkspaceDir(cfg, agentId);

  // Look up session file and sessionId from the session store.
  let sessionFile: string | undefined;
  let sessionId: string;
  try {
    const resolved = resolveSessionFileFromStore(sessionKey);
    sessionFile = resolved.sessionFile
      ? resolveAbsoluteSessionFile(resolved.sessionFile, agentId)
      : undefined;
    sessionId = resolved.sessionId ?? "unknown";
  } catch {
    sessionId = "unknown";
  }

  await saveMemoryEntry({
    sessionKey,
    sessionFile,
    sessionId,
    cfg,
    now: event.timestamp,
    source: "auto-save",
    hookConfig: hookConfig as Record<string, unknown> | undefined,
    workspaceDir,
  });
}

/**
 * Save session context to memory when /new or /reset command is triggered
 */
const saveSessionToMemory: HookHandler = async (event) => {
  // Handle auto-save on message:sent events.
  if (event.type === "message" && event.action === "sent") {
    try {
      await handleAutoSave(event);
    } catch (err) {
      if (err instanceof Error) {
        log.error("Auto-save failed", {
          errorName: err.name,
          errorMessage: err.message,
        });
      } else {
        log.error("Auto-save failed", { error: String(err) });
      }
    }
    return;
  }

  // Only trigger on reset/new commands for the explicit-save path.
  const isResetCommand = event.action === "new" || event.action === "reset";
  if (event.type !== "command" || !isResetCommand) {
    return;
  }

  try {
    log.debug("Hook triggered for reset/new command", { action: event.action });

    const context = event.context || {};
    const cfg = context.cfg as OpenClawConfig | undefined;
    const contextWorkspaceDir =
      typeof context.workspaceDir === "string" && context.workspaceDir.trim().length > 0
        ? context.workspaceDir
        : undefined;
    const agentId = resolveAgentIdFromSessionKey(event.sessionKey);
    const workspaceDir =
      contextWorkspaceDir ||
      (cfg
        ? resolveAgentWorkspaceDir(cfg, agentId)
        : path.join(resolveStateDir(process.env, os.homedir), "workspace"));

    // Generate descriptive slug from session using LLM
    // Prefer previousSessionEntry (old session before /new) over current (which may be empty)
    const sessionEntry = (context.previousSessionEntry || context.sessionEntry || {}) as Record<
      string,
      unknown
    >;
    const currentSessionId = sessionEntry.sessionId as string;
    let currentSessionFile = (sessionEntry.sessionFile as string) || undefined;

    // If sessionFile is empty or looks like a new/reset file, try to find the previous session file.
    if (!currentSessionFile || currentSessionFile.includes(".reset.")) {
      const sessionsDirs = new Set<string>();
      if (currentSessionFile) {
        sessionsDirs.add(path.dirname(currentSessionFile));
      }
      sessionsDirs.add(path.join(workspaceDir, "sessions"));

      for (const sessionsDir of sessionsDirs) {
        const recoveredSessionFile = await findPreviousSessionFile({
          sessionsDir,
          currentSessionFile,
          sessionId: currentSessionId,
        });
        if (!recoveredSessionFile) {
          continue;
        }
        currentSessionFile = recoveredSessionFile;
        log.debug("Found previous session file", { file: currentSessionFile });
        break;
      }
    }

    log.debug("Session context resolved", {
      sessionId: currentSessionId,
      sessionFile: currentSessionFile,
      hasCfg: Boolean(cfg),
    });

    const hookConfig = resolveHookConfig(cfg, "session-memory");

    await saveMemoryEntry({
      sessionKey: event.sessionKey,
      sessionFile: currentSessionFile || undefined,
      sessionId: currentSessionId || "unknown",
      cfg,
      now: new Date(event.timestamp),
      source: (context.commandSource as string) || "unknown",
      hookConfig: hookConfig as Record<string, unknown> | undefined,
      workspaceDir,
    });
  } catch (err) {
    if (err instanceof Error) {
      log.error("Failed to save session memory", {
        errorName: err.name,
        errorMessage: err.message,
        stack: err.stack,
      });
    } else {
      log.error("Failed to save session memory", { error: String(err) });
    }
  }
};

export default saveSessionToMemory;
