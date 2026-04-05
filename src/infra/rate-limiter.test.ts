import { describe, expect, it } from "vitest";
import type { OpenClawConfig } from "../config/config.js";
import { createMessageRateLimiter } from "./rate-limiter.js";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeConfig(overrides: OpenClawConfig["rateLimit"]): OpenClawConfig {
  return { rateLimit: overrides };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("createMessageRateLimiter", () => {
  it("allows messages within the per-user limit", () => {
    const limiter = createMessageRateLimiter(
      makeConfig({ perUser: 3, global: 100, windowMs: 60_000 }),
    );
    expect(limiter.check("slack", "alice").allowed).toBe(true);
    expect(limiter.check("slack", "alice").allowed).toBe(true);
    expect(limiter.check("slack", "alice").allowed).toBe(true);
    limiter.dispose();
  });

  it("rejects messages exceeding the per-user limit", () => {
    const limiter = createMessageRateLimiter(
      makeConfig({ perUser: 2, global: 100, windowMs: 60_000 }),
    );
    expect(limiter.check("slack", "alice").allowed).toBe(true);
    expect(limiter.check("slack", "alice").allowed).toBe(true);
    const result = limiter.check("slack", "alice");
    expect(result.allowed).toBe(false);
    expect(result.reason).toMatch(/too quickly/i);
    expect(result.retryAfterMs).toBeGreaterThan(0);
    limiter.dispose();
  });

  it("rejects messages exceeding the global limit", () => {
    const limiter = createMessageRateLimiter(
      makeConfig({ perUser: 100, global: 2, windowMs: 60_000 }),
    );
    // Two different users consume the global quota.
    expect(limiter.check("slack", "alice").allowed).toBe(true);
    expect(limiter.check("slack", "bob").allowed).toBe(true);
    // Third message — global is exhausted.
    const result = limiter.check("slack", "carol");
    expect(result.allowed).toBe(false);
    expect(result.reason).toMatch(/capacity/i);
    limiter.dispose();
  });

  it("per-user limits are isolated between users", () => {
    const limiter = createMessageRateLimiter(
      makeConfig({ perUser: 1, global: 100, windowMs: 60_000 }),
    );
    expect(limiter.check("slack", "alice").allowed).toBe(true);
    // alice is now blocked
    expect(limiter.check("slack", "alice").allowed).toBe(false);
    // bob is a different user — should still be allowed
    expect(limiter.check("slack", "bob").allowed).toBe(true);
    limiter.dispose();
  });

  it("per-channel limits are isolated between channels", () => {
    const limiter = createMessageRateLimiter(
      makeConfig({ perUser: 1, global: 100, windowMs: 60_000 }),
    );
    // Different channel — different per-user window
    expect(limiter.check("telegram", "alice").allowed).toBe(true);
    expect(limiter.check("slack", "alice").allowed).toBe(true);
    limiter.dispose();
  });

  it("returns the remaining count in the result", () => {
    const limiter = createMessageRateLimiter(
      makeConfig({ perUser: 5, global: 100, windowMs: 60_000 }),
    );
    const first = limiter.check("slack", "alice");
    expect(first.allowed).toBe(true);
    // remaining should decrease after each message
    expect(first.remaining).toBeLessThan(5);
    limiter.dispose();
  });

  it("uses defaults when config is empty", () => {
    const limiter = createMessageRateLimiter({});
    // Should allow one message without any config set
    const result = limiter.check("whatsapp", "user1");
    expect(result.allowed).toBe(true);
    limiter.dispose();
  });

  it("applies channel-specific overrides", () => {
    const limiter = createMessageRateLimiter(
      makeConfig({
        perUser: 100,
        global: 100,
        windowMs: 60_000,
        channelOverrides: {
          discord: { perUser: 1 },
        },
      }),
    );
    // Discord channel uses the override limit of 1.
    expect(limiter.check("discord", "alice").allowed).toBe(true);
    expect(limiter.check("discord", "alice").allowed).toBe(false);
    // Slack still uses the base limit of 100.
    expect(limiter.check("slack", "alice").allowed).toBe(true);
    limiter.dispose();
  });

  it("prune clears expired entries", () => {
    const limiter = createMessageRateLimiter(
      makeConfig({ perUser: 2, global: 100, windowMs: 60_000 }),
    );
    limiter.check("slack", "alice");
    // Calling prune before window expires keeps entries.
    limiter.prune();
    // Second call should still track state properly.
    expect(limiter.check("slack", "alice").allowed).toBe(true);
    limiter.dispose();
  });
});
