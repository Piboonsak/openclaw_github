# Phase II — Backlog

> Requirements identified but **not scheduled** in Phase II/1 (Go-Live MVP) or Phase II/2 (Post-Go-Live Enhancement).
> These items are candidates for future sprints, CR (Change Request) pricing, or Phase III.

---

## How to use this file

- Each item has a **BL-NNN** ID for tracking
- **Priority**: P0 = must-have before go-live (should be moved to an epic), P1 = high value but deferrable, P2 = nice-to-have
- **Source**: who requested and when
- Items that get scheduled should be moved to the relevant epic and marked as `[MOVED]` here

---

## BL-001: AI auto-match vendor/customer from OCR extraction

**Priority**: P1
**Source**: Client requirement, 2026-06-15
**Related**: TASK-1207 (vendor/customer import), TASK-1001 (template engine)
**Estimated effort**: 3-5 days

### Client request (verbatim)

> "ถ้าพี่มี list รายชื่อผู้จำหน่าย, รายชื่อลูกค้า เข้าไปในระบบ,
> ai สามารถตรวจเช็คและเลือก รหัสผู้จำหน่าย หรือ รหัส ลูกหนี้ ขึ้นมาใส่ให้ได้เองไหมคะ
> กรณีที่มีเจ้าหนี้ หรือ ลูกหนี้รายใหม่ เพิ่มเข้ามา"

### Scope

TASK-1207 covers the **import** part (CSV upload of vendor/customer lists). This backlog item covers the **AI matching** part:

1. **Fuzzy match seller_name → vendor_code**: When OCR extracts a `seller_name` from an invoice, AI should search the vendor master and suggest the best matching `vendor_code`. Approaches:
   - String similarity (Levenshtein, Jaro-Winkler) on vendor_name
   - LLM-assisted matching with confidence score
   - Cached mapping (seller_name → vendor_code) that learns from user confirmations
2. **Fuzzy match buyer_name → customer_code**: Same for sales documents.
3. **New entity detection**: When no match is found above a confidence threshold, flag the document as "new vendor/customer" and prompt the user to:
   - Create a new vendor/customer record (pre-filled from OCR data)
   - Or manually select from existing list
4. **User confirmation loop**: AI suggestion → user confirms/corrects → system learns for next time (feedback into `AccountMappingRule` or similar cache).

### Why deferred

- Requires ML/fuzzy matching infrastructure not in current sprint
- TASK-1207 (import lists) must be done first — no list = no matching
- The existing `account_resolver_cache.py` pattern could be extended, but needs design work
- Higher risk: incorrect auto-match could produce wrong accounting entries

### Prerequisite tasks

- TASK-1207 (vendor/customer master import) — must exist in DB first
- TASK-1001 (template engine field resolver) — lookup mechanism
- TASK-901 or TASK-902 (extraction accuracy) — seller_name quality from OCR

---

## BL-002: Date format preservation in CSV export (Excel compatibility)

**Priority**: P0 → **[MOVED to TASK-1001]**
**Source**: Client bug report, 2026-06-15
**Related**: TASK-1001 (template engine), [CLIENT-TEMPLATE-ANALYSIS.md](epic-10/CLIENT-TEMPLATE-ANALYSIS.md)

~~dd/mm/yy → dd/mm/yyyy issue when opening CSV in Excel. Fix: write dates as text strings.~~

**Status**: Incorporated into TASK-1001 as `thai_date_short` transform + date-as-text CSV writer fix. See [EPIC-10-TASKS-DETAIL.md](epic-10/EPIC-10-TASKS-DETAIL.md) ac_1001_date_text.

---

## BL-003: Express document number auto-generation per book type

**Priority**: P1
**Source**: Template analysis, 2026-06-15
**Related**: TASK-1001 (template engine), [CLIENT-TEMPLATE-ANALYSIS.md](epic-10/CLIENT-TEMPLATE-ANALYSIS.md)
**Estimated effort**: 1-2 days

### Scope

Generate document numbers automatically based on book type rules:

- Book 12 (ซื้อสด): `YYMM/NNN` starting from 001 (e.g., `6905/001`)
- Book 14 (ซื้อเชื่อ): `YYMM/NNN` starting from 100 (e.g., `6905/100`)
- Book 22 (ขายสด): `YYMM` + 6-digit seq (e.g., `6905000001`)
- Book 24 (ขายเชื่อ): same as 22

Requires:
- Book type config per template (which book number, starting sequence, format pattern)
- Sequence counter per company + book + period (monthly reset)
- Possibly DB-persisted sequence to prevent gaps/duplicates

### Why deferred

- Can use manual doc numbers for MVP (user provides or imports from source data)
- Auto-generation adds state management complexity (sequence tracking)
- Low risk to defer: client can manually set doc numbers initially

---

## BL-004: WHT (Withholding Tax) formula document computed column

**Priority**: P2
**Source**: Template analysis (Book 15+WHT template), 2026-06-15
**Related**: TASK-1001, [CLIENT-TEMPLATE-ANALYSIS.md](epic-10/CLIENT-TEMPLATE-ANALYSIS.md) section 2C
**Estimated effort**: 0.5 day

### Scope

For expense templates with WHT, generate a "formula document number" column: `OE` + document_number (e.g., `OE6905/100`). This is a simple `prefix:OE` transform — partially covered by the new `prefix` transform in TASK-1001. May be fully handled by the existing transform pipeline without dedicated work.

### Why deferred

- Low priority: only affects one template variant
- May already be covered by `prefix:X` transform added to TASK-1001
- Verify during TASK-1001 implementation

---

## BL-005: Multi-line journal entry templates

**Priority**: P2
**Source**: Anticipated from file naming pattern ("บรรทัดเดียว" = single line)
**Related**: Epic 10 template engine
**Estimated effort**: 2-3 days

### Scope

Current client templates are all "บรรทัดเดียว" (single line per transaction). The naming convention implies multi-line variants may exist (e.g., a purchase with multiple expense account splits). Multi-line templates would need:
- Group-by logic (multiple output rows per source document)
- Sub-line numbering
- Running total validation per group

### Why deferred

- No multi-line template samples provided yet
- Single-line covers the client's current workflow
- Significantly more complex template engine logic

---

## BL-006: Sales Tax Report template (Express format)

**Priority**: P1
**Source**: Epic 15 scope + template analysis
**Related**: Epic 15 (Sales Tax Report), Book 22/24 templates
**Estimated effort**: Already estimated in Epic 15 (~1 week)

### Scope

Sales Tax Report export in Express format. Already planned as Epic 15 in Phase II/2. Listing here for completeness — this is **scheduled**, not truly backlogged.

**Status**: Scheduled in Phase II/2 (Epic 15).

---

## Summary

| ID | Title | Priority | Est. | Status |
| --- | --- | --- | --- | --- |
| BL-001 | AI auto-match vendor/customer from OCR | P1 | 3-5d | Backlog |
| BL-002 | Date format preservation (CSV/Excel) | P0 | - | **MOVED** to TASK-1001 |
| BL-003 | Express doc number auto-generation | P1 | 1-2d | Backlog |
| BL-004 | WHT formula doc computed column | P2 | 0.5d | Backlog (may be covered) |
| BL-005 | Multi-line journal entry templates | P2 | 2-3d | Backlog |
| BL-006 | Sales Tax Report (Express format) | P1 | 1w | Scheduled (Epic 15, Phase II/2) |

---

*Created: 2026-06-15*
*Last updated: 2026-06-15*
