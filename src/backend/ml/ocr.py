"""OCR processing helpers for TASK-501.

The processor writes OCR artifacts to `src/backend/ml/cache/{sha256}/ocr_output.json`.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_ROOT = REPO_ROOT / "src" / "backend" / "ml" / "cache"
_PADDLE_OCR_INSTANCE: Any | None = None
_LOW_CONF_THRESHOLD = 0.55
_MIN_ALNUM_RATIO = 0.30
OCR_SCHEMA_VERSION = "v3"
# Bumped from 2.0 (≈144 DPI) so Thai diacritics survive PaddleOCR/Tesseract;
# override via OCR_RENDER_SCALE for tuning per environment.
OCR_RENDER_SCALE = float(os.environ.get("OCR_RENDER_SCALE", "3.0"))
# Set OCR_DESKEW=1 to enable automatic deskew correction (requires opencv-python-headless).
OCR_DESKEW = os.environ.get("OCR_DESKEW", "0") == "1"
# Set OCR_ADAPTIVE_THRESH=1 to enable adaptive binarization for faded/low-contrast scans.
OCR_ADAPTIVE_THRESH = os.environ.get("OCR_ADAPTIVE_THRESH", "1") == "1"
# Repo-local tessdata dir: Program Files install ships eng+osd only, so we
# bundle tha.traineddata here and point Tesseract at it via --tessdata-dir.
LOCAL_TESSDATA_DIR = Path(os.environ.get("TESSDATA_DIR", str(REPO_ROOT / ".tessdata")))


def _deskew_image(image_obj: Any) -> Any:
    """Deskew a grayscale PIL image using OpenCV moment-based angle detection."""
    try:
        cv2 = importlib.import_module("cv2")
        numpy_module = importlib.import_module("numpy")
    except ImportError:
        # opencv-python-headless not available: skip silently.
        return image_obj

    img_array = numpy_module.array(image_obj)
    # Invert so text pixels are white (OpenCV moments expect white foreground).
    _, thresh = cv2.threshold(
        img_array, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
    )
    coords = numpy_module.column_stack(numpy_module.where(thresh > 0))
    if len(coords) < 10:
        return image_obj
    angle = cv2.minAreaRect(coords)[-1]
    # minAreaRect returns angle in (-90, 0]; skip rotation for tiny skew.
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return image_obj
    h, w = img_array.shape
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        img_array, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )
    pil_module = importlib.import_module("PIL.Image")
    return pil_module.fromarray(rotated)


def _adaptive_threshold_image(image_obj: Any) -> Any:
    """Apply adaptive binarization for faded/low-contrast scans.

    Only activates when mean luminance > 200 (bright faded scan) or < 60 (dark scan).
    Returns original grayscale image unchanged for normal contrast documents.
    """
    try:
        cv2 = importlib.import_module("cv2")
        numpy_module = importlib.import_module("numpy")
    except ImportError:
        return image_obj

    img_array = numpy_module.array(image_obj)
    mean_luminance = float(numpy_module.mean(img_array))
    if 60 <= mean_luminance <= 200:
        # Normal contrast: autocontrast sufficient, skip adaptive threshold.
        return image_obj

    binarized = cv2.adaptiveThreshold(
        img_array,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,
        C=10,
    )
    pil_module = importlib.import_module("PIL.Image")
    return pil_module.fromarray(binarized)


def _preprocess_image_for_ocr(image_obj: Any) -> Any:
    """Apply preprocessing for scanned documents before OCR.

    Pipeline (each step is optional and env-gated):
    1. Grayscale conversion
    2. Autocontrast (always on — preserves Thai tone mark strokes)
    3. Deskew via OpenCV (gated: OCR_DESKEW=1)
    4. Adaptive threshold for faded scans (gated: OCR_ADAPTIVE_THRESH=1, auto-skips normal docs)
    """
    image = image_obj.convert("L")
    image_ops = importlib.import_module("PIL.ImageOps")
    # MedianFilter(size=3) used to be applied here; it blurred small Thai tone
    # marks and vowels into the baseline, which hurt PaddleOCR recall on
    # scanned receipts. Plain autocontrast preserves stroke detail.
    image = image_ops.autocontrast(image, cutoff=2)
    if OCR_DESKEW:
        image = _deskew_image(image)
    if OCR_ADAPTIVE_THRESH:
        image = _adaptive_threshold_image(image)
    return image


def _looks_garbled(blocks: list[dict[str, Any]]) -> bool:
    if not blocks:
        return True

    text = "".join(str(block.get("text", "")) for block in blocks)
    if not text.strip():
        return True

    conf_values = [float(block.get("confidence", 0.0)) for block in blocks]
    avg_conf = sum(conf_values) / max(len(conf_values), 1)
    alnum_chars = re.findall(r"[A-Za-z0-9ก-๙]", text)
    alnum_ratio = len(alnum_chars) / max(len(text), 1)

    return avg_conf < _LOW_CONF_THRESHOLD or alnum_ratio < _MIN_ALNUM_RATIO


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
    """Return a neutral degraded block without leaking filename into extracted fields."""
    return [
        {
            "id": 0,
            "text": "",
            "confidence": 0.0,
            "bbox": [0, 0, 80, 24],
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
    preprocessed = _preprocess_image_for_ocr(image_obj)

    try:
        paddle_blocks = _extract_text_blocks_with_paddle(
            preprocessed, id_offset=id_offset
        )
        if paddle_blocks and not _looks_garbled(paddle_blocks):
            return paddle_blocks
        paddle_exc = RuntimeError("PaddleOCR output quality below threshold")
    except RuntimeError as exc:
        paddle_exc = exc

    try:
        return _extract_text_blocks_with_tesseract(preprocessed, id_offset=id_offset)
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

    config_args = ""
    if (
        LOCAL_TESSDATA_DIR.exists()
        and (LOCAL_TESSDATA_DIR / "tha.traineddata").exists()
    ):
        # Tesseract treats the value after --tessdata-dir as a literal path; do not
        # wrap it in quotes (pytesseract passes args directly, no shell parsing).
        config_args = f"--tessdata-dir {LOCAL_TESSDATA_DIR.as_posix()}"

    data = pytesseract.image_to_data(
        image_obj,
        lang="tha+eng",
        config=config_args,
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
        bitmap = page.render(scale=OCR_RENDER_SCALE)
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


def run_ocr(
    file_path: str,
    cache_root: Path | None = None,
    force_refresh: bool = False,
) -> dict[str, Any]:
    """Run OCR and persist `ocr_output.json` under cache/{sha256}/."""
    source = Path(file_path)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")

    sha = _sha256_file(source)
    root = cache_root or DEFAULT_CACHE_ROOT
    artifact_dir = root / sha
    artifact_path = artifact_dir / "ocr_output.json"

    if artifact_path.exists() and not force_refresh:
        cached = json.loads(artifact_path.read_text(encoding="utf-8"))
        if cached.get("schema_version") == OCR_SCHEMA_VERSION:
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
        if not (
            _is_tesseract_unavailable_error(exc) or _is_paddle_unavailable_error(exc)
        ):
            raise
        # Keep pipeline alive on developer machines without OCR engines.
        blocks = _fallback_blocks_when_ocr_unavailable(source)
        warnings.append(
            "OCR engines are unavailable (PaddleOCR/Tesseract). OCR ran in degraded mode without source text fallback."
        )

    # Weight by text length so single-char noise blocks don't dominate the
    # arithmetic mean and drag the score down on Thai receipts.
    total_chars = sum(len(str(block.get("text", ""))) for block in blocks) or 1
    avg_conf = round(
        sum(
            float(block["confidence"]) * len(str(block.get("text", "")))
            for block in blocks
        )
        / total_chars,
        4,
    )

    payload = {
        "schema_version": OCR_SCHEMA_VERSION,
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
