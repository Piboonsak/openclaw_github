#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const repoRoot = process.cwd();
const sourceDir = path.join(repoRoot, 'agents');
const targetDir = path.join(repoRoot, '.agent', 'definitions');

if (!fs.existsSync(sourceDir)) {
  console.error('Source folder not found: agents/');
  process.exit(1);
}

fs.mkdirSync(targetDir, { recursive: true });

const files = fs
  .readdirSync(sourceDir, { withFileTypes: true })
  .filter((entry) => entry.isFile() && entry.name.endsWith('.agent.md'))
  .map((entry) => entry.name);

for (const file of files) {
  fs.copyFileSync(path.join(sourceDir, file), path.join(targetDir, file));
}

console.log(`Synced ${files.length} agent definition files to .agent/definitions`);
