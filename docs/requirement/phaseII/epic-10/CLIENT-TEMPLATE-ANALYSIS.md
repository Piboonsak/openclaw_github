# Client Template Analysis — Express Accounting Import Format

> Analyzed from: `private_data/poc/Comp_1/template/*.csv`
> Date: 2026-06-15
> Epic: [Epic 10 — Template Engine + Configurator UI](README-EPIC-10.md)

---

## 1. Source files

| File | Book | Type | Rows | Encoding |
|------|------|------|------|----------|
| `12 ซื้อสด บรรทัดเดียว.csv` | 12 | Cash Purchase | 5 | TIS-620 |
| `14 ซื้อเชื่อ บรรทัดเดียว.csv` | 14 | Credit Purchase | 5 | TIS-620 |
| `15 ค่าใช้จ่ายอื่นๆ บรรทัดเดียว.csv` | 15 | Other Expenses | 5 | TIS-620 |
| `15 ค่าใช้จ่ายอื่นๆ(มีหัก)3บรรทัดเดียว.csv` | 15+WHT | Other Expenses (3% WHT) | 5 | TIS-620 |
| `22 ขายสด บรรทัดเดียว.csv` | 22 | Cash Sales | ~275 | TIS-620 |
| `24 ขายเชื่อ บรรทัดเดียว.csv` | 24 | Credit Sales | ~275 | TIS-620 |

All files use **comma-delimited CSV** with **TIS-620 encoding** (legacy Thai).

---

## 2. Column structures per template type

### 2A. Purchase templates (Book 12, 14)

| # | Thai Header | English | Data Type | Example | Source |
|---|-------------|---------|-----------|---------|--------|
| 1 | ลำดับ | Sequence | int | 1, 2, 3... | auto-increment |
| 2 | วันที่ | Date | date | 01/05/69 | document date (DD/MM/YY พ.ศ.) |
| 3 | เลขที่เอกสาร | Document No. | string | 6905/001 | generated per book |
| 4 | เลขที่ใบกำกับภาษี | Tax Invoice No. | string | 010526E00015843 | from OCR extraction |
| 5 | จำนวนเงินก่อนภาษี | Amount Before Tax | decimal | 29,952.07 | net_amount |
| 6 | รหัสผู้จำหน่าย | Vendor Code | int | 5004 | vendor master lookup |
| 7 | ชื่อผู้จำหน่าย | Vendor Name | string | ธนาคารกสิกรไทย | vendor master lookup |
| 8 | รหัสลงบัญชี | Account Code | int | 536004 | account master / rule |

**Differences between Book 12 and 14:**
- Doc number series only: Book 12 uses `6905/001+`, Book 14 uses `6905/100+`
- Column structure is identical

### 2B. Expense template (Book 15)

| # | Thai Header | English | Data Type | Example | Source |
|---|-------------|---------|-----------|---------|--------|
| 1 | ลำดับ | Sequence | int | 1 | auto-increment |
| 2 | วันที่ | Date | date | 01/05/69 | DD/MM/YY พ.ศ. |
| 3 | เลขที่เอกสาร | Document No. | string | 6905/100 | generated |
| 4 | เลขที่ใบกำกับภาษี | Tax Invoice No. | string | 010526E00015843 | OCR (optional) |
| 5 | **คำอธิบาย** | **Description** | string | ค่าของ, ค่าจ้างเหมา | free text |
| 6 | จำนวนเงินก่อนภาษี | Amount Before Tax | decimal | 29,952.07 | net_amount |
| 7 | รหัสผู้จำหน่าย | Vendor Code | int | 5004, 1238 | vendor master |
| 8 | ชื่อผู้จำหน่าย | Vendor Name | string | ธนาคารกสิกรไทย | vendor master |
| 9 | รหัสลงบัญชี | Account Code | int | 536004 | account master |

**Key difference:** adds `คำอธิบาย` (description) column between tax invoice and amount.

### 2C. Expense with WHT template (Book 15 + WHT 3%)

Same as 2B plus:

| # | Thai Header | English | Data Type | Example | Source |
|---|-------------|---------|-----------|---------|--------|
| 10 | *(empty)* | separator | - | OE | static prefix |
| 11 | เลขที่เอกสาร(สูตร) | Formula Doc No. | string | OE6905/100 | computed: "OE" + doc_no |

**Notes:**
- Date format changes to D/M/YYYY (full 4-digit CE year: 1/5/1969 = 1 พ.ค. 2569?)
- The "3" in filename refers to WHT 3% rate
- "สูตร" column uses OE prefix + doc number (computed field)

### 2D. Sales templates (Book 22, 24)

| # | Thai Header | English | Data Type | Example | Source |
|---|-------------|---------|-----------|---------|--------|
| 1 | ลำดับ | Sequence | int | 1 | auto-increment |
| 2 | วันที่ | Date | date | 2/5/1969 | D/M/YYYY (CE/พ.ศ.?) |
| 3 | เลขที่เอกสาร | Document No. | string | 6905000001 | generated (no slash) |
| 4 | จำนวนเงิน**รวม**ภาษี | Amount **Including** Tax | decimal | 301 | total_amount |
| 5 | รหัสลูกค้า | Customer Code | int | 163 | customer master |
| 6 | ชื่อลูกค้า | Customer Name | string | ลูกค้าShopee | customer master |
| 7 | รหัสลงบัญชี | Account Code | int | 410001 | account master |

**Key differences from purchase templates:**
- **Amount is "รวมภาษี" (including tax)** not "ก่อนภาษี (before tax)"
- **Customer fields** instead of vendor fields
- **No tax invoice number** column
- **Doc number format**: continuous digits `6905000001` (no slash)
- **Date format**: `D/M/YYYY` not `DD/MM/YY`

---

## 3. Client bug report: Date format issue

> **Reported 2026-06-15 by client:**
> "ช่องวันที่ ที่ระบบต้องการ คือ dd/mm/yy แต่พอเซฟไฟล์ แล้วเปิดใหม่ มันคืนค่าเป็น dd/mm/yyyy
> ไม่ต้องการให้มันเป็น yyyy ค่ะ เพราะระบบมันไม่รับ"

### Root cause

Excel (and some CSV editors) auto-interpret date-looking strings as date values. When saving back to CSV, Excel uses its own locale-based date format (dd/mm/yyyy), overwriting the original 2-digit year.

### Required fix

The template engine must ensure dates are **written as plain text strings**, not date values:

1. **CSV output**: wrap date cells in quotes and/or prefix with `=""01/05/69""` to force text mode
2. **Excel output**: set cell format to `@` (text) before writing date string
3. **New transform**: `thai_date_short` — outputs `DD/MM/YY` where YY = Buddhist Era 2-digit year
   - Input: `2026-06-14` (ISO date)
   - Output: `14/06/69` (พ.ศ. 2569 → 69)
4. **Existing transform update**: `thai_date` should support both `DD/MM/YY` and `DD/MM/YYYY` via format_pattern

### Date format patterns needed

| Pattern | Example | Use case |
|---------|---------|----------|
| `DD/MM/YY` | 01/05/69 | Express purchase import (พ.ศ. 2 หลัก) |
| `D/M/YYYY` | 2/5/1969 | Express sales import (ค.ศ. 4 หลัก? or พ.ศ.?) |
| `YYYY-MM-DD` | 2026-06-14 | ISO standard (internal use) |

**Open question:** ไฟล์ขาย (Book 22/24) ใช้ปี ค.ศ. หรือ พ.ศ.? ถ้า `2/5/1969` หมายถึง 2 พ.ค. 2512 (ค.ศ. 1969) ก็ผิดยุค — น่าจะเป็น formatting issue ของ Excel อีกกรณี ต้อง confirm กับลูกค้า.

---

## 4. Master data requirements

### 4A. Vendor Master (ผู้จำหน่าย)

From purchase templates, vendors found:

| Code | Name | Notes |
|------|------|-------|
| 5004 | ธนาคารกสิกรไทย | Payment channel (bank) |
| 1238 | ธนาคารกสิกรไทย | Different code, same name? |

**Action needed:** Import full vendor master from Express or client's existing data. → **TASK-1207** (Epic 12)

### 4B. Customer Master (ลูกค้า)

From sales templates, ~100+ unique customer codes found, all mapping to "ลูกค้าShopee":

- Codes: 1, 3, 7, 19, 28, 38, 41, 43, 45, 56, 57, 65, 83, 90, 91, 92, 96, 107, 112, 119, 121, 127, 129, 133, 141, 151, 157, 163, 172, 176, 189, 198, 201, 222, 238, 242, 247, 255, 286, 295, 298, 303, 305, 308, 313, 324, 330, 331, 333, 343, 350, 355, 362, 365, 368, 369, 371, 375, 377, 378, 380, 381, 382, 383, 384, 385, 386, 387, 388, 389, 390, 391, 392, 393, 394, 395, 396, 397, 398, ...

**Observation:** All customer names are "ลูกค้าShopee" — these codes likely represent **product categories or sub-accounts** within Shopee marketplace, not actual separate customers. Need clarification from client.

**Action needed:** Confirm what customer codes represent and import full customer master. → **TASK-1207** (Epic 12)

### 4C. Account Code Master (ผังบัญชี)

| Code | Template | Likely Account |
|------|----------|---------------|
| 536004 | Purchase (Book 12, 14, 15) | ค่าสินค้า/ค่าใช้จ่าย (expense account) |
| 410001 | Sales (Book 22, 24) | รายได้จากการขาย (revenue account) |

**Action needed:** Import full chart of accounts from Express. → **TASK-1203** (Epic 12, already planned)

---

## 5. Document numbering patterns

| Book | Pattern | Example | Rule |
|------|---------|---------|------|
| 12 (ซื้อสด) | `YYMM/NNN` | 6905/001 | YY=69 (พ.ศ.), MM=05, seq from 001 |
| 14 (ซื้อเชื่อ) | `YYMM/NNN` | 6905/100 | Same format, seq from 100 |
| 15 (ค่าใช้จ่าย) | `YYMM/NNN` | 6905/100 | Same as 14 |
| 22 (ขายสด) | `YYMM` + 6 digits | 6905000001 | No slash, 10-digit total |
| 24 (ขายเชื่อ) | `YYMM` + 6 digits | 6905000001 | Same as 22 |

**Note:** Prefix `69` = พ.ศ. 2569, `05` = May. Starting sequence varies by book type.

---

## 6. Gap analysis: Demo configurator vs real templates

### What the demo already covers

| Feature | Status | Notes |
|---------|--------|-------|
| Column selection (checkbox picker) | Covered | Need to add Express transaction fields |
| Drag-drop reorder | Covered | Works with SortableJS |
| Inline rename headers | Covered | |
| Static columns | Covered | e.g., fixed customer name per template |
| Encoding selector (TIS-620) | Covered | |
| CSV format | Covered | |
| Preview table | Covered | |

### What must be added

| Gap | Priority | Impact | Task |
|-----|----------|--------|------|
| **Express transaction-level fields** (ลำดับ, เลขที่เอกสาร, เลขใบกำกับ, รหัสผู้จำหน่าย/ลูกค้า, ชื่อผู้จำหน่าย/ลูกค้า) | P0 | Can't generate Express CSV without these | TASK-1001, TASK-1003 |
| **`thai_date_short` transform** (DD/MM/YY พ.ศ. 2 หลัก) | P0 | Client bug: Express rejects yyyy dates | TASK-1001 |
| **Date-as-text CSV writer** (prevent Excel auto-format) | P0 | Client bug: dates reformat on open | TASK-1001 |
| **Book type selector** per template (12/14/15/22/24) | P1 | Determines doc number format and field set | TASK-1003, TASK-1004 |
| **Doc number format rule** per book type | P1 | Auto-generate document numbers | TASK-1001 |
| **Amount type toggle** (ก่อนภาษี vs รวมภาษี) | P1 | Different mapping for purchase vs sales | TASK-1001 |
| **Vendor/Customer master data import** | P1 | Needed for code→name lookup | **TASK-1207** (Epic 12) |
| **Account code master import** | P1 | Chart of accounts for รหัสลงบัญชี | New task or TASK-801A |
| **WHT formula doc computed column** (OE prefix) | P2 | Only for expense+WHT template variant | TASK-1001 |

### New source fields to add (TASK-1001)

Current fields in design doc cover GL journal export. For Express transaction-level export, add:

```
# Transaction fields (Express import format)
row_sequence        # ลำดับ — auto-increment per export
document_number     # เลขที่เอกสาร — generated per book type + sequence
tax_invoice_number  # เลขที่ใบกำกับภาษี — from OCR extraction (= invoice_number)
transaction_desc    # คำอธิบาย — free text description
amount_before_tax   # จำนวนเงินก่อนภาษี (= net_amount)
amount_including_tax # จำนวนเงินรวมภาษี (= total_amount)
vendor_code         # รหัสผู้จำหน่าย — from vendor master
vendor_name         # ชื่อผู้จำหน่าย — from vendor master
customer_code       # รหัสลูกค้า — from customer master
customer_name       # ชื่อลูกค้า — from customer master
posting_account_code # รหัสลงบัญชี — account code for posting
formula_doc_number  # เลขที่เอกสาร(สูตร) — computed: prefix + doc_number
```

### New transforms to add (TASK-1001)

| Transform | Input | Output | Purpose |
|-----------|-------|--------|---------|
| `thai_date_short` | 2026-05-01 | 01/05/69 | DD/MM/YY พ.ศ. 2 หลัก |
| `thai_date_full` | 2026-05-01 | 1/5/2569 | D/M/YYYY พ.ศ. 4 หลัก |
| `prefix:OE` | 6905/100 | OE6905/100 | Add prefix string |
| `doc_number:YYMM/NNN` | (context) | 6905/001 | Generate doc number |
| `doc_number:YYMM######` | (context) | 6905000001 | Generate doc number |

---

## 7. New master templates to seed (TASK-1004 update)

In addition to the existing GL + Purchase Tax Report masters, add **6 Express transaction templates**:

| # | Template Name | Book | Columns | Based on |
|---|--------------|------|---------|----------|
| 1 | Express ซื้อสด (Cash Purchase) | 12 | 8 cols | Section 2A |
| 2 | Express ซื้อเชื่อ (Credit Purchase) | 14 | 8 cols | Section 2A |
| 3 | Express ค่าใช้จ่ายอื่นๆ (Other Expenses) | 15 | 9 cols | Section 2B |
| 4 | Express ค่าใช้จ่าย+หัก ณ ที่จ่าย (Expenses+WHT) | 15+WHT | 11 cols | Section 2C |
| 5 | Express ขายสด (Cash Sales) | 22 | 7 cols | Section 2D |
| 6 | Express ขายเชื่อ (Credit Sales) | 24 | 7 cols | Section 2D |

---

## 8. Estimation considerations

### Effort to support real Express templates

| Item | Estimate | Notes |
|------|----------|-------|
| Add Express transaction source fields to template engine | 1-2 days | Extend field resolver |
| `thai_date_short` + date-as-text CSV fix | 0.5 day | Transform + writer fix |
| 6 new master template seeds | 0.5 day | Alembic migration data |
| Master data import (vendor/customer/account) | 1-2 days | → **TASK-1207** (Epic 12), COA already in TASK-1203 |
| Doc number generator per book type | 1 day | Computed field with state |
| **Total additional effort** | **~4-6 days** | On top of existing Epic 10 estimate |

### Pricing implications

This is additional scope beyond the original Epic 10 estimate of 2.5 weeks. The client's real Express import format requires:
- More source fields and transforms than originally designed
- Master data management (vendor/customer/account)
- Document numbering logic per book type
- Date format handling specific to Express

**Recommendation:** Factor these additions into the Phase II pricing discussion with the client.

---

*Created: 2026-06-15*
*Last updated: 2026-06-15*
