import { defineConfig } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

declare const process: { env: Record<string, string | undefined> };

// Load an untracked `.env.sit.local` (git-ignored via `.env.*.local`) so SIT
// credentials never live in the repo or in shell history. Dependency-free.
const sitEnvPath = resolve(__dirname, ".env.sit.local");
if (existsSync(sitEnvPath)) {
  for (const raw of readFileSync(sitEnvPath, "utf8").split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    const value = line.slice(eq + 1).trim();
    if (key && process.env[key] === undefined) process.env[key] = value;
  }
}

// Only attach Basic-Auth when both edge creds are present (SIT edge gate).
const basicUser = process.env.SIT_BASIC_USER;
const basicPass = process.env.SIT_BASIC_PASS;
const httpCredentials =
  basicUser && basicPass ? { username: basicUser, password: basicPass } : undefined;

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
    ...(httpCredentials ? { httpCredentials } : {}),
  },
  reporter: [["html", { open: "never" }]],
});
