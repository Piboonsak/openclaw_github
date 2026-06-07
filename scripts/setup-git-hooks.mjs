#!/usr/bin/env node

import { execSync } from 'node:child_process';

try {
  execSync('git config core.hooksPath .githooks', { stdio: 'inherit' });
  console.log('Configured git hooks path to .githooks');
} catch (error) {
  console.error('Failed to configure git hooks path. Run manually: git config core.hooksPath .githooks');
  process.exit(1);
}
