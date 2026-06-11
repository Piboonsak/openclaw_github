import { defineConfig } from "@playwright/test";

declare const process: { env: Record<string, string | undefined> };

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  retries: 1,
  use: {
    baseURL:
      process.env.POC_URL ||
      process.env.DEMO_URL ||
      "https://demo-aiaccount.yahwan.biz",
    headless: true,
    screenshot: "on",
    trace: "on-first-retry",
  },
  reporter: [["html", { open: "never" }]],
});
