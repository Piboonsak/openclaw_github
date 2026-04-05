import { describe, expect, it } from "vitest";
import {
  DEFAULT_MEMORY_FLUSH_PROMPT,
  DEFAULT_MEMORY_FLUSH_SOFT_TOKENS,
  resolveMemoryFlushSettings,
  shouldRunMemoryFlush,
} from "../../src/auto-reply/reply/memory-flush.js";
import type { OpenClawConfig } from "../../src/config/config.js";

// Regression suite: NongKung agent memory.md load-at-startup capability.
// Verifies that memory flush settings are resolved from config correctly and
// that the flush threshold gates work as expected when a session grows large.

describe("NongKung regression — memory.md loaded at startup", () => {
  it("memory flush is enabled by default when no config is provided", () => {
    const settings = resolveMemoryFlushSettings(undefined);
    expect(settings).not.toBeNull();
    expect(settings?.enabled).toBe(true);
  });

  it("memory flush is enabled by default with an empty agent config", () => {
    const cfg: OpenClawConfig = {};
    const settings = resolveMemoryFlushSettings(cfg);
    expect(settings).not.toBeNull();
    expect(settings?.enabled).toBe(true);
  });

  it("default flush prompt instructs agent to write memory files", () => {
    expect(DEFAULT_MEMORY_FLUSH_PROMPT).toContain("memory");
    expect(DEFAULT_MEMORY_FLUSH_PROMPT).toContain("YYYY-MM-DD");
  });

  it("resolveMemoryFlushSettings uses default prompt when none configured", () => {
    const settings = resolveMemoryFlushSettings({});
    expect(settings?.prompt).toBeTruthy();
    expect(settings?.prompt).toContain("memory");
  });

  it("resolveMemoryFlushSettings uses default soft threshold tokens when unconfigured", () => {
    const settings = resolveMemoryFlushSettings({});
    expect(settings?.softThresholdTokens).toBe(DEFAULT_MEMORY_FLUSH_SOFT_TOKENS);
  });

  it("respects a custom flush prompt from config", () => {
    const customPrompt = "Store all key decisions to memory/decisions.md.";
    const cfg: OpenClawConfig = {
      agents: {
        defaults: {
          compaction: {
            memoryFlush: {
              enabled: true,
              prompt: customPrompt,
            },
          },
        },
      },
    };
    const settings = resolveMemoryFlushSettings(cfg);
    // ensureNoReplyHint appends a NO_REPLY hint when the custom prompt lacks it.
    expect(settings?.prompt).toContain(customPrompt);
  });

  it("can disable memory flush via config", () => {
    const cfg: OpenClawConfig = {
      agents: {
        defaults: {
          compaction: {
            memoryFlush: { enabled: false },
          },
        },
      },
    };
    const settings = resolveMemoryFlushSettings(cfg);
    expect(settings).toBeNull();
  });

  it("shouldRunMemoryFlush is false when session has no tokens", () => {
    const result = shouldRunMemoryFlush({
      entry: {
        totalTokens: 0,
        totalTokensFresh: undefined,
        compactionCount: 0,
        memoryFlushCompactionCount: undefined,
      },
      contextWindowTokens: 128_000,
      reserveTokensFloor: 20_000,
      softThresholdTokens: DEFAULT_MEMORY_FLUSH_SOFT_TOKENS,
    });
    expect(result).toBe(false);
  });

  it("shouldRunMemoryFlush is false when session is well within context window", () => {
    const result = shouldRunMemoryFlush({
      entry: {
        totalTokens: 1_000,
        totalTokensFresh: undefined,
        compactionCount: 0,
        memoryFlushCompactionCount: undefined,
      },
      contextWindowTokens: 128_000,
      reserveTokensFloor: 20_000,
      softThresholdTokens: DEFAULT_MEMORY_FLUSH_SOFT_TOKENS,
    });
    expect(result).toBe(false);
  });

  it("shouldRunMemoryFlush triggers when session exceeds soft threshold", () => {
    // threshold = contextWindowTokens - reserveTokensFloor - softThresholdTokens
    //           = 128_000 - 20_000 - 4_000 = 104_000
    const result = shouldRunMemoryFlush({
      entry: {
        totalTokens: 110_000,
        totalTokensFresh: undefined,
        compactionCount: 0,
        memoryFlushCompactionCount: undefined,
      },
      contextWindowTokens: 128_000,
      reserveTokensFloor: 20_000,
      softThresholdTokens: DEFAULT_MEMORY_FLUSH_SOFT_TOKENS,
    });
    expect(result).toBe(true);
  });
});
