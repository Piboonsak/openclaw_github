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

## 4. Current W5 Status After 2026-07-11 Code Pass

Two W5 code slices are now on `origin/dev` and ready for one Copilot SIT deploy/proof batch:

- `5836bd6` — `feat(processing): POC-parity per-file stage tracker, elapsed + honest progress (W5-PROCESSING-POC-PARITY-01)`
- `1f4d964` — `feat(ui): add W5 human review functional fixes`

What is now true in repo code:

- `W5-02` Processing perceived-stall fix is implemented locally and pushed; live SIT proof is still required.
- `W5-03` Users functional gap is **partially** closed: deactivate action, company-name rendering, and `SysAdmin` badge/role path are implemented; first-login/live credential proof is still open.
- `W5-04` Company functional gap is **partially** closed: Mapping Rules DOCX row delete is implemented; COA PDF Thai glyph normalization is still open.
- `W5-06` Template continuity is **partially** closed: blank Template Configurator path is implemented; full live export continuity still depends on W5-12.
- `W5-12` real scanned-data export + line-item path remains the next major implementation task and must stay visible as open.

---

## 5. W5 Delivery Board

| ID | Priority | Owner | Status | Task | Why It Matters | Acceptance / Proof |
| --- | --- | --- | --- | --- | --- |
| W5-01 | P0 | Copilot first, Claude if defect found | Ready for deploy/proof | Full header-only routine E2E proof on SIT | Result 23 only proved file selection/navigation, not a completed OCR round-trip | On SIT: Upload 2-3 real docs -> start Processing -> stage progress completes -> Review Scan opens real docs -> approve -> Review Mapping shows rows -> Export downloads file |
| W5-02 | P0 | Claude | Code done in `5836bd6`; SIT proof pending | Processing progress and perceived-stall fix | User sees `0 / 3` and feels the scan is stuck even when backend may still run | UI must show per-document stages, elapsed time, queued/running/done/error state, and never look frozen during long OCR/LLM work |
| W5-03 | P0 | Claude | Partial code done in `1f4d964`; login proof still open | User admin CRUD and role correctness | Human review found: cannot delete user, deleted user's company assignment shows raw UUIDs, cannot add `SysAdmin`, double-login behavior | User delete works or is clearly disabled with reason; deleted/disabled users do not leave UUID display garbage; `SysAdmin` role can be assigned by sys_admin; login/first-login flow happens once and is understandable |
| W5-04 | P0 | Claude | Partial: Mapping Rules row delete done in `1f4d964`; COA glyph repair still open | Company import quality: COA PDF text normalization + Mapping Rules row delete | COA AI import has corrupted Thai tone/glyphs such as `คา`; Mapping Rules import review cannot remove unwanted/duplicate rows | COA preview normalizes Thai text before confirm; Mapping Rules review table supports delete/remove before save; deleted rows are not persisted |
| W5-05 | P0 | Claude | Waiting on live processed document proof | Review Mapping filename-first proof with real processed document | Repo/local says fixed, but live proof had no real document row | Real processed document appears in Review Mapping with uploaded filename as primary label and invoice number only secondary |
| W5-06 | P0 | Claude + Copilot | Partial: blank-configurator path done in `1f4d964`; full export continuity still open | Template/export continuity | Customer presentation needs a clear Template -> Export story, not disconnected screens | Create/edit template without forced CSV-only path; sample upload remains helper; Quick/Template Export preview/download works from selected company data on SIT |
| W5-07 | P0 | Copilot | Ready after deploy | End-to-end SIT proof pack after W5 fixes | Payment/presentation needs one trustworthy proof, not many isolated claims | One report with screenshots/network proof for Companies, Users, Upload, Processing, Review Scan, Review Mapping, Templates, Export |
| W5-12 | P0 | Claude | Open next implementation task | Export real scanned data + line-item scan path | Human review found Export still contains demo/static rows and the target company is configured for line-item scan | Remove demo export rows and fixture fallback; Export document selector/preview/download must read from reviewed/mapped documents for selected company; when `enable_stock=true`, Processing must extract line items, Review Scan/Mapping must allow line-item confirmation, and Export must include confirmed line-item rows |
| W5-08 | P1 | Claude | Open | Dashboard honesty / real data boundary | Dashboard still has fixture disclosure; acceptable only if clearly labeled, but confusing for presentation | Either wire minimal real counts or keep a concise "analytics pending" state with no fake operational rows |
| W5-09 | P1 | Claude | Open | Internal Console follow-through | Result 23 proves Model Router only; logs/settings are still partial | Keep sys_admin access; wire existing endpoints where present; label panels with exact missing backend dependency |
| W5-10 | P1 | Codex | Open after SIT proof | Customer-facing demo script and status wording | 24 Jul presentation needs a safe route through working features | Prepare concise demo flow and customer-safe "done / in progress / next" notes |
| W5-11 | P1 | Copilot | Open | UAT static/prototype page refresh path | User says `https://uat.bwcacc.biz/prototype` is the easy UX/UI page for customer view | Confirm current UAT/prototype source, publish only approved customer-facing pages, and prove route/content |

---

## 6. Human Review Issues Added To W5

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

## 7. Acceptance Gates For W5

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

## 8. Recommended Execution Order

1. **Copilot - deploy and live proof of the already-pushed W5 slices**: deploy `dev` including `5836bd6` and `1f4d964` via Openclaw, then run one full SIT proof pack
2. **Claude - W5-12 implementation**: real scanned-data export + line-item path for `enable_stock=true` companies, because the current deploy should still report this honestly as open unless live SIT somehow already proves otherwise
3. **Codex - review and customer script**: verify result reports, summarize demo path, update customer-facing status

Full Epic 9 line-item extraction/review is now promoted for the W5 customer-critical path where `enable_stock=true`. Header-only companies must continue to work without line-item blocking.
