# UX Freeze — Export Page + Template Configurator

> **Status**: FROZEN 2026-06-28 — Approval gated on SIT environment
> **Scope**: TASK-1001 ✅ done, TASK-1009 ✅ done | TASK-1003/TASK-1006 blocked
> **Effect**: TASK-1003/TASK-1006 blocked until SIT env ready (§10) AND all 5 approval items ✅
> **Approval required by**: Piboonsak (product owner) — must review on live SIT

---

## 1. Problems With Current UX

### 1A — Export Step 6 (ux-ui-prototype.html line 295)

Current export is a step panel with checkbox column toggles only:

```
Export Express GL
[✓] Voucher No  [✓] Date  [✓] Book Code  [✓] Account Code
[✓] Debit  [✓] Credit  [✓] Description  [✓] Company Tax ID
[  ] VAT Rate  [✓] WHT Rate

[Download Express-Journal.CSV]  [Download รายงานภาษีซื้อ.xlsx]
```

Defects:
- No column ordering — cannot reorder
- No column rename — header label hardcoded
- No transform selector — cannot set `thai_date_short` per column
- Template hardcoded (two buttons, not dynamic)
- No per-run overrides: every export must use identical column config
- Hidden behind a step stepper — narrow UX, not full-page

### 1B — Template Configurator (template-configurator-demo.html)

- Standalone demo page, not integrated into prototype
- Has drag-drop + rename, but no sample file upload
- No round-trip proof: user cannot verify template produces Express-compatible output before saving
- Cannot know if configured template actually works with Express until manual test

### 1C — No Schema Analyzer path

TASK-1009 planned as mid-sprint. With Express having fixed column formats, the correct first step is:
upload existing Express CSV → auto-detect mapping → verify round-trip → save template.

---

## 2. Frozen Design Decisions

### Decision 1: Export is a full-page workflow with two paths

Not a step inside the 6-step stepper. Accessed from document review workflow after Step 5 (Map Review).

เลือก Export Mode ก่อนในหน้าแรก — สองเส้นทางที่แยกอิสระ:

**Path A — Quick Export** (ไม่ต้องการ template, ข้อมูลออกได้เร็ว):
```
① Select Docs → ② Adjust Columns (all fields pre-selected) → ③ Preview → ④ Download
```
ไม่มี template selection, ไม่มี transform config.
ใช้เมื่อต้องการ: ส่งรายงานภายใน, check ข้อมูล, ad-hoc analysis.
Format: Excel หรือ CSV, encoding: UTF-8 / TIS-620 — เลือกได้เหมือนกัน.
Default: Excel (.xlsx), UTF-8.

**Path B — Template Export** (ต้องการ format ตาม template ที่กำหนดไว้):
```
① Select Docs → ② Select Template → ③ Adjust Columns/Data → ④ Preview → ⑤ Download
```
ใช้เมื่อต้องการ: Express CSV สำหรับ LoveAutoBot, รายงานภงด., หรือ format อื่นที่มี transform/encoding ตาม template.

ทั้งสอง path มาเจอกันที่ Step Adjust Columns — column editor เดียวกัน ต่างกันแค่ pre-fill source (Path A = all fields, Path B = template columns).

### Decision 2: Step ③ is a full-width inline column panel, not a modal

Column selection and per-run data adjustments live **on the Export page itself**.

- Pre-filled from selected template
- Show/hide columns, drag-reorder, rename header label
- Override transform or static value for this run
- Changes are **ephemeral by default** — not saved to DB
- Optional persist: [💾 Save as Company Template] or [↺ Update Template] buttons at bottom of Step ③

Template Configurator remains for persistent setup. Export page Step ③ is for per-run tuning.

### Decision 3: Template Configurator has 3 tabs (persistent setup only)

Accessed from "Manage Templates →" link on Export page, or from Admin menu.
Changes here save to DB and become the default for future exports.

| Tab | Name | Purpose |
|-----|------|---------|
| ① | Upload & Detect | Upload Express sample CSV/Excel → schema analyzer auto-fills column mapping |
| ② | กำหนด Columns | Drag-drop reorder, rename, transform selector, encoding/format (persistent) |
| ③ | ทดสอบ Output | Round-trip proof — must pass before Save Template |

### Decision 4: Schema Analyzer (TASK-1009) is W3 P0

First feature to implement in W3. Reason: once analyzer works, Tab ① auto-fills Tab ② → eliminates manual column mapping. Manual config (Tab ② only) is the fallback, not primary path.

---

## 3. Screen Designs

### Screen A: Export Page

#### Step ①: Select Documents + Choose Export Mode

Both paths start here. After selecting documents, user picks mode before continuing.

```
╔══════════════════════════════════════════════════════════════════╗
║ Export                                                           ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Company: [ฤทธิ์ล้ำเลิศ จำกัด ▾]   Period: [พ.ค. 2569 ▾]       ║
║                                                                  ║
║  Batch: UploadBatch_2025-05-01 (32 documents)                   ║
║  ┌─────────────────────────────────────────────────────────┐    ║
║  │ ☑ Select all (32)                [Filter: all types ▾]  │    ║
║  ├─────────────────────────────────────────────────────────┤    ║
║  │ ☑ INV-001  01/05/69  Metro Electric      ฿10,700.00     │    ║
║  │ ☑ INV-002  02/05/69  TCC Technology       ฿5,350.00     │    ║
║  │ ☑ INV-003  03/05/69  Thai Bank            ฿3,210.00     │    ║
║  │ ...                                                     │    ║
║  └─────────────────────────────────────────────────────────┘    ║
║  15 documents selected · ฿245,300 total                         ║
║                                                                  ║
║  ────────────────────────────────────────────────────────────   ║
║  Export mode:                                                    ║
║                                                                  ║
║  ┌──────────────────────────────┐  ┌──────────────────────────┐ ║
║  │  ⚡ Quick Export             │  │  📋 Template Export       │ ║
║  │  Get data out fast.          │  │  Format for Express /     │ ║
║  │  All fields, no transforms.  │  │  LoveBot / Tax reports.   │ ║
║  │  Output: Excel (.xlsx)       │  │  CSV or Excel per config. │ ║
║  │                              │  │                           │ ║
║  │  [Select & Continue →]       │  │  [Select & Continue →]    │ ║
║  └──────────────────────────────┘  └──────────────────────────┘ ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
```

---

#### Path A — Quick Export (no template required)

Steps: ① Select Docs+Mode → ② Adjust Columns → ③ Preview → ④ Download

```
╔══════════════════════════════════════════════════════════════════╗
║ Quick Export                                                     ║
║ ① Docs+Mode ✓  ② Adjust Columns  ③ Preview  ④ Download          ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  All available fields — uncheck to hide, drag to reorder         ║
║                                                                  ║
║  ┌────┬──────────────────────┬────────────────────────┬────────┐ ║
║  │    │ Header Label         │ Source Field           │ Show   │ ║
║  ├────┼──────────────────────┼────────────────────────┼────────┤ ║
║  │ ⠿  │ Invoice No.          │ invoice_number         │ ☑      │ ║
║  │ ⠿  │ Date                 │ invoice_date           │ ☑      │ ║
║  │ ⠿  │ Seller               │ seller_name            │ ☑      │ ║
║  │ ⠿  │ Seller Tax ID        │ seller_tax_id          │ ☑      │ ║
║  │ ⠿  │ Net Amount           │ net_amount             │ ☑      │ ║
║  │ ⠿  │ VAT Amount           │ vat_amount             │ ☑      │ ║
║  │ ⠿  │ Total Amount         │ total_amount           │ ☑      │ ║
║  │ ⠿  │ Document Type        │ document_type          │ ☑      │ ║
║  │ ⠿  │ Account Code         │ account_code           │ ☑      │ ║
║  │ ⠿  │ Description          │ description            │ ☑      │ ║
║  └────┴──────────────────────┴────────────────────────┴────────┘ ║
║  No transforms applied.                                          ║
║  Encoding: [UTF-8 ▾]           Format: [Excel (.xlsx) ▾]         ║
║                                                                  ║
║  [← Back]                     [Continue → Preview]              ║
╚══════════════════════════════════════════════════════════════════╝
```

No transform selector — plain data out. Encoding and format selectable same as Template Export.
Preview and Download steps are identical to Path B (Step ④/⑤ below).

---

#### Path B — Template Export

Steps: ① Docs+Mode ✓ → ② Select Template → ③ Adjust Columns/Data → ④ Preview → ⑤ Download

##### Step ②: Select Template

```
╔══════════════════════════════════════════════════════════════════╗
║ Template Export                                                  ║
║ ① Docs+Mode ✓  ② Select Template  ③ Adjust  ④ Preview  ⑤ Download║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  ● Express ซื้อสด (Book 12)   [master]                           ║
║    8 columns · TIS-620 · thai_date_short              [Preview]  ║
║                                                                  ║
║  ○ Express ซื้อเชื่อ (Book 14)  [master]                          ║
║    8 columns · TIS-620 · thai_date_short              [Preview]  ║
║                                                                  ║
║  ○ Express ค่าใช้จ่ายอื่นๆ (Book 15)  [master]                   ║
║    9 columns · TIS-620 · thai_date_short              [Preview]  ║
║                                                                  ║
║  ○ LoveBot Book 12  [company template]                           ║
║    8 columns · TIS-620 · cloned from master           [Preview]  ║
║                                                                  ║
║  [Manage Templates →]                                            ║
║                                                                  ║
║  [← Back]                       [Continue → Adjust Columns]     ║
╚══════════════════════════════════════════════════════════════════╝
```

##### Step ③: Adjust Columns/Data (inline, full-width, NOT a modal)

```
╔══════════════════════════════════════════════════════════════════╗
║ Template Export                                                  ║
║ ① ✓  ② ✓  ③ Adjust Columns/Data  ④ Preview  ⑤ Download          ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  Template: Express ซื้อสด (Book 12) — adjustments for this run  ║
║                                                                  ║
║  ┌────┬────────────────────┬──────────────────┬──────────┬────┐ ║
║  │    │ Header Label       │ Source Field     │Transform │ ☑  │ ║
║  ├────┼────────────────────┼──────────────────┼──────────┼────┤ ║
║  │ ⠿  │ ลำดับ              │ row_sequence     │ —        │ ☑  │ ║
║  │ ⠿  │ วันที่        [✏] │ invoice_date     │ thai_date_short ▾│☑│ ║
║  │ ⠿  │ เลขที่เอกสาร       │ document_number  │ —        │ ☑  │ ║
║  │ ⠿  │ เลขที่ใบกำกับ      │ tax_invoice_no   │ —        │ ☑  │ ║
║  │ ⠿  │ จำนวนเงินก่อนภาษี  │ amount_before_tax│ —        │ ☑  │ ║
║  │ ⠿  │ รหัสผู้จำหน่าย     │ vendor_code      │ —        │ ☑  │ ║
║  │ ⠿  │ ชื่อผู้จำหน่าย     │ vendor_name      │ —        │ ☑  │ ║
║  │ ⠿  │ รหัสลงบัญชี        │ posting_acc_code │ —        │ ☑  │ ║
║  └────┴────────────────────┴──────────────────┴──────────┴────┘ ║
║  ⠿ = drag to reorder   [✏] = click to rename   [☑] = show/hide  ║
║  Transform options: —, uppercase, thai_date_short, thai_date_full║
║                     pad_left:5:0, strip_dash, prefix:OE, ...     ║
║                                                                  ║
║  Encoding for this run: [TIS-620 ▾]    Format: [CSV ▾]           ║
║                                                                  ║
║  ┌──────────────────────────────────────────────────────────┐   ║
║  │ Adjustments apply to this download only (not saved)      │   ║
║  │ [💾 Save as Company Template]  [↺ Update Template]        │   ║
║  └──────────────────────────────────────────────────────────┘   ║
║                                                                  ║
║  [← Back]                        [Continue → Preview]           ║
╚══════════════════════════════════════════════════════════════════╝
```

#### Step ④: Preview Output

```
╔══════════════════════════════════════════════════════════════════╗
║ Export                                                           ║
║ ① ✓  ② ✓  ③ ✓  ④ Preview Output  ⑤ Download                     ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  ✅ Balanced — ฿245,300 Debit = ฿245,300 Credit  (15 docs)       ║
║  8 columns · TIS-620 · 15 rows                                   ║
║                                                                  ║
║  ┌─────┬──────────┬──────────────┬────────────────┬──────────┐  ║
║  │ลำดับ│วันที่    │เลขที่เอกสาร  │เลขที่ใบกำกับภาษ│จำนวนเงิน │  ║
║  ├─────┼──────────┼──────────────┼────────────────┼──────────┤  ║
║  │  1  │01/05/69  │6905/001      │IV-2025-001     │10,000.00 │  ║
║  │  2  │01/05/69  │6905/002      │IV-2025-002     │ 8,500.00 │  ║
║  │  3  │02/05/69  │6905/003      │TAX-003         │ 3,000.00 │  ║
║  │  4  │03/05/69  │6905/004      │B-240501        │15,200.00 │  ║
║  │  5  │03/05/69  │6905/005      │INV-9988        │ 4,750.00 │  ║
║  │ ... │ ...      │ ...          │ ...            │ ...      │  ║
║  └─────┴──────────┴──────────────┴────────────────┴──────────┘  ║
║  แสดง 10 แถวแรก จาก 15 แถว                                       ║
║                                                                  ║
║  [← Back]                          [Continue → Download]         ║
╚══════════════════════════════════════════════════════════════════╝
```

Unbalanced state:
```
║  ❌ Unbalanced — ฿245,300 Debit ≠ ฿244,100 Credit (ต่างกัน ฿1,200)║
║  เอกสารที่ไม่ balance: INV-003 (Dr ฿3,000 / Cr ฿1,800)            ║
║  [← กลับไปแก้ Map Review]           [Download ต่อไป (เสี่ยง)]     ║
```

#### Step ⑤: Download

```
╔══════════════════════════════════════════════════════════════════╗
║ Export                                                           ║
║ ① ✓  ② ✓  ③ ✓  ④ ✓  ⑤ Download                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  ✅ พร้อม Export                                                  ║
║  Template: Express ซื้อสด (Book 12)                              ║
║  15 เอกสาร · 8 คอลัมน์ · TIS-620                                ║
║                                                                  ║
║  ┌──────────────────────────────────────────────────────────┐   ║
║  │  [⬇ Download express_book12_6905.csv]                   │   ║
║  └──────────────────────────────────────────────────────────┘   ║
║                                                                  ║
║  [⬇ Download .xlsx]  (ถ้า template รองรับ Excel)                 ║
║                                                                  ║
║  [← กลับ]                      [Export ชุดใหม่ →]              ║
╚══════════════════════════════════════════════════════════════════╝
```

Filename pattern: `express_{book_type}_{period_YYMM}.csv`
Example: `express_book12_6905.csv`, `lovebot_book14_6905.csv`

---

### Screen B: Template Configurator — 3-Tab Persistent Setup

#### Tab ①: Upload & Detect (Schema Analyzer — W3 P0)

```
╔══════════════════════════════════════════════════════════════════╗
║ Template Configurator: Express ซื้อสด (Book 12)                  ║
║ [① Upload & Detect ●] [② กำหนด Columns] [③ ทดสอบ Output]        ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  อัปโหลดไฟล์ตัวอย่างจาก Express เพื่อตรวจสอบรูปแบบอัตโนมัติ        ║
║                                                                  ║
║  ┌──────────────────────────────────────────────────────────┐   ║
║  │                                                          │   ║
║  │         📂  วางไฟล์ที่นี่ หรือ คลิกเพื่อเลือก              │   ║
║  │              รองรับ .csv .xlsx .xls                     │   ║
║  │                                                          │   ║
║  └──────────────────────────────────────────────────────────┘   ║
║                                                                  ║
║  ──── ผลการตรวจสอบ ────────────────────────────────────────────  ║
║  ไฟล์: ซื้อสด_6905.csv · Encoding: TIS-620 · 8 คอลัมน์          ║
║                                                                  ║
║  ┌────┬───────────────────┬────────────────────┬────────────┐   ║
║  │ #  │ Header (sample)   │ LF Field           │ Confidence │   ║
║  ├────┼───────────────────┼────────────────────┼────────────┤   ║
║  │  1 │ ลำดับ             │ row_sequence       │ ████ 98%  │   ║
║  │  2 │ วันที่             │ invoice_date       │ ████ 95%  │   ║
║  │  3 │ เลขที่เอกสาร      │ document_number    │ ████ 92%  │   ║
║  │  4 │ เลขที่ใบกำกับ     │ tax_invoice_number │ ████ 90%  │   ║
║  │  5 │ จำนวนเงินก่อนภาษี │ amount_before_tax  │ ████ 96%  │   ║
║  │  6 │ รหัสผู้จำหน่าย    │ vendor_code        │ ████ 88%  │   ║
║  │  7 │ ชื่อผู้จำหน่าย    │ vendor_name        │ ████ 91%  │   ║
║  │  8 │ รหัสลงบัญชี       │ posting_acc_code   │ ▓▓▓  72%  │   ║
║  └────┴───────────────────┴────────────────────┴────────────┘   ║
║  ⚠ คอลัมน์ #8 confidence < 80% — กรุณายืนยัน LF field           ║
║                                                                  ║
║  แนะนำ: วันที่ → thai_date_short (DD/MM/YY)                      ║
║  Template mode: Flat Document (1 row per invoice)                ║
║                                                                  ║
║  [ข้ามขั้นตอนนี้]          [Apply to Column Config → Tab ②]       ║
╚══════════════════════════════════════════════════════════════════╝
```

#### Tab ②: กำหนด Columns (Persistent)

```
╔══════════════════════════════════════════════════════════════════╗
║ Template Configurator: Express ซื้อสด (Book 12)                  ║
║ [① Upload & Detect ✓] [② กำหนด Columns ●] [③ ทดสอบ Output]      ║
╠══════════════════════════════════════════════════════════════════╣
║  Name: [Express ซื้อสด บรรทัดเดียว    ]                          ║
║  Format: [CSV ▾]  Encoding: [TIS-620 ▾]  Delim: [, (comma) ▾]  ║
║  ──────────────────────────────────────────────────────────────  ║
║                                                                  ║
║  ┌─────────────────────────┐  ┌──────────────────────────────┐  ║
║  │ Available Fields        │  │ Selected Columns (drag)      │  ║
║  │─────────────────────────│  │──────────────────────────────│  ║
║  │ ▸ Express Transaction   │  │ ⠿ ลำดับ      row_sequence    │  ║
║  │  ☐ row_sequence         │  │ ⠿ วันที่      invoice_date   │  ║
║  │  ☐ document_number      │  │    Transform: [thai_date_short▾]│ ║
║  │  ☐ tax_invoice_number   │  │ ⠿ เลขที่เอกสาร document_no   │  ║
║  │  ☐ amount_before_tax    │  │ ⠿ เลขที่ใบกำกับ tax_inv_no   │  ║
║  │  ☐ vendor_code          │  │ ⠿ จำนวนเงิน  amount_before   │  ║
║  │  ☐ vendor_name          │  │ ⠿ รหัสผู้จำหน่าย vendor_code │  ║
║  │  ☐ posting_account_code │  │ ⠿ ชื่อผู้จำหน่าย vendor_name │  ║
║  │─────────────────────────│  │ ⠿ รหัสลงบัญชี posting_acc   │  ║
║  │ ▸ Extraction Fields     │  │──────────────────────────────│  ║
║  │  ☐ invoice_number       │  │ [+ Add Column]               │  ║
║  │  ☐ seller_name          │  └──────────────────────────────┘  ║
║  │  ...                    │                                     ║
║  └─────────────────────────┘                                     ║
║                                                                  ║
║  [← ยกเลิก]                 [Next: ทดสอบ Output → Tab ③]         ║
╚══════════════════════════════════════════════════════════════════╝
```

Column row — expand on click:
```
⠿  วันที่  [✏ Rename]  invoice_date  [Transform: thai_date_short ▾]  [🗑]
```

#### Tab ③: ทดสอบ Output — Round-trip Proof

```
╔══════════════════════════════════════════════════════════════════╗
║ Template Configurator: Express ซื้อสด (Book 12)                  ║
║ [① ✓] [② ✓] [③ ทดสอบ Output ●]                                  ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  ──── ผลการทดสอบ Round-trip ─────────────────────────────────── ║
║  เปรียบเทียบ output ที่ระบบสร้างกับ sample ที่อัปโหลดใน Tab ①    ║
║                                                                  ║
║  ┌─────────────────────────────────┬──────────────────────────┐ ║
║  │ การตรวจสอบ                     │ ผล                       │ ║
║  ├─────────────────────────────────┼──────────────────────────┤ ║
║  │ จำนวนคอลัมน์ (8)               │ ✅ ตรงกัน (8 = 8)        │ ║
║  │ ชื่อ Header ทุกคอลัมน์         │ ✅ ตรงกันทุกคอลัมน์       │ ║
║  │ ลำดับคอลัมน์                   │ ✅ ถูกต้อง                │ ║
║  │ Encoding (TIS-620)             │ ✅ ไม่มีอักขระเสีย         │ ║
║  │ รูปแบบวันที่ (DD/MM/YY)        │ ✅ ตรงกับ thai_date_short │ ║
║  └─────────────────────────────────┴──────────────────────────┘ ║
║                                                                  ║
║  ──── Preview: Output vs Sample ─────────────────────────────── ║
║  ┌──────────┬──────────────────────────┬───────────────────┐   ║
║  │          │ วันที่                   │ เลขที่เอกสาร      │   ║
║  ├──────────┼──────────────────────────┼───────────────────┤   ║
║  │ Sample   │ 01/05/69                 │ 6905/001          │   ║
║  │ Output   │ 01/05/69                 │ 6905/001          │   ║
║  │ Match    │ ✅                       │ ✅                 │   ║
║  └──────────┴──────────────────────────┴───────────────────┘   ║
║  ⚠ เปรียบเทียบเฉพาะ structure — ค่าจริงจะต่างกันเมื่อใช้ OCR data  ║
║                                                                  ║
║  [← แก้ไข Columns]           [💾 Save Template (ผ่านทุก check)] ║
╚══════════════════════════════════════════════════════════════════╝
```

Error state (header mismatch → Save blocked):
```
║  │ ชื่อ Header ทุกคอลัมน์         │ ❌ คอลัมน์ #8 ไม่ตรง      │ ║
║  │                                 │  Sample: "รหัสลงบัญชี"   │ ║
║  │                                 │  Output: "Posting Code"  │ ║
║  [💾 Save Template — ไม่สามารถบันทึกได้ กรุณาแก้ไขชื่อคอลัมน์ #8]  ║
```

No sample uploaded — always allow save:
```
║  ⚠ ไม่มีไฟล์ sample — ตรวจสอบได้เฉพาะโครงสร้าง column ไม่ได้เปรียบเทียบ ║
║  [💾 Save Template]                                                ║
```

---

## 4. User Flows

### Flow 1: Quick Export — get data out to Excel fast

```
Document Review Step 5 → [Continue to Export →]
  → Export Page Step ①: select documents → choose "Quick Export"
  → Step ②: column list (all fields pre-selected, no transforms)
     → uncheck any fields to hide, drag to reorder if needed
  → Step ③: preview (plain data, UTF-8 Excel)
  → Step ④: [Download data_export_6905.xlsx]
```

No template needed. No encoding concern. No transforms. Fastest path.

### Flow 2: Template Export — daily Express/LoveBot operation

```
Document Review Step 5 → [Continue to Export →]
  → Export Page Step ①: select documents → choose "Template Export"
  → Step ②: select template (e.g. Express ซื้อสด Book 12)
  → Step ③: review column adjustments for this run (pre-filled from template)
     → optionally rename, reorder, toggle visible, change encoding
  → Step ④: preview rendered output, verify balance
  → Step ⑤: [Download express_book12_6905.csv]
```

### Flow 3: Per-run adjustment → save back to template

```
Template Export Step ③: make adjustments
  → [💾 Save as Company Template] → enter name → new template saved to DB
  → [↺ Update Template]           → confirm → overwrites selected template
```

### Flow 4: First-time template setup (have Express sample file)

```
Export Page → [Manage Templates →] → [+ New Template]
  → Template Configurator Tab ①: upload Express CSV sample
  → System auto-detects column mapping with confidence scores
  → Fix any low-confidence columns (<80%)
  → [Apply to Column Config →] → Tab ②
  → Review columns, drag-drop reorder, set transforms
  → [Next: Test Output →] → Tab ③
  → Round-trip proof passes → [Save Template]
```

### Flow 5: Manual template setup (no sample file)

```
Export Page → [Manage Templates →] → [Clone master template] → Edit
  → Template Configurator Tab ② (skip Tab ①)
  → Manually add/reorder/rename columns
  → [Next →] → Tab ③ (no sample = structural check only, always saveable)
  → [Save Template]
```

---

## 5. Data Contracts

### Export page Step ② → Step ③ (template → runtime column state)

```typescript
interface ExportColumnState {
  template_id: string;
  columns: Array<{
    position: number;
    header_label: string;       // editable per-run (rename)
    source_field: string;
    transform: string | null;   // editable per-run
    visible: boolean;           // per-run show/hide (default true)
    override_value?: string;    // per-run static value override
  }>;
  encoding: "utf-8" | "utf-8-sig" | "cp874";  // editable per-run; default "utf-8" for Quick, from template for Template Export
  file_format: "csv" | "xlsx";               // editable per-run; default "xlsx" for Quick, from template for Template Export
  is_modified: boolean;                      // true if any field differs from saved template (always true for Quick Export)
}
```

### Export page Step ⑤ → Download API

```
POST /api/v1/export
{
  "template_id": "uuid",
  "document_ids": ["uuid", ...],
  "column_overrides": ExportColumnState | null,  // null = use saved template as-is
  "format": "csv" | "xlsx"
}
Response: file download (Content-Disposition: attachment; filename="express_book12_6905.csv")
```

If `column_overrides` is present and `is_modified=true` → backend builds runtime template from overrides instead of loading from DB. The saved template is NOT modified.

### Schema Analyzer API

```
POST /api/v1/templates/analyze
Content-Type: multipart/form-data
Body: file (CSV or Excel)

Response 200: AnalysisResult
```

```typescript
interface AnalysisResult {
  file_info: {
    filename: string;
    encoding_detected: "utf-8" | "utf-8-sig" | "cp874";
    rows_detected: number;
    file_size_kb: number;
  };
  suggested_file_format: "csv" | "xlsx";
  suggested_encoding: string;
  suggested_template_mode: "flat_document" | "flatten_row";
  columns: Array<{
    position: number;
    original_header: string;    // from sample file (e.g. "วันที่")
    lf_field: string;           // matched LF internal field name
    confidence: number;         // 0.0–1.0
    data_type: "string" | "date" | "number";
    suggested_transform: string | null;
    sample_values: string[];
  }>;
  warnings: Array<{
    column: string;
    message: string;
    alternatives?: string[];
  }>;
}
```

### Round-trip Test API

```
POST /api/v1/templates/{id}/round-trip-test
Content-Type: multipart/form-data
Body: sample_file (same file used in Tab ①)

Response 200: RoundTripResult
```

```typescript
interface RoundTripResult {
  checks: {
    column_count: boolean;
    header_match: boolean;
    encoding: boolean;
    date_format: boolean;
    row_count: boolean;
  };
  details: {
    header_mismatches?: Array<{
      position: number;
      sample: string;
      output: string;
    }>;
    encoding_errors?: number;   // count of U+FFFD replacement chars
  };
  blocked: boolean;             // true if column_count or header_match fail
  preview_comparison?: Array<{
    row_index: number;
    sample_values: string[];
    output_values: string[];
    match: boolean[];
  }>;
}
```

---

## 6. Round-trip Proof — Exact Pass/Fail Criteria

| Check | Pass condition | Blocks Save? |
|-------|---------------|-------------|
| `column_count` | Output CSV column count == sample file column count | **YES** |
| `header_match` | Every output header == sample header at same position (case-sensitive, byte-equal after TIS-620 decode) | **YES** |
| `encoding` | Output file decoded with `template.encoding` produces 0 replacement chars (U+FFFD) | Warning only |
| `date_format` | All values in date columns match `^\d{2}/\d{2}/\d{2}$` when `transform=thai_date_short` | Warning only |
| `row_count` | Output row count == sample data row count (excludes header row) | Info only |

**Note**: Round-trip proof compares structure (headers, order, encoding, date format) only.  
Values differ because sample is historical data and live export uses new OCR data.

**Blocking failures** cannot be overridden. They indicate template column config is wrong.  
**Warning-only failures** show a warning but Save is allowed — user accepts responsibility.

---

## 7. Task Impact

| Task | Before freeze | After freeze (frozen spec) |
|------|-------------|---------------------------|
| TASK-1001 Engine | implement whenever | **wait for freeze approval; must support `column_overrides` at render time** |
| TASK-1003 Configurator UI | one-panel drag-drop | **3-tab persistent setup per Screen B** |
| TASK-1006 Export screen | step 6 with checkboxes | **Full-page two-path (Quick / Template) per Screen A** |
| TASK-1009 Schema Analyzer | mid-sprint | **W3 P0 — implement first** |

### New requirement on Quick Export (Path A)

Quick Export bypasses template engine entirely for Path A.  
Backend: when `template_id` is null and `column_overrides` is provided → render using overrides only, no transforms, UTF-8 Excel output.

```
POST /api/v1/export
{
  "template_id": null,           // null = Quick Export path
  "document_ids": ["uuid", ...],
  "column_overrides": ExportColumnState,  // required when template_id null
  "format": "xlsx" | "csv"       // user-selectable, same as Template Export
}
```

### New requirement on TASK-1001

`TemplateEngine.render()` must accept an optional `column_overrides: list[ColumnDefinition]` parameter.  
When provided, use overrides instead of loading template columns from DB.  
This enables the per-run adjustment flow on the Export page.

```python
def render(
    self,
    template: ExportTemplate,
    rows: list[dict],
    column_overrides: list[ColumnDefinition] | None = None
) -> list[dict]:
    columns = column_overrides or template.columns
    ...
```

### W3 Implementation order (after freeze approved)

```
Day 1-2:  TASK-1009 backend — schema_analyzer.py + POST /api/v1/templates/analyze
Day 3-4:  TASK-1001 — template_engine.py (8 transforms + column_overrides param)
Day 5-6:  TASK-1003 — Template Configurator UI (3-tab, persistent)
Day 7-8:  TASK-1006 — Export full-page 5-step workflow + POST /api/v1/export with column_overrides
```

---

## 8. Out of Scope (Not Decided Here)

- Authentication/authorization for template endpoints (TASK-1002 scope)
- Clone workflow UI details (TASK-1005 scope)
- LoveBot-specific export naming (TASK-1208 scope)
- Mobile/responsive layout
- Multi-company batch export (future)

---

## 9. Approval Gate

> ⛔ **PREREQUISITE**: All 5 items below can only be validated and checked against a **live SIT environment**.  
> SIT environment (Section 10) must be fully operational **before any checkbox here can be reviewed**.  
> Dependency chain: **SIT ready → §9 review → ✅ → TASK-1003/1006 implementation**

All 5 items must be ✅ before Codex/Copilot begins implementation of TASK-1003/TASK-1006:

- ☐ Export page has two paths: **Quick Export** (all fields, no transforms, xlsx) and **Template Export** (template-driven, full column adjust, csv/xlsx)
- ☐ Export page Step ① shows mode picker (Quick vs Template) after document selection
- ☐ Column adjust panel is inline full-width on Export page (not modal), per-run by default, with optional "Save as Template" / "Update Template"
- ☐ Template Configurator 3-tab (persistent setup only, separate page, accessed from "Manage Templates →")
- ☐ TASK-1009 Schema Analyzer promoted to W3 P0 (implemented before TASK-1001/1003/1006)

## 10. SIT Runtime Alignment (Mandatory Before Any Export UX Implementation)

Export-related implementation for TASK-1001/TASK-1003/TASK-1006/TASK-1009 is blocked until SIT runtime validation is green.

Branch/environment alignment:

- `feature/* -> dev -> uat -> main`
- SIT gate host: `sit.yahwan.biz` on VPS `76.13.210.250`
- UAT host: `uat.bwcacc.biz` on VPS `72.62.74.232`
- PROD host: `app.bwcacc.biz` on VPS `72.62.247.9`

Required SIT evidence for UX tasks:

1. End-to-end export flow is executable by clicking through real UI on SIT (not dry run, not health-only)

1. Actions persist real data in PostgreSQL and can be read back in the same test run

1. Redis cache is used in the request path (cache hit/update evidence attached)

1. MinIO object write/read works for upload/export artifacts used by export flow

1. SIT gate run URL and evidence logs are attached to PR before requesting UAT promotion

**To approve**: change each `☐` to `✅` and add date. Commit to dev branch.

---

*Created: 2026-06-28*
*Author: Piboonsak Pimsarn + Claude Sonnet 4.6*
