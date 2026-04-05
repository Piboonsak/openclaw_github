import { defineConfig } from "vitest/config";
import baseConfig from "./vitest.config.js";

const base = baseConfig as unknown as Record<string, unknown>;
const baseTest = (baseConfig as { test?: { exclude?: string[] } }).test ?? {};

export default defineConfig({
  ...base,
  test: {
    ...baseTest,
    include: ["tests/regression/**/*.test.ts"],
    // Exclude nothing extra — regression tests are always run standalone.
    exclude: ["dist/**", "**/node_modules/**", "**/vendor/**"],
    // Regression suite runs single-threaded to keep results predictable.
    maxWorkers: 1,
    minWorkers: 1,
  },
});
