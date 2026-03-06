import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { getLineRuntime } from "./runtime.js";

// Valid thinking levels as per src/config/types.agent-defaults.ts
type ThinkingLevel = "off" | "minimal" | "low" | "medium" | "high" | "xhigh";

const VALID_LEVELS: ThinkingLevel[] = ["off", "minimal", "low", "medium", "high", "xhigh"];

const USAGE = `Usage: /thinking [level]

View or change the OpenClaw reasoning mode setting.

Examples:
  /thinking           → Show current reasoning level
  /thinking low       → Set reasoning to "low" (balanced)
  /thinking off       → Disable extended reasoning
  /thinking high      → Enable deep reasoning

Valid levels: ${VALID_LEVELS.join(", ")}`;

function isValidThinkingLevel(level: string): level is ThinkingLevel {
  return VALID_LEVELS.includes(level as ThinkingLevel);
}

export function registerLineThinkingCommand(api: OpenClawPluginApi): void {
  api.registerCommand({
    name: "thinking",
    description: "View or set OpenClaw reasoning mode (LINE).",
    acceptsArgs: true,
    requireAuth: false,
    handler: async (ctx) => {
      const argsStr = ctx.args?.trim() ?? "";

      // GET: Show current level
      if (!argsStr) {
        const currentLevel = ctx.config.agents?.defaults?.thinkingDefault ?? "(not set)";
        return {
          text: `Current reasoning mode: ${currentLevel}\n\n${USAGE}`,
        };
      }

      // SET: Change level
      const newLevel = argsStr.toLowerCase();
      if (!isValidThinkingLevel(newLevel)) {
        return {
          text: `Invalid reasoning level: "${argsStr}"\n\n${USAGE}`,
        };
      }

      try {
        // Load current config, modify, and write back
        const runtime = getLineRuntime();
        const config = runtime.config.loadConfig();

        // Ensure nested structure exists
        if (!config.agents) {
          config.agents = { defaults: {} };
        }
        if (!config.agents.defaults) {
          config.agents.defaults = {};
        }

        // Set new thinking level
        config.agents.defaults.thinkingDefault = newLevel;

        // Persist to config file
        await runtime.config.writeConfigFile(config);

        return {
          text: `✅ Reasoning mode updated: ${newLevel}`,
        };
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return {
          text: `❌ Failed to update reasoning mode: ${message}`,
        };
      }
    },
  });
}
