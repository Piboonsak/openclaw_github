# Epic 9 — Extraction Accuracy + Line Item PoC: Tasks Detail

> **Epic Goal**: ยกระดับ accuracy จาก PoC feedback + พิสูจน์ feasibility ของ line item extraction
> **Duration**: W1-W2 | **Critical Path**: No (parallel with Epic 8)
> **Baseline Date**: 2026-06-15

---

## TASK-906: Line Item Extraction PoC — Black Box Clear

**Owner**: ML Dev
**Risk**: MEDIUM
**Duration**: ~3 days (FIRST PRIORITY W1)
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-5 (evidence required), PP-11 (business logic mismatch)

### Purpose

ก่อนลงทุนสร้าง line item extraction เต็มรูปแบบ (Epic 14, Phase II/2), ต้องตอบ 3 คำถามให้ชัด: (1) ทำได้ไหม? (2) Cost เท่าไร? (3) แพงเกินไปไหมสำหรับลูกค้า? ผลลัพธ์นี้กำหนด scope + ราคางวด 4 (Phase II/2) โดยตรง.

### What exists today

- OCR pipeline (PaddleOCR + Tesseract) working สำหรับ header fields
- LLM repair (Stage C) with model router working (Gemini Flash / Claude Sonnet fallback)
- Field extraction regex v29 สำหรับ header-level fields
- ไม่มี line item extraction ใดๆ — header only

### What to build

1. **Test harness** — script ที่ส่งเอกสารไปยัง 3 LLM models แล้ว parse/score ผลลัพธ์
2. **Document diversity** — ทดสอบ 20-30 documents ครอบคลุม 8 categories (diversity checklist)
3. **3 model comparison** — Gemini 2.5 Flash (free), Gemini 2.5 Pro, Claude Sonnet 4
4. **6 metrics measurement** — per-field accuracy, document-level success, line total reconciliation, cost/doc, processing time, manual correction time
5. **Go/No-Go evaluation** — score 6 metrics against thresholds, determine Go/Conditional/No-Go
6. **Feasibility report** — 3-5 pages: model recommendation, cost projection at 10K-20K docs/month, limitations found

**Document Diversity Checklist (must cover):**

| Category | ตัวอย่าง | ขั้นต่ำ |
|----------|---------|--------|
| สแกนชัด (300 DPI+) | สแกนเนอร์สำนักงาน | 5 docs |
| สแกนเบลอ / ถ่ายมือถือ | กล้องมือถือ, เอียง, แสงไม่ดี | 3 docs |
| PDF ดิจิทัล (มี text layer) | ออกจากระบบ e-Tax / ERP | 3 docs |
| ตาราง gridline ชัด | invoice มีเส้นตาราง | 5 docs |
| ไม่มี gridline (text-only layout) | ใบเสร็จทั่วไป | 3 docs |
| หลายหน้า (multi-page) | invoice > 1 หน้า | 2 docs |
| มี discount / WHT | หัก ณ ที่จ่าย, ส่วนลด | 3 docs |
| VAT included vs excluded | ทั้ง 2 แบบ | 2 docs |

**Metrics & Go Thresholds:**

| # | Metric | Go Threshold |
|---|--------|-------------|
| 1 | Per-field accuracy (product_name, qty, unit_price, line_amount, unit) | >= 80% ทุก field |
| 2 | Document-level success rate (ทุก field ถูกครบ) | >= 60% |
| 3 | Line total reconciliation (sum(line_amounts) = invoice total) | >= 70% pass |
| 4 | Cost per document | <= 1.50 THB/doc |
| 5 | Processing time per document (LLM call only) | <= 15 sec |
| 6 | Manual correction time (estimated from error count) | <= 3 min/doc |

**Go/No-Go Criteria:**

| Result | Decision | Impact on Phase II/2 |
|--------|---------|---------------------|
| >= 4/6 metrics pass | **Go** | Epic 14 full scope + pricing confirmed |
| 3/6 metrics pass | **Conditional** | Epic 14 scope reduced (specific formats only) |
| <= 2/6 metrics pass | **No-Go** | Epic 14 deferred, งวด 4 ลดราคาตาม scope |

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Create | `scripts/line_item_poc.py` | Test harness: send docs to 3 models, parse results, compute metrics |
| Create | `scripts/line_item_prompts.py` | LLM prompt templates for line item extraction (structured output) |
| Create | `tests/ml/test_line_item_poc.py` | Validation tests: metric computation, scoring logic |
| Create | `docs/PoC/reports/TASK-906-FEASIBILITY-REPORT.md` | Feasibility report (3-5 pages) |
| Create | `tests/fixtures/line_item_samples/` | Directory for test document images/PDFs |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_906_1 | Tested >= 20 documents across diversity checklist (>= 6/8 categories covered) | `test_diversity_coverage` |
| ac_906_2 | 3 models compared with same document set | `test_three_models_compared` |
| ac_906_3 | 6 metrics computed per model with numeric results | `test_all_metrics_computed` |
| ac_906_4 | Go/No-Go recommendation in feasibility report with supporting data | manual review |
| ac_906_5 | Cost projection at 10K docs/month in THB per model | manual review |
| ac_906_6 | Feasibility report identifies limitations (formats that fail, fields with issues) | manual review |

### Governance fields

```json
{
  "task_id": "TASK-906",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["tests/**", "docs/**", "scripts/**", "src/backend/ml/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/db/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-901: VAT Disambiguation — Arithmetic-First

**Owner**: ML / Backend Dev
**Risk**: MEDIUM
**Duration**: ~3 days
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-5 (evidence required), PP-10 (wrong-fix retry loop), PP-11 (business logic mismatch)

### Purpose

PoC amount_reconciler ทำ VAT inclusive/exclusive detection ได้ระดับหนึ่ง แต่มีกรณีที่ OCR อ่าน amount ผิดตำแหน่ง (สลับ net กับ total). วิธีแก้: ทดสอบ 4 combinations ทั้งหมดแล้วเลือก best-fit ตาม arithmetic match — ไม่ guess, ให้คณิตศาสตร์ตัดสิน.

### What exists today

- `src/backend/ml/amount_reconciler.py` — basic VAT inclusive/exclusive detection
- Reconciliation logic ที่เลือก 1 interpretation แล้ว validate
- Test corpus มีบ้างแต่ไม่ครอบคลุม 4 combinations

### What to build

1. **4-combination tester** — สำหรับทุก document, ทดสอบ:
   - Combination A: slot1=net, slot2=total, mode=exclusive (net + vat = total)
   - Combination B: slot1=total, slot2=net, mode=exclusive (net + vat = total)
   - Combination C: slot1=net_incl_vat, mode=inclusive (amount / 1.07 = net, amount - net = vat)
   - Combination D: slot2=net_incl_vat, mode=inclusive (amount / 1.07 = net, amount - net = vat)
2. **Best-fit selector** — pick combination with lowest arithmetic error (abs difference)
3. **Confidence boost** — when arithmetic matches perfectly (error < 0.50 THB), boost confidence to 0.95+
4. **Tolerance handling** — Thai tax rounding: allow +/- 1 satang (0.01 THB) tolerance
5. **Logging** — log all 4 combinations' errors for debugging + accuracy measurement

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/ml/amount_reconciler.py` | Rewrite core logic: test 4 combos, pick best, confidence boost |
| Create | `tests/ml/test_vat_disambiguation.py` | Tests: all 4 combos, best-fit selection, edge cases |
| Create | `tests/fixtures/vat_test_corpus.json` | Golden test corpus: 20+ documents with known VAT mode + amounts |
| Modify | `tests/services/test_export_service.py` | Update tests if amount output format changes |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_901_1 | 4 combinations tested per document (all arithmetic paths evaluated) | `test_four_combinations_tested` |
| ac_901_2 | Best-fit combination selected based on lowest arithmetic error | `test_best_fit_selected` |
| ac_901_3 | Confidence boosted to >= 0.95 when arithmetic error < 0.50 THB | `test_confidence_boost_on_perfect_match` |
| ac_901_4 | Rounding tolerance of +/- 1 satang (0.01 THB) applied | `test_satang_rounding_tolerance` |
| ac_901_5 | Accuracy improvement measurable on test corpus (before/after comparison) | `test_accuracy_improvement` |
| ac_901_6 | All 4 combination errors logged for debugging | `test_combination_errors_logged` |

### Governance fields

```json
{
  "task_id": "TASK-901",
  "risk_tier": "MEDIUM",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/ml/amount_reconciler.py", "tests/ml/**", "tests/services/**", "tests/fixtures/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/db/**"],
  "max_loops": 5,
  "escalation_policy": "human"
}
```

---

## TASK-902: WHT Detection + Backfill Solver

**Owner**: ML / Backend Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-5 (evidence required), PP-11 (business logic mismatch)

### Purpose

PoC ไม่มี WHT (Withholding Tax / ภาษีหัก ณ ที่จ่าย) detection. สำนักงานบัญชีต้องรู้ว่ามี WHT หรือไม่ + rate เท่าไร + เป็น PND3 หรือ PND53 เพื่อกรอก voucher ถูก. Backfill solver ช่วยเติมข้อมูลเมื่อ OCR อ่านได้แค่บางส่วน.

### What exists today

- `src/backend/ml/field_extractor.py` — regex v29 สำหรับ header fields
- ไม่มี WHT detection patterns
- ไม่มี `has_wht`, `wht_rate`, `wht_form` fields ใน extraction output
- WHT amount field มีใน DB model แต่ไม่ได้ populate

### What to build

1. **WHT rate detection** — regex patterns สำหรับ common rates: 1%, 2%, 3%, 5%, 10%
2. **WHT keyword patterns** — "ภาษีหัก ณ ที่จ่าย", "WHT", "หัก ณ ที่จ่าย", "Withholding Tax"
3. **PND form detection** — PND3 (บุคคลธรรมดา/individual), PND53 (นิติบุคคล/corporate) based on tax ID pattern
4. **Backfill solver** — when net + vat known but WHT missing, derive from context:
   - If total_payment < net_amount: WHT = net_amount - total_payment
   - If WHT rate visible in document: wht_amount = net_amount * rate
5. **Output fields** — add to extraction: `has_wht` (boolean), `wht_rate` (float), `wht_amount` (float), `wht_form` (PND3/PND53/null)
6. **Confidence scoring** — separate confidence for WHT fields

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/ml/field_extractor.py` | เพิ่ม WHT detection regex, rate patterns, PND form detection |
| Create | `tests/ml/test_wht_detection.py` | Tests: rate detection, backfill, PND form, edge cases |
| Create | `tests/fixtures/wht_test_samples.json` | Test samples: documents with various WHT scenarios |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_902_1 | WHT rates 1%, 2%, 3%, 5%, 10% detected from document text | `test_wht_rate_detection` |
| ac_902_2 | Backfill solver derives WHT amount when net + vat known but WHT missing | `test_wht_backfill_from_context` |
| ac_902_3 | `has_wht` flag correctly set (True when WHT present, False otherwise) | `test_has_wht_flag` |
| ac_902_4 | PND3 detected for individual tax IDs (13 digits), PND53 for corporate (13 digits starting with 0) | `test_pnd_form_detection` |
| ac_902_5 | WHT amount matches expected value within rounding tolerance | `test_wht_amount_accuracy` |
| ac_902_6 | Documents without WHT correctly return `has_wht=False` (no false positives) | `test_no_false_positive_wht` |

### Governance fields

```json
{
  "task_id": "TASK-902",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/ml/field_extractor.py", "tests/ml/**", "tests/fixtures/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/db/**"],
  "max_loops": 5,
  "escalation_policy": "stop"
}
```

---

## TASK-903: OCR Gridline Removal

**Owner**: ML Dev
**Risk**: LOW
**Duration**: ~2 days
**Closes pain points**: PP-2 (requirements in AC), PP-3 (details encoded), PP-5 (evidence required), PP-8 (scope locked — only modifies ocr.py)

### Purpose

PoC OCR มีปัญหากับเอกสารที่มีเส้นตาราง (gridlines) — Tesseract/PaddleOCR อ่าน line characters เป็นส่วนหนึ่งของ text ทำให้ extraction accuracy ลดลง. OpenCV morphological preprocessing ลบ gridlines ก่อน OCR เพื่อให้ text ชัดขึ้น.

### What exists today

- `src/backend/ml/ocr.py` — PaddleOCR + Tesseract pipeline
- Digital PDF text layer detection (bypass OCR for digital PDFs)
- ไม่มี image preprocessing สำหรับ gridline removal

### What to build

1. **Gridline detection** — OpenCV morphological operations (erode + dilate) เพื่อ detect horizontal + vertical lines
2. **Line masking** — mask detected lines with white pixels before OCR
3. **Digital PDF bypass** — ไม่ทำ gridline removal สำหรับ PDF ที่มี text layer (ใช้ text layer โดยตรง)
4. **Feature flag** — `OCR_REMOVE_GRIDLINES` env var (default: True)
5. **Quality check** — compare OCR results with/without gridline removal, use better result
6. **Min line length** — only remove lines longer than threshold (e.g., 100px) to avoid removing text underscores

### Files to create/modify

| Action | File | What |
|--------|------|------|
| Modify | `src/backend/ml/ocr.py` | เพิ่ม gridline removal as preprocessing step |
| Create | `src/backend/ml/image_preprocessing.py` | OpenCV gridline detection + masking functions |
| Create | `tests/ml/test_gridline_removal.py` | Tests: gridlines removed, text preserved, feature flag, digital PDF bypass |
| Create | `tests/fixtures/gridline_samples/` | Test images: with gridlines, without gridlines, mixed |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_903_1 | Horizontal + vertical gridlines removed from scanned images before OCR | `test_gridlines_removed` |
| ac_903_2 | Text content preserved after gridline removal (no character loss) | `test_text_preserved` |
| ac_903_3 | Digital PDFs with text layer bypass gridline removal (text layer used directly) | `test_digital_pdf_bypass` |
| ac_903_4 | Feature flag `OCR_REMOVE_GRIDLINES=false` disables preprocessing | `test_feature_flag_disables` |
| ac_903_5 | Accuracy improvement measurable on gridline test corpus (before/after) | `test_accuracy_improvement_gridlines` |
| ac_903_6 | Short lines (< 100px, e.g., underscores) not removed | `test_short_lines_preserved` |

### Governance fields

```json
{
  "task_id": "TASK-903",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/ml/ocr.py", "src/backend/ml/image_preprocessing.py", "tests/ml/**", "tests/fixtures/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/db/**"],
  "max_loops": 5,
  "escalation_policy": "stop"
}
```

---

## TASK-905: Vendor Branch Extraction (DONE)

**Owner**: ML / Backend Dev
**Risk**: LOW
**Duration**: Completed
**Closes pain points**: --

### Purpose

Extract vendor branch information (สำนักงานใหญ่/สาขา) from documents — regex patterns + zero-padded 5-digit branch codes.

### What exists today

Completed. Regex patterns for branch extraction integrated into `src/backend/ml/field_extractor.py`.

### What to build

No work needed — task is done.

### Files to create/modify

| Action | File | What |
|--------|------|------|
| -- | -- | No changes needed |

### Acceptance criteria

| ID | Condition | Test |
|----|-----------|------|
| ac_905_1 | Branch codes extracted as zero-padded 5-digit format | Already passing |
| ac_905_2 | สำนักงานใหญ่ detected as branch 00000 | Already passing |

### Governance fields

```json
{
  "task_id": "TASK-905",
  "risk_tier": "LOW",
  "model_tier": "tier-2a-copilot",
  "allowed_scope": ["src/backend/ml/field_extractor.py", "tests/ml/**"],
  "forbidden_scope": [".env*", "src/backend/auth/**", "src/backend/db/**"],
  "max_loops": 5,
  "escalation_policy": "stop"
}
```

---

*Created: 2026-06-15*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
*Master Plan: [PHASE-II-MASTER-PLAN.md](../PHASE-II-MASTER-PLAN.md)*
