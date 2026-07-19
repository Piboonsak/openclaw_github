# W5 Task Board - Product Shell Stability And SIT Proof

> Week: W5 planning target
> Present target: 24 Jul 2026
> Purpose: close the human-reviewed functional gaps before the next customer presentation
> Source inputs: W4 live proof result 23, W4 human review regression register, W4-W7 rebaseline plan, latest manual SIT review

---

## 1. W5 Goal In Plain Thai

W5 ไม่ใช่สัปดาห์เปิด scope ใหม่เยอะ ๆ แล้วกระจายงานเพิ่ม แต่เป็นสัปดาห์ "เก็บหน้าระบบให้กดใช้งานจริงได้ครบ ไม่หลอก ไม่หลุด และไม่สับสน"

Focus หลัก:

1. **Product shell stability** - หน้าหลักที่ผู้ใช้กดจริงต้องนิ่งและไม่แสดงข้อมูลตัวอย่างปนเป็นข้อมูลจริง
2. **End-to-end SIT proof** - ต้องพิสูจน์บน SIT ว่า Upload -> Processing -> Review Scan -> Review Mapping -> Export วิ่งจบจริง
3. **Template/export continuity** - Template / Configurator / Export ต้องต่อกันได้ ไม่ใช่แต่ละหน้าผ่านแยกกัน

---

## 2. W4 Result 23 Decision

`W4-SIT-E2E-COPILOT-PRODUCT-SHELL-LIVE-PROOF-RESULT-23.prompt.json` เป็นหลักฐานที่ดี แต่ยัง **ไม่ปิด W5 functional risk** ทั้งหมด

| Area | Result | W5 Decision |
| --- | --- | --- |
| Runtime SHA includes product-shell work | PASS | Use as W5 baseline |
| Company `enable_stock` setting persists | PASS | Keep, then connect to deeper workflow later |
| Company delete role visibility | PASS | Keep testing with real roles |
| Internal Console + Model Router | PASS | Expand only where backend exists; label remaining internal panels honestly |
| Dashboard / Export fake shell cleanup | PASS with honest deferred banners | W5 should remove or wire the remaining high-confusion surfaces |
| Header-only routine flow | PARTIAL PASS | P0 W5 proof/fix item; must run full Upload -> OCR -> Review -> Mapping -> Export |
| Review Mapping filename-first with real document | NOT FULLY EXERCISED | P0 W5 proof/fix item |
| Line-item extraction/review | NOT CLOSED | Promoted to W5 P0 by human review because the target company has `enable_stock=true` and Export must include scanned line-item data |

---

## 3. Owner Split

| Owner | W5 responsibility |
| --- | --- |
| Codex | W5 board, issue routing, review stance, acceptance wording, customer-safe status |
| Claude | Product/frontend/backend implementation for user-visible functional gaps |
| Copilot | Deploy, SIT runtime proof, browser/network evidence, control-plane workflow |

---

## 4. Current W5 Status After 2026-07-11 SIT Proof

The W5 code slices were deployed to SIT and one live proof pack was completed:

- `5836bd6` — `feat(processing): POC-parity per-file stage tracker, elapsed + honest progress (W5-PROCESSING-POC-PARITY-01)`
- `1f4d964` — `feat(ui): add W5 human review functional fixes`
- Live deploy proof: Openclaw run `#29148944553`
- Live deployed commit recorded by Copilot: `eac484d63442110e7c73c7900c267bc958b7bbc3`
- Live proof artifacts:
  - `docs/requirement/phaseII/W5-SIT-E2E-ACCEPTANCE-MATRIX-01.md`
  - `test-results/w5-copilot-batch-deploy-sit-proof-03/2026-07-11T10-35-52-413Z/summary.json`

What is now true after SIT proof:

- `W5-01` is only **partially** proven on SIT: upload works, task starts, Processing UI moves, and Review screens open, but the captured proof still ends with `0` docs in Review Scan / Review Mapping, so the full Upload -> OCR -> Review -> Mapping -> Export round-trip is not yet closed with a real processed row.
- `W5-02` Processing perceived-stall fix is now **live-proven** on SIT.
- `W5-03` Users functional gap is **mostly closed on SIT**: deactivate action, company-name rendering, and `SysAdmin` badge/role path are live; first-login/live credential behavior still remains open.
- `W5-04` Company functional gap is **partially** closed on SIT: Mapping Rules DOCX row delete is live-proven; COA PDF Thai glyph normalization is still open.
- `W5-06` Template continuity is **partially** live-proven: blank Template Configurator path is working; upload sub-tab is honestly deferred; full real-data export continuity still depends on W5-12.
- `W5-07` Copilot SIT proof pack is **done**.
- `W5-12` real scanned-data export + line-item path remains the next major implementation task and must stay visible as open.
- OCR runtime stabilization is now a recorded W5 sub-result, not just a chat conclusion:
  - note: `docs/requirement/phaseII/W5-OCR-STABILIZATION-NOTE-2026-07-12.md`
  - current engineering decision: **Conditional Go**
  - keep SIT at `celery-worker --concurrency=2` and `OCR_TESSERACT_TIMEOUT_SECONDS=45` until export proof + one short soak cycle are completed.

---

## 5. W5-12 Spotlight

`W5-12` is intentionally still OPEN and is the next major Claude implementation task after the current Copilot SIT deploy/proof pass.

Why it is special:

- This is the bridge from the current honest header-only/product-shell state into the real `enable_stock=true` workflow.
- It is not just "one more export tweak" — it is the combined real-data export path plus line-item extraction/review/export path.
- Copilot should **not** close it during the current SIT proof unless the live app truly proves backend-driven line-item extraction, confirmation, and export for reviewed documents.

What W5-12 must close:

1. Export must stop depending on demo/static rows and read real reviewed/mapped documents for the selected company.
2. `enable_stock=true` must trigger non-blocking line-item extraction after header extraction.
3. Extracted line items must be stored and exposed for human confirmation in Review Scan / Review Mapping.
4. Export output must include confirmed line-item rows from the real document set.

Short status:

- Current state: open
- Owner: Claude
- Dependency before proof/closure: Copilot deploy/prove the already-pushed W5 slices first
- Do not mark done from banner-only behavior

---

## 6. W5 Delivery Board

### 6.1 Snapshot

| ID | Priority | Owner | Status | Short Task |
| --- | --- | --- | --- | --- |
| W5-01 | P0 | Copilot | Partial live proof only; real review-row round-trip still open | Full header-only E2E on SIT |
| W5-02 | P0 | Claude | Live-proven on SIT | Processing progress / perceived-stall fix |
| W5-03 | P0 | Claude | Mostly live-proven; first-login proof open | User admin CRUD + role correctness |
| W5-04 | P0 | Claude | Partial live-proven; COA glyph repair open | COA/Mapping Rules import quality |
| W5-05 | P0 | Claude | Waiting on live proof | Review Mapping filename-first with real doc |
| W5-06 | P0 | Claude + Copilot | Partial live-proven; upload tab deferred; export continuity open | Template/configurator/export continuity |
| W5-07 | P0 | Copilot | Done | One SIT proof pack after W5 fixes |
| W5-12 | P0 | Claude | Open next implementation task | Real-data export + line-item path |
| W5-08 | P1 | Claude | Open | Dashboard honesty / real-data boundary |
| W5-09 | P1 | Claude | Open | Internal Console follow-through |
| W5-10 | P1 | Codex | Open after SIT proof | Demo script + customer-safe wording |
| W5-11 | P1 | Copilot | Open | UAT prototype refresh path |

### 6.2 Task Notes

`W5-01` Full header-only routine E2E proof on SIT:
Current SIT result: upload worked, Processing task started, running notice/stage UI appeared, and Review screens opened, but the captured proof still showed `0` docs in Review Scan / Review Mapping.
Still needed to close: Upload 2-3 real docs -> start Processing -> stage progress completes -> Review Scan opens real docs -> approve -> Review Mapping shows rows -> Export downloads file.

`W5-02` Processing progress and perceived-stall fix:
Live SIT result: passed and then further stabilized. The original perceived-stall fix landed earlier; the later SIT OCR stabilization pass reduced worker concurrency to `2`, capped native OCR thread fan-out, and added a `45s` tesseract timeout guard. Latest proof batch completed `4/4` docs to `review_scan` with no `SoftTimeLimitExceeded()`.

Reference:
- `docs/requirement/phaseII/W5-OCR-STABILIZATION-NOTE-2026-07-12.md`
- `docs/requirement/phaseII/W5-COPILOT-OCR-LIVE-PROOF-13-RESULT.md`

`W5-03` User admin CRUD and role correctness:
Live SIT result: create `sys_admin`, `SysAdmin` badge, company-name rendering, deactivate, and inactive-after-reload all passed.
Still open: login/first-login flow needs its own explicit proof.

`W5-04` Company import quality:
Live SIT result: Mapping Rules DOCX preview/delete/confirm passed with 2 rules -> delete 1 -> import 1.
Still open: COA AI import Thai glyph normalization such as `คา`.

`W5-05` Review Mapping filename-first proof:
Repo/local says fixed, but live proof had no real document row.
Acceptance: real processed document appears in Review Mapping with uploaded filename as primary label and invoice number only secondary.

`W5-06` Template/export continuity:
Live SIT result: blank Template Configurator opens and configure tab is visible.
Still open: upload sub-tab is deferred in current build, and full export continuity from real reviewed documents still depends on W5-12.

`W5-07` End-to-end SIT proof pack after W5 fixes:
Live SIT result: done. Report, screenshots, and summary artifact were produced.

`W5-12` Export real scanned data + line-item scan path:
Human review found Export still contains demo/static rows and the target company is configured for line-item scan.
Acceptance: remove demo export rows and fixture fallback; Export document selector/preview/download must read from reviewed/mapped documents for selected company; when `enable_stock=true`, Processing must extract line items, Review Scan/Mapping must allow line-item confirmation, and Export must include confirmed line-item rows.

`W5-08` Dashboard honesty / real-data boundary:
Dashboard still has fixture disclosure; acceptable only if clearly labeled, but confusing for presentation.
Acceptance: either wire minimal real counts or keep a concise `analytics pending` state with no fake operational rows.

`W5-09` Internal Console follow-through:
Result 23 proves Model Router only; logs/settings are still partial.
Acceptance: keep sys_admin access; wire existing endpoints where present; label panels with exact missing backend dependency.

`W5-10` Customer-facing demo script and status wording:
24 Jul presentation needs a safe route through working features.
Acceptance: prepare concise demo flow and customer-safe `done / in progress / next` notes.

`W5-11` UAT static/prototype page refresh path:
User says `https://uat.bwcacc.biz/prototype` is the easy UX/UI page for customer view.
Acceptance: confirm current UAT/prototype source, publish only approved customer-facing pages, and prove route/content.

---

## 7. Human Review Issues Added To W5

### Users

| Issue | Priority | Owner | W5 action |
| --- | --- | --- | --- |
| Cannot delete user | P0 | Claude | Implement soft-delete/deactivate or explicitly disable with reason; prefer real admin API if route exists |
| Deleted/changed user still shows raw company UUIDs in `บริษัทที่ดูแล` | P0 | Claude | Resolve company names from company list; never show raw UUIDs in normal user table |
| Cannot add role `SysAdmin` | P0 | Claude | Allow sys_admin to grant sys_admin safely; preserve admin/staff restrictions |
| Login asks twice / `admin/admin` behavior confusing | P0 | Claude + Copilot | Normalize seeded credential truth, first-login state, and session refresh; SIT proof should use documented account flow |

### Company

| Issue | Priority | Owner | W5 action |
| --- | --- | --- | --- |
| COA PDF AI import corrupts Thai tone/glyph characters like `คา` | P0 | Claude | Add Thai text normalization/repair in COA preview path before confirm |
| Mapping Rules DOCX AI import cannot delete unwanted/duplicate rows before save | P0 | Claude | Add row remove action in review table and ensure removed rows are not persisted |

### Processing

| Issue | Priority | Owner | W5 action |
| --- | --- | --- | --- |
| Processing 3 docs feels stuck at `0 / 3` | P0 | Claude | Better polling, staged state, timeout messaging, and retry/error states |
| User needs confidence while waiting | P0 | Claude | Show current step per document: queued -> OCR -> extract -> mapping -> review-ready |
| Backend may still be running while UI looks frozen | P0 | Copilot + Claude | Copilot captures runtime/task evidence; Claude fixes UI/API gap if task state is not exposed well enough |

### Export + Line Items

| Issue | Priority | Owner | W5 action |
| --- | --- | --- | --- |
| Export still shows demo/static rows instead of real scanned data | P0 | Claude | Remove fixture/sample export rows from Dashboard/Processing/Review Mapping/Export operational surfaces; Export must load candidate documents from backend for the selected company and selected status |
| Export API still accepts caller-provided `sample_data` as the primary data source for live export | P0 | Claude | Add a backend-backed export dataset path using selected `document_ids` / company context; `sample_data` may remain only for template designer preview, not live export |
| Target company has stock/line-item scan enabled | P0 | Claude | When `Company.settings.enable_stock=true`, run line-item extraction after header extraction; store extracted line items; expose them for human confirmation; include confirmed line rows in export |
| Export expected output must match scanned rows | P0 | Claude + Copilot | Prove an exported CSV/XLSX can produce rows shaped like: Invoice No., Date, Seller, Seller Tax ID, Net Amount, VAT Amount, Total Amount, Document Type, Account Code, Description |

---

## 8. Acceptance Gates For W5

W5 is not done until all P0 gates pass:

| Gate | Condition | Owner |
| --- | --- | --- |
| G1 | One selected company context is used across Upload, Processing, Review, Mapping, Export | Copilot proof |
| G2 | Full header-only E2E flow finishes on SIT with real sample files | Copilot proof |
| G3 | Users admin flow is no longer broken/confusing for delete, roles, company display, login | Claude implementation + Copilot proof |
| G4 | COA and Mapping Rules review/import can be corrected before save | Claude implementation + Copilot proof |
| G5 | Template/create/export path is demo-safe for customer presentation | Claude implementation + Copilot proof |
| G6 | No visible P0 path uses fake-success, raw UUID display, or unlabeled fixture data | Codex review + Copilot proof |
| G7 | Export output is generated from real scanned/reviewed/mapped documents, and line-item-enabled companies produce confirmable line-item rows before export | Claude implementation + Copilot proof |

---

## 9. Recommended Execution Order

1. **Copilot - export normalization live proof (`W5-14`)**: OCR queue/pending-stall is now unblocked enough to continue, so the next customer-facing checkpoint is the real one-row export proof.
2. **Copilot - short OCR soak cycle**: keep current OCR runtime settings and run 3 consecutive small-batch checks so W5 is not closed from a single lucky run.
3. **Claude - only if W5-14 fails for real product reasons**: patch export normalization / AP-AR join / template-specific row-shaping based on live proof evidence, not assumption.
4. **Codex - review and customer script**: verify result reports, summarize demo path, update customer-facing status and final W5 acceptance position.

Full Epic 9 line-item extraction/review is now promoted for the W5 customer-critical path where `enable_stock=true`. Header-only companies must continue to work without line-item blocking.

---

## 10. Work While Waiting For Deploy

These are the best follow-on tasks that do not need the current SIT deploy result first:

1. **Codex - capture stabilization decisions**
   Keep `W5-OCR-STABILIZATION-NOTE-2026-07-12.md` and the board aligned so future reruns do not silently revert concurrency/timeout assumptions.
2. **Claude - COA Thai glyph normalization spike**
   Fix the remaining `W5-04` COA PDF text corruption path, because it is independent from the current OCR stabilization result.
3. **Codex - customer-safe demo/status draft**
   Prepare the short `done / proving now / next` wording and a safe demo route for the 24 Jul review.
4. **Copilot - UAT prototype route inventory**
   Only if it does not block the current SIT proof path: confirm what `uat.bwcacc.biz/prototype` currently serves and whether it should be refreshed later as a separate lane.

---

## 11. Human Review Regression 07 - Current Blocker

After `W5-COPILOT-DEPLOY-PROOF-HARDENED-06`, W5 is **not accepted** for closure.

Detailed issue register:

- `docs/requirement/phaseII/W5-HUMAN-REVIEW-REGRESSION-ISSUES-07.md`

Claude Code fix prompt:

- `docs/requirement/phaseII/W5-CLAUDE-HUMAN-REVIEW-REGRESSION-FIX-07.prompt.json`

Copilot deploy/proof prompt after Claude fix:

- `docs/requirement/phaseII/W5-COPILOT-HUMAN-REVIEW-DEPLOY-PROOF-08.prompt.json`

HR-07 acceptance matrix:

- `docs/requirement/phaseII/W5-HR07-ACCEPTANCE-MATRIX-02.md`

Copilot clean-lane follow-up prompt:

- `docs/requirement/phaseII/W5-COPILOT-CLEAN-LANE-FOLLOWUP-09.prompt.json`

Combined final Copilot lane after Claude 07 completion:

- `docs/requirement/phaseII/W5-COPILOT-FINAL-HR07-DEPLOY-PROOF-10.prompt.json`

P0 findings now blocking W5:

| ID | Owner | Status | Required next action |
| --- | --- | --- | --- |
| HR-07-01 Browser Basic Auth double login | Copilot runtime + Claude repo guard | Open | Remove browser Basic Auth from app login path through Openclaw deploy proof; app login must be the only visible login. |
| HR-07-02 Processing `SoftTimeLimitExceeded()` after first success | Claude | Open | Fix provider/stage timeouts, non-blocking line-item extraction, and stage evidence; prove small parallel batch no longer collapses. |
| HR-07-03 Company delete button missing | Claude | Open | Restore/prove true sys_admin delete visibility and backend enforcement; add regression coverage. |
| HR-07-04 SysAdmin company assignment cannot save | Claude | Open | Fix role/company assignment payload behavior without weakening sys_admin escalation rules. |
| HR-07-05 SIT test data left behind | Copilot + optional repo script hardening | Open | Clean W5 proof data by API and make proof runners cleanup or report cleanup evidence. |
| HR-07-06 Template Configurator demo content | Claude | Open | Remove demo/static template/runtime content from operational blank state. |

Corrected Processing note: this is not only a batch-scope issue. The frontend already fires concurrent processing workers; the live failure pattern points to backend/provider/stage timeout handling and optional line-item extraction behavior.

---

## 12. Codex Closeout Update - 2026-07-19

Latest closeout doc:

- `docs/requirement/phaseII/W5-CODEX-CLOSEOUT-STATUS-2026-07-19.md`
- W6 decision bundle: `docs/requirement/phaseII/W6-CLOSEOUT-DECISION-BUNDLE-2026-07-19.md`

Manual SIT review on 2026-07-17 added a new carryover set to the human-review
register:

- `docs/requirement/phaseII/W5-HUMAN-REVIEW-REGRESSION-ISSUES-07.md`
- New issue IDs: `HR-17-01` through `HR-17-10`

Current decision:

- W5 is **not accepted as fully closed** for customer-readiness.
- SIT route/health is currently reachable (`/api/health`, `/api/health/ready`, `/phase2/prototype` all returned `200` on 2026-07-19 read-only checks).
- Backend/service focused tests passed for export, master import/list, product master, stage timeouts, and line-item extraction (`54 passed`).
- COA/Mapping Rules local Playwright regression passed (`6 passed`).
- Product Master Playwright and W5 export/line-item Playwright are **verification gaps** because the local harness did not reliably leave the login screen / complete the static auth bootstrap. Do not count these as customer-facing proof.

W6 must start as a closeout sprint, not a broad new-feature sprint. The W6 decision bundle now includes `MENU-TREE-IA.html`, `BACKLOG.md`, `PHASE-II-TIMELINE.html`, `PHASE-II-MASTER-PLAN.md`, and `PHASE-II-EPIC-ROADMAP.md` as mandatory decision inputs.

### W6 P0 Carryover

| Carryover | Source issue | Why it blocks confidence |
| --- | --- | --- |
| Export per-document selection + Select All | `HR-17-05` | Customer cannot choose which reviewed documents to export. |
| Line-item confirm/reject/unconfirm + Approve All behavior | `HR-17-04` | `enable_stock=true` flow cannot be trusted if line rows cannot be explicitly accepted/rejected. |
| Review Scan party-field completeness | `HR-17-02` | Seller/buyer name and tax ID context is needed for accounting review. |
| Template Configurator mode/manual-flow repair | `HR-17-08`, `HR-17-09` | UI-only controls and missing manual fallback make the configurator feel broken. |
| COA/AP/AR/Product Master table UX consistency | `HR-17-07` | Customer cannot comfortably search, page/load more, add, edit, and delete/deactivate master data. |
| W6 SIT proof after fixes | `HR-17-10` | Automated proof must cover the real human-found problems, not only optimistic mock paths. |

### UX/UI Source Files For All W6 Prompts

Every W6 implementation prompt must explicitly say to align with:

- `docs/ux/UX-FREEZE-EXPORT-CONFIGURATOR.md`
- `src/frontend/main-ux-ui.html`
- `src/frontend/index.html`
- `src/frontend/ux-ui-prototype.html`
- `src/frontend/ux-ui-prototype.css`
- `docs/requirement/phaseII/PHASE-II-PROTOTYPE.html`

Do not replace the frozen full-page Export flow with a modal-first flow. Do not
leave fake-click controls on customer-facing surfaces; wire, hide, or label them
as deferred.
