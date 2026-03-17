import { triggerOpenClawRestart } from "../infra/restart.js";
import type { RuntimeEnv } from "../runtime.js";
import { defaultRuntime } from "../runtime.js";

export type RestartGatewayOptions = {
  json?: boolean;
};

export async function restartGatewayCommand(
  options: RestartGatewayOptions = {},
  runtime: RuntimeEnv = defaultRuntime,
) {
  const result = triggerOpenClawRestart();

  if (options.json) {
    runtime.log(JSON.stringify(result, null, 2));
    if (!result.ok) {
      runtime.exit(1);
    }
    return;
  }

  if (!result.ok) {
    const detail = result.detail ? ` Details: ${result.detail}` : "";
    runtime.error(`Restart failed (${result.method}).${detail}`);
    runtime.exit(1);
    return;
  }

  runtime.log(`Restart requested via ${result.method}.`);
}
