"""FastAPI main application entrypoint."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from src.backend.app.endpoints import router as api_router
from src.backend.services.secrets_loader import load_llm_keys

app = FastAPI(
    title="AI Pre-Accounting Copilot",
    description="Automated document processing backend for OCR, extraction, and validation.",
    version="1.1.0",
)

# Include API endpoints router
app.include_router(api_router, prefix="/api")


@app.on_event("startup")
def load_runtime_secrets() -> None:
    """Populate runtime API keys before the first request hits the app."""
    load_llm_keys()
    settings.reload()


@app.get("/health")
def root_health() -> dict[str, str]:
    """Direct root-level health check endpoint."""
    return {"status": "ok"}


# Mount frontend static files
REPO_ROOT = Path(__file__).resolve().parents[3]
FRONTEND_DIR = REPO_ROOT / "src" / "frontend"
MANUAL_PATH = REPO_ROOT / "docs" / "PoC" / "plan" / "epic-5" / "USER-MANUAL-TH.html"
PHASE_II_DIR = REPO_ROOT / "docs" / "requirement" / "phaseII"
PHASE_II_TIMELINE_PATH = PHASE_II_DIR / "PHASE-II-TIMELINE.html"
PHASE_II_PROTOTYPE_PATH = PHASE_II_DIR / "PHASE-II-PROTOTYPE.html"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


def serve_html_file(file_path: Path, not_found_title: str) -> HTMLResponse:
    """Serve a UTF-8 HTML file with no-cache headers for review accuracy."""
    if not file_path.exists():
        return HTMLResponse(
            f"<html><body><h1>{not_found_title} not found</h1></body></html>",
            status_code=404,
        )
    return HTMLResponse(
        file_path.read_text(encoding="utf-8"),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/")
def read_root():
    """Redirect root path to interactive prototype view."""
    return RedirectResponse(url="/prototype")


@app.get("/manual", response_class=HTMLResponse)
def get_manual():
    """Serve the Thai user manual for the PoC."""
    if not MANUAL_PATH.exists():
        return HTMLResponse(
            "<html><body><h1>User manual not found</h1></body></html>",
            status_code=404,
        )
    return HTMLResponse(
        MANUAL_PATH.read_text(encoding="utf-8"),
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/prototype", response_class=HTMLResponse)
def get_prototype():
    """Serve the static interactive HTML pre-accounting prototype page."""
    prototype_path = FRONTEND_DIR / "ux-ui-prototype.html"
    if not prototype_path.exists():
        return HTMLResponse(
            "<html><body><h1>Prototype file not found!</h1></body></html>",
            status_code=404,
        )
    html = prototype_path.read_text(encoding="utf-8")
    # Keep legacy relative hrefs working by normalizing stylesheet path to /static.
    for old_href in (
        'href="./ux-ui-prototype.css"',
        "href='./ux-ui-prototype.css'",
        'href="ux-ui-prototype.css?v=20260610b"',
    ):
        html = html.replace(old_href, 'href="/static/ux-ui-prototype.css"')
    return HTMLResponse(
        html,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/timeline")
def legacy_timeline_redirect():
    """Backward-compatible redirect to the Phase II timeline review route."""
    return RedirectResponse(url="/phase2/timeline")


@app.get("/phase2", response_class=HTMLResponse)
def get_phase2_review_index():
    """Serve a lightweight reviewer index for Phase II pages."""
    return HTMLResponse(
        """
<!doctype html>
<html lang="th">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>LedgerFlow Phase II — Review Index</title>
    <style>
        :root {
            --bg: #f3f5f7;
            --surface: #ffffff;
            --ink: #1b2430;
            --muted: #5e6978;
            --line: #d6dde7;
            --accent: #0b66c3;
            --accent-soft: #e9f2fd;
            --radius: 12px;
            --shadow: 0 10px 30px rgba(12, 34, 57, 0.08);
            --font: "DM Sans", "Segoe UI", sans-serif;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: var(--font);
            background: radial-gradient(circle at top left, #eef6ff 0%, var(--bg) 45%, #eef2f6 100%);
            color: var(--ink);
            min-height: 100vh;
            display: grid;
            place-items: center;
            padding: 1.5rem;
        }
        .wrap {
            width: min(860px, 100%);
            background: var(--surface);
            border: 1px solid var(--line);
            border-radius: calc(var(--radius) + 2px);
            box-shadow: var(--shadow);
            padding: 1.5rem;
        }
        h1 {
            margin: 0;
            font-size: clamp(1.35rem, 2vw, 1.8rem);
            line-height: 1.2;
        }
        .sub {
            margin: 0.55rem 0 0;
            color: var(--muted);
            font-size: 0.95rem;
        }
        .grid {
            margin-top: 1.2rem;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            gap: 0.9rem;
        }
        .card {
            border: 1px solid var(--line);
            border-radius: var(--radius);
            padding: 1rem;
            background: linear-gradient(180deg, #ffffff 0%, #fbfcfe 100%);
        }
        .card h2 {
            margin: 0;
            font-size: 1rem;
        }
        .card p {
            margin: 0.55rem 0 0;
            color: var(--muted);
            font-size: 0.88rem;
            line-height: 1.5;
        }
        .actions {
            margin-top: 0.85rem;
            display: flex;
            gap: 0.55rem;
            flex-wrap: wrap;
        }
        a.btn {
            text-decoration: none;
            padding: 0.45rem 0.72rem;
            border-radius: 9px;
            border: 1px solid var(--line);
            color: var(--ink);
            font-size: 0.83rem;
            font-weight: 600;
            background: #fff;
        }
        a.btn.primary {
            background: var(--accent);
            border-color: var(--accent);
            color: #fff;
        }
        .note {
            margin-top: 1rem;
            padding: 0.7rem 0.8rem;
            border-radius: 10px;
            border: 1px solid #c5dcf9;
            background: var(--accent-soft);
            color: #12447c;
            font-size: 0.83rem;
        }
    </style>
</head>
<body>
    <main class="wrap">
        <h1>LedgerFlow Phase II Review</h1>
        <p class="sub">Reviewer entry point for Timeline and UX/UI prototype pages.</p>

        <section class="grid">
            <article class="card">
                <h2>Project Timeline</h2>
                <p>8-week milestone timeline and payment schedule for stakeholder planning.</p>
                <div class="actions">
                    <a class="btn primary" href="/phase2/timeline">Open Timeline</a>
                </div>
            </article>

            <article class="card">
                <h2>Full UX/UI Prototype</h2>
                <p>Phase II full prototype document for UX flow and UI scope review.</p>
                <div class="actions">
                    <a class="btn primary" href="/phase2/prototype">Open Prototype</a>
                    <a class="btn" href="/prototype">Open Interactive PoC</a>
                </div>
            </article>
        </section>

        <p class="note">For implementation validation, interactive flow remains available at /prototype. These Phase II pages are review documents.</p>
    </main>
</body>
</html>
        """.strip(),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/phase2/timeline", response_class=HTMLResponse)
def get_phase2_timeline():
    """Serve the Phase II timeline review document."""
    return serve_html_file(PHASE_II_TIMELINE_PATH, "Phase II timeline")


@app.get("/phase2/prototype", response_class=HTMLResponse)
def get_phase2_prototype():
    """Serve the Phase II full prototype review document."""
    return serve_html_file(PHASE_II_PROTOTYPE_PATH, "Phase II prototype")
