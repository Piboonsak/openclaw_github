param(
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

$taskContent = @{
    'TASK-501' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Build `OCRProcessor.process_document(file_path)` in `src/backend/app/ocr/processor.py`.
2. Rasterize pages via `pdf2image` and OCR with `pytesseract` (`tha+eng`).
3. Cache result at `cache/<sha256>/ocr_output.json`.
4. Emit standardized `error_code` for timeout, corrupted, and password-protected PDFs.

### Design Notes
- Pipeline: load -> rasterize -> ocr -> merge -> cache -> emit.
- Keep both `pages[]` and `merged_text` for debugging and downstream extraction.
- Cache key must be deterministic (`sha256(file bytes)`).
'@
    'TASK-502' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Implement `extract_fields(ocr_text, schema, doc_type)` in `src/backend/app/extraction/fields.py`.
2. Enforce strict JSON schema validation with retry (max 2 attempts).
3. Add model routing by complexity and fallback path with typed errors.
4. Emit `low_confidence_fields` for human review queue.

### Design Notes
- Split modules: doc-type detector, prompt builder, model client, schema validator.
- Failure mode is explicit (`primary -> fallback -> error_code`), never silent.
- Confidence threshold default 0.75 and configurable.
'@
    'TASK-503' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Implement `compile_rules()` and `post_journal_entry()` in `src/backend/app/validation/rules.py`.
2. Parse `rule_coa.yaml` and map extracted fields to Dr/Cr entries.
3. Apply VAT/WHT logic and rounding policy consistently.
4. Validate debit-credit balance with tolerance +/- 0.01.

### Design Notes
- Rule evaluation must be deterministic.
- Express GL output contract is fixed and versioned.
- Balance mismatch must block pass with actionable error message.
'@
    'TASK-504' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Define canonical expectations schema with reviewer metadata.
2. Build expectations validator to reject incomplete or invalid rows.
3. Build evaluator that compares prediction vs truth by field and document.

### Design Notes
- Expectations dataset is single source of truth for quality gates.
- `doc_id` must be immutable and traceable to manifest row.
'@
    'TASK-505' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Use `scripts/build_comp1_dataset_metadata.ps1` to scan PDFs and hash files.
2. Split with fixed seed `20260604` for reproducibility.
3. Write `manifest.jsonl` and `split.json` with include/exclude metadata.

### Design Notes
- Same input must produce identical manifest and split output.
- Exclusion reason must be explicit for audit trail.
'@
    'TASK-506' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Generate `expectations.template.jsonl` from manifest (`1 row = 1 doc_id`).
2. Pre-fill structural fields and leave extraction fields empty.
3. Mark excluded rows as `labeling_status=excluded`.

### Design Notes
- Template schema must match final filled schema.
- Field order should optimize human labeling flow.
'@
    'TASK-507' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Detect page count and process page-by-page in OCR flow.
2. Merge page text with separators while preserving order.
3. Keep per-page artifacts in output for reviewer traceability.

### Design Notes
- Preserve page provenance (`pages[]`) plus `merged_text`.
- Multi-page behavior should be parity-tested vs single-page baseline.
'@
    'TASK-508' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Implement fallback middleware for OCR and extraction stages.
2. Capture `model_used`, `fallback_reason`, and `fallback_count`.
3. Add cohort-level fallback-rate metric and alert threshold.

### Design Notes
- No hidden retries; all fallback transitions are observable.
- Fallback metrics are part of quality diagnostics, not only ops logs.
'@
    'TASK-509' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Create `LABELING-SOP.md` with field definitions and normalization policy.
2. Add dual-review checklist and discrepancy escalation process.
3. Include annotated examples for at least 3 documents.

### Design Notes
- Label noise directly degrades model quality; SOP is a hard gate.
- Every conflict resolution must be documented with rationale.
'@
    'TASK-510' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Define KPI thresholds for field/doc/balance/fallback/manual-review rates.
2. Build evaluator output table with pass/fail gate status.
3. Add regression gate to fail when accuracy drops beyond allowed delta.

### Design Notes
- KPI gate is a release gate, not reporting-only output.
- Metrics must be reported by doc type to expose weak segments.
'@
    'TASK-511' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Maintain hash-based exclusion registry in dataset build script.
2. Set `include_in_training=false` and record exclusion reason.
3. Block build if excluded hashes appear in train/val/test split.

### Design Notes
- Hash identity is more reliable than filename identity.
- Exclusion metadata is mandatory for traceability.
'@
    'TASK-512' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Validate split counts, duplicate entries, and path integrity.
2. Validate exclusion integrity against manifest and split outputs.
3. Emit machine-readable and markdown report; fail CI on error.

### Design Notes
- Dataset quality gate must run before model quality gate.
- Error messages must be explicit to reduce triage time.
'@
    'TASK-513' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Build self-contained responsive HTML for cohort and KPI status.
2. Render counts, split bars, exclusions, and readiness indicators.
3. Bind values from generated metadata files (no hardcoded numbers).

### Design Notes
- One-file artifact for stakeholder review and async discussion.
- Visual hierarchy should prioritize risk and release readiness.
'@
    'TASK-514' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Build generator script to read latest `manifest.jsonl` and `split.json`.
2. Populate HTML template with computed metrics.
3. Support local execution and CI execution.

### Design Notes
- Template/data separation keeps maintenance simple.
- Output should be deterministic and diff-friendly.
'@
    'TASK-515' = @'
## How To Implement (Core Design)

### Implementation Plan
1. Freeze benchmark cohort and record dataset fingerprint.
2. Compare prediction vs manual truth field-by-field.
3. Publish mismatch taxonomy with prioritized remediation list.

### Design Notes
- Benchmark artifact is regression baseline for future releases.
- Track aggregate metrics and critical-field metrics separately.
'@
}

$issues = gh issue list --limit 200 --label "epic:5" --json number,title,body,url | ConvertFrom-Json

$startMarker = '<!-- HOWTO-DESIGN:START -->'
$endMarker = '<!-- HOWTO-DESIGN:END -->'

$updated = 0
$skipped = 0

foreach ($issue in $issues) {
    $taskId = $null

    if ($issue.title -match '(TASK-\d{3})') {
        $taskId = $Matches[1]
    } elseif ($issue.body -match '(TASK-\d{3})') {
        $taskId = $Matches[1]
    }

    if (-not $taskId -or -not $taskContent.ContainsKey($taskId)) {
        $skipped++
        continue
    }

    $newSection = "${startMarker}`n$($taskContent[$taskId].Trim())`n${endMarker}"
    $newBody = $issue.body

    if ($newBody -match [regex]::Escape($startMarker) -and $newBody -match [regex]::Escape($endMarker)) {
        $pattern = [regex]::Escape($startMarker) + '[\s\S]*?' + [regex]::Escape($endMarker)
        $newBody = [regex]::Replace($newBody, $pattern, $newSection)
    } else {
        $newBody = ($newBody.TrimEnd() + "`n`n" + $newSection + "`n")
    }

    if ($DryRun) {
        Write-Host "[DRY-RUN] Would update issue #$($issue.number) ($taskId)"
        $updated++
        continue
    }

    $tmp = New-TemporaryFile
    Set-Content -Path $tmp -Value $newBody -Encoding UTF8
    gh issue edit $issue.number --body-file $tmp | Out-Null
    Remove-Item $tmp -Force

    Write-Host "Updated issue #$($issue.number) ($taskId)"
    $updated++
}

Write-Host "Done. Updated=$updated Skipped=$skipped"

