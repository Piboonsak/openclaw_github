#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

const repoRoot = process.cwd();

const AGENT_REQUIRED_FRONTMATTER = ['name', 'description', 'model', 'tools', 'scope', 'version'];
const SKILL_REQUIRED_FRONTMATTER = ['name', 'description', 'scope', 'version'];

const AGENT_REQUIRED_SECTIONS = [
  '## Mission',
  '## Core Responsibilities',
  '## Step-by-Step Workflow',
  '## Forbidden Operations'
];

const SKILL_REQUIRED_SECTIONS = [
  '## When to Use This Skill',
  '## Step-by-Step Workflows',
  '## Output Checklist'
];

function listFilesRecursively(dirPath, predicate) {
  const out = [];
  if (!fs.existsSync(dirPath)) {
    return out;
  }
  const entries = fs.readdirSync(dirPath, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dirPath, entry.name);
    if (entry.isDirectory()) {
      out.push(...listFilesRecursively(fullPath, predicate));
      continue;
    }
    if (predicate(fullPath)) {
      out.push(fullPath);
    }
  }
  return out;
}

function parseFrontmatter(markdownText) {
  const match = markdownText.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n/);
  if (!match) {
    return null;
  }
  const raw = match[1];
  const map = new Map();
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) {
      continue;
    }
    const idx = trimmed.indexOf(':');
    if (idx <= 0) {
      continue;
    }
    const key = trimmed.slice(0, idx).trim();
    const value = trimmed.slice(idx + 1).trim();
    map.set(key, value);
  }
  return map;
}

function validateFile(filePath, requiredFrontmatterKeys, requiredSections) {
  const rel = path.relative(repoRoot, filePath).replaceAll('\\', '/');
  const content = fs.readFileSync(filePath, 'utf8');
  const errors = [];

  const fm = parseFrontmatter(content);
  if (!fm) {
    errors.push(`${rel}: missing YAML frontmatter block at top of file`);
  } else {
    for (const key of requiredFrontmatterKeys) {
      if (!fm.has(key) || !String(fm.get(key)).trim()) {
        errors.push(`${rel}: missing frontmatter key '${key}'`);
      }
    }
  }

  for (const section of requiredSections) {
    if (!content.includes(section)) {
      errors.push(`${rel}: missing required section '${section}'`);
    }
  }

  return errors;
}

function main() {
  const agentFiles = listFilesRecursively(
    path.join(repoRoot, 'agents'),
    (p) => p.endsWith('.agent.md')
  );
  const skillFiles = listFilesRecursively(
    path.join(repoRoot, 'skills'),
    (p) => p.endsWith(`${path.sep}SKILL.md`)
  );

  const allErrors = [];

  for (const filePath of agentFiles) {
    allErrors.push(
      ...validateFile(filePath, AGENT_REQUIRED_FRONTMATTER, AGENT_REQUIRED_SECTIONS)
    );
  }

  for (const filePath of skillFiles) {
    allErrors.push(
      ...validateFile(filePath, SKILL_REQUIRED_FRONTMATTER, SKILL_REQUIRED_SECTIONS)
    );
  }

  if (agentFiles.length === 0) {
    allErrors.push('agents/: no .agent.md files found');
  }
  if (skillFiles.length === 0) {
    allErrors.push('skills/: no SKILL.md files found');
  }

  if (allErrors.length > 0) {
    console.error('Validation failed for agent/skill markdown files:\n');
    for (const err of allErrors) {
      console.error(`- ${err}`);
    }
    process.exit(1);
  }

  console.log(`Validation passed: ${agentFiles.length} agents, ${skillFiles.length} skills.`);
}

main();
