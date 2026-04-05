import type { OpenClawConfig, OpenClawPluginApi, PluginRuntime } from "openclaw/plugin-sdk";
import { describe, expect, it, vi } from "vitest";
import { setLineRuntime } from "./runtime.js";
import { registerLineThinkingCommand } from "./thinking-command.js";

type CommandHandler = NonNullable<Parameters<OpenClawPluginApi["registerCommand"]>[0]["handler"]>;
type CommandContext = Parameters<CommandHandler>[0];

function makeConfig(thinkingDefault?: string): OpenClawConfig {
  if (thinkingDefault === undefined) {
    return {} as unknown as OpenClawConfig;
  }
  return {
    agents: {
      defaults: {
        thinkingDefault,
      },
    },
  } as unknown as OpenClawConfig;
}

function makeCtx(args: string, thinkingDefault?: string): CommandContext {
  return {
    args,
    config: makeConfig(thinkingDefault),
    channel: "line",
    isAuthorizedSender: true,
  } as unknown as CommandContext;
}

/**
 * Build a mock OpenClawPluginApi that captures the registered command handlers.
 */
function buildMockApi() {
  const commands = new Map<string, CommandHandler>();
  const api = {
    registerCommand(def: {
      name: string;
      description: string;
      acceptsArgs?: boolean;
      requireAuth?: boolean;
      handler: CommandHandler;
    }) {
      commands.set(def.name, def.handler);
    },
    registerChannel: vi.fn(),
  } as unknown as OpenClawPluginApi;
  return { api, commands };
}

/**
 * Build a mock PluginRuntime with a writable config.
 */
function buildMockRuntime(initialConfig: OpenClawConfig = {} as OpenClawConfig) {
  let stored = { ...initialConfig };
  const runtime = {
    config: {
      loadConfig: vi.fn(() => ({ ...stored })),
      writeConfigFile: vi.fn(async (cfg: OpenClawConfig) => {
        stored = { ...cfg };
      }),
    },
  } as unknown as PluginRuntime;
  return { runtime, getStored: () => stored };
}

describe("registerLineThinkingCommand", () => {
  it("registers commands named 'thinking' and 'think'", () => {
    const { api, commands } = buildMockApi();
    const { runtime } = buildMockRuntime();
    setLineRuntime(runtime);
    registerLineThinkingCommand(api);
    expect(commands.has("thinking")).toBe(true);
    expect(commands.has("think")).toBe(true);
  });

  describe("GET (no args)", () => {
    it("shows '(not set)' when thinkingDefault is not configured", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("thinking")!;
      const result = await handler(makeCtx(""));
      expect(result.text).toContain("(not set)");
      expect(result.text).toContain("Current reasoning mode:");
    });

    it("shows configured thinking level", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("thinking")!;
      const result = await handler(makeCtx("", "low"));
      expect(result.text).toContain("Current reasoning mode: low");
    });

    it("shows usage text alongside current level", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("thinking")!;
      const result = await handler(makeCtx(""));
      expect(result.text).toContain("Usage: /thinking");
    });
  });

  describe("HELP", () => {
    it("shows usage on 'help'", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("thinking")!;
      const result = await handler(makeCtx("help"));
      expect(result.text).toContain("Usage: /thinking");
    });

    it("shows usage on '?'", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("thinking")!;
      const result = await handler(makeCtx("?"));
      expect(result.text).toContain("Usage: /thinking");
    });

    it("includes current level in help output", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("thinking")!;
      const result = await handler(makeCtx("help", "medium"));
      expect(result.text).toContain("Current reasoning mode: medium");
    });
  });

  describe("SET level", () => {
    it.each(["off", "minimal", "low", "medium", "high", "xhigh"] as const)(
      "persists valid level '%s' to config",
      async (level) => {
        const { api, commands } = buildMockApi();
        const { runtime, getStored } = buildMockRuntime();
        setLineRuntime(runtime);
        registerLineThinkingCommand(api);
        const handler = commands.get("thinking")!;
        const result = await handler(makeCtx(level));
        expect(result.text).toContain(`✅ Reasoning mode updated: ${level}`);
        expect(getStored().agents?.defaults?.thinkingDefault).toBe(level);
      },
    );

    it("accepts uppercase input and normalises to lowercase", async () => {
      const { api, commands } = buildMockApi();
      const { runtime, getStored } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("thinking")!;
      const result = await handler(makeCtx("HIGH"));
      expect(result.text).toContain("✅ Reasoning mode updated: high");
      expect(getStored().agents?.defaults?.thinkingDefault).toBe("high");
    });

    it("rejects an invalid level", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("thinking")!;
      const result = await handler(makeCtx("turbo"));
      expect(result.text).toContain('Invalid reasoning level: "turbo"');
      expect(result.text).toContain("Usage: /thinking");
    });

    it("initialises agents.defaults when config is empty", async () => {
      const { api, commands } = buildMockApi();
      const { runtime, getStored } = buildMockRuntime({} as OpenClawConfig);
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("thinking")!;
      await handler(makeCtx("low"));
      expect(getStored().agents?.defaults?.thinkingDefault).toBe("low");
    });

    it("returns an error message when writeConfigFile throws", async () => {
      const { api, commands } = buildMockApi();
      const runtime = {
        config: {
          loadConfig: vi.fn(() => ({}) as OpenClawConfig),
          writeConfigFile: vi.fn(async () => {
            throw new Error("disk full");
          }),
        },
      } as unknown as PluginRuntime;
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("thinking")!;
      const result = await handler(makeCtx("low"));
      expect(result.text).toContain("❌ Failed to update reasoning mode");
      expect(result.text).toContain("disk full");
    });
  });

  describe("/think alias", () => {
    it("GET shows current level", async () => {
      const { api, commands } = buildMockApi();
      const { runtime } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("think")!;
      const result = await handler(makeCtx("", "high"));
      expect(result.text).toContain("Current reasoning mode: high");
    });

    it("SET persists level via /think alias", async () => {
      const { api, commands } = buildMockApi();
      const { runtime, getStored } = buildMockRuntime();
      setLineRuntime(runtime);
      registerLineThinkingCommand(api);
      const handler = commands.get("think")!;
      const result = await handler(makeCtx("medium"));
      expect(result.text).toContain("✅ Reasoning mode updated: medium");
      expect(getStored().agents?.defaults?.thinkingDefault).toBe("medium");
    });
  });
});
