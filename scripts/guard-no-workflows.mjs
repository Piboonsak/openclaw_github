#!/usr/bin/env node

import { readdir } from "node:fs/promises";
import path from "node:path";

const workflowsDir = path.resolve(process.cwd(), ".github", "workflows");
const allowedFiles = new Set([".gitkeep", "deploy-openclaw-github-private-secrets.yml"]);

async function main() {
  let entries;
  try {
    entries = await readdir(workflowsDir, { withFileTypes: true });
  } catch {
    // If the directory does not exist, policy is satisfied.
    return;
  }

  const forbidden = entries
    .filter((entry) => {
      if (entry.isDirectory()) {
        return true;
      }
      return !allowedFiles.has(entry.name);
    })
    .map((entry) => entry.name)
    .toSorted();

  if (forbidden.length === 0) {
    return;
  }

  const lines = [
    "Policy violation: workflow files are not allowed in openclaw_github.",
    "Move CI/CD workflows to Piboonsak/Openclaw.",
    "Forbidden entries:",
    ...forbidden.map((name) => ` - .github/workflows/${name}`),
  ];
  console.error(lines.join("\n"));
  process.exit(1);
}

void main();
