import { describe, expect, it } from "vitest";
import {
  resolveFallbackTransition,
  resolveActiveFallbackState,
  type FallbackNoticeState,
} from "../../src/auto-reply/fallback-state.js";

// Regression suite: NongKung agent model fallback capability.
// Verifies that when the primary model fails, the fallback mechanism
// activates correctly and surfaces the right reason to the user.

const PRIMARY_PROVIDER = "openrouter";
const PRIMARY_MODEL = "anthropic/claude-opus-4";
const FALLBACK_PROVIDER = "openrouter";
const FALLBACK_MODEL = "anthropic/claude-sonnet-4";

const makeBaseAttempt = (overrides: Partial<{ reason: string; error: string }> = {}) => ({
  provider: PRIMARY_PROVIDER,
  model: PRIMARY_MODEL,
  error: overrides.error ?? "Provider is in cooldown",
  reason: (overrides.reason ?? "rate_limit") as "rate_limit",
});

describe("NongKung regression — model fallback when primary fails", () => {
  it("activates fallback when primary model is rate-limited", () => {
    const result = resolveFallbackTransition({
      selectedProvider: PRIMARY_PROVIDER,
      selectedModel: PRIMARY_MODEL,
      activeProvider: FALLBACK_PROVIDER,
      activeModel: FALLBACK_MODEL,
      attempts: [makeBaseAttempt({ reason: "rate_limit" })],
      state: {},
    });

    expect(result.fallbackActive).toBe(true);
    expect(result.fallbackTransitioned).toBe(true);
    expect(result.fallbackCleared).toBe(false);
    expect(result.stateChanged).toBe(true);
  });

  it("records the selected and active model in fallback state", () => {
    const result = resolveFallbackTransition({
      selectedProvider: PRIMARY_PROVIDER,
      selectedModel: PRIMARY_MODEL,
      activeProvider: FALLBACK_PROVIDER,
      activeModel: FALLBACK_MODEL,
      attempts: [makeBaseAttempt()],
      state: {},
    });

    // nextState stores full provider/model refs formatted as "provider/model".
    // e.g. "openrouter" + "anthropic/claude-opus-4" → "openrouter/anthropic/claude-opus-4"
    expect(result.nextState.selectedModel).toBe(`${PRIMARY_PROVIDER}/${PRIMARY_MODEL}`);
    expect(result.nextState.activeModel).toBe(`${FALLBACK_PROVIDER}/${FALLBACK_MODEL}`);
  });

  it("summarizes fallback reason from the attempt", () => {
    const result = resolveFallbackTransition({
      selectedProvider: PRIMARY_PROVIDER,
      selectedModel: PRIMARY_MODEL,
      activeProvider: FALLBACK_PROVIDER,
      activeModel: FALLBACK_MODEL,
      attempts: [makeBaseAttempt({ reason: "rate_limit" })],
      state: {},
    });

    expect(result.reasonSummary).toBe("rate limit");
  });

  it("clears fallback when primary model recovers", () => {
    const state: FallbackNoticeState = {
      fallbackNoticeSelectedModel: PRIMARY_MODEL,
      fallbackNoticeActiveModel: FALLBACK_MODEL,
      fallbackNoticeReason: "rate limit",
    };

    const result = resolveFallbackTransition({
      selectedProvider: PRIMARY_PROVIDER,
      selectedModel: PRIMARY_MODEL,
      activeProvider: PRIMARY_PROVIDER,
      activeModel: PRIMARY_MODEL,
      attempts: [],
      state,
    });

    expect(result.fallbackCleared).toBe(true);
    expect(result.fallbackActive).toBe(false);
  });

  it("does not activate fallback when selected and active models are the same", () => {
    const result = resolveFallbackTransition({
      selectedProvider: PRIMARY_PROVIDER,
      selectedModel: PRIMARY_MODEL,
      activeProvider: PRIMARY_PROVIDER,
      activeModel: PRIMARY_MODEL,
      attempts: [],
      state: {},
    });

    expect(result.fallbackActive).toBe(false);
    expect(result.fallbackTransitioned).toBe(false);
    expect(result.stateChanged).toBe(false);
  });

  it("resolveActiveFallbackState detects active fallback from persisted state", () => {
    const state: FallbackNoticeState = {
      fallbackNoticeSelectedModel: PRIMARY_MODEL,
      fallbackNoticeActiveModel: FALLBACK_MODEL,
      fallbackNoticeReason: "rate limit",
    };

    const resolved = resolveActiveFallbackState({
      selectedModelRef: PRIMARY_MODEL,
      activeModelRef: FALLBACK_MODEL,
      state,
    });

    expect(resolved.active).toBe(true);
    expect(resolved.reason).toBe("rate limit");
  });

  it("resolveActiveFallbackState is inactive when persisted state does not match runtime", () => {
    const state: FallbackNoticeState = {
      fallbackNoticeSelectedModel: "other/model",
      fallbackNoticeActiveModel: FALLBACK_MODEL,
      fallbackNoticeReason: "rate limit",
    };

    const resolved = resolveActiveFallbackState({
      selectedModelRef: PRIMARY_MODEL,
      activeModelRef: FALLBACK_MODEL,
      state,
    });

    expect(resolved.active).toBe(false);
  });
});
