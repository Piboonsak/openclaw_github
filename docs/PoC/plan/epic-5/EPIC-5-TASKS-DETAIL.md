# Epic 5: Core Document Parser & Double-Entry Mapping Loop — Task Details

## Overview

Epic 5 implements the complete PoC extraction pipeline over 41-43 authentic PDF files (Comp_1 cohort) with OCR, structured LLM extraction, journal routing, and accuracy measurement.

**Status**: In Progress  
**Lead**: ML Team  
**Duration**: ~3-4 weeks  
**Phase**: PoC (Proof of Concept)

---

## TASK-501: Build the PDF image rasterization pipeline and secure raw text file caches

**Purpose**: Implement OCR processing to extract raw text from PDF pages.

### Acceptance Criteria

- [ ] PDF files convert to images via `pdf2image` at configurable DPI
- [ ] Images are processed via `pytesseract` with `-l tha+eng` training
- [ ] OCR text output is cached with SHA-256 hash key to prevent re-processing
- [ ] Output structure includes: page-level text, merged full-document text, metadata
- [ ] Handles multi-page PDFs (TASK-507 dependency)
- [ ] Error handling for corrupted/password-protected PDFs with reason codes
- [ ] Implementation: `src/ocr/processor.py`
- [ ] Tests pass: `tests/test_ocr.py` with >80% coverage

### Workflow

1. Load PDF from `private_data/poc/Comp_1/{doc_path}`
2. Rasterize pages to images (DPI config, typically 300)
3. OCR each image with pytesseract
4. Merge page texts into single document text
5. Hash PDF file and cache output
6. Return structured output (page texts, merged text, metadata)

### Inputs

- Source: `private_data/poc/Comp_1/manifest.jsonl` (doc_id, file_path)
- Config: OCR DPI, language packs (`tha+eng`), retry policy

### Outputs

- `cache/{sha256}/ocr_output.json` with fields:
  ```json
  {
    "doc_id": "comp1-0001",
    "sha256": "...",
    "pages": [{"page": 1, "text": "...", "page_size": "A4"}, ...],
    "merged_text": "...",
    "page_count": 2,
    "processing_time_ms": 1234,
    "ocr_engine": "pytesseract",
    "language": "tha+eng",
    "status": "ok" | "error",
    "error_code": "OCR_CORRUPTED" | "OCR_TIMEOUT" | null
  }
  ```

### Dependencies

- TASK-505 (manifest + split)
- TASK-507 (multi-page support)

### Acceptance Checklist

- [ ] `src/ocr/processor.py` implements `process_document(file_path)` → structured output
- [ ] Caching layer reduces redundant OCR calls by >95%
- [ ] Error handling emits standardized `error_code` for all failure modes
- [ ] Unit tests for success path + multi-page + corrupted files
- [ ] Integration test on 5 sample PDFs from Comp_1

---

## TASK-502: Build the Claude structured message JSON schema miner

**Purpose**: Extract structured accounting fields from OCR text using Claude.

### Acceptance Criteria

- [ ] LLM prompt templates support purchase/sale/receipt/payment doc types
- [ ] Claude returns strict JSON schema (no free text) per extraction
- [ ] JSON output validates against schema with retry on parse failure
- [ ] Low-confidence fields (<75%) are flagged for manual review
- [ ] Model routing: standard invoices → Claude-3.5-Haiku; complex → Claude-3.5-Sonnet
- [ ] Timeout: max 30s per document, fallback to Haiku if Sonnet times out
- [ ] Implementation: `src/extraction/fields.py`
- [ ] Tests pass: `tests/test_extraction.py` with >80% coverage

### Workflow

1. Read merged OCR text from TASK-501 output
2. Detect doc_type (purchase/sale/receipt/payment) via heuristics or LLM
3. Select model: Haiku for simple, Sonnet for complex structures
4. Invoke Claude with few-shot prompt + JSON schema
5. Parse response, validate against schema
6. Flag low-confidence fields (e.g., VAT amount if confidence < 75%)
7. Return structured extraction result

### Inputs

- OCR text: from `cache/{sha256}/ocr_output.json` (merged_text field)
- Schema: predefined extraction fields (invoice_number, date, amounts, tax_ids, etc.)
- Claude API key: from environment

### Outputs

- `cache/{sha256}/extraction_output.json`:
  ```json
  {
    "doc_id": "comp1-0001",
    "doc_type_detected": "purchase",
    "model_used": "claude-3-5-haiku-20250122",
    "fields": {
      "invoice_number": {"value": "INV-001", "confidence": 0.98},
      "invoice_date": {"value": "2026-06-04", "confidence": 0.95},
      "seller_name": {"value": "...", "confidence": 0.87},
      "total_amount": {"value": 1500.00, "confidence": 0.92},
      ...
    },
    "low_confidence_fields": ["seller_tax_id"],
    "processing_time_ms": 2100,
    "status": "ok" | "error",
    "error_code": null | "LLM_TIMEOUT" | "JSON_PARSE_FAIL" | "SCHEMA_INVALID"
  }
  ```

### Dependencies

- TASK-501 (OCR output)
- TASK-502 itself (no external dependency)

### Acceptance Checklist

- [ ] `src/extraction/fields.py` with `extract_fields(ocr_text, schema, doc_type)` function
- [ ] Model routing logic implemented with fallback
- [ ] Confidence scoring per field implemented
- [ ] Unit tests: success path + low-confidence scenarios + LLM failure
- [ ] Integration test on 5 sample PDFs with manual accuracy spot-check

---

## TASK-503: Write the journal rules router compiling coa accounts

**Purpose**: Map extracted fields to accounting journal entries (Dr/Cr posting).

### Acceptance Criteria

- [ ] Parse `rule_coa.yaml` config file for COA account mappings
- [ ] Compile extraction output + rule conditions → journal entry lines
- [ ] Support doc types: purchase (AP), sale (AR), receipt, payment
- [ ] Generate Dr/Cr pairs with tax logic (VAT, WHT)
- [ ] Validate debit == credit per voucher (tolerance ±0.01)
- [ ] Output is Express GL compatible JSON
- [ ] Implementation: `src/validation/rules.py`
- [ ] Tests pass: `tests/test_validation.py` with >80% coverage

### Workflow

1. Load `rule_coa.yaml` and compile rule conditions
2. Read extraction output (fields + confidence)
3. Determine transaction type from doc_type + fields
4. Map vendor/customer → GL account codes
5. Calculate tax amounts (VAT, WHT) per rule
6. Build Dr/Cr posting lines
7. Validate debit-credit balance
8. Output formatted journal voucher

### Inputs

- Extraction output: from TASK-502
- Rules config: `rule_coa.yaml` (account mappings, tax rules)
- Expectations: from TASK-504 (ground truth for validation)

### Outputs

- `cache/{sha256}/journal_output.json`:
  ```json
  {
    "doc_id": "comp1-0001",
    "doc_type": "purchase",
    "voucher_date": "2026-06-04",
    "reference": "INV-001",
    "lines": [
      {"account": "2000", "description": "AP - Metro Electric", "debit": 0, "credit": 15000.00},
      {"account": "5010", "description": "Office Expense", "debit": 12711.86, "credit": 0},
      {"account": "2100", "description": "VAT Payable", "debit": 0, "credit": 2288.14},
      ...
    ],
    "total_debit": 15000.00,
    "total_credit": 15000.00,
    "balanced": true,
    "balance_check_status": "ok" | "failed",
    "balance_error": null | "debit_credit_mismatch",
    "status": "ok" | "error"
  }
  ```

### Dependencies

- TASK-502 (extraction output)
- TASK-504 (expectations for validation)

### Acceptance Checklist

- [ ] `src/validation/rules.py` with `compile_rules()` and `post_journal_entry()` functions
- [ ] Tax calculation logic tested against manual samples
- [ ] Dr/Cr balance validator emits clear error messages
- [ ] Unit tests: all 4 doc_types + multi-line vouchers + balance failures
- [ ] Integration test on 5 complex vouchers from Comp_1

---

## TASK-504: Create expectations.json containing ground-truth values to calculate exact accuracy metrics

**Purpose**: Define ground-truth values for each document to enable accuracy measurement.

### Acceptance Criteria

- [ ] Template file generated for all 42 included documents: `private_data/poc/Comp_1/expectations.template.jsonl`
- [ ] Each row contains: doc_id, required fields (invoice_number, date, amounts, tax_id, etc.), labeler, review_note
- [ ] Labeling SOP defined to ensure consistency
- [ ] Dual-review process for conflict resolution
- [ ] Implementation: support for `expectations.filled.jsonl` after labeling
- [ ] Accuracy evaluator compares prediction vs ground truth

### Workflow

1. Generate template from manifest (doc_id, file_name, split)
2. Distribute to labelers
3. Labelers fill in expected field values for each document
4. Dual-review: second reviewer confirms or flags discrepancies
5. Resolve conflicts via majority vote or domain expert
6. Finalize `expectations.filled.jsonl`
7. Use in TASK-504 accuracy evaluator

### Inputs

- Manifest: `private_data/poc/Comp_1/manifest.jsonl`
- Template: `private_data/poc/Comp_1/expectations.template.jsonl` (generated by TASK-505)

### Outputs

- `tests/expectations.filled.jsonl` (after labeling):
  ```json
  {
    "doc_id": "comp1-0001",
    "split": "train",
    "file_name": "...",
    "doc_type": "purchase",
    "party_type": "vendor",
    "invoice_number": "INV-001",
    "invoice_date": "2026-06-04",
    "seller_name": "Metro Electric",
    "seller_tax_id": "1234567890123",
    "total_amount": 15000.00,
    "vat_amount": 2288.14,
    "labeler": "alice@company.com",
    "review_status": "approved" | "flagged_discrepancy",
    "review_notes": "..."
  }
  ```

### Dependencies

- TASK-505 (manifest to template)
- TASK-509 (labeling guide + QA checklist)

### Acceptance Checklist

- [ ] `private_data/poc/Comp_1/expectations.template.jsonl` generated with one row per doc_id
- [ ] Labeling SOP document created: `docs/PoC/LABELING-SOP.md`
- [ ] Dual-review checklist implemented
- [ ] All 42 documents labeled and conflict-resolved
- [ ] `tests/expectations.filled.jsonl` created and validated

---

## TASK-505: Build dataset manifest + deterministic split from Comp_1

**Purpose**: Create reproducible train/val/test split from 43 PDFs.

### Acceptance Criteria

- [ ] Manifest file: `private_data/poc/Comp_1/manifest.jsonl` with all document metadata
- [ ] Split file: `private_data/poc/Comp_1/split.json` with deterministic random assignment (seed: 20260604)
- [ ] Counts: train=29 (67.44%), val=6 (13.95%), test=7 (16.28%), excluded=1 (2.33%)
- [ ] Excluded: non-transaction reference documents (e.g., chart of accounts)
- [ ] Each manifest row: doc_id, company_id, file_path, sha256, split, doc_type_guess, include_in_training
- [ ] Each split row: train[], val[], test[], excluded[] arrays with relative paths
- [ ] Metadata script: `scripts/build_comp1_dataset_metadata.ps1` (regenerable)

### Workflow

1. Scan `private_data/poc/Comp_1` for all PDF files
2. Hash each file (SHA-256) and identify excluded docs by hash
3. Shuffle included PDFs deterministically (seed 20260604)
4. Assign splits: 70% train, 15% val, 15% test
5. Output manifest (JSONL) and split (JSON) files
6. Record metadata: doc_id, file sizes, hashes, split assignment, exclusion reason

### Inputs

- PDF directory: `private_data/poc/Comp_1`
- Excluded hashes: non-transaction reference docs (e.g., "ba1aedd99e...")

### Outputs

- `private_data/poc/Comp_1/manifest.jsonl` (one line per PDF)
- `private_data/poc/Comp_1/split.json` (train/val/test/excluded lists)

### Dependencies

- None (initial)

### Acceptance Checklist

- [ ] `scripts/build_comp1_dataset_metadata.ps1` creates both files
- [ ] manifest.jsonl has 42 rows (included) + 1 row (excluded)
- [ ] split.json counts match: train=29, val=6, test=7, excluded=1
- [ ] All paths use forward slashes and relative paths
- [ ] Manifest rows validate against schema (doc_id, sha256, split, include_in_training)
- [ ] Script is deterministic (same output for same input)

---

## TASK-506: Build expectations template for labeling (TASK-504 bootstrap)

**Purpose**: Generate blank expectations.jsonl template for labelers to fill in.

### Acceptance Criteria

- [ ] Template generated from manifest: one row per doc_id
- [ ] Each row contains: doc_id, split, file_name, labeling_status=pending, and all extraction field names (empty)
- [ ] Extraction fields: invoice_number, invoice_date, seller_name, seller_tax_id, buyer_name, buyer_tax_id, net_amount, vat_amount, wht_amount, total_amount, etc.
- [ ] Output: `private_data/poc/Comp_1/expectations.template.jsonl`
- [ ] Excluded documents marked with labeling_status=excluded

### Workflow

1. Read manifest
2. For each included doc, create template row with all field names (empty values)
3. For each excluded doc, mark labeling_status=excluded
4. Output JSONL

### Inputs

- Manifest: `private_data/poc/Comp_1/manifest.jsonl`

### Outputs

- `private_data/poc/Comp_1/expectations.template.jsonl` (blank template)

### Dependencies

- TASK-505 (manifest)

### Acceptance Checklist

- [ ] Template JSONL has 43 rows (42 included + 1 excluded)
- [ ] All extraction field names present (empty values)
- [ ] Excluded row has labeling_status=excluded, inclusion_reason=non_transaction_reference_doc
- [ ] Template matches expectations.filled.jsonl schema

---

## TASK-507: Multi-page support script-first pipeline

**Purpose**: Handle multi-page PDFs by rasterizing and merging all pages.

### Acceptance Criteria

- [ ] PDF pages rasterized individually, text merged per document
- [ ] Metadata includes: page_count, is_multi_page
- [ ] Multi-page logic integrated into TASK-501 OCR processor
- [ ] Test on 3+ multi-page PDFs from Comp_1
- [ ] No loss of accuracy due to page merging (manual spot-check on 2 multi-page samples)

### Workflow

1. Detect multi-page PDFs in manifest
2. For each page: rasterize → OCR → extract text
3. Merge all page texts with page separators (e.g., `--- Page 2 ---`)
4. Return merged text + per-page breakdown
5. Include metadata: page_count, is_multi_page

### Inputs

- TASK-501 processor + multi-page PDF files

### Outputs

- OCR output with per-page + merged text, page_count metadata

### Dependencies

- TASK-501 (OCR processor)

### Acceptance Checklist

- [ ] `src/ocr/processor.py` detects multi-page PDFs
- [ ] Pages rasterized and merged correctly
- [ ] Metadata fields page_count and is_multi_page populated
- [ ] Unit tests on 3 multi-page PDFs
- [ ] Accuracy spot-check: merged text extraction quality ≥ single-page baseline

---

## TASK-508: Fallback-first OCR/Extraction routing

**Purpose**: Implement primary→fallback chain for OCR and LLM extraction from day 1.

### Acceptance Criteria

- [ ] OCR: pytesseract (primary) → AWS Textract (fallback)
- [ ] Extraction: Claude-3.5-Haiku (primary) → Claude-3.5-Sonnet (fallback)
- [ ] Auto-routing: failure in primary triggers fallback immediately (no manual intervention)
- [ ] Output includes: `model_used`, `fallback_reason`, `fallback_count`
- [ ] Error codes for all failure modes: timeout, API error, parse error, etc.
- [ ] Monitoring: track fallback rate per document cohort

### Workflow

1. Try primary model with timeout
2. If success, return (model_used = primary)
3. If timeout/error, invoke fallback
4. If fallback success, return (model_used = fallback, fallback_reason = "timeout")
5. If fallback fails, return error_code (no retry)
6. Log fallback event for monitoring

### Inputs

- Processor configs: timeouts, model API keys, fallback flags

### Outputs

- Processor output includes: model_used, fallback_reason, fallback_count per workflow step

### Dependencies

- TASK-501 (OCR)
- TASK-502 (extraction)

### Acceptance Checklist

- [ ] Primary OCR + fallback implemented
- [ ] Primary LLM extraction + fallback implemented
- [ ] Auto-routing logic works (no manual intervention required)
- [ ] Error codes defined and logged
- [ ] Unit test: simulate primary timeout → fallback success
- [ ] Integration test on 3-5 documents, measure fallback rate

---

## TASK-509: Ground-truth labeling guide + QA checklist

**Purpose**: Define clear SOP for labelers to reduce label noise.

### Acceptance Criteria

- [ ] Labeling SOP document: `docs/PoC/LABELING-SOP.md`
- [ ] Field-by-field guidance: what to extract, normalization rules, edge cases
- [ ] QA checklist: dual-review process, conflict resolution
- [ ] Examples: 3-5 sample documents with annotated expected values
- [ ] Training: quick onboarding doc for new labelers
- [ ] Implementation: reviewer fields in template (labeler, review_status, review_notes)

### Workflow

1. Write SOP: field definitions, normalization, edge cases
2. Create QA checklist: dual-review process, voting/escalation
3. Prepare 3-5 example documents with manual annotations
4. Brief labelers on SOP and examples
5. Labelers fill template
6. Reviewers check against SOP + examples
7. Flag discrepancies, resolve via escalation

### Inputs

- TASK-504/TASK-506 requirements
- Sample documents from Comp_1

### Outputs

- `docs/PoC/LABELING-SOP.md` (SOP + examples + checklist)
- `docs/PoC/LABELING-QA-CHECKLIST.md` (dual-review process)

### Dependencies

- TASK-504 (expectations definition)
- TASK-506 (template)

### Acceptance Checklist

- [ ] LABELING-SOP.md covers all extraction fields
- [ ] 3+ example documents with annotated expected values
- [ ] Dual-review checklist defined
- [ ] Escalation process documented
- [ ] Reviewer fields present in expectations template

---

## TASK-510: KPI gate definition for pre-prod and prod monitoring

**Purpose**: Define quality thresholds to prevent low-quality models reaching production.

### Acceptance Criteria

- [ ] **Field-level accuracy**:
  - Tax IDs (seller + buyer): ≥99% exact match
  - Invoice numbers: ≥97%
  - Invoice dates: ≥97%
  - Total amounts: ≥98% (tolerance ±0.01)
  
- [ ] **Document-level pass rate**: ≥95% (all required fields present + balanced)
- [ ] **Debit-credit balancing success**: ≥99%
- [ ] **Fallback rate**: ≤20% (if exceeded, investigate template/OCR quality)
- [ ] **Manual review rate**: ≤15% in steady state
- [ ] **Regression gate**: test cohort accuracy must not drop >1-2 points vs baseline per release

### Workflow

1. Establish baseline metrics on train cohort
2. Measure on val cohort (tuning gate)
3. Measure on test cohort (release gate)
4. Define go/no-go thresholds per metric
5. Monitor in production against KPIs
6. Escalate if any KPI breached

### Inputs

- Test expectations from TASK-504
- Accuracy evaluator from TASK-504

### Outputs

- `docs/PoC/KPI-GATES.md`:
  ```markdown
  ## KPI Gates for Release
  | Metric | Threshold | Baseline | Current | Status |
  |--------|-----------|----------|---------|--------|
  | Tax ID Accuracy | ≥99% | 99.2% | ? | ? |
  | Invoice # Accuracy | ≥97% | 97.8% | ? | ? |
  | ...
  ```

### Dependencies

- TASK-504 (expectations + accuracy eval)

### Acceptance Checklist

- [ ] `docs/PoC/KPI-GATES.md` defines all thresholds
- [ ] Baseline metrics measured and documented
- [ ] Go/no-go decision logic defined
- [ ] Monitoring strategy outlined (per cohort, per doc_type)

---

## TASK-511: Exclusion rule for non-transaction documents in cohort build

**Purpose**: Enforce exclusion rules to prevent reference documents entering train/val/test.

### Acceptance Criteria

- [ ] Exclusion rule implemented by stable hash (SHA-256)
- [ ] Non-transaction docs marked: include_in_training=false
- [ ] Exclusion reason recorded: "non_transaction_reference_doc"
- [ ] Excluded docs appear in split.json["excluded"] array (not in train/val/test)
- [ ] Build fails if excluded doc found in train/val/test
- [ ] Current baseline: 1 doc excluded (chart of accounts)

### Workflow

1. Define exclusion hash list in script
2. For each PDF, compute SHA-256
3. Check against exclusion list
4. If match, mark include_in_training=false
5. Output to manifest + split files
6. Validate in TASK-512 quality gate

### Inputs

- Script: `scripts/build_comp1_dataset_metadata.ps1`
- Exclusion hash list (hardcoded or config)

### Outputs

- Manifest + split with exclusion flags

### Dependencies

- TASK-505 (manifest + split)

### Acceptance Checklist

- [ ] Exclusion hash list defined and documented
- [ ] Script marks excluded docs correctly
- [ ] Manifest rows have include_in_training flag
- [ ] Split file has excluded[] array
- [ ] Build validation in TASK-512 passes

---

## TASK-512: Data quality gate for cohort composition

**Purpose**: Validate that excluded docs don't accidentally enter splits.

### Acceptance Criteria

- [ ] Build validation script checks:
  - No excluded doc in train/val/test
  - Split counts match expected (train=29, val=6, test=7, excluded=1)
  - All included docs present in manifest
  - No duplicates
  - All paths valid relative to Comp_1 root
  
- [ ] Fail with clear error message if validation fails
- [ ] Acceptance checklist: auto-generated report `docs/PoC/COHORT-QUALITY-REPORT.md`

### Workflow

1. After manifest + split generated (TASK-505/511)
2. Load manifest + split files
3. Validate all checks above
4. Output report: ✓ passed or ✗ failed with reason
5. Build continues only if all checks pass

### Inputs

- Manifest: `private_data/poc/Comp_1/manifest.jsonl`
- Split: `private_data/poc/Comp_1/split.json`

### Outputs

- Validation report: `docs/PoC/COHORT-QUALITY-REPORT.md`

### Dependencies

- TASK-505 (manifest + split)
- TASK-511 (exclusion rules)

### Acceptance Checklist

- [ ] Validation script implemented and callable
- [ ] All checks implemented (no excluded in splits, counts, duplicates, paths)
- [ ] Report generated with clear status + error messages
- [ ] Build integration: fail on validation error

---

## TASK-513: Convert cohort status report from Markdown to HTML infographic

**Purpose**: Create visual HTML infographic for stakeholder review.

### Acceptance Criteria

- [ ] HTML file: `docs/PoC/plan/epic-5/cohort-dataset-infographic.html`
- [ ] Visual display of:
  - Total / Included / Excluded counts
  - Train/val/test/excluded split (with proportional bar chart)
  - KPI gates summary (from TASK-510)
  - Exclusion rationale + hash details
  
- [ ] Responsive design (desktop + mobile)
- [ ] No external CSS/JS (self-contained)
- [ ] Auto-refresh capability (TASK-514)

### Workflow

1. Design infographic layout
2. Implement HTML + inline CSS
3. Display metrics from split.json + manifest.jsonl
4. Add visual elements (bar charts, badges)
5. Test on multiple browsers

### Inputs

- TASK-505 (split/manifest data)
- TASK-510 (KPI summary)

### Outputs

- `docs/PoC/plan/epic-5/cohort-dataset-infographic.html`

### Dependencies

- TASK-505, TASK-510, TASK-512

### Acceptance Checklist

- [ ] HTML file created and validates
- [ ] Displays all metrics correctly
- [ ] Responsive layout works (desktop + mobile)
- [ ] No broken links or missing data
- [ ] Ready for TASK-514 (auto-refresh integration)

---

## TASK-514: Auto-refresh HTML infographic from split/manifest metadata

**Purpose**: Keep infographic up-to-date when cohort metadata changes.

### Acceptance Criteria

- [ ] Script/tool auto-generates HTML from latest split.json + manifest.jsonl
- [ ] Callable from CI/CD or manual command
- [ ] Preserves design from TASK-513
- [ ] Updates data fields dynamically (counts, percentages, KPI summary)

### Workflow

1. Read split.json + manifest.jsonl
2. Extract metrics (counts, percentages, exclusion details)
3. Render into HTML template from TASK-513
4. Write output to `docs/PoC/plan/epic-5/cohort-dataset-infographic.html`
5. Commit or publish (CI/CD integration)

### Inputs

- `private_data/poc/Comp_1/split.json`
- `private_data/poc/Comp_1/manifest.jsonl`

### Outputs

- Updated `docs/PoC/plan/epic-5/cohort-dataset-infographic.html`

### Dependencies

- TASK-513 (HTML template)
- TASK-505, TASK-512 (metadata files)

### Acceptance Checklist

- [ ] Script reads split/manifest correctly
- [ ] Generates valid HTML
- [ ] Matches TASK-513 design
- [ ] Data fields update automatically
- [ ] Callable from terminal or CI/CD

---

## TASK-515 (Optional): Epic 5 Summary Report

**Purpose**: Final PoC readiness summary for stakeholders.

### Acceptance Criteria

- [ ] Markdown report: `docs/PoC/plan/epic-5/EPIC-5-SUMMARY.md`
- [ ] Sections:
  - Overview (what was built)
  - Cohort composition (split, exclusions)
  - Module status (OCR, extraction, routing, validation)
  - Accuracy baseline (from test cohort)
  - Known issues + workarounds
  - Recommendations for MVP
  
- [ ] Include links to all task outputs (manifest, split, infographic, expectations, etc.)

### Dependencies

- All TASK-501 to TASK-514

---

## Consolidated Checklist (All Tasks)

### Data & Metadata
- [ ] TASK-505: Manifest + split generated and validated
- [ ] TASK-506: Expectations template created
- [ ] TASK-511: Exclusion rules applied
- [ ] TASK-512: Cohort quality gate passed

### Extraction Pipeline
- [ ] TASK-501: OCR processor complete (pytesseract + Textract fallback)
- [ ] TASK-507: Multi-page support integrated
- [ ] TASK-502: Claude structured extraction (Haiku + Sonnet routing)
- [ ] TASK-508: Fallback routing working

### Validation & Routing
- [ ] TASK-503: Journal routing + Dr/Cr validation complete
- [ ] TASK-509: Labeling SOP + QA checklist documented

### Accuracy & KPIs
- [ ] TASK-504: Expectations filled + accuracy evaluator working
- [ ] TASK-510: KPI gates defined and baseline measured

### Reporting
- [ ] TASK-513: HTML infographic created
- [ ] TASK-514: Auto-refresh working

---

## Next Steps

1. **Immediate** (This week): TASK-505, TASK-506 (data prep)
2. **Week 2-3**: TASK-501, TASK-502, TASK-503 (extraction pipeline)
3. **Week 3-4**: TASK-504, TASK-509 (labeling + accuracy)
4. **Week 4+**: TASK-510, TASK-513, TASK-514 (reporting + KPI monitoring)

---

*Last updated: 2026-06-04*
