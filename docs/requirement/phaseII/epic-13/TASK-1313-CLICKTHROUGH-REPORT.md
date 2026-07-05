# TASK-1313 — SIT Live Click-Through Report

> Task: `TASK-1313-CLICKTHROUGH` · Risk tier: LOW
> Surface: `https://sit.yahwan.biz/phase2/prototype` (production-facing `main-ux-ui.html`)
> Method: Playwright automated browser session (`tests/e2e/sit-clickthrough.spec.ts`)
> Date: 2026-07-04 · Result: **PASS** (1 passed, 0 failed)
> Evidence: full-page screenshots in `test-results/sit-evidence/` (git-ignored)

## Result summary

**PASS** — a real browser session logged in through the app UI (not curl), reached every core
screen by clicking the sidebar, and completed with **zero console errors** and **zero
401/403/404/5xx responses** across the whole session. This closes the gap Copilot's terminal-only
verification left open.

## Acceptance criteria

| Criterion (from handoff) | Result | Evidence |
|--------------------------|--------|----------|
| Login succeeds via the real UI on `/phase2/prototype` (not just curl) | ✅ PASS | `POST /api/v1/auth/login` returned **200**; app shell (`#app.visible`) rendered; topbar shows "System Admin – admin", company "บ. เมโทร อีเล็กทริค จำกัด"; login-success toast captured |
| Basic-Auth edge gate passes | ✅ PASS | Page loaded through nginx Basic-Auth (`httpCredentials`); no `401` on the review route |
| Dashboard renders populated content (not blank/static shell) | ✅ PASS* | `sit-dashboard.png` — KPI tiles (47/23/312/289), recent-activity table, page-credits panel |
| Upload / Review / Export / Templates / Configurator reachable, each distinct | ✅ PASS | `sit-upload.png`, `sit-review.png`, `sit-review-map.png`, `sit-export.png`, `sit-templates.png`, `sit-configurator.png` |
| Export screen wired to live template data | ✅ PASS | `sit-export.png` — template dropdown populated post-login ("GL เมโทร อีเล็กทริค (Clone)") from `/api/v1/templates`; CSV/Excel + UTF-8/TIS-620 options; balance badges |
| No unhandled console errors / 401 loops during navigation | ✅ PASS | Test collects all `console.error` + `>=400` responses per screen; none observed |
| `/index.html` behaves identically after cache fix | ⚠️ NOT COVERED | Only `/phase2/prototype` was driven this run; `/index.html` parity not yet re-checked in-browser |

\* **Honest caveat:** the Dashboard KPI numbers and activity rows are **prototype placeholder
content baked into `main-ux-ui.html`**, not DB-derived. The genuinely API-backed, live-wired paths
proven in this run are **auth (login + `/me`)**, the **template list** (Export dropdown), and the
**export actions** (`/api/v1/export/preview|validate|export` handlers are bound). So "backend is
wired, not mocked" holds for the auth + template + export flow; the dashboard tiles remain static.

## Cross-check against the UX-freeze acceptance review

The live surface visually confirms two findings from `W4-UX-FREEZE-ACCEPTANCE-REVIEW.md`:
- **Export (mismatch M1):** single-flow export with a template dropdown — **no Quick/Template mode
  picker**. The frozen two-path Screen A is not yet built.
- **Configurator (mismatch M4 / item 4):** a single-page builder ("Configurator Runtime State" +
  Available Fields + Template Mode), **not** the frozen 3-tab layout (Upload & Detect / กำหนด
  Columns / ทดสอบ Output). Spec approved, implementation still pending.

These are expected — W4-03/06 are blocked-by-approval-gate, not yet implemented — and do **not**
affect the TASK-1313 runtime PASS.

## How to reproduce

```bash
# credentials live in git-ignored .env.sit.local (see .env.sit.local.example)
npx playwright test tests/e2e/sit-clickthrough.spec.ts
# screenshots -> test-results/sit-evidence/
```

## Open follow-up (optional, non-blocking)

- Add an `/index.html` parity assertion to the same spec to fully close the last handoff item.
