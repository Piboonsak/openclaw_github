/**
 * Message-level rate limiter for OpenClaw.
 *
 * Provides two independent sliding-window counters:
 *  - Per-user: keyed by (channel, accountId) — enforces per-user message quotas.
 *  - Global:   a single shared counter across all users and channels — guards
 *              against API cost spikes.
 *
 * Channel-aware overrides allow tighter or looser limits per channel
 * (e.g. Slack may have different limits than WhatsApp).
 *
 * Design notes:
 * - Pure in-memory Maps; no external dependencies.
 * - Periodic pruning prevents unbounded Map growth.
 * - The module is side-effect-free: callers create instances via
 *   {@link createMessageRateLimiter}.
 */

import type { OpenClawConfig } from "../config/config.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface MessageRateLimitResult {
  /** Whether the message is allowed to proceed. */
  allowed: boolean;
  /** Human-friendly rejection message when `allowed` is false. */
  reason: string;
  /** Milliseconds until the client may retry (0 when allowed). */
  retryAfterMs: number;
  /** Remaining quota in the current window (per-user or global, whichever is tighter). */
  remaining: number;
}

export interface MessageRateLimiter {
  /** Check whether a message from the given user on the given channel is allowed. */
  check(channel: string, accountId: string): MessageRateLimitResult;
  /** Remove expired entries to reclaim memory. */
  prune(): void;
  /** Dispose the limiter and cancel background prune timer. */
  dispose(): void;
}

// ---------------------------------------------------------------------------
// Internals
// ---------------------------------------------------------------------------

const DEFAULT_PER_USER = 60; // 60 messages per window
const DEFAULT_GLOBAL = 600; // 600 messages per window across all users
const DEFAULT_WINDOW_MS = 60_000; // 1 minute
const PRUNE_INTERVAL_MS = 60_000;

interface SlidingWindowEntry {
  /** Timestamps (epoch ms) of messages inside the current window. */
  timestamps: number[];
}

function createSlidingWindow(maxRequests: number, windowMs: number) {
  const entries = new Map<string, SlidingWindowEntry>();

  function slide(entry: SlidingWindowEntry, now: number): void {
    const cutoff = now - windowMs;
    entry.timestamps = entry.timestamps.filter((ts) => ts > cutoff);
  }

  function check(key: string): { allowed: boolean; remaining: number; retryAfterMs: number } {
    const now = Date.now();
    const entry = entries.get(key) ?? { timestamps: [] };
    slide(entry, now);
    const count = entry.timestamps.length;
    const remaining = Math.max(0, maxRequests - count);
    return {
      allowed: remaining > 0,
      remaining,
      // Approximate retry delay: time until the oldest request in the window falls out.
      retryAfterMs: remaining > 0 ? 0 : Math.max(0, entry.timestamps[0] + windowMs - now),
    };
  }

  function record(key: string): void {
    const now = Date.now();
    let entry = entries.get(key);
    if (!entry) {
      entry = { timestamps: [] };
      entries.set(key, entry);
    }
    slide(entry, now);
    entry.timestamps.push(now);
  }

  function prune(): void {
    const now = Date.now();
    for (const [key, entry] of entries) {
      slide(entry, now);
      if (entry.timestamps.length === 0) {
        entries.delete(key);
      }
    }
  }

  return { check, record, prune, size: () => entries.size };
}

// ---------------------------------------------------------------------------
// Public factory
// ---------------------------------------------------------------------------

/**
 * Resolve the effective limits for a given channel, merging base config with
 * any channel-specific overrides.
 */
function resolveChannelLimits(
  cfg: OpenClawConfig,
  channel: string,
): { perUser: number; global: number; windowMs: number } {
  const base = cfg.rateLimit;
  const override = base?.channelOverrides?.[channel];
  return {
    perUser: override?.perUser ?? base?.perUser ?? DEFAULT_PER_USER,
    global: override?.global ?? base?.global ?? DEFAULT_GLOBAL,
    windowMs: override?.windowMs ?? base?.windowMs ?? DEFAULT_WINDOW_MS,
  };
}

/**
 * Create a new {@link MessageRateLimiter} backed by the provided config.
 *
 * The returned instance shares state across all calls; create one per gateway
 * process and reuse it.
 */
export function createMessageRateLimiter(cfg: OpenClawConfig): MessageRateLimiter {
  const base = cfg.rateLimit;

  // Per-user windows — keyed by channel so each channel gets its own limits.
  const perUserWindows = new Map<string, ReturnType<typeof createSlidingWindow>>();

  // Single shared global window (all channels combined) for API cost protection.
  const sharedGlobal = createSlidingWindow(
    base?.global ?? DEFAULT_GLOBAL,
    base?.windowMs ?? DEFAULT_WINDOW_MS,
  );

  // Per-channel global windows — only created for channels that have a
  // channelOverrides.global value, which overrides (rather than adds to) the
  // shared global limit for that specific channel.
  const channelGlobalWindows = new Map<string, ReturnType<typeof createSlidingWindow>>();

  const pruneTimer = setInterval(() => prune(), PRUNE_INTERVAL_MS);
  if (pruneTimer.unref) {
    pruneTimer.unref();
  }

  function getPerUserWindow(
    channel: string,
    limits: ReturnType<typeof resolveChannelLimits>,
  ): ReturnType<typeof createSlidingWindow> {
    const existing = perUserWindows.get(channel);
    if (existing) {
      return existing;
    }
    const w = createSlidingWindow(limits.perUser, limits.windowMs);
    perUserWindows.set(channel, w);
    return w;
  }

  function getGlobalWindow(
    channel: string,
    limits: ReturnType<typeof resolveChannelLimits>,
  ): ReturnType<typeof createSlidingWindow> {
    // If there's a channel-specific global override, use a separate window for
    // that channel rather than the shared one.
    if (base?.channelOverrides?.[channel]?.global !== undefined) {
      const existing = channelGlobalWindows.get(channel);
      if (existing) {
        return existing;
      }
      const w = createSlidingWindow(limits.global, limits.windowMs);
      channelGlobalWindows.set(channel, w);
      return w;
    }
    return sharedGlobal;
  }

  function check(channel: string, accountId: string): MessageRateLimitResult {
    const limits = resolveChannelLimits(cfg, channel);
    const perUserKey = `${channel}:${accountId}`;

    const userWindow = getPerUserWindow(channel, limits);
    const globalWindow = getGlobalWindow(channel, limits);

    const userResult = userWindow.check(perUserKey);
    const globalResult = globalWindow.check("global");

    // Enforce per-user limit first (most common rejection path).
    if (!userResult.allowed) {
      const seconds = Math.ceil(userResult.retryAfterMs / 1000);
      return {
        allowed: false,
        reason: `You're sending messages too quickly. Please wait ${seconds} second${seconds !== 1 ? "s" : ""} before trying again.`,
        retryAfterMs: userResult.retryAfterMs,
        remaining: 0,
      };
    }

    // Then enforce global limit.
    if (!globalResult.allowed) {
      const seconds = Math.ceil(globalResult.retryAfterMs / 1000);
      return {
        allowed: false,
        reason: `The service is currently at capacity. Please try again in ${seconds} second${seconds !== 1 ? "s" : ""}.`,
        retryAfterMs: globalResult.retryAfterMs,
        remaining: 0,
      };
    }

    // Both checks passed — record the message.
    userWindow.record(perUserKey);
    globalWindow.record("global");

    return {
      allowed: true,
      reason: "",
      retryAfterMs: 0,
      remaining: Math.min(userResult.remaining - 1, globalResult.remaining - 1),
    };
  }

  function prune(): void {
    for (const w of perUserWindows.values()) {
      w.prune();
    }
    sharedGlobal.prune();
    for (const w of channelGlobalWindows.values()) {
      w.prune();
    }
  }

  function dispose(): void {
    clearInterval(pruneTimer);
    perUserWindows.clear();
    channelGlobalWindows.clear();
  }

  return { check, prune, dispose };
}
