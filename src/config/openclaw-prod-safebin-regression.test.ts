import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

function extractObjectBlock(text: string, key: string): string {
  const escapedKey = key.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const startExpr = new RegExp(`${escapedKey}\\s*:\\s*\\{`, "m");
  const startMatch = startExpr.exec(text);
  if (!startMatch || startMatch.index < 0) {
    throw new Error(`${key} block not found in config/openclaw.prod.json5`);
  }

  const start = startMatch.index + startMatch[0].length;
  let depth = 1;
  let i = start;
  while (i < text.length && depth > 0) {
    const ch = text[i];
    if (ch === "{") depth += 1;
    if (ch === "}") depth -= 1;
    i += 1;
  }
  return text.slice(start, i - 1);
}

function extractProfileBlock(safeBinProfilesText: string, bin: string): string {
  const escapedBin = bin.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const profileStart = new RegExp(`${escapedBin}\\s*:\\s*\\{`, "m");
  const startMatch = profileStart.exec(safeBinProfilesText);
  if (!startMatch || startMatch.index < 0) {
    throw new Error(`safeBinProfiles.${bin} not found in config/openclaw.prod.json5`);
  }

  const start = startMatch.index + startMatch[0].length;
  let depth = 1;
  let i = start;
  while (i < safeBinProfilesText.length && depth > 0) {
    const ch = safeBinProfilesText[i];
    if (ch === "{") depth += 1;
    if (ch === "}") depth -= 1;
    i += 1;
  }
  return safeBinProfilesText.slice(start, i - 1);
}

describe("KI-067 regression guard for safeBinProfiles", () => {
  const configPath = path.resolve(process.cwd(), "config/openclaw.prod.json5");
  const configText = fs.readFileSync(configPath, "utf8");
  const safeBinProfilesText = extractObjectBlock(configText, "safeBinProfiles");

  it("keeps allowPathPositionals: true on required path bins", () => {
    for (const bin of ["ls", "find", "cat", "stat", "curl"]) {
      const block = extractProfileBlock(safeBinProfilesText, bin);
      expect(block).toMatch(/allowPathPositionals\s*:\s*true/);
    }
  });
});
