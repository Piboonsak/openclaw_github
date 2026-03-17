import { describe, expect, it, vi } from "vitest";
import type { RuntimeEnv } from "../runtime.js";

const triggerOpenClawRestartMock = vi.hoisted(() => vi.fn());

vi.mock("../infra/restart.js", () => ({
  triggerOpenClawRestart: triggerOpenClawRestartMock,
}));

import { restartGatewayCommand } from "./restart-gateway.js";

function createRuntime(): {
  runtime: RuntimeEnv;
  log: ReturnType<typeof vi.fn>;
  error: ReturnType<typeof vi.fn>;
  exit: ReturnType<typeof vi.fn>;
} {
  const log = vi.fn();
  const error = vi.fn();
  const exit = vi.fn();
  return {
    runtime: {
      log,
      error,
      exit,
    } as unknown as RuntimeEnv,
    log,
    error,
    exit,
  };
}

describe("restartGatewayCommand", () => {
  it("logs success without exiting", async () => {
    triggerOpenClawRestartMock.mockReturnValue({ ok: true, method: "systemd" });
    const { runtime, log, exit } = createRuntime();

    await restartGatewayCommand({}, runtime);

    expect(log).toHaveBeenCalledWith("Restart requested via systemd.");
    expect(exit).not.toHaveBeenCalled();
  });

  it("emits json and exits on failure", async () => {
    triggerOpenClawRestartMock.mockReturnValue({
      ok: false,
      method: "supervisor",
      detail: "service not found",
    });
    const { runtime, log, exit, error } = createRuntime();

    await restartGatewayCommand({ json: true }, runtime);

    expect(log).toHaveBeenCalledWith(
      JSON.stringify({ ok: false, method: "supervisor", detail: "service not found" }, null, 2),
    );
    expect(error).not.toHaveBeenCalled();
    expect(exit).toHaveBeenCalledWith(1);
  });
});
