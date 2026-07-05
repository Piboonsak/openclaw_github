#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = process.cwd();
const indexPath = resolve(root, "src/frontend/index.html");
const mainPath = resolve(root, "src/frontend/main-ux-ui.html");

const indexHtml = readFileSync(indexPath, "utf8");
const mainHtml = readFileSync(mainPath, "utf8");

const mojibakePatterns = [/à¸/g, /â€”/g, /Ã/g, /Â/g];
const requiredMarkers = [
  "exportModeQuickCard",
  "exportModeTemplateCard",
  "exportTemplateSelect",
  "exportPreviewInline",
  "exportColumnsBody",
  "previewExport()",
  "downloadExportFile()",
  "validateExport()",
  "template_id: templateId",
  "column_overrides"
];

const parityCountMarkers = [
  "exportModeQuickCard",
  "exportModeTemplateCard",
  "exportTemplateSelect",
  "exportPreviewInline",
  "using null-template runtime columns",
  "template_id: templateId"
];

function countMatches(content, pattern) {
  const matches = content.match(new RegExp(pattern, "g"));
  return matches ? matches.length : 0;
}

function fail(message) {
  console.error(`VERIFY_FAIL: ${message}`);
  process.exitCode = 1;
}

for (const marker of requiredMarkers) {
  if (!indexHtml.includes(marker)) {
    fail(`index missing marker: ${marker}`);
  }
  if (!mainHtml.includes(marker)) {
    fail(`main missing marker: ${marker}`);
  }
}

for (const marker of parityCountMarkers) {
  const indexCount = countMatches(indexHtml, marker);
  const mainCount = countMatches(mainHtml, marker);
  if (indexCount !== mainCount) {
    fail(`marker count mismatch for ${marker}: index=${indexCount} main=${mainCount}`);
  }
}

for (const pattern of mojibakePatterns) {
  if (pattern.test(indexHtml)) {
    fail(`index contains mojibake token pattern: ${pattern}`);
  }
  if (pattern.test(mainHtml)) {
    fail(`main contains mojibake token pattern: ${pattern}`);
  }
}

if (indexHtml !== mainHtml) {
  fail("index and main are not byte-identical; parity drift detected");
}

if (!process.exitCode) {
  console.log("VERIFY_OK: W4 HTML integrity and parity checks passed");
}
