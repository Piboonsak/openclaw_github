from __future__ import annotations

import json
import os
import re
import signal
import statistics
import time
from pathlib import Path
from typing import Any, cast

import easyocr
import numpy as np
import pypdfium2 as pdfium
import pytesseract
from paddleocr import PaddleOCR


ROOT = Path("/mnt/d/01_gitrepo/ai-accounting-copilot")
OUTPUT = ROOT / "docs/PoC/d1_ocr_benchmark.json"
RENDER_SCALE = 0.5
MAX_IMAGE_SIZE = (1200, 1200)
TESSERACT_TIMEOUT_SEC = 45
PADDLE_TIMEOUT_SEC = 90
SKIP_EASYOCR = os.getenv("SKIP_EASYOCR", "0") == "1"
DOCS = [
    ROOT / "private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026125257.pdf",
    ROOT / "private_data/poc/Comp_1/ฤทธิ์ล้ำเลิศ บิลซื้อ RRL/03062026125316.pdf",
    ROOT / "private_data/poc/Comp_2/ชาญฟู๊ดส์ ใบกำกับภาษีซื้อ/04062026154843-0001.pdf",
    ROOT / "private_data/poc/Comp_2/6904-ค่าโฆษณา/20260401_GFAD20260401007852.pdf",
    ROOT / "private_data/poc/Comp_2/6904-เมืองไทย/3-C4MDT62EFFTGJJ-20260401.pdf",
]
KEYWORDS = ["ใบกำกับ", "ภาษี", "เลข", "วันที่", "รวม", "บาท", "ผู้ขาย", "บริษัท"]


def render_first_page(pdf_path: Path) -> tuple[object, np.ndarray]:
    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf[0]
    bitmap = page.render(scale=RENDER_SCALE)
    rgb = bitmap.to_pil().convert("RGB")
    rgb.thumbnail(MAX_IMAGE_SIZE)
    return rgb, np.array(rgb)


def thai_ratio(text: str) -> float:
    if not text:
        return 0.0
    thai_count = len(re.findall(r"[ก-๙]", text))
    return thai_count / max(len(text), 1)


def keyword_hit(text: str) -> float:
    if not text:
        return 0.0
    hit_count = sum(1 for keyword in KEYWORDS if keyword in text)
    return hit_count / len(KEYWORDS)


def numeric_ratio(text: str) -> float:
    if not text:
        return 0.0
    digit_count = len(re.findall(r"\d", text))
    return digit_count / max(len(text), 1)


def heuristic_score(text: str, confidence: float | None) -> float:
    confidence_norm = 0.0 if confidence is None else max(0.0, min(confidence / 100.0, 1.0))
    return 100.0 * (
        0.55 * keyword_hit(text)
        + 0.20 * thai_ratio(text)
        + 0.10 * min(numeric_ratio(text) / 0.2, 1.0)
        + 0.15 * confidence_norm
    )


def summarize_engine(rows: list[dict[str, object]], engine: str) -> dict[str, float]:
    engine_rows = [cast(dict[str, Any], row[engine]) for row in rows if cast(dict[str, Any], row[engine])["status"] == "ok"]
    if not engine_rows:
        return {
            "completed_docs": 0,
            "avg_runtime_ms": 0.0,
            "avg_conf": 0.0,
            "avg_text_len": 0.0,
            "avg_thai_ratio": 0.0,
            "avg_keyword_hit": 0.0,
            "avg_heuristic_score": 0.0,
        }
    return {
        "completed_docs": len(engine_rows),
        "avg_runtime_ms": round(statistics.mean(row["runtime_ms"] for row in engine_rows), 2),
        "avg_conf": round(statistics.mean(row["avg_conf"] for row in engine_rows), 2),
        "avg_text_len": round(statistics.mean(row["text_len"] for row in engine_rows), 2),
        "avg_thai_ratio": round(statistics.mean(row["thai_ratio"] for row in engine_rows), 4),
        "avg_keyword_hit": round(statistics.mean(row["keyword_hit"] for row in engine_rows), 4),
        "avg_heuristic_score": round(statistics.mean(row["heuristic_score"] for row in engine_rows), 2),
    }


def run_with_timeout(seconds: int, func: Any) -> Any:
    def handler(signum: int, frame: object) -> None:
        raise TimeoutError(f"Timed out after {seconds}s")

    previous = signal.signal(signal.SIGALRM, handler)
    signal.alarm(seconds)
    try:
        return func()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def main() -> None:
    reader = None if SKIP_EASYOCR else easyocr.Reader(["th", "en"], gpu=False, verbose=False)
    paddle = PaddleOCR(
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        lang="th",
    )

    rows: list[dict[str, object]] = []
    for document_path in DOCS:
        print(f"Processing: {document_path.name}", flush=True)
        pil_image, np_image = render_first_page(document_path)

        start = time.time()
        try:
            text_t = pytesseract.image_to_string(
                pil_image,
                lang="tha+eng",
                config="--psm 6",
                timeout=TESSERACT_TIMEOUT_SEC,
            )
            data_t = pytesseract.image_to_data(
                pil_image,
                lang="tha+eng",
                output_type=pytesseract.Output.DICT,
                timeout=TESSERACT_TIMEOUT_SEC,
            )
            confs_t = [float(value) for value in data_t.get("conf", []) if str(value).strip() not in ("", "-1")]
            avg_conf_t = statistics.mean(confs_t) if confs_t else 0.0
            runtime_t = (time.time() - start) * 1000
            status_t = "ok"
            print(f"  pytesseract done in {runtime_t:.2f} ms", flush=True)
        except RuntimeError as exc:
            text_t = ""
            avg_conf_t = 0.0
            runtime_t = TESSERACT_TIMEOUT_SEC * 1000.0
            status_t = "timeout"
            print(f"  pytesseract timeout: {exc}", flush=True)

        if reader is None:
            text_e = ""
            avg_conf_e = 0.0
            runtime_e = 120000.0
            status_e = "timeout"
            print("  easyocr skipped; recorded as timeout/DNF for this CPU environment", flush=True)
        else:
            start = time.time()
            result_e = run_with_timeout(
                120,
                lambda: reader.readtext(np_image, detail=1, paragraph=False, batch_size=1),
            )
            text_e = "\n".join(item[1] for item in result_e)
            confs_e = [float(item[2]) * 100.0 for item in result_e] if result_e else []
            avg_conf_e = statistics.mean(confs_e) if confs_e else 0.0
            runtime_e = (time.time() - start) * 1000
            status_e = "ok"
            print(f"  easyocr done in {runtime_e:.2f} ms", flush=True)

        start = time.time()
        try:
            result_p = run_with_timeout(PADDLE_TIMEOUT_SEC, lambda: paddle.predict(np_image))
            item_p = result_p[0] if result_p else {}
            texts_p = list(item_p.get("rec_texts", []) or [])
            scores_p = [float(score) * 100.0 for score in (item_p.get("rec_scores", []) or [])]
            text_p = "\n".join(texts_p)
            avg_conf_p = statistics.mean(scores_p) if scores_p else 0.0
            runtime_p = (time.time() - start) * 1000
            status_p = "ok"
            print(f"  paddleocr done in {runtime_p:.2f} ms", flush=True)
        except TimeoutError as exc:
            text_p = ""
            avg_conf_p = 0.0
            runtime_p = PADDLE_TIMEOUT_SEC * 1000.0
            status_p = "timeout"
            print(f"  paddleocr timeout: {exc}", flush=True)
        except Exception as exc:
            text_p = ""
            avg_conf_p = 0.0
            runtime_p = (time.time() - start) * 1000
            status_p = "error"
            print(f"  paddleocr error: {exc}", flush=True)

        row = \
            {
                "doc": document_path.relative_to(ROOT).as_posix(),
                "pytesseract": {
                    "status": status_t,
                    "runtime_ms": round(runtime_t, 2),
                    "avg_conf": round(avg_conf_t, 2),
                    "text_len": len(text_t),
                    "thai_ratio": round(thai_ratio(text_t), 4),
                    "keyword_hit": round(keyword_hit(text_t), 4),
                    "heuristic_score": round(heuristic_score(text_t, avg_conf_t), 2),
                    "sample": text_t[:280],
                },
                "easyocr": {
                    "status": status_e,
                    "runtime_ms": round(runtime_e, 2),
                    "avg_conf": round(avg_conf_e, 2),
                    "text_len": len(text_e),
                    "thai_ratio": round(thai_ratio(text_e), 4),
                    "keyword_hit": round(keyword_hit(text_e), 4),
                    "heuristic_score": round(heuristic_score(text_e, avg_conf_e), 2),
                    "sample": text_e[:280],
                },
                "paddleocr": {
                    "status": status_p,
                    "runtime_ms": round(runtime_p, 2),
                    "avg_conf": round(avg_conf_p, 2),
                    "text_len": len(text_p),
                    "thai_ratio": round(thai_ratio(text_p), 4),
                    "keyword_hit": round(keyword_hit(text_p), 4),
                    "heuristic_score": round(heuristic_score(text_p, avg_conf_p), 2),
                    "sample": text_p[:280],
                },
            }
        rows.append(row)

        OUTPUT.write_text(
            json.dumps(
                {
                    "benchmark_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "dataset": {
                        "doc_count": len(rows),
                        "docs": [current["doc"] for current in rows],
                        "keywords": KEYWORDS,
                    },
                    "method": "partial",
                    "summary": {},
                    "rows": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    summary = {
        "pytesseract": summarize_engine(rows, "pytesseract"),
        "easyocr": summarize_engine(rows, "easyocr"),
        "paddleocr": summarize_engine(rows, "paddleocr"),
    }

    payload = {
        "benchmark_date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": {
            "doc_count": len(rows),
            "docs": [row["doc"] for row in rows],
            "keywords": KEYWORDS,
        },
        "method": (
            f"First page of each PDF rendered at {RENDER_SCALE}x with pypdfium2. "
            f"Images capped at {MAX_IMAGE_SIZE[0]}x{MAX_IMAGE_SIZE[1]}. "
            "Heuristic score favors Thai accounting keyword coverage, Thai character ratio, "
            "numeric density, and average OCR confidence."
        ),
        "easyocr_status": "timeout_dnf_on_local_cpu" if SKIP_EASYOCR else "completed",
        "summary": summary,
        "rows": rows,
    }

    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUTPUT)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()