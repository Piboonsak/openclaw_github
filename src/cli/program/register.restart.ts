import type { Command } from "commander";
import { restartGatewayCommand } from "../../commands/restart-gateway.js";
import { defaultRuntime } from "../../runtime.js";
import { runCommandWithRuntime } from "../cli-utils.js";

export function registerRestartCommands(program: Command) {
  const restart = program.command("restart").description("Restart OpenClaw services");

  restart
    .command("gateway")
    .description("Restart the OpenClaw gateway service")
    .option("--json", "Output JSON instead of text", false)
    .action(async (opts) => {
      await runCommandWithRuntime(defaultRuntime, async () => {
        await restartGatewayCommand({ json: Boolean(opts.json) }, defaultRuntime);
      });
    });
}
