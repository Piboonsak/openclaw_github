# TASK-906 Line Item Extraction PoC Plan

> Phase: Phase II/1 PoC only  
> Downstream: Epic 14 Line Item + Inventory Full, Phase II/2 CR-based  
> Status: Draft plan aligned with real folder scan findings  
> Scope rule: no production API, DB, or UI changes in TASK-906 unless explicitly approved

---

## 1. Goal

TASK-906 ต้องตอบให้ชัดก่อนลงทุนทำ Line Item + Inventory เต็มรูปแบบ:

1. Vision LLM อ่าน line item จากเอกสารจริงได้แม่นพอไหม
2. ต้นทุนและเวลาต่อเอกสารรับได้ไหม
3. Human review ต้องแก้เยอะไหม
4. ถ้าจะต่อเป็น inventory/stock workflow ต้องลด scope หรือแก้ schema อะไรบ้าง

ผลลัพธ์สุดท้ายต้องเป็น feasibility report ที่ตัดสินเป็น:

| Result | Meaning | Downstream action |
|---|---|---|
| Go | ทำ production full ได้ | Epic 14 full scope + pricing confirmed |
| Conditional | ทำได้เฉพาะบาง format/use case | Epic 14 scope reduced to supported formats |
| No-Go | ยังไม่คุ้มทำ full | Defer Epic 14 / move to later phase |

---

## 2. Product Workflow Hypothesis

Line item extraction ควรทำรวมใน scan pipeline ปกติ แต่แยกเป็น sub-stage เพื่อไม่ทำให้เอกสารหลักค้างถ้า line item fail.

Recommended flow:

1. User upload เอกสารตามปกติ
2. OCR/header extraction ทำงานก่อน เช่น vendor, invoice no, date, net, VAT, gross, WHT
3. Line item vision extraction ทำงานเป็น optional sub-stage หลัง header extraction
4. ระบบ reconcile `sum(line_amount)` กับ `net_amount` เป็นหลัก เพราะ VAT/gross เป็น document summary
5. ระบบ classify แต่ละ row เป็น `stock_item`, `part_or_material`, `labor`, `service`, `office_supply`, `unknown`
6. ระบบ match line item กับ company product/stock master ถ้ามี
7. Review UI แสดง suggested match + confidence:
   - Green: confidence สูง, match ชัด
   - Amber: น่าจะ match แต่ต้องให้คนยืนยัน
   - Red/Flag: ไม่มั่นใจ, ยอดไม่ reconcile, หรือ row boundary น่าสงสัย
8. User เลือกต่อ row:
   - confirm as existing stock item
   - create new stock item candidate
   - mark as non-stock expense
   - mark as labor/service
   - reject/ignore row
9. Confirmation ถูกบันทึกเป็น alias/history ก่อน แล้วค่อย batch dedup/merge เข้า product master เพื่อลด latency

TASK-906 จะยังไม่สร้าง workflow นี้ทั้งหมด แต่ PoC ต้องพิสูจน์ว่า extraction + classification + match-confidence design ไปต่อได้จริง.

---

## 3. Corpus And Real Data Source

Primary real-data folder:

```text
private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL
```

PoC corpus target:

| Set | Count | Purpose |
|---|---:|---|
| Core selected set | 20 docs | locked set for model comparison |
| Reserve set | 5 docs | promote only if core doc becomes unusable |
| Full folder scan | all available docs | practical review HTML and failure pattern discovery |

Selection rules:

1. Start from included docs in existing `private_data/poc` manifests.
2. Exclude multi-invoice files, reference-only docs, and files with no usable line-item area.
3. Preserve diversity coverage where possible.
4. Minimum fallback: at least 20 docs and at least 6/8 diversity categories.
5. Use the same locked core doc set for every model.

Diversity categories:

| Category | Minimum target |
|---|---:|
| Clear scan / 300 DPI+ | 5 docs |
| Blurry / mobile / skewed | 3 docs |
| Digital PDF / text layer | 3 docs |
| Clear table gridline | 5 docs |
| No gridline / text layout | 3 docs |
| Multi-page | 2 docs |
| Discount or WHT | 3 docs |
| VAT included/excluded mix | 2 docs |

---

## 4. Extraction Strategy

Use vision input as primary source. OCR text may be sent as fallback/reference only.

Prompt contract:

1. Extract every visible invoice line item row.
2. Do not include header fields as rows.
3. Do not include VAT, WHT, gross total, net total, payment total, or footer summary rows as line items.
4. Return strict JSON only.
5. Required fields:
   - `product_name`
   - `qty`
   - `unit`
   - `unit_price`
   - `line_amount`
   - `line_type`
   - `line_type_confidence`
   - `stock_candidate`
   - `confidence_reasons`
6. If line item table is not visible, return empty `line_items` with notes.
7. If a row is ambiguous, keep it but lower confidence and add reason.

Recommended JSON shape:

```json
{
  "document_total": "",
  "currency": "THB",
  "line_items": [
    {
      "product_name": "",
      "qty": "",
      "unit": "",
      "unit_price": "",
      "line_amount": "",
      "line_type": "unknown",
      "line_type_confidence": 0.0,
      "stock_candidate": false,
      "confidence_reasons": []
    }
  ],
  "notes": []
}
```

---

## 5. Line Type And Confidence Design

Line item confidence should not rely only on LLM self-confidence. It should combine model output with rule-based signals and optional company master matching.

### 5.1 Output categories

| Category | Meaning | Default inventory behavior |
|---|---|---|
| `stock_item` | matched known company stock/product item | default selectable for stock |
| `part_or_material` | likely part/material but not confirmed against master | review required |
| `labor` | labor/wage/fee line | default non-stock |
| `service` | service/logistics/transport line | default non-stock unless user overrides |
| `office_supply` | supply item that may not be stock for this business | review required or default non-stock |
| `unknown` | insufficient evidence | review required |

### 5.2 Labor/service keyword boost

Boost `labor` or `service` confidence when product/description includes terms like:

```text
ค่าแรง
ค่า
ค่าบริการ
ค่าซ่อม
ค่าติดตั้ง
ค่าเดินทาง
ค่าส่ง
ค่าขนส่ง
ขนส่ง
บริการ
service
fee
wage
labor
delivery
shipping
transport
```

Special note:

1. The Thai word `ค่า` alone is a strong expense/service signal, but not always enough to decide exact type.
2. `ค่าแรง` should be treated as very high-confidence labor.
3. WHT at document level should boost labor/service suspicion, but must not mark every row as labor automatically.
4. If WHT exists and a row has labor/service keywords, confidence should increase further.

### 5.3 Part/material keyword boost

Boost `part_or_material` confidence when product/description includes spare-part/product terms like:

```text
ท่อ
ท่อแบน
แหวน
สกรู
น็อต
น๊อต
ลูกปืน
สายพาน
โซ่
เฟือง
มอเตอร์
ปั๊ม
วาล์ว
เซ็นเซอร์
สายไฟ
สวิตช์
แผ่น
เหล็ก
อลูมิเนียม
bearing
screw
bolt
nut
washer
motor
sensor
valve
pipe
plate
roller
sprocket
cable
connector
part
spare
material
```

### 5.4 Unit-based boost

Units can boost product/material confidence, but should not decide stock status by themselves.

Strong stock/material unit signals:

```text
ชิ้น
ตัว
อัน
เส้น
ท่อน
แท่ง
ชุด
กล่อง
ม้วน
แผ่น
pcs
pc
piece
set
roll
box
meter
m
kg
```

No-unit rows should be reviewed more carefully. They often represent labor/service, but many real invoices also omit units for parts.

### 5.5 Office supply caution

Items like paper, notebook, pen, office equipment, or consumables may be physical goods but not business stock.

Examples:

```text
กระดาษ
สมุด
ปากกา
แฟ้ม
หมึก
เครื่องเขียน
office supply
paper
pen
notebook
toner
stationery
```

These should not auto-confirm as stock unless:

1. They match the company's product/stock master, or
2. The reviewer confirms this business wants to track them as stock.

### 5.6 Company master fuzzy match boost

If company has product/stock master data, fuzzy matching should be the strongest stock signal.

Match features:

1. normalized name similarity
2. SKU/part number exact or near-exact match
3. unit compatibility
4. supplier/vendor history
5. prior human confirmations
6. alias table match

Suggested confidence bands:

| Band | Rule of thumb | UI behavior |
|---|---|---|
| `>= 0.90` | exact SKU/alias or strong name + unit + supplier match | green suggested match |
| `0.70 - 0.89` | likely match but needs review | amber candidate |
| `0.50 - 0.69` | weak similarity only | flag for manual selection |
| `< 0.50` | no reliable match | no auto-match |

### 5.7 Final confidence formula

PoC can start with a simple weighted score:

```text
final_confidence =
  0.45 * extraction_confidence
+ 0.25 * keyword_signal
+ 0.20 * unit_signal
+ 0.10 * reconciliation_signal
```

If company product master is available:

```text
final_confidence =
  0.35 * extraction_confidence
+ 0.15 * keyword_signal
+ 0.10 * unit_signal
+ 0.10 * reconciliation_signal
+ 0.30 * master_match_signal
```

This is only a starting point. TASK-906 should record enough evidence to tune these weights later.

---

## 6. Ground Truth Creation

Ground truth is sidecar data, not an extension of existing header expectations.

Files:

```text
private_data/poc/line_item_poc/corpus_manifest.json
private_data/poc/line_item_poc/line_item_ground_truth.json
```

Ground truth workflow:

1. Bootstrap labels with selected model.
2. Human verifies every core doc.
3. Lock verified labels with reviewer status and timestamp.
4. Reserve docs are promoted only if core doc is excluded.
5. Timed review sample uses 5 stratified core docs.

Line-item truth fields:

```json
{
  "doc_id": "",
  "review_status": "locked",
  "reviewer_notes": "",
  "locked_at": "",
  "line_items": [
    {
      "product_name": "",
      "qty": "",
      "unit": "",
      "unit_price": "",
      "line_amount": "",
      "line_type": "",
      "stock_candidate": false
    }
  ]
}
```

---

## 7. Model Comparison

Use the exact same locked core set for all models.

Model set:

```text
google/gemini-2.5-flash-lite
google/gemini-2.5-flash
anthropic/claude-sonnet-4
```

Runtime model routing should stay configurable. Do not hardcode the production
line-item model in business logic.

Recommended routing parameters:

```text
BWCACC_OPENROUTER_API_KEY=<loaded from D:\key\bwcacc-keys.txt>
STAGE_C_FREE_MODELS=google/gemini-2.5-flash-lite
STAGE_C_DEFAULT_MODEL=google/gemini-2.5-flash-lite
STAGE_C_BACKUP_MODELS=openai/gpt-4.1-nano,google/gemini-3.1-flash-lite
STAGE_C_ESCALATION_MODEL=anthropic/claude-sonnet-4
```

Backup decision from smoke test:

| Role | Model | Notes |
|---|---|---|
| Primary | `google/gemini-2.5-flash-lite` | cheapest proven path in current PoC |
| First backup | `openai/gpt-4.1-nano` | non-Gemini backup, same row count on Comp_3 smoke test |
| Same-family backup | `google/gemini-3.1-flash-lite` | works, faster in smoke test, higher observed cost |
| Emergency | `openai/gpt-4o-mini` | works, but too expensive for normal fallback |

Qwen/Mistral vision models remain candidates only after OpenRouter provider
routing is adjusted for their available providers.

Outputs per model:

```text
private_data/poc/line_item_poc/results/<model>/raw/
private_data/poc/line_item_poc/results/<model>/normalized/
private_data/poc/line_item_poc/results/<model>/metrics.json
private_data/poc/line_item_poc/results/comparison_summary.json
docs/PoC/reports/TASK-906-FEASIBILITY-REPORT.md
```

Folder-level human review output:

```text
docs/PoC/reports/TASK-906-LINE-ITEM-FOLDER-REVIEW.html
private_data/poc/line_item_poc/folder_scan_results.json
private_data/poc/line_item_poc/folder_scan_raw/
```

---

## 8. Normalization And Matching

Normalize before scoring:

| Field | Normalization |
|---|---|
| `product_name` | trim, collapse whitespace, lowercase for comparison |
| `unit` | normalize Thai/English variants, e.g. `pcs`, `pc`, `ชิ้น` |
| `qty` | numeric tolerance `0.001` |
| `unit_price` | numeric tolerance `0.01 THB` |
| `line_amount` | numeric tolerance `0.01 THB` |

Row matching:

1. Match predicted rows to truth rows with best line-level alignment.
2. Use product-name similarity plus numeric similarity.
3. Treat row-count mismatch as document-level failure.
4. Still calculate per-field accuracy for matched rows to show where it failed.

Reconciliation:

1. Prefer `net_amount` for line total reconciliation.
2. Use `gross/total_amount` only if net is missing and there is no VAT summary.
3. Pass if `abs(sum(line_amount) - expected_line_total) <= 1.00 THB`.

---

## 9. Metrics

TASK-906 uses 6 metrics.

| # | Metric | How to calculate | Go threshold |
|---|---|---|---|
| 1 | Per-field accuracy | accuracy per field over matched rows | `>= 80%` every required field |
| 2 | Document-level success | every required field correct for every row and row count matches | `>= 60%` docs |
| 3 | Line total reconciliation | line sum matches expected invoice net total within `1.00 THB` | `>= 70%` docs |
| 4 | Cost per document | prompt/completion tokens x pricing table | `<= 1.50 THB/doc` |
| 5 | Processing time per document | LLM wall-clock only | `<= 15 sec/doc` |
| 6 | Manual correction time | timed review sample, mean minutes/doc | `<= 3 min/doc` |

Final decision:

| Pass count | Decision |
|---:|---|
| `>= 4/6` | Go |
| `3/6` | Conditional |
| `<= 2/6` | No-Go |

If decision is Conditional, the report must explicitly name supported document formats and excluded patterns.

---

## 10. Harness Implementation

CLI:

```text
scripts/line_item_poc.py
```

Required commands:

```powershell
.\.venv\Scripts\python.exe scripts\line_item_poc.py build-manifest
.\.venv\Scripts\python.exe scripts\line_item_poc.py bootstrap-labels --model google/gemini-2.5-flash-lite
.\.venv\Scripts\python.exe scripts\line_item_poc.py evaluate --models google/gemini-2.5-flash-lite google/gemini-2.5-flash anthropic/claude-sonnet-4
.\.venv\Scripts\python.exe scripts\line_item_poc.py report
```

Folder scan review CLI:

```powershell
.\.venv\Scripts\python.exe scripts\line_item_folder_review.py --max-pages 4
```

Implementation requirements:

1. All three models evaluate exactly the same doc IDs.
2. Raw model response is saved before parsing.
3. Parsed normalized JSON is saved separately.
4. Token usage, estimated cost, and elapsed seconds are recorded per document.
5. Scoring should continue even if one document parse fails.
6. Final report should be generated from machine-readable JSON, not manually copied tables.

---

## 11. DB And Schema Impact If TASK-906 Is Go

TASK-906 itself does not modify production DB. If Go/Conditional leads to Epic 14, schema should be expanded.

Recommended production tables:

### 11.1 `document_line_items`

Purpose: persist extracted line item rows per document and support row-level review.

Key fields:

```text
id
document_id
company_id
line_order
raw_description
product_name
sku
part_number
qty
unit
unit_price
discount_amount
line_amount
line_type
type_confidence
extraction_confidence
stock_candidate
matched_inventory_item_id
match_confidence
match_status
review_status
reviewed_by
reviewed_at
raw_payload
classification_reasons
created_at
updated_at
```

Suggested statuses:

```text
auto_matched
needs_review
confirmed
rejected
non_stock
no_match
```

### 11.2 `company_inventory_items`

Purpose: canonical product/stock master per company.

Key fields:

```text
id
company_id
canonical_name
normalized_name
item_type
sku
part_number
unit
default_account_code
is_active
created_from_line_item_id
created_at
updated_at
```

Notes:

1. Exact SKU can be unique per company when present.
2. Fuzzy name should not be hard-unique because real supplier names vary.
3. Office supplies should not auto-enter stock unless company confirms.

### 11.3 `company_inventory_item_aliases`

Purpose: learn from human confirmations and improve future matching.

Key fields:

```text
id
company_id
inventory_item_id
alias_text
normalized_alias
supplier_name
supplier_tax_id
unit
confidence
confirmed_count
last_confirmed_at
created_at
updated_at
```

### 11.4 Optional review/dedup event table

Purpose: keep review fast and move expensive dedup/merge to batch workflow.

Possible table:

```text
inventory_match_events
```

Key fields:

```text
id
company_id
document_line_item_id
event_type
candidate_inventory_item_id
payload
created_by
created_at
processed_at
```

This allows review UI to save confirmation quickly, then a background job can merge aliases and deduplicate product master later.

---

## 12. Review UI Requirements To Validate In PoC

TASK-906 report should describe the expected review screen even if not implemented.

Review table columns:

| Column | Purpose |
|---|---|
| Source row/image crop | human sees where the row came from |
| Product/service text | editable extracted name |
| Qty/unit/price/amount | editable numeric fields |
| Line type | stock/labor/service/office supply/unknown |
| Stock candidate | checkbox or pill |
| Suggested match | product master candidate |
| Confidence | green/amber/red |
| Action | confirm, reject, create new, non-stock |

Review rules:

1. Reconciled document with high-confidence matches can be fast-reviewed.
2. Row-count mismatch, missing unit/qty, or net mismatch must be flagged.
3. WHT + labor/service keywords should flag likely labor rows.
4. Confirmed aliases should improve future matching for the same company.

---

## 13. Test Plan

Unit tests:

1. row normalization
2. unit normalization Thai/English
3. numeric tolerance checks
4. row matching and row-count mismatch
5. per-field aggregation
6. document-level success logic
7. line-total reconciliation against net amount
8. Go/Conditional/No-Go scoring
9. diversity coverage calculation
10. line-type keyword boost
11. unit-based stock/material boost
12. WHT + service/labor confidence boost
13. office-supply caution logic
14. fuzzy match confidence banding

Harness tests:

1. all three models use same doc set
2. all six metrics are emitted
3. cost/time fields are recorded
4. failed parse does not stop full evaluation
5. report tables generate from JSON outputs
6. folder review HTML includes per-row review cues

Corpus validation:

1. selected core count is at least 20
2. reserve count is at least 5
3. diversity coverage is at least 6/8 categories
4. timed-review sample has 5 stratified docs
5. excluded docs have explicit exclusion reason

---

## 14. Report Requirements

Final report:

```text
docs/PoC/reports/TASK-906-FEASIBILITY-REPORT.md
```

Must include:

1. selected corpus summary and diversity coverage
2. full-folder scan summary when available
3. three-model comparison table across all six metrics
4. monthly cost projection at 10K and 20K documents
5. best model recommendation with rationale
6. supported document patterns
7. failing document patterns
8. line-type and inventory confidence findings
9. schema impact recommendation for Epic 14
10. final Go / Conditional / No-Go

If Conditional:

1. explicitly name allowed document formats
2. explicitly name excluded document patterns
3. describe reduced Epic 14 scope
4. state whether inventory matching requires product master setup first

---

## 15. Acceptance Criteria

| ID | Condition | Evidence |
|---|---|---|
| ac_906_01 | Core set has at least 20 docs and reserve has at least 5 docs | corpus manifest |
| ac_906_02 | At least 6/8 diversity categories covered | manifest validation |
| ac_906_03 | Line-item ground truth stored separately from header expectations | sidecar JSON |
| ac_906_04 | Three required models evaluated on the same locked core set | comparison summary |
| ac_906_05 | All six metrics emitted per model | metrics JSON |
| ac_906_06 | Line total reconciliation uses net amount when available | unit tests + metrics |
| ac_906_07 | Confidence includes keyword/unit/WHT/fuzzy-match signals | tests + report |
| ac_906_08 | Folder-level HTML review report generated for real sample folder | HTML report |
| ac_906_09 | Report includes cost projection at 10K and 20K docs/month | feasibility report |
| ac_906_10 | Report ends with Go / Conditional / No-Go decision | feasibility report |
| ac_906_11 | If Conditional, allowed formats are explicitly named | feasibility report |
| ac_906_12 | DB/schema impact for Epic 14 is documented | feasibility report |

---

## 16. Out Of Scope For TASK-906

These are intentionally deferred to Epic 14:

1. production database migrations
2. production API endpoints for line items
3. inventory/product master UI
4. automatic stock posting
5. product master dedup batch job
6. accounting export changes based on line items
7. row-level audit trail in production DB

TASK-906 may create scripts, tests, local JSON outputs, and PoC reports only.
