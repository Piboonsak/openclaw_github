# Epic 5 Core Implementation How-To and Design

Objective: move Epic 5 issues from process-oriented text to concrete implementation design for PoC delivery.

## TASK-501 OCR Processor

How to:

1. Build `OCRProcessor` in `src/backend/app/ocr/processor.py` with `process_document(file_path)`.
2. Convert PDF pages using `pdf2image`, then OCR each page using `pytesseract` (`tha+eng`).
3. Cache by SHA-256 at `cache/<sha256>/ocr_output.json`.
4. Emit standardized error codes for timeout/corrupt/password-protected files.

Design:

- Pipeline stages: `load -> rasterize -> ocr -> merge -> cache -> emit`.
- Idempotent cache key is `sha256(file bytes)`.
- Output contracts are page-level + merged text + metadata.

## TASK-502 Structured Field Extraction

How to:

1. Implement `extract_fields(ocr_text, schema, doc_type)` in `src/backend/app/extraction/fields.py`.
2. Use strict JSON schema prompting and schema validation retry (max 2 retries).
3. Route model by complexity and confidence.
4. Emit `low_confidence_fields` for human review queue.

Design:

- Separation of concerns: `doc_type detect`, `prompt builder`, `model client`, `schema validator`.
- Failure strategy: `primary -> fallback -> typed error`.
- Confidence threshold default 0.75, configurable.

## TASK-503 Journal Rule Router

How to:

1. Implement `compile_rules()` and `post_journal_entry()` in `src/backend/app/validation/rules.py`.
2. Parse `rule_coa.yaml`, map extracted fields to Dr/Cr lines.
3. Apply VAT/WHT calculation and rounding policy.
4. Validate balance with tolerance +/- 0.01.

Design:

- Rule engine with deterministic evaluation order.
- Accounting output contract compatible with Express GL JSON.
- Any balance mismatch blocks pass and emits actionable reason.

## TASK-504 Ground Truth Dataset

How to:

1. Define canonical schema for expectations rows (doc metadata + accounting fields + reviewer metadata).
2. Build loader/validator to detect missing required fields and format mismatch.
3. Produce evaluator comparing prediction vs truth by field.

Design:

- Expectations is the single source of truth for quality gates.
- Enforce immutable `doc_id` and versioned labeling metadata.

## TASK-505 Manifest and Deterministic Split

How to:

1. Use `scripts/build_comp1_dataset_metadata.ps1` to scan PDFs and compute hashes.
2. Deterministically split with fixed seed `20260604`.
3. Write `manifest.jsonl` and `split.json` with included/excluded sets.

Design:

- Reproducibility first: same input produces same manifest and split.
- Include exclusion reason in metadata for auditability.

## TASK-506 Expectations Template Generator

How to:

1. Generate `expectations.template.jsonl` from manifest with one row per `doc_id`.
2. Pre-fill structural columns and empty extraction fields.
3. Mark excluded docs with `labeling_status=excluded`.

Design:

- Template schema mirrors filled expectations schema to avoid migration later.
- Labeling UX optimized: fields ordered by human review workflow.

## TASK-507 Multi-Page Support

How to:

1. Detect page count early in OCR stage.
2. OCR page-by-page and merge with explicit delimiters.
3. Preserve per-page artifacts for debugging.

Design:

- Keep both `pages[]` and `merged_text` outputs.
- Never lose page provenance, needed for correction UI.

## TASK-508 Fallback Routing

How to:

1. Implement unified fallback middleware for OCR and LLM extraction.
2. Capture `model_used`, `fallback_reason`, `fallback_count` per run.
3. Track fallback rate by cohort.

Design:

- Fast-fail with typed reason; no hidden retries.
- Fallback events become KPI signals, not silent behavior.

## TASK-509 Labeling SOP and QA Checklist

How to:

1. Document field definitions, normalization rules, and edge-case policy.
2. Add dual-review checklist and conflict escalation path.
3. Add annotated examples for 3-5 real docs.

Design:

- SOP prevents label noise from becoming model noise.
- Conflict resolution always records rationale.

## TASK-510 KPI Gates

How to:

1. Define release thresholds (field, doc-level, balance, fallback, manual review).
2. Build evaluator output table and gate status.
3. Add regression guard: fail when drop exceeds threshold.

Design:

- KPI gate is release control point, not a reporting-only dashboard.
- Per-doc-type metrics required to avoid hidden weak segments.

## TASK-511 Exclusion Rule Enforcement

How to:

1. Maintain hash-based exclusion registry.
2. Enforce exclusion in split generation and quality gate.
3. Fail build if excluded hash appears in train/val/test.

Design:

- Hash identity beats filename identity for robustness.
- Exclusion reason is mandatory metadata.

## TASK-512 Cohort Quality Gate

How to:

1. Validate count consistency, duplicates, path validity, and exclusion integrity.
2. Emit machine-readable and human-readable report.
3. Integrate into CI as blocking check.

Design:

- Dataset quality gate runs before model quality gate.
- Clear error messages to minimize debugging cycle.

## TASK-513 HTML Cohort Infographic

How to:

1. Build self-contained HTML with split metrics and KPI highlights.
2. Render responsive sections: counts, bars, exclusions, status badges.
3. Use data from generated JSON, not hardcoded values.

Design:

- One-file artifact for stakeholder sharing.
- Visual hierarchy emphasizes risks and readiness.

## TASK-514 Auto-Refresh Infographic

How to:

1. Build generator script reading latest manifest and split.
2. Inject computed metrics into HTML template.
3. Make callable from local and CI flows.

Design:

- Template + data separation for maintainability.
- Regeneration is deterministic and testable.

## TASK-515 Baseline Benchmarking

How to:

1. Fix benchmark cohort and fingerprint dataset version.
2. Compare manual truth vs pipeline prediction field-by-field.
3. Publish mismatch taxonomy and prioritized fixes.

Design:

- Benchmark artifact is regression anchor for future releases.
- Track both aggregate and critical-field metrics.

## Discussion Topics

1. Confirm implementation ownership per TASK-501..515.
2. Approve default thresholds (confidence 0.75, balance tolerance 0.01, regression <= 2 points).
3. Decide KPI report format for release go/no-go.
4. Lock code locations for OCR/extraction/validation modules.
