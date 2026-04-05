/**
 * Tests for the auto-save feature in the session-memory hook.
 *
 * Auto-save listens on `message:sent` events and writes a memory snapshot
 * once the per-session-key counter reaches the configured `every` threshold.
 */

import fs from "node:fs/promises";
import path from "node:path";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import type { OpenClawConfig } from "../../../config/config.js";
import { makeTempWorkspace, writeWorkspaceFile } from "../../../test-helpers/workspace.js";
import { createHookEvent } from "../../hooks.js";
import type { HookHandler } from "../../hooks.js";
import type { _resetAutoSaveCountersForTest } from "./handler.js";

// Module-level mocks must be declared before any imports of the mocked modules.
// The handler imports loadConfig and the sessions helpers; we replace them here
// so tests can control what they return without touching the filesystem.
vi.mock("../../llm-slug-generator.js", () => ({
  generateSlugViaLLM: vi.fn().mockResolvedValue("auto-slug"),
}));
vi.mock("../../../config/config.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../config/config.js")>();
  return {
    ...actual,
    loadConfig: vi.fn(),
  };
});
vi.mock("../../../config/sessions.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../config/sessions.js")>();
  return {
    ...actual,
    loadSessionStore: vi.fn(),
    resolveStorePath: vi.fn().mockReturnValue("/tmp/fake/sessions.json"),
  };
});

// Import the mocked modules so we can configure them per-test.
const { loadConfig } = await import("../../../config/config.js");
const { loadSessionStore, resolveStorePath } = await import("../../../config/sessions.js");

let handler: HookHandler;
let resetCounters: typeof _resetAutoSaveCountersForTest;

beforeAll(async () => {
  const mod = await import("./handler.js");
  handler = mod.default;
  resetCounters = mod._resetAutoSaveCountersForTest;
});

afterEach(() => {
  // Clear per-session counters so tests don't bleed into each other.
  resetCounters();
  vi.clearAllMocks();
});

function makeSentEvent(sessionKey: string) {
  return createHookEvent("message", "sent", sessionKey, {
    to: "+1234567890",
    content: "Hello",
    success: true,
    channelId: "telegram",
  });
}

function makeCfgWithEvery(tempDir: string, every: number): OpenClawConfig {
  return {
    agents: { defaults: { workspace: tempDir } },
    hooks: {
      internal: {
        entries: {
          "session-memory": { enabled: true, every },
        },
      },
    },
  } satisfies OpenClawConfig;
}

describe("session-memory hook — auto-save", () => {
  it("ignores message:sent when loadConfig throws", async () => {
    const tempDir = await makeTempWorkspace("openclaw-session-memory-auto-");
    vi.mocked(loadConfig).mockImplementation(() => {
      throw new Error("No config file");
    });

    await handler(makeSentEvent("agent:main:main"));

    // Memory dir must not be created.
    await expect(fs.access(path.join(tempDir, "memory"))).rejects.toThrow();
  });

  it("ignores message:sent when every is not set", async () => {
    const tempDir = await makeTempWorkspace("openclaw-session-memory-auto-");
    vi.mocked(loadConfig).mockReturnValue({
      agents: { defaults: { workspace: tempDir } },
    } satisfies OpenClawConfig);

    await handler(makeSentEvent("agent:main:main"));

    await expect(fs.access(path.join(tempDir, "memory"))).rejects.toThrow();
  });

  it("ignores message:sent when every is zero", async () => {
    const tempDir = await makeTempWorkspace("openclaw-session-memory-auto-");
    vi.mocked(loadConfig).mockReturnValue(makeCfgWithEvery(tempDir, 0));

    await handler(makeSentEvent("agent:main:main"));

    await expect(fs.access(path.join(tempDir, "memory"))).rejects.toThrow();
  });

  it("ignores message:received events", async () => {
    const tempDir = await makeTempWorkspace("openclaw-session-memory-auto-");
    vi.mocked(loadConfig).mockReturnValue(makeCfgWithEvery(tempDir, 1));

    const receivedEvent = createHookEvent("message", "received", "agent:main:main", {
      from: "+1234567890",
      content: "Hello",
      channelId: "telegram",
    });
    await handler(receivedEvent);

    // message:received should not trigger auto-save.
    await expect(fs.access(path.join(tempDir, "memory"))).rejects.toThrow();
  });

  it("does not save before the every threshold is reached", async () => {
    const tempDir = await makeTempWorkspace("openclaw-session-memory-auto-");
    const sessionsDir = path.join(tempDir, "sessions");
    await fs.mkdir(sessionsDir, { recursive: true });

    const sessionFile = await writeWorkspaceFile({
      dir: sessionsDir,
      name: "session.jsonl",
      content: JSON.stringify({ type: "message", message: { role: "user", content: "Hello" } }),
    });

    vi.mocked(loadConfig).mockReturnValue(makeCfgWithEvery(tempDir, 3));
    vi.mocked(resolveStorePath).mockReturnValue("/tmp/fake/sessions.json");
    vi.mocked(loadSessionStore).mockReturnValue({
      "agent:main:main": {
        sessionId: "sess-below-thresh",
        updatedAt: Date.now(),
        sessionFile,
      },
    });

    // Send 2 messages — threshold is 3, so no save yet.
    await handler(makeSentEvent("agent:main:main"));
    await handler(makeSentEvent("agent:main:main"));

    const memoryDir = path.join(tempDir, "memory");
    const files = await fs.readdir(memoryDir).catch(() => [] as string[]);
    expect(files.length).toBe(0);
  });

  it("saves exactly once when every threshold is reached", async () => {
    const tempDir = await makeTempWorkspace("openclaw-session-memory-auto-");
    const sessionsDir = path.join(tempDir, "sessions");
    await fs.mkdir(sessionsDir, { recursive: true });

    const sessionContent = [
      JSON.stringify({
        type: "message",
        message: { role: "user", content: "Trigger auto-save" },
      }),
      JSON.stringify({
        type: "message",
        message: { role: "assistant", content: "Auto-save reply" },
      }),
    ].join("\n");

    const sessionFile = await writeWorkspaceFile({
      dir: sessionsDir,
      name: "auto-thresh.jsonl",
      content: sessionContent,
    });

    const cfg = makeCfgWithEvery(tempDir, 2);
    vi.mocked(loadConfig).mockReturnValue(cfg);
    vi.mocked(resolveStorePath).mockReturnValue("/tmp/fake/sessions.json");
    vi.mocked(loadSessionStore).mockReturnValue({
      "auto:thresh:key": {
        sessionId: "auto-thresh-id",
        updatedAt: Date.now(),
        sessionFile,
      },
    });

    const sessionKey = "auto:thresh:key";

    // First message: counter = 1, threshold = 2 → no save.
    await handler(makeSentEvent(sessionKey));
    const memoryDir = path.join(tempDir, "memory");
    const afterFirst = await fs.readdir(memoryDir).catch(() => [] as string[]);
    expect(afterFirst.length).toBe(0);

    // Second message: counter = 2, threshold = 2 → save fires.
    await handler(makeSentEvent(sessionKey));
    const afterSecond = await fs.readdir(memoryDir).catch(() => [] as string[]);
    expect(afterSecond.length).toBe(1);

    const content = await fs.readFile(path.join(memoryDir, afterSecond[0]), "utf-8");
    expect(content).toContain("**Source**: auto-save");
    expect(content).toContain("Trigger auto-save");
    expect(content).toContain("Auto-save reply");
  });

  it("resets counter after save and saves again after another cycle", async () => {
    const tempDir = await makeTempWorkspace("openclaw-session-memory-auto-cycle-");
    const sessionsDir = path.join(tempDir, "sessions");
    await fs.mkdir(sessionsDir, { recursive: true });

    const sessionFile = await writeWorkspaceFile({
      dir: sessionsDir,
      name: "cycle.jsonl",
      content: JSON.stringify({
        type: "message",
        message: { role: "user", content: "Cycle test" },
      }),
    });

    const cfg = makeCfgWithEvery(tempDir, 2);
    vi.mocked(loadConfig).mockReturnValue(cfg);
    vi.mocked(resolveStorePath).mockReturnValue("/tmp/fake/sessions.json");
    vi.mocked(loadSessionStore).mockReturnValue({
      "cycle:session:key": {
        sessionId: "cycle-id",
        updatedAt: Date.now(),
        sessionFile,
      },
    });

    const sessionKey = "cycle:session:key";
    const memoryDir = path.join(tempDir, "memory");

    // First cycle: 2 messages → 1 save.
    await handler(makeSentEvent(sessionKey));
    await handler(makeSentEvent(sessionKey));
    const afterFirstCycle = await fs.readdir(memoryDir).catch(() => []);
    expect(afterFirstCycle.length).toBeGreaterThanOrEqual(1);

    // Record file mtime after first cycle.
    const firstFileStat = await fs.stat(path.join(memoryDir, afterFirstCycle[0]));
    const mtimeAfterFirst = firstFileStat.mtimeMs;

    // Wait briefly so the second save gets a different mtime.
    await new Promise((resolve) => setTimeout(resolve, 10));

    // Second cycle: 2 more messages → counter reset, so save fires again.
    await handler(makeSentEvent(sessionKey));
    await handler(makeSentEvent(sessionKey));

    // The saved file(s) must have been written during the second cycle.
    // Since slug/date may be identical, we check that the mtime advanced.
    const allFiles = await fs.readdir(memoryDir).catch(() => [] as string[]);
    expect(allFiles.length).toBeGreaterThanOrEqual(1);
    const anyUpdated = await Promise.all(
      allFiles.map((f) =>
        fs.stat(path.join(memoryDir, f)).then((s) => s.mtimeMs > mtimeAfterFirst),
      ),
    );
    expect(anyUpdated.some(Boolean)).toBe(true);
  });
});
