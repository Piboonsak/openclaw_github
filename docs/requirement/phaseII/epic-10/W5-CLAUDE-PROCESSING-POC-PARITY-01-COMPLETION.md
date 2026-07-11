# W5-CLAUDE-PROCESSING-POC-PARITY-01 — Completion Report

## Doc ID
- **Task:** `docs/requirement/phaseII/W5-CLAUDE-PROCESSING-POC-PARITY-01.prompt.json`
- **Board item:** W5-02 (Processing progress / perceived-stall fix); closes human findings W5-PROC-01, W5-PROC-02, and the Processing side of W5-PROC-03.
- **Tracking tag:** `W5-PROCESSING-POC-PARITY-01`
- **Branch:** `dev`

## Commit SHA
- **`8f07201`** — `feat(processing): POC-parity per-file stage tracker, elapsed + honest progress (W5-PROCESSING-POC-PARITY-01)`
- Docs commit (this report) follows on `dev`.

## What changed
Goal: make a human watching 2–3 real documents process understand what is happening and trust the system is still working — **without** restoring PoC localStorage/demo behaviour and **without** faking a backend percent.

**Frontend** — `src/frontend/index.html` and `src/frontend/main-ux-ui.html` (kept byte-identical):
- **Per-file glyph stage columns** `OCR · สกัดข้อมูล · จัดบัญชี`, driven by the real Celery task `stage` field the frontend already polls. Each cell renders `✓` done (green) / `⟳` running (spin) / `○` pending / `✗` failed. The 3 columns map 1:1 to the 3 real emitted pipeline stages — no fake "classify" column that never lights.
- **Stage-weighted summary bar**, labelled *"ความคืบหน้าตามขั้นตอน"* (stage progress, not a backend percent). Conservative weights (`queued .08, ocr .35, extract .65, mapping .88, done 1`) so the bar visibly leaves 0% as soon as OCR starts, instead of sitting frozen at `0 / N` through a multi-minute OCR/LLM job.
- **Live elapsed clock** per running row (`⏱ mm:ss`), updated by a 1 s ticker that runs only while work is active and the screen is visible; a **calm long-running note** appears past ~25 s ("งาน OCR/AI อาจใช้เวลาหลายนาที — ระบบยังทำงานอยู่").
- **Status legend** (`เสร็จแล้ว · กำลังทำงาน · รอคิว · ผิดพลาด`) and a running-batch reassurance banner while ≥1 doc runs.
- **Honest failure states:** the UI now recognises **both** `failed` and the off-enum `error` as a danger row (red background, danger badge, `✗` glyphs, error message) with a **retry** button; the "ประมวลผลแล้ว X / N" count excludes failed docs.
- `enable_stock` line-item notice left exactly as-is (header-only; Epic 9 stays honestly not-closed).

**Backend** — `src/backend/workers/tasks.py`:
- `_error_status_value()` now returns `DocumentStatus.FAILED.value` (root fix). Previously a task-level exception persisted the off-enum string `"error"`, which the Processing UI did not recognise and rendered as a healthy/green badge.

## PoC behavior reused
- Reference: `docs/requirement/phaseII/PHASE-II-PROTOTYPE.html` Screen 3 (per-file stage table with `✓ / ⟳ / ○` glyphs, running row highlight, per-status legend, progress summary) and `src/frontend/ux-ui-prototype.html` (`.spin` running glyph, status chips).
- **Reused: the visual/UX structure only** — glyph stage tracker, running-row accent background, danger-row background, `.spin`, the progress summary + legend layout (all existing CSS already present in the production files; no new CSS added).
- **Deliberately NOT reused:** the PoC's `localStorage` demo store, "Reset to Demo Data" flow, hard-coded fixture rows, and the "fill all 4 stage bars from one response" optimism. Every stage/percent/elapsed value shown is derived from the real task/document state.

## Real backend contract preserved
- Dispatch still `POST /api/v1/tasks/process-document/{id}`; polling still `GET /api/v1/tasks/{task_id}` every 1200 ms reading `status` + `stage`; per-doc refresh still `GET /api/v1/documents/{id}`; list still `GET /api/v1/companies/{id}/documents`. No endpoint contracts changed.
- The backend emits no percent/elapsed/timestamps — so percent is a **client-side conservative stage weight** (clearly labelled) and elapsed is **client-side since dispatch**. No fabricated backend data.
- Concurrency worker-pool (`MAX_CONCURRENT_PROCESSING = 5`) and the auto-handoff into Review Scan are unchanged.

## Tests run
- **Playwright (local, `POC_URL=http://127.0.0.1:8765`, `--workers=1`):**
  - New `tests/e2e/w5-processing-poc-parity-uxui.spec.ts` — **2/2 passed**: (a) stage progression queued→OCR→extract→mapping→success with a spinning glyph, live `⏱` elapsed, reassurance note, `35%` stage-weighted bar while running, then handoff to Review Scan; (b) a `status: "error"` document renders a danger badge + `✗` + error text + retry, with the legend counting `ผิดพลาด 1`.
  - Existing `tests/e2e/w4-routine-ops-uxui.spec.ts` — **11/11 passed** (no regression; HR-10/HR-12 batch-scope summary preserved).
  - Combined run: **13 passed** in ~20 s.
  - Local server note: the page loads `/static/auth.js`, so the scratch static root must expose `auth.js` at `/static/auth.js` (serving `src/frontend` flat 404s it and hangs `login()`).
- **pytest:** `tests/workers/test_tasks.py` + `tests/workers/test_task_status_endpoint.py` — **13 passed** (two failure-status assertions updated from `"error"` to `DocumentStatus.FAILED.value`).

## Residual risks
- **Elapsed resets on reload / lost `task_id`:** elapsed is client-side since dispatch, so a full page reload while a doc is still `processing` loses its start time and elapsed (stage still shows honestly; the bar falls back to coarse status). Persisting `started_at`/`updated_at` from the backend would fix this — deferred (backend exposes no timestamps today).
- **Failed-doc bar contribution:** a failed doc counts as "settled" (1.0) in the stage bar so it never looks stuck; the failure is surfaced via the red row, danger badge and legend, but a viewer glancing only at the bar could read it as complete.
- **Stage granularity:** backend emits 4 coarse stages (`queued/ocr/extract/mapping`) with no intra-stage percent; the tracker is discrete by design (glyphs, not filling bars).
- **Line-items (`enable_stock=true`):** unchanged — still header-only with the honest notice. Epic 9 remains open.

## Next Copilot proof required
- Deploy `dev` via Openclaw GitHub Actions (no direct SSH) and run a live SIT round that **clicks "เริ่มประมวลผลเอกสารที่รออยู่"** on 2–3 real documents and waits for the Celery jobs to finish (long timeout — real OCR/LLM takes minutes), capturing: the moving stage-progress bar, per-file `⟳→✓` stage glyphs, elapsed clock, the reassurance note, and the auto-handoff into Review Scan → Review Mapping (filename-first) → Export.
- Capture at least one genuine failure (or induced error) to prove the honest danger/retry row on live SIT.
