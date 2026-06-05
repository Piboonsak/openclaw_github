# Epic 5 Task Summary & Project References

## Quick Overview Table

| TASK ID | Title | Owner | Status | Acceptance Criteria | Links |
|---------|-------|-------|--------|-------------------|-------|
| **TASK-501** | OCR Rasterization Pipeline | ML | Design | PDF→images→OCR with caching | [Details](EPIC-5-TASKS-DETAIL.md#task-501-build-the-pdf-image-rasterization-pipeline-and-secure-raw-text-file-caches) |
| **TASK-502** | Claude Structured Extraction | ML | Design | JSON schema with field confidence | [Details](EPIC-5-TASKS-DETAIL.md#task-502-build-the-claude-structured-message-json-schema-miner) |
| **TASK-503** | Journal Rules & Dr/Cr Router | ML | Design | COA mapping + balance validation | [Details](EPIC-5-TASKS-DETAIL.md#task-503-write-the-journal-rules-router-compiling-coa-accounts) |
| **TASK-504** | Ground-Truth Expectations | Data | Design | Dual-review labeling + accuracy eval | [Details](EPIC-5-TASKS-DETAIL.md#task-504-create-expectationsjson-containing-ground-truth-values-to-calculate-exact-accuracy-metrics) |
| **TASK-505** | Dataset Manifest & Split | Data | **Done** ✓ | 42/29/6/7 split, SHA256 exclusion | [Details](EPIC-5-TASKS-DETAIL.md#task-505-build-dataset-manifest--deterministic-split-from-comp_1) |
| **TASK-506** | Expectations Template | Data | **Done** ✓ | Blank template for 42 docs | [Details](EPIC-5-TASKS-DETAIL.md#task-506-build-expectations-template-for-labeling-task-504-bootstrap) |
| **TASK-507** | Multi-Page Support | ML | Design | Per-page + merged OCR output | [Details](EPIC-5-TASKS-DETAIL.md#task-507-multi-page-support-script-first-pipeline) |
| **TASK-508** | Fallback OCR/LLM Routing | ML | Design | pytesseract→Textract, Haiku→Sonnet | [Details](EPIC-5-TASKS-DETAIL.md#task-508-fallback-first-ocrextraction-routing) |
| **TASK-509** | Labeling SOP & QA | Data | Design | Field guidance + dual-review | [Details](EPIC-5-TASKS-DETAIL.md#task-509-ground-truth-labeling-guide--qa-checklist) |
| **TASK-510** | KPI Gates Definition | ML | Design | Tax ID ≥99%, Doc pass ≥95% | [Details](EPIC-5-TASKS-DETAIL.md#task-510-kpi-gate-definition-for-pre-prod-and-prod-monitoring) |
| **TASK-511** | Exclusion Rules | Data | **Done** ✓ | Non-transaction doc filtering | [Details](EPIC-5-TASKS-DETAIL.md#task-511-exclusion-rule-for-non-transaction-documents-in-cohort-build) |
| **TASK-512** | Cohort Quality Gate | Data | **Done** ✓ | No excluded→train/val/test | [Details](EPIC-5-TASKS-DETAIL.md#task-512-data-quality-gate-for-cohort-composition) |
| **TASK-513** | HTML Infographic | Frontend | **Done** ✓ | Visual cohort status report | [Details](EPIC-5-TASKS-DETAIL.md#task-513-convert-cohort-status-report-from-markdown-to-html-infographic) |
| **TASK-514** | Auto-Refresh Infographic | Frontend | Design | Dynamic JSON→HTML generation | [Details](EPIC-5-TASKS-DETAIL.md#task-514-auto-refresh-html-infographic-from-splitmanifest-metadata) |

---

## Artifact Locations

### Data Files
- **Manifest**: `private_data/poc/Comp_1/manifest.jsonl` (43 rows with metadata)
- **Split**: `private_data/poc/Comp_1/split.json` (deterministic assignment: 29/6/7/1)
- **Expectations Template**: `private_data/poc/Comp_1/expectations.template.jsonl` (blank, ready for labeling)

### Configuration & Scripts
- **Build Script**: `scripts/build_comp1_dataset_metadata.ps1` (regenerates manifest + split)
- **COA Rules Config**: `rule_coa.yaml` (journal mapping, TBD)

### Documentation
- **Full Task Details**: `docs/PoC/plan/epic-5/EPIC-5-TASKS-DETAIL.md` ← **Master reference**
- **Cohort Infographic**: `docs/PoC/plan/epic-5/cohort-dataset-infographic.html` (visual stakeholder report)
- **KPI Gates** (TBD): `docs/PoC/KPI-GATES.md`
- **Labeling SOP** (TBD): `docs/PoC/LABELING-SOP.md`

---

## What Each Task Delivers (At a Glance)

### Data Preparation (TASK-505, 506, 511, 512)
- ✅ **TASK-505**: Generates manifest (doc_id, sha256, file_path, split assignment) and split.json (train/val/test/excluded)
- ✅ **TASK-506**: Blank expectations.jsonl template with field names for labelers to fill
- ✅ **TASK-511**: Exclusion logic by hash (removes 1 non-transaction doc automatically)
- ✅ **TASK-512**: Quality gate validates no excluded docs enter train/val/test splits

### OCR Pipeline (TASK-501, 507, 508)
- ⚙️ **TASK-501**: PDF→Image→Tesseract OCR with caching (outputs merged_text + per-page text)
- ⚙️ **TASK-507**: Handles multi-page PDFs (page-by-page rasterization + text merge)
- ⚙️ **TASK-508**: Fallback routing: pytesseract (primary) → AWS Textract (fallback on timeout)

### Extraction & Validation (TASK-502, 503, 504)
- ⚙️ **TASK-502**: Claude LLM structured extraction with JSON schema (Haiku → Sonnet fallback)
- ⚙️ **TASK-503**: Journal routing (extracts fields → Dr/Cr posting → balance validation)
- ⚙️ **TASK-504**: Ground-truth expectations + accuracy evaluator (measures field-level recall/precision)

### Quality & Process (TASK-509, 510)
- ⚙️ **TASK-509**: Labeling guide (SOP, field definitions, QA checklist, examples)
- ⚙️ **TASK-510**: KPI gates (Tax ID ≥99%, Invoice date ≥97%, Doc pass ≥95%, etc.)

### Reporting (TASK-513, 514)
- ✅ **TASK-513**: HTML infographic showing cohort split, KPI thresholds, exclusion details
- ⚙️ **TASK-514**: Auto-generate HTML from split.json/manifest.jsonl (dynamic refresh)

---

## How to Verify a Task is Complete

### For Data Tasks (505, 506, 511, 512)
1. Open `private_data/poc/Comp_1/manifest.jsonl` → verify 43 rows (42 included + 1 excluded)
2. Open `private_data/poc/Comp_1/split.json` → verify train=29, val=6, test=7, excluded=1
3. Open `private_data/poc/Comp_1/expectations.template.jsonl` → verify 43 rows with empty field values
4. Run `docs/PoC/COHORT-QUALITY-REPORT.md` validation → should show all checks ✓ passed

### For ML/Extraction Tasks (501, 502, 503, 507, 508, 510)
1. Run unit tests: `pytest tests/test_ocr.py`, `tests/test_extraction.py`, `tests/test_validation.py`
2. Run integration test on 5 sample PDFs from Comp_1
3. Verify output structure (JSON schema) matches expected format
4. Verify error codes emitted for failure modes

### For Labeling Tasks (504, 509)
1. Check `docs/PoC/LABELING-SOP.md` exists and covers all fields
2. Check `expectations.filled.jsonl` has all 42 rows labeled + dual-reviewed
3. Run accuracy evaluator: compare predictions vs ground-truth

### For Reporting Tasks (513, 514)
1. Open `docs/PoC/plan/epic-5/cohort-dataset-infographic.html` in browser → visual display loads correctly
2. For TASK-514: run auto-refresh script → HTML updates with latest split/manifest data

---

## Access Patterns (How to Use This Info)

**I'm starting TASK-501 (OCR):**
- Read: [EPIC-5-TASKS-DETAIL.md § TASK-501](EPIC-5-TASKS-DETAIL.md#task-501-build-the-pdf-image-rasterization-pipeline-and-secure-raw-text-file-caches)
- Input: `private_data/poc/Comp_1/manifest.jsonl` (from TASK-505 ✓ already done)
- Output: `cache/{sha256}/ocr_output.json` (per-page + merged text)
- Test: `tests/test_ocr.py` (>80% coverage)

**I'm starting TASK-509 (Labeling SOP):**
- Read: [EPIC-5-TASKS-DETAIL.md § TASK-509](EPIC-5-TASKS-DETAIL.md#task-509-ground-truth-labeling-guide--qa-checklist)
- Inputs: TASK-506 (template ✓) + TASK-504 (expectations definition ✓)
- Outputs: `docs/PoC/LABELING-SOP.md`, `docs/PoC/LABELING-QA-CHECKLIST.md`
- Resource: 3-5 example PDFs from Comp_1 with manual annotations

**I want to verify cohort is ready:**
- Open: `docs/PoC/plan/epic-5/cohort-dataset-infographic.html` → instant visual summary
- Check: `docs/PoC/COHORT-QUALITY-REPORT.md` → validation status
- Data: `private_data/poc/Comp_1/split.json` → exact counts + seed

---

## Common Questions

**Q: Why is TASK-505 marked "Done" but TASK-514 "Design"?**
A: TASK-505 generates the data files (manifest + split). TASK-514 is the future automation to regenerate the HTML report whenever data changes. Both are necessary.

**Q: Can I start TASK-502 before TASK-501 finishes?**
A: No. TASK-502 consumes OCR output from TASK-501, so they have a hard dependency.

**Q: Where do I find the full task specification?**
A: Open [EPIC-5-TASKS-DETAIL.md](EPIC-5-TASKS-DETAIL.md). Each task has: Acceptance Criteria, Workflow, Inputs/Outputs, Dependencies, and a Checklist.

**Q: Who's responsible for TASK-509 (Labeling SOP)?**
A: Data team. It's a prerequisite for TASK-504 (ground-truth labeling).

**Q: How do I know if extraction accuracy is good enough?**
A: Check TASK-510 (KPI gates). Baseline targets: Tax ID ≥99%, Invoice # ≥97%, Total amount ≥98%. Measure on test split.

---

## GitHub Project Links

- **Project Board**: [ai-accounting-copilot Project #1](https://github.com/YAHWAN-SHOP/ai-accounting-copilot/projects/1)
- **TASK-505 Issue**: (created as draft item, convert to issue to open)
- **TASK-506 Issue**: (created as draft item, convert to issue to open)
- ... (all TASK items 501-514 in project board)

---

*Last Updated: 2026-06-04*  
*Maintainer: ML Data Team*  
*Status: Epic 5 data + reporting phase complete; awaiting OCR/extraction/routing implementation*
