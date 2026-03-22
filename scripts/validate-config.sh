#!/usr/bin/env bash
# validate-config.sh — OpenClaw config schema validation gate
# Usage: ./scripts/validate-config.sh <config-file>
# Exit 0 = valid, non-zero = invalid
#
# Guards against known issues:
#   KI-047: Stale invalid .models causes container restart loop
#   KI-048: Container not recreated after env sync
#   KI-050: Health 502 after deploy (bad config causes crash on start)
#   KI-052: .models = null crashes container ('models: expected object, received null')
#
# Run BEFORE any docker compose restart/up in deploy or hotfix workflows.

set -euo pipefail

CONFIG_FILE="${1:?Usage: validate-config.sh <config-file>}"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "ERROR: Config file not found: $CONFIG_FILE"
  exit 1
fi

echo "=== OpenClaw Config Validation ==="
echo "File: $CONFIG_FILE"
echo ""

# Use node for JSON5 parsing (node is available in GitHub Actions ubuntu-latest)
node -e "
const fs = require('fs');
const path = require('path');

const configFile = process.argv[1];
let text;
try {
  text = fs.readFileSync(configFile, 'utf8');
} catch (e) {
  console.error('FAIL [read]: Cannot read config file:', e.message);
  process.exit(1);
}

// Strip JSON5 single-line and multi-line comments for parsing
// This handles the common JSON5 comment patterns
const stripped = text
  .replace(/\/\/[^\n]*/g, '')           // single-line comments
  .replace(/\/\*[\s\S]*?\*\//g, '')    // multi-line comments
  .replace(/,(\s*[}\]])/g, '\$1');     // trailing commas (basic)

let config;
try {
  config = JSON.parse(stripped);
} catch (e) {
  console.error('FAIL [syntax]: Invalid JSON/JSON5 syntax:', e.message);
  console.error('');
  console.error('This check guards against malformed config reaching the container.');
  process.exit(1);
}
console.log('PASS [syntax]: JSON/JSON5 syntax is valid');

// ── Check 1: gateway section ─────────────────────────────────────────────
// KI-048: missing gateway section causes container crash
if (!config.gateway || typeof config.gateway !== 'object') {
  console.error('FAIL [gateway]: gateway section is missing or not an object (KI-048)');
  console.error('  Expected: config.gateway = { ... }');
  console.error('  Fix: add gateway section to openclaw.prod.json5');
  process.exit(1);
}
console.log('PASS [gateway]: gateway section exists');

// ── Check 2: agents.defaults.model ──────────────────────────────────────
// KI-050: missing agents.defaults.model crashes container on start
if (!config.agents || typeof config.agents !== 'object') {
  console.error('FAIL [agents]: agents section is missing (KI-050)');
  process.exit(1);
}
if (!config.agents.defaults || typeof config.agents.defaults !== 'object') {
  console.error('FAIL [agents.defaults]: agents.defaults section is missing (KI-050)');
  process.exit(1);
}
const model = config.agents.defaults.model;
if (!model || typeof model !== 'object') {
  console.error('FAIL [agents.defaults.model]: agents.defaults.model is missing or not an object (KI-050)');
  console.error('  Expected: agents.defaults.model = { primary: \"...\", ... }');
  process.exit(1);
}
if (!model.primary || typeof model.primary !== 'string' || model.primary.trim() === '') {
  console.error('FAIL [agents.defaults.model.primary]: agents.defaults.model.primary is missing or empty (KI-050)');
  console.error('  Expected: agents.defaults.model.primary = \"<provider>/<model-name>\"');
  process.exit(1);
}
console.log('PASS [agents.defaults.model]: model.primary =', model.primary);

// ── Check 3: models is not null (if present) ─────────────────────────────
// KI-052: .models = null crashes container ('models: expected object, received null')
// KI-047: Stale invalid .models causes restart loop
const hasModels = Object.prototype.hasOwnProperty.call(config, 'models');
if (hasModels) {
  if (config.models === null) {
    console.error('FAIL [models]: top-level models is explicitly null (KI-052)');
    console.error('  This will cause: \"models: expected object, received null\" crash on container start');
    console.error('  Fix: either remove the models key entirely OR set it to a valid object with at least one provider');
    process.exit(1);
  }
  if (typeof config.models !== 'object') {
    console.error('FAIL [models]: top-level models is not an object (KI-052)');
    console.error('  Got:', typeof config.models, '=', JSON.stringify(config.models));
    process.exit(1);
  }
  const providerKeys = Object.keys(config.models);
  if (providerKeys.length === 0) {
    console.error('FAIL [models]: top-level models object is empty — no providers configured (KI-047, KI-052)');
    console.error('  Fix: add at least one provider under models, or remove the models key entirely');
    process.exit(1);
  }
  // Validate each provider entry
  let invalidProviders = [];
  for (const [providerName, providerConfig] of Object.entries(config.models)) {
    if (providerConfig === null || typeof providerConfig !== 'object') {
      invalidProviders.push(providerName + ' (null or not an object)');
    }
  }
  if (invalidProviders.length > 0) {
    console.error('FAIL [models]: invalid provider entries (KI-047):', invalidProviders.join(', '));
    process.exit(1);
  }
  console.log('PASS [models]: top-level models has', providerKeys.length, 'provider(s):', providerKeys.join(', '));
} else {
  console.log('INFO [models]: no top-level models key (will be removed from live config — OK per KI-052 fix)');
}

console.log('');
console.log('PASS: All config validation checks passed. Safe to restart container.');
" "$CONFIG_FILE"
