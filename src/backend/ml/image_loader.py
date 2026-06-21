"""Helpers to load source documents (PDF or image) as base64-encoded image bytes
suitable for multi-modal LLM provider calls.

PDFs are rendered to PNG via pypdfium2 at a fixed scale and cached on disk to
avoid repeated rendering across cascade attempts.
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import os
from pathlib import Path

_CACHE_ROOT = Path(__file__).resolve().parents[3] / "tmp" / "stage_c_images"
_PDF_RENDER_SCALE = float(os.environ.get("STAGE_C_PDF_RENDER_SCALE", "2.0"))
_DEFAULT_MAX_PAGES = int(os.environ.get("STAGE_C_MAX_PAGES", "1"))


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _render_pdf_to_png(pdf_path: Path, max_pages: int) -> list[Path]:
    pdfium = importlib.import_module("pypdfium2")
    cache_dir = _CACHE_ROOT / _sha256_file(pdf_path)
    cache_dir.mkdir(parents=True, exist_ok=True)

    rendered: list[Path] = []
    doc = pdfium.PdfDocument(str(pdf_path))
    page_count = min(len(doc), max(1, max_pages))
    for i in range(page_count):
        out = cache_dir / f"page_{i + 1}.png"
        if not out.exists():
            page = doc[i]
            bitmap = page.render(scale=_PDF_RENDER_SCALE)
            bitmap.to_pil().save(out, format="PNG")
        rendered.append(out)
    return rendered


def load_images_for_vision(
    source_path: str, max_pages: int | None = None
) -> list[tuple[bytes, str]]:
    """Return list of (image_bytes, mime_type) for the given source path.

    PDFs are rendered to PNG (first `max_pages` pages, default 1).
    Image files are returned as-is with mime inferred from suffix.
    """
    path = Path(source_path)
    if not path.exists():
        raise FileNotFoundError(f"Source not found for vision input: {path}")

    pages = (
        max_pages
        if max_pages is not None
        else int(os.environ.get("STAGE_C_MAX_PAGES", str(_DEFAULT_MAX_PAGES)))
    )
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        png_paths = _render_pdf_to_png(path, max_pages=pages)
        return [(p.read_bytes(), "image/png") for p in png_paths]

    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix, "image/png")
    return [(path.read_bytes(), mime)]


def encode_image_data_uri(image_bytes: bytes, mime: str) -> str:
    """Encode image bytes as a base64 data URI for OpenAI-compatible APIs."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def encode_image_base64(image_bytes: bytes) -> str:
    """Encode image bytes as raw base64 (no data URI prefix) for Anthropic API."""
    return base64.b64encode(image_bytes).decode("ascii")
