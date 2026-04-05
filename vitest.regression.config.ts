import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

const repoRoot = path.dirname(fileURLToPath(import.meta.url));

// Standalone config for the NongKung regression suite.
// Only runs tests/regression/**/*.test.ts — no src/ or extensions/ tests.
export default defineConfig({
  resolve: {
    alias: [
      {
        find: "openclaw/plugin-sdk/account-id",
        replacement: path.join(repoRoot, "src", "plugin-sdk", "account-id.ts"),
      },
      {
        find: "openclaw/plugin-sdk",
        replacement: path.join(repoRoot, "src", "plugin-sdk", "index.ts"),
      },
    ],
  },
  test: {
    testTimeout: 120_000,
    hookTimeout: 120_000,
    pool: "forks",
    // Regression suite runs single-threaded to keep results predictable.
    maxWorkers: 1,
    minWorkers: 1,
    include: ["tests/regression/**/*.test.ts"],
    exclude: ["dist/**", "**/node_modules/**", "**/vendor/**"],
    setupFiles: ["test/setup.ts"],
    unstubEnvs: true,
    unstubGlobals: true,
  },
});
