import type { OpenClawPluginApi } from "openclaw/plugin-sdk";
import { emptyPluginConfigSchema } from "openclaw/plugin-sdk";
import { registerLineCardCommand } from "./src/card-command.js";
import { linePlugin } from "./src/channel.js";
import { registerLineHeartbeatCommand } from "./src/heartbeat-command.js";
import { setLineRuntime } from "./src/runtime.js";
import { registerLineThinkingCommand } from "./src/thinking-command.js";

const plugin = {
  id: "line",
  name: "LINE",
  description: "LINE Messaging API channel plugin",
  configSchema: emptyPluginConfigSchema(),
  register(api: OpenClawPluginApi) {
    setLineRuntime(api.runtime);
    api.registerChannel({ plugin: linePlugin });
    registerLineCardCommand(api);
    registerLineHeartbeatCommand(api);
    registerLineThinkingCommand(api);
  },
};

export default plugin;
