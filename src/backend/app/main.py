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
    version="1.0.0",
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

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


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
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
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
