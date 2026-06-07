"""OCR processing helpers for TASK-501.

The processor writes OCR artifacts to `src/backend/ml/cache/{sha256}/ocr_output.json`.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_ROOT = REPO_ROOT / "src" / "backend" / "ml" / "cache"
_PADDLE_OCR_INSTANCE: Any | None = None


def _sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _extract_text_blocks_for_text_file(file_path: Path) -> list[dict[str, Any]]:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    blocks: list[dict[str, Any]] = []
    for idx, line in enumerate(text.splitlines()):
        if not line.strip():
            continue
        blocks.append(
            {
                "id": idx,
                "text": line.strip(),
                "confidence": 1.0,
                "bbox": [0, idx * 24, max(len(line.strip()) * 8, 40), (idx + 1) * 24],
            }
        )
    return blocks


def _fallback_blocks_when_ocr_unavailable(file_path: Path) -> list[dict[str, Any]]:
    """Return a minimal block so downstream pipeline can continue in degraded mode."""
    stem = file_path.stem.strip() or "unknown_document"
    return [
        {
            "id": 0,
            "text": stem,
            "confidence": 0.2,
            "bbox": [0, 0, max(len(stem) * 8, 80), 24],
        }
    ]


def _is_tesseract_unavailable_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "tesseract" in message and (
        "not installed" in message or "not in your path" in message
    )


def _is_paddle_unavailable_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "paddle" in message and (
        "not installed" in message
        or "no module named" in message
        or "cannot import" in message
    )


def _get_paddle_ocr() -> Any:
    global _PADDLE_OCR_INSTANCE
    if _PADDLE_OCR_INSTANCE is not None:
        return _PADDLE_OCR_INSTANCE

    try:
        paddleocr_module = importlib.import_module("paddleocr")
    except ImportError as exc:  # pragma: no cover - depends on local OCR stack
        raise RuntimeError(
            "Missing OCR dependencies: paddleocr + paddlepaddle are required for PaddleOCR"
        ) from exc

    # Thai-first OCR engine per D1 design decision.
    _PADDLE_OCR_INSTANCE = paddleocr_module.PaddleOCR(
        use_angle_cls=True,
        lang="th",
        show_log=False,
    )
    return _PADDLE_OCR_INSTANCE


def _extract_text_blocks_with_paddle(
    image_obj: Any, id_offset: int = 0
) -> list[dict[str, Any]]:
    try:
        numpy_module = importlib.import_module("numpy")
        paddle = _get_paddle_ocr()
    except RuntimeError:
        raise
    except ImportError as exc:  # pragma: no cover - depends on local OCR stack
        raise RuntimeError(
            "Missing OCR dependency: numpy is required for PaddleOCR image conversion"
        ) from exc

    image_array = numpy_module.array(image_obj)
    result = paddle.ocr(image_array, cls=True)

    blocks: list[dict[str, Any]] = []
    next_id = id_offset
    lines = result[0] if result else []
    for line in lines:
        if not line or len(line) < 2:
            continue

        box = line[0]
        rec = line[1] if len(line) > 1 else None
        if not rec or len(rec) < 2:
            continue

        text = str(rec[0]).strip()
        if not text:
            continue

        try:
            conf = max(min(float(rec[1]), 1.0), 0.0)
        except (TypeError, ValueError):
            conf = 0.0

        xs = [int(point[0]) for point in box]
        ys = [int(point[1]) for point in box]
        blocks.append(
            {
                "id": next_id,
                "text": text,
                "confidence": conf,
                "bbox": [min(xs), min(ys), max(xs), max(ys)],
            }
        )
        next_id += 1

    return blocks


def _extract_text_blocks_with_preferred_engine(
    image_obj: Any, id_offset: int = 0
) -> list[dict[str, Any]]:
    paddle_exc: Exception | None = None

    try:
        paddle_blocks = _extract_text_blocks_with_paddle(image_obj, id_offset=id_offset)
        if paddle_blocks:
            return paddle_blocks
    except RuntimeError as exc:
        paddle_exc = exc

    try:
        return _extract_text_blocks_with_tesseract(image_obj, id_offset=id_offset)
    except RuntimeError as tesseract_exc:
        if paddle_exc is not None:
            raise RuntimeError(
                f"PaddleOCR failed ({paddle_exc}); Tesseract failed ({tesseract_exc})"
            ) from tesseract_exc
        raise


def _extract_text_blocks_with_tesseract(
    image_obj: Any, id_offset: int = 0
) -> list[dict[str, Any]]:
    try:
        pytesseract = importlib.import_module("pytesseract")
    except ImportError as exc:  # pragma: no cover - depends on local OCR stack
        raise RuntimeError(
            "Missing OCR dependencies: Pillow + pytesseract are required for image OCR"
        ) from exc

    # If PATH is not refreshed yet after installation, fallback to common Windows path.
    if shutil.which("tesseract") is None:
        windows_default = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
        if windows_default.exists():
            pytesseract.pytesseract.tesseract_cmd = str(windows_default)

    data = pytesseract.image_to_data(
        image_obj,
        lang="tha+eng",
        output_type=pytesseract.Output.DICT,
    )

    blocks: list[dict[str, Any]] = []
    count = len(data.get("text", []))
    for idx in range(count):
        text = str(data["text"][idx]).strip()
        if not text:
            continue
        conf_raw = str(data["conf"][idx]).strip()
        try:
            conf = max(min(float(conf_raw), 100.0), 0.0) / 100.0
        except ValueError:
            conf = 0.0
        blocks.append(
            {
                "id": id_offset + idx,
                "text": text,
                "confidence": conf,
                "bbox": [
                    int(data["left"][idx]),
                    int(data["top"][idx]),
                    int(data["left"][idx] + data["width"][idx]),
                    int(data["top"][idx] + data["height"][idx]),
                ],
            }
        )
    return blocks


def _extract_text_blocks_for_pdf(file_path: Path) -> list[dict[str, Any]]:
    # Prefer native text extraction for searchable PDFs before OCR fallback.
    try:
        pypdf = importlib.import_module("pypdf")
    except ImportError as exc:  # pragma: no cover - depends on local PDF stack
        raise RuntimeError(
            "Missing PDF dependency: pypdf is required for PDF processing"
        ) from exc

    reader = pypdf.PdfReader(str(file_path))
    blocks: list[dict[str, Any]] = []
    block_id = 0

    for page_idx, page in enumerate(reader.pages):
        page_text = (page.extract_text() or "").strip()
        if not page_text:
            continue

        for line_idx, line in enumerate(page_text.splitlines()):
            text = line.strip()
            if not text:
                continue
            blocks.append(
                {
                    "id": block_id,
                    "text": text,
                    "confidence": 1.0,
                    "bbox": [
                        0,
                        line_idx * 24,
                        max(len(text) * 8, 40),
                        (line_idx + 1) * 24,
                    ],
                    "page": page_idx + 1,
                }
            )
            block_id += 1

    if blocks:
        return blocks

    # Fallback for scanned PDFs: render pages to images then OCR each page.
    # Engine order: PaddleOCR (primary) -> Tesseract (fallback).
    try:
        pdfium = importlib.import_module("pypdfium2")
        importlib.import_module("PIL.Image")
    except ImportError as exc:  # pragma: no cover - optional fallback path
        raise RuntimeError(
            "PDF has no embedded text and image OCR fallback requires pypdfium2 + Pillow + PaddleOCR/Tesseract"
        ) from exc

    pdf_doc = pdfium.PdfDocument(str(file_path))
    for page_idx in range(len(pdf_doc)):
        page = pdf_doc[page_idx]
        bitmap = page.render(scale=2.0)
        pil_image = bitmap.to_pil()
        page_blocks = _extract_text_blocks_with_preferred_engine(
            pil_image, id_offset=block_id
        )
        for block in page_blocks:
            block["page"] = page_idx + 1
        blocks.extend(page_blocks)
        block_id += len(page_blocks)

    return blocks


def _extract_text_blocks_for_image_file(file_path: Path) -> list[dict[str, Any]]:
    try:
        image_module = importlib.import_module("PIL.Image")
    except ImportError as exc:  # pragma: no cover - depends on local OCR stack
        raise RuntimeError(
            "Missing OCR dependency: Pillow is required for image OCR"
        ) from exc

    image = image_module.open(file_path)
    return _extract_text_blocks_with_preferred_engine(image)


def _build_layout_zones(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not blocks:
        return []

    top_limit = min(b["bbox"][1] for b in blocks) + 240
    header = [b for b in blocks if b["bbox"][1] <= top_limit]
    body = [b for b in blocks if b["bbox"][1] > top_limit]

    zones: list[dict[str, Any]] = []
    if header:
        zones.append(
            {
                "name": "header",
                "block_ids": [b["id"] for b in header],
            }
        )
    if body:
        zones.append(
            {
                "name": "body",
                "block_ids": [b["id"] for b in body],
            }
        )
    return zones


def run_ocr(file_path: str, cache_root: Path | None = None) -> dict[str, Any]:
    """Run OCR and persist `ocr_output.json` under cache/{sha256}/."""
    source = Path(file_path)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")

    sha = _sha256_file(source)
    root = cache_root or DEFAULT_CACHE_ROOT
    artifact_dir = root / sha
    artifact_path = artifact_dir / "ocr_output.json"

    if artifact_path.exists():
        cached = json.loads(artifact_path.read_text(encoding="utf-8"))
        cached["cache_hit"] = True
        return cached

    suffix = source.suffix.lower()
    warnings: list[str] = []
    try:
        if suffix == ".txt":
            blocks = _extract_text_blocks_for_text_file(source)
        elif suffix == ".pdf":
            blocks = _extract_text_blocks_for_pdf(source)
        else:
            blocks = _extract_text_blocks_for_image_file(source)
    except RuntimeError as exc:
        if not (_is_tesseract_unavailable_error(exc) or _is_paddle_unavailable_error(exc)):
            raise
        # Keep pipeline alive on developer machines without OCR engines.
        blocks = _fallback_blocks_when_ocr_unavailable(source)
        warnings.append(
            "OCR engines are unavailable (PaddleOCR/Tesseract). OCR ran in degraded mode using filename fallback text."
        )

    avg_conf = round(
        sum(float(block["confidence"]) for block in blocks) / max(len(blocks), 1),
        4,
    )

    payload = {
        "schema_version": "v1",
        "source_file": str(source),
        "sha256": sha,
        "blocks": blocks,
        "layout_zones": _build_layout_zones(blocks),
        "avg_confidence": avg_conf,
        "needs_human_review": avg_conf < 0.60,
        "warnings": warnings,
        "cache_hit": False,
    }

    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return payload


def process_document(file_path: str) -> str:
    """Legacy compatibility API used by existing tests and callers.

    Returns extracted text joined from OCR blocks.
    """
    ocr_output = run_ocr(file_path)
    return "\n".join(block["text"] for block in ocr_output["blocks"])
