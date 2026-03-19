import { beforeEach, describe, expect, it, vi } from "vitest";
import type { OpenClawConfig } from "../config/config.js";
import type { AuthProfileStore } from "./auth-profiles.js";

vi.mock("./auth-profiles.js", () => ({
  ensureAuthProfileStore: vi.fn(),
  getSoonestCooldownExpiry: vi.fn(),
  isProfileInCooldown: vi.fn(),
  resolveAuthProfileOrder: vi.fn(),
}));

import { ensureAuthProfileStore, isProfileInCooldown, resolveAuthProfileOrder } from "./auth-profiles.js";
import { runWithModelFallback } from "./model-fallback.js";

const mockedEnsureAuthProfileStore = vi.mocked(ensureAuthProfileStore);
const mockedIsProfileInCooldown = vi.mocked(isProfileInCooldown);
const mockedResolveAuthProfileOrder = vi.mocked(resolveAuthProfileOrder);

describe("runWithModelFallback selected-model 404 recovery", () => {
  beforeEach(() => {
    const fakeStore: AuthProfileStore = {
      version: 1,
      profiles: {},
    };
    mockedEnsureAuthProfileStore.mockReturnValue(fakeStore);
    mockedResolveAuthProfileOrder.mockImplementation(({ provider }: { provider: string }) => {
      if (provider === "openrouter") {
        return ["openrouter-profile-1"];
      }
      if (provider === "anthropic") {
        return ["anthropic-profile-1"];
      }
      return [];
    });
    mockedIsProfileInCooldown.mockReturnValue(false);
  });

  it("falls back to the configured primary when an override model has no allowed providers", async () => {
    const cfg = {
      agents: {
        defaults: {
          model: {
            primary: "anthropic/claude-haiku-3-5",
            fallbacks: ["openai/gpt-4.1-mini"],
          },
        },
      },
    } as OpenClawConfig;

    const run = vi
      .fn()
      .mockRejectedValueOnce(
        Object.assign(new Error("404 No allowed providers are available for the selected model."), {
          status: 404,
        }),
      )
      .mockResolvedValueOnce("primary-recovered");

    const result = await runWithModelFallback({
      cfg,
      provider: "openrouter",
      model: "qwen/qwen3.5-122b-a10b",
      run,
    });

    expect(result.result).toBe("primary-recovered");
    expect(result.provider).toBe("anthropic");
    expect(result.model).toBe("claude-haiku-3-5");
    expect(result.attempts).toContainEqual(
      expect.objectContaining({
        provider: "openrouter",
        model: "qwen/qwen3.5-122b-a10b",
        reason: "model_not_found",
        status: 404,
      }),
    );
    expect(run).toHaveBeenNthCalledWith(1, "openrouter", "qwen/qwen3.5-122b-a10b");
    expect(run).toHaveBeenNthCalledWith(2, "anthropic", "claude-haiku-3-5");
  });
});