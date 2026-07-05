# Epic 10 — Template Engine + Configurator UI

**Goal**: Dynamic export mapping -- ให้ลูกค้าเลือก fields, ลำดับ columns, ตั้งชื่อ headers, clone template ได้ตามต้องการ (Req #5-9)

## Documentation

- **[EPIC-10-TASKS-DETAIL.md](EPIC-10-TASKS-DETAIL.md)** — full design for all tasks with ACs, schemas, governance fields
- **[UX-FREEZE-FINAL-CODEX-HANDOFF.md](UX-FREEZE-FINAL-CODEX-HANDOFF.md)** — 2026-07-05: UX freeze final resolution + what Claude already implemented on `main-ux-ui.html` (Export mode picker/inline columns, AP/AR split, Express master cards) + what's left for Codex on `TASK-1003`/`TASK-1006`. **Read this before touching Export/Configurator/Companies UI.**
- **[W4-CLAUDE-COMPLETED-SUMMARY-FOR-CODEX-REVIEW.md](W4-CLAUDE-COMPLETED-SUMMARY-FOR-CODEX-REVIEW.md)** — 2026-07-05: consolidated diff-level summary of both Claude passes (frontend UX/UI + backend Quick Export contract), with specific review checkpoints for Codex. **Read this before reviewing or building on top of either pass.**
- **[W4-EPIC10-CLAUDE-FOLLOWUP-01-COMPLETION.md](W4-EPIC10-CLAUDE-FOLLOWUP-01-COMPLETION.md)** — 2026-07-05: Configurator evidence-hardening pass. Found and fixed a real bug (every Configurator tab button threw `ReferenceError` on click — looked wired, wasn't), replaced the static column-editor mockup with a real one shared with the Export screen, fixed corrupted-encoding test assertions, and added real interaction-based regression tests. **Read this if you're about to touch the Configurator or its test coverage.**
- **[W4-EPIC10-CLAUDE-DOCS-CARRYOVER-CLEANUP-01-COMPLETION.md](W4-EPIC10-CLAUDE-DOCS-CARRYOVER-CLEANUP-01-COMPLETION.md)** — 2026-07-05: doc/carryover reconciliation pass across `W4-EXECUTION-PLAN.md`, `W4-TASK-BOARD.md`, and `PHASE-II-EPIC-ROADMAP.md`. Resolved the `TASK-906` cross-report tracking item, removed stale "Configurator unbuilt"/"gate still hold" wording, and added explicit deferral notes for template delete/clone and the row-grouping strategy panel. **Read this to find the current, non-contradictory W4 status without cross-checking every doc yourself.**
- **[W4-SIT-E2E-CLAUDE-CODE-COMPLETION-01.md](W4-SIT-E2E-CLAUDE-CODE-COMPLETION-01.md)** — 2026-07-05: whole-product-shell visible-control audit + closure. Found Companies/Users/Company-detail COA-AP-AR-Settings/Internal Console were 100% static demo markup faking success on every action. Added real `Company`/`User` DB-backed CRUD APIs (`/v1/admin/companies`, `/v1/admin/users` + reset-password) and rewired Companies/Users/AP-AR to them; converted every remaining fake-success control to an honest deferred/disabled state or a labeled demo-data banner. **Read this before touching Companies, Users, AP/AR, or any Internal Console screen.**
- **[W4-SIT-E2E-CODEX-REVIEW-01.md](W4-SIT-E2E-CODEX-REVIEW-01.md)** — 2026-07-05: Codex's review of the pass above — not deploy-ready yet; found residual fake-success controls on Review Scan/Review Mapping/Processing and the still-failing `index.html` parity check.
- **[W4-SIT-E2E-CLAUDE-CODE-FOLLOWUP-02-COMPLETION.md](W4-SIT-E2E-CLAUDE-CODE-FOLLOWUP-02-COMPLETION.md)** — 2026-07-05: closes every residual finding from the Codex review above (Review Scan Approve/Approve All, Review Mapping Confirm, Processing retry, plus the adjacent Flag modal found in re-audit) and includes a full justified list of every remaining `'ok'`-toast in `main-ux-ui.html`. **Read this for the final, Codex-reviewed state of the visible-control audit before Copilot deploys.**

## At a glance

| Aspect | Details |
|--------|---------|
| Lead | Full-stack Dev |
| Duration | 2.5 weeks (W3-W5) |
| Status | Partial - backend W3 path done, UI gate pending |
| Critical path | **Yes** — Core of Phase II, covers Req #5-9 (template engine is the main deliverable) |
| Week | W3-W5 |

## Task overview

| Task | Title | Complexity | Status | Pain points closed |
|------|-------|-----------|--------|-------------------|
| TASK-1001 | Template engine backend | L | Done (`a350333`) | PP-2, PP-3, PP-5, PP-8 |
| TASK-1002 | Template CRUD + Clone API endpoints | M | Done (`66c7419`) | PP-2, PP-3, PP-5, PP-8 |
| TASK-1003 | Template Configurator UI | L | UX freeze resolved 2026-07-04 (see [handoff](UX-FREEZE-FINAL-CODEX-HANDOFF.md)); 3-tab rebuild still pending — Codex | PP-2, PP-3, PP-5, PP-8 |
| TASK-1004 | Master templates + seed migration | M | New | PP-2, PP-3, PP-5 |
| TASK-1005 | Clone workflow | M | New | PP-2, PP-3, PP-5, PP-8 |
| TASK-1006 | Export screen integration | M | Export mode-picker + inline columns implemented by Claude 2026-07-05 on `main-ux-ui.html`; backend `column_overrides`/`template_id:null` still pending — see [handoff](UX-FREEZE-FINAL-CODEX-HANDOFF.md) | PP-2, PP-3, PP-5, PP-11 |
| TASK-1014 | Customer template-pack coverage expansion | M | New | PP-2, PP-3, PP-5, PP-11 |

## Dependencies

- **Upstream**: Epic 8 (`TASK-801A` schema slice, `TASK-801B` DB integration, `TASK-802` data migration, `TASK-803` JWT auth)
- **Downstream**: Epic 11 (Purchase Tax Report integration uses template engine), Epic 12 (Export screen needs templates)

## Execution order

```text
W3 Day 1-3:  TASK-1001 — Template engine backend (done: a350333)
W3 Day 3-5:  TASK-1002 — Template CRUD + Clone API (done: 66c7419)
W4 Day 1-3:  TASK-1003 — Template Configurator UI (integrate demo with real API)
W4 Day 3-5:  TASK-1004 — Master templates + seed migration (seed data for configurator)
W5 Day 1-2:  TASK-1005 — Clone workflow (Master -> Company, depends on TASK-1002 + 1004)
W5 Day 3-5:  TASK-1006 — Export screen integration (template selector + preview + download)
```

## Definition of Done

1. Template engine maps source fields to output columns with correct transforms (uppercase, pad_left, thai_date, strip_dash)
2. CSV export supports UTF-8, UTF-8 BOM, and TIS-620 encodings
3. Excel export generates styled worksheets via xlsxwriter
4. CRUD API endpoints work for template management (create, read, update, soft delete)
5. Clone creates deep copy of columns JSONB with independent company_id
6. Template Configurator UI supports drag-drop reorder, field picker, inline rename, transform selector
7. Master templates (Express GL 8-col, Purchase Tax 12-col) seeded via Alembic migration
8. Export screen shows template selector dropdown, preview table (first 5 rows), and download button
9. Balance validation blocks export when Sum(Debit) != Sum(Credit) per voucher
10. All ACs pass with pytest tests
11. Production-facing export retains PoC-level column select/reorder flexibility for both no-template and template-based export
12. Additional customer `excelformat` sample packs are classified into Epic work vs backlog questions

## Discussion Prompts

1. **Express CSV sample**: ~~ลูกค้าต้องส่ง sample CSV/Excel ที่ import เข้า Express ได้จริงก่อน W3~~
   - **RESOLVED 2026-06-15**: ได้รับ 6 template files ใน `private_data/poc/Comp_1/template/`. วิเคราะห์แล้ว → [CLIENT-TEMPLATE-ANALYSIS.md](epic-10/CLIENT-TEMPLATE-ANALYSIS.md)
2. **TIS-620 encoding**: ~~ลูกค้าใช้ Express รุ่นไหน?~~
   - **RESOLVED**: ไฟล์ทั้ง 6 ใช้ TIS-620 encoding. ต้อง support TIS-620 จริง.
3. **Transform extensibility**: ~~ตอนนี้ support 4 transforms -- ต้องเพิ่ม transform อื่นไหม?~~
   - **RESOLVED**: ต้องเพิ่ม 4 transforms ใหม่: `thai_date_short`, `thai_date_full`, `prefix:X`, `doc_number:PATTERN`. อัพเดท TASK-1001 แล้ว.
4. **Static columns**: บาง template อาจต้องใส่ค่าคงที่ (เช่น branch code "00000" ทุกแถว) -- ใช้ static_values JSONB ที่ออกแบบไว้พอไหม หรือต้อง per-column static?
5. **Preview data source**: Preview ใช้ sample data จาก DB (document ล่าสุด) หรือ mock data? ถ้า DB ยังไม่มี document ต้อง fallback อย่างไร?
6. **Date format bug** *(new 2026-06-15)*: ลูกค้าแจ้ง DD/MM/YY ถูก Excel เปลี่ยนเป็น DD/MM/YYYY เมื่อเปิดไฟล์ใหม่ → ต้อง write date as text string ใน CSV. ดู [CLIENT-TEMPLATE-ANALYSIS.md § 3](epic-10/CLIENT-TEMPLATE-ANALYSIS.md#3-client-bug-report-date-format-issue)
7. **Customer codes** *(new 2026-06-15)*: ไฟล์ขายมี ~100+ customer codes แต่ชื่อเป็น "ลูกค้าShopee" ทุกตัว — codes เหล่านี้คือรหัสอะไร? ต้อง confirm กับลูกค้า.
8. **Sales date year** *(new 2026-06-15)*: ไฟล์ขาย (Book 22/24) ใช้ปี 1969 ใน date field — เป็น ค.ศ. (ผิดยุค) หรือ Excel auto-format จาก 69 (พ.ศ.)? ต้อง confirm.

---

*Created: 2026-06-15*
*Updated: 2026-06-29 - TASK-1001 and TASK-1002 completed; TASK-1003/TASK-1006 remain gated by live SIT PO approval*
*Epic Roadmap: [PHASE-II-EPIC-ROADMAP.md](../PHASE-II-EPIC-ROADMAP.md)*
