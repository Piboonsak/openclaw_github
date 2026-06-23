# Export by Template (6 Files) — Task Summary

> Scope: สรุปงานให้ระบบ LF (LedgerFlow) ส่งออกไฟล์รูปแบบเดียวกับ template ลูกค้า 6 ไฟล์ จากข้อมูล OCR ของระบบ
> Source templates: private_data/poc/Comp_1/template/
> Related analysis: CLIENT-TEMPLATE-ANALYSIS.md

---

## 1) วัตถุประสงค์

ระบบ LF ต้องสามารถสร้างไฟล์ CSV สำหรับนำเข้า Express Accounting ให้ได้ครบ 6 รูปแบบ โดยโครงสร้างคอลัมน์ รูปแบบวันที่ รูปแบบเลขที่เอกสาร และ encoding ต้องสอดคล้องกับไฟล์ตัวอย่างลูกค้า

ผลลัพธ์ต่อ 1 export job:

- สร้าง 6 ไฟล์พร้อมกัน
- แต่ละไฟล์มีเฉพาะข้อมูลที่เข้ากลุ่มของ template นั้น
- เข้ารหัส TIS-620
- พร้อมดาวน์โหลดแบบ zip

---

## 2) สรุปแต่ละไฟล์ว่าใช้ทำอะไร

| ไฟล์ | Book | ใช้กับงานบัญชี | สำนักบัญชีใช้ทำอะไร |
| --- | --- | --- | --- |
| 12 ซื้อสด บรรทัดเดียว.csv | 12 | ซื้อสด | นำเข้ารายการซื้อที่จ่ายทันที เพื่อบันทึกค่าใช้จ่าย/ภาษีซื้อ/เงินสดหรือธนาคาร |
| 14 ซื้อเชื่อ บรรทัดเดียว.csv | 14 | ซื้อเชื่อ | นำเข้ารายการซื้อที่ยังไม่ชำระ เพื่อบันทึกเจ้าหนี้การค้าและภาษีซื้อ |
| 15 ค่าใช้จ่ายอื่นๆ บรรทัดเดียว.csv | 15 | ค่าใช้จ่ายทั่วไป | นำเข้ารายการค่าใช้จ่ายที่ไม่ใช่ซื้อสินค้าโดยตรง พร้อมคำอธิบายรายการ |
| 15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv | 15 + WHT | ค่าใช้จ่ายมีหัก ณ ที่จ่าย | นำเข้ารายการค่าใช้จ่ายที่มี WHT โดยมีคอลัมน์สูตรเอกสารเพิ่มเติม |
| 22 ขายสด บรรทัดเดียว.csv | 22 | ขายสด | นำเข้ารายการขายรับเงินทันที โดยใช้ยอดรวมภาษีและรหัสลูกค้า |
| 24 ขายเชื่อ บรรทัดเดียว.csv | 24 | ขายเชื่อ | นำเข้ารายการขายที่ยังไม่ได้รับเงิน เพื่อบันทึกลูกหนี้การค้า |

---

## 3) LF ต้องทำอะไรเพื่อให้ได้ไฟล์หน้าตาเหมือน template

### 3.1 Data pipeline (จาก OCR ไป export)

1. OCR + extraction

- อ่านเอกสารและสกัดข้อมูลหลัก เช่น invoice_number, invoice_date, net_amount, vat_amount, total_amount, seller_name, seller_tax_id, buyer_name

1. Normalize เป็น transaction model กลาง

- แปลงข้อมูลให้เป็นฟิลด์มาตรฐานที่ template ใช้ร่วมกัน เช่น amount_before_tax, amount_including_tax, transaction_desc

1. Classify เอกสารให้เข้ากลุ่ม Book

- Purchase cash ไป Book 12
- Purchase credit ไป Book 14
- Expense ไป Book 15
- Expense + WHT ไป Book 15(WHT)
- Sales cash ไป Book 22
- Sales credit ไป Book 24

1. Enrich จาก master data

- จับคู่ vendor/customer code + name
- จับคู่ posting account code

1. Generate fields

- row_sequence
- document_number ตาม pattern ของแต่ละ Book
- formula_doc_number สำหรับ template WHT (เช่น OE + document_number)

1. Render ตาม schema ของแต่ละ template

- map source field -> output columns
- apply transform

1. Write CSV

- comma-delimited
- encoding TIS-620
- วันที่ต้องเขียนเป็น text ตามรูปแบบที่ลูกค้าต้องการ

1. Fan-out output พร้อมกัน 6 ไฟล์

- บันทึกชื่อไฟล์ตาม template เดิม
- zip รวมผลลัพธ์

### 3.2 ข้อกำหนดด้าน format ที่ห้ามพลาด

- Encoding: TIS-620
- Delimiter: comma
- Date format:

  - กลุ่มซื้อ: DD/MM/YY
  - กลุ่มขาย: D/M/YYYY (ยืนยันกับลูกค้าอีกครั้งเรื่องปี)

- เลขที่เอกสาร:

  - Book 12/14/15: YYMM/NNN
  - Book 22/24: YYMM######

- ฟิลด์ยอดเงิน:

  - กลุ่มซื้อใช้ จำนวนเงินก่อนภาษี
  - กลุ่มขายใช้ จำนวนเงินรวมภาษี

---

## 4) Schema ราย template (LF mapping)

## 4.1 Template: 12 ซื้อสด บรรทัดเดียว.csv

| ลำดับคอลัมน์ | Header | LF source field | Rule/Transform |
| --- | --- | --- | --- |
| 1 | ลำดับ | row_sequence | auto increment ต่อไฟล์ |
| 2 | วันที่ | invoice_date | thai_date_short => DD/MM/YY |
| 3 | เลขที่เอกสาร | document_number | pattern YYMM/NNN (book 12) |
| 4 | เลขที่ใบกำกับภาษี | invoice_number | trim |
| 5 | จำนวนเงินก่อนภาษี | net_amount | number format |
| 6 | รหัสผู้จำหน่าย | vendor_code | lookup จาก vendor master |
| 7 | ชื่อผู้จำหน่าย | vendor_name | lookup จาก vendor master |
| 8 | รหัสลงบัญชี | posting_account_code | lookup จาก account mapping |

## 4.2 Template: 14 ซื้อเชื่อ บรรทัดเดียว.csv

| ลำดับคอลัมน์ | Header | LF source field | Rule/Transform |
| --- | --- | --- | --- |
| 1 | ลำดับ | row_sequence | auto increment ต่อไฟล์ |
| 2 | วันที่ | invoice_date | thai_date_short => DD/MM/YY |
| 3 | เลขที่เอกสาร | document_number | pattern YYMM/NNN (book 14, เริ่ม sequence ตามนโยบายลูกค้า) |
| 4 | เลขที่ใบกำกับภาษี | invoice_number | trim |
| 5 | จำนวนเงินก่อนภาษี | net_amount | number format |
| 6 | รหัสผู้จำหน่าย | vendor_code | lookup จาก vendor master |
| 7 | ชื่อผู้จำหน่าย | vendor_name | lookup จาก vendor master |
| 8 | รหัสลงบัญชี | posting_account_code | lookup จาก account mapping |

## 4.3 Template: 15 ค่าใช้จ่ายอื่นๆ บรรทัดเดียว.csv

| ลำดับคอลัมน์ | Header | LF source field | Rule/Transform |
| --- | --- | --- | --- |
| 1 | ลำดับ | row_sequence | auto increment ต่อไฟล์ |
| 2 | วันที่ | invoice_date | thai_date_short => DD/MM/YY |
| 3 | เลขที่เอกสาร | document_number | pattern YYMM/NNN (book 15) |
| 4 | เลขที่ใบกำกับภาษี | invoice_number | optional ได้ |
| 5 | คำอธิบาย | transaction_desc | จาก OCR line summary หรือคำอธิบายมาตรฐาน |
| 6 | จำนวนเงินก่อนภาษี | net_amount | number format |
| 7 | รหัสผู้จำหน่าย | vendor_code | lookup จาก vendor master |
| 8 | ชื่อผู้จำหน่าย | vendor_name | lookup จาก vendor master |
| 9 | รหัสลงบัญชี | posting_account_code | lookup จาก account mapping |

## 4.4 Template: 15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv

| ลำดับคอลัมน์ | Header | LF source field | Rule/Transform |
| --- | --- | --- | --- |
| 1 | ลำดับ | row_sequence | auto increment ต่อไฟล์ |
| 2 | วันที่ | invoice_date | thai_date_full => D/M/YYYY (ตามไฟล์ตัวอย่าง) |
| 3 | เลขที่เอกสาร | document_number | pattern YYMM/NNN (book 15) |
| 4 | เลขที่ใบกำกับภาษี | invoice_number | optional ได้ |
| 5 | คำอธิบาย | transaction_desc | จาก OCR line summary |
| 6 | จำนวนเงินก่อนภาษี | net_amount | number format |
| 7 | รหัสผู้จำหน่าย | vendor_code | lookup จาก vendor master |
| 8 | ชื่อผู้จำหน่าย | vendor_name | lookup จาก vendor master |
| 9 | รหัสลงบัญชี | posting_account_code | lookup จาก account mapping |
| 10 | (empty header) | static_value | ค่า OE |
| 11 | เลขที่เอกสาร(สูตร) | formula_doc_number | prefix:OE + document_number |

## 4.5 Template: 22 ขายสด บรรทัดเดียว.csv

| ลำดับคอลัมน์ | Header | LF source field | Rule/Transform |
| --- | --- | --- | --- |
| 1 | ลำดับ | row_sequence | auto increment ต่อไฟล์ |
| 2 | วันที่ | invoice_date | thai_date_full => D/M/YYYY |
| 3 | เลขที่เอกสาร | document_number | pattern YYMM###### (book 22) |
| 4 | จำนวนเงินรวมภาษี | total_amount | number format |
| 5 | รหัสลูกค้า | customer_code | lookup จาก customer master |
| 6 | ชื่อลูกค้า | customer_name | lookup จาก customer master |
| 7 | รหัสลงบัญชี | posting_account_code | lookup จาก account mapping |

## 4.6 Template: 24 ขายเชื่อ บรรทัดเดียว.csv

| ลำดับคอลัมน์ | Header | LF source field | Rule/Transform |
| --- | --- | --- | --- |
| 1 | ลำดับ | row_sequence | auto increment ต่อไฟล์ |
| 2 | วันที่ | invoice_date | thai_date_full => D/M/YYYY |
| 3 | เลขที่เอกสาร | document_number | pattern YYMM###### (book 24) |
| 4 | จำนวนเงินรวมภาษี | total_amount | number format |
| 5 | รหัสลูกค้า | customer_code | lookup จาก customer master |
| 6 | ชื่อลูกค้า | customer_name | lookup จาก customer master |
| 7 | รหัสลงบัญชี | posting_account_code | lookup จาก account mapping |

---

## 5) Task breakdown สำหรับทีมพัฒนา LF

## TASK-A: Template definitions

- เพิ่ม template definitions ให้ครบ 6 แบบใน export_templates
- เก็บ schema column ตามตารางด้านบน

## TASK-B: Field resolver + transforms

- เพิ่มตัวแปลง date 2 แบบ (short/full)
- เพิ่ม document_number generator ตาม book
- เพิ่ม formula_doc_number สำหรับ WHT

## TASK-C: Book routing

- เขียนกฎ route เอกสารจาก OCR ให้เข้า Book 12/14/15/22/24
- รองรับกรณี WHT แยกเป็น template 15(WHT)

## TASK-D: Master data integration

- Vendor/customer/account lookup
- กำหนด fallback เมื่อหา code ไม่เจอ (เช่น UNKNOWN หรือ error queue)

## TASK-E: Multi-file export job

- สร้างไฟล์ทั้ง 6 พร้อมกันใน job เดียว
- export เป็น zip พร้อม metadata และสรุปจำนวนรายการต่อไฟล์

## TASK-F: Validation + QA

- Snapshot test เทียบ header และ sample row กับไฟล์ลูกค้า
- ตรวจ encoding TIS-620
- ทดสอบ import เข้า Express จริง

---

## 6) Acceptance criteria

- ได้ไฟล์ครบ 6 ชื่อ ต่อ 1 export job
- Header และลำดับคอลัมน์ตรง template 100%
- Encoding เป็น TIS-620
- วันที่เป็นรูปแบบตาม template
- เลขที่เอกสารถูกต้องตามกฎแต่ละ Book
- ยอดเงิน map ถูก field (ก่อนภาษี/รวมภาษี)
- ผ่านการนำเข้า Express ของทีมบัญชี

---

## 7) Deliverables

- Template config 6 แบบในระบบ
- Export service ที่ fan-out 6 files พร้อม zip
- Test cases ครอบคลุม schema และ format
- คู่มือ mapping ระหว่าง OCR fields กับแต่ละ template
- JSONB seed spec: [EXPORT-TEMPLATE-JSONB-SEED.md](EXPORT-TEMPLATE-JSONB-SEED.md)

---

## 8) สิ่งใหม่ที่เพิ่มเข้ามา (2026-06-24)

### 8.1 Schema Analyzer — Auto-detect Template from Sample File (TASK-1009)

**ที่มา:** user กังวลว่าจะ set template เองไม่เป็น เพราะ Template Configurator ต้องการความเข้าใจ technical concepts (data type, transform, row source) ที่ accountant ทั่วไปไม่คุ้นเคย

**Feature ใหม่:** user อัปโหลดไฟล์ CSV/Excel ที่เคย import Express ได้แล้ว → ระบบวิเคราะห์ schema และ pre-fill Template Configurator อัตโนมัติ

**UX flow ใหม่:**

```text
Templates page
  └─ [Auto-detect จาก Sample File]
       └─ Screen: Schema Analyzer
            ├─ Step 1: Upload zone (CSV/Excel)
            ├─ Step 2: Analyzing (encoding → schema → column match → data profile)
            └─ Step 3: Results
                 ├─ Column Mapping table (original header → LF field, confidence %)
                 ├─ Data Profile (unique values, date format, balance check)
                 ├─ AI Insights (template mode, row source, encoding suggestion)
                 ├─ Detected Transforms (pad_left, thai_date, etc.)
                 └─ [Apply to Configurator →] → Template Configurator (pre-filled)
```

**สิ่ง detect ได้โดยไม่ต้องใช้ LLM (structural analysis):**

- TIS-620 encoding → suggest encoding ปลายทาง
- `DD/MM/YY` year 60-99 → `thai_date_short` transform
- `D/M/YYYY` year 2500-2599 → `thai_date_full` transform
- Zero-padded codes "05100" → `pad_left:5:0` transform
- Voucher_No ซ้ำหลาย rows → `Flatten Row` mode + `journal_lines` source
- Debit/Credit alternating zeros → double-entry GL
- All rows identical value → `static_value` column type

**สิ่งที่ใช้ LLM (claude-haiku-4-5, fallback เท่านั้น):**

- Column header matching เมื่อ fuzzy similarity < 70%
- เช่น header ที่ไม่อยู่ใน alias table → ส่งให้ LLM ตัดสิน
- ลด cost: ใช้ LLM เฉพาะ ambiguous columns เท่านั้น

**Prototype:** Screen `s-schema-analyzer` (Screen 11C) ใน `PHASE-II-PROTOTYPE.html`
**Task:** [TASK-1009](EPIC-10-TASKS-DETAIL.md#task-1009-schema-analyzer--auto-detect-template-from-sample-file)
**Analysis details:** [CLIENT-TEMPLATE-ANALYSIS.md § 9](CLIENT-TEMPLATE-ANALYSIS.md#9-schema-analyzer-ux--ขอคนพบใหม่-2026-06-24)

### 8.2 Column alias table สำหรับ Thai headers

สร้าง lookup table ใน `schema_analyzer.py` ครอบคลุม headers ที่พบจากไฟล์ลูกค้า Express ทั้ง 6 แบบ รายละเอียดอยู่ใน [CLIENT-TEMPLATE-ANALYSIS.md § 9.6](CLIENT-TEMPLATE-ANALYSIS.md#96-column-alias-table-thai-headers--lf-fields)

### 8.3 Impact ต่อ task ที่มีอยู่

| Task | Impact |
| ---- | ------ |
| TASK-1003 (Template Configurator UI) | เพิ่ม entry point "Auto-detect" button บนหน้า Templates |
| TASK-1001 (Template Engine) | field registry และ transform registry ที่ TASK-1009 จะ reuse |
| TASK-1004 (Master Templates) | ไม่กระทบ — Schema Analyzer เป็น UX layer เพิ่มเติม |
| **TASK-1009 (ใหม่)** | Backend API + Frontend screen ใหม่ทั้งหมด |
