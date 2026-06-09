"""Probe: LLM-transcribed text vs Tesseract text → text-only models extract invoice_number.

Isolates "Tesseract garbage" vs "extraction task ยาก" by feeding two different text
sources into each candidate text-only model and measuring invoice_number hit rate.

Pipeline per doc:
  1. Render page 1 (PNG, scale=2.0) via pypdfium2
  2. Transcribe via vision LLM (default: google/gemini-2.5-flash-lite) → cache to
     tmp/transcriptions/{doc_id}.txt (skip re-call if cached)
  3. Run Tesseract on the same rendered image → tmp/transcriptions/{doc_id}.tesseract.txt
  4. For each candidate text model, run two extraction calls:
       (a) input = transcribed text
       (b) input = Tesseract text
  5. Save raw per-doc per-model results to tmp/probe_text_extraction.json
  6. Print aggregated table — per (model, input_source) hit rate

Usage:
    python scripts/probe_text_extraction_from_clean_ocr.py \
        --doc-ids comp1-0003,comp1-0007,comp1-0008,comp1-0009,comp1-0010,\
comp1-0016,comp1-0017,comp1-0019,comp1-0029,comp1-0041

Cost: ~$0.05 total (10 vision transcriptions + ~80 free/cheap text calls).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.backend.services.secrets_loader import load_llm_keys  # noqa: E402

EXPECTATIONS_PATH = (
    ROOT / "private_data" / "poc" / "Comp_1" / "expectations.filled.jsonl"
)
DOC_ROOT = ROOT / "private_data" / "poc" / "Comp_1"
TRANSCRIPTION_DIR = ROOT / "tmp" / "transcriptions"
OUT_JSON = ROOT / "tmp" / "probe_text_extraction.json"

TRANSCRIBE_MODEL = "google/gemini-2.5-flash-lite"
TRANSCRIBE_MAX_PAGES = 1  # page 1 holds invoice_number for the sample docs
RENDER_SCALE = 2.0

# Text-only candidates (tier = "free" → :free suffix; "cheap" = paid but tiny cost).
TEXT_CANDIDATES: list[tuple[str, str]] = [
    ("free", "deepseek/deepseek-chat-v3-0324:free"),
    ("free", "meta-llama/llama-3.3-70b-instruct:free"),
    ("free", "qwen/qwen-2.5-72b-instruct:free"),
    ("free", "google/gemma-2-9b-it:free"),
    ("free", "mistralai/mistral-7b-instruct:free"),
    ("cheap", "google/gemini-2.5-flash-lite"),  # upper bound for "clean text" path
]

TRANSCRIBE_PROMPT = (
    "You are an OCR engine. Transcribe ALL text visible in the attached Thai/English "
    "invoice image VERBATIM. Preserve EVERY digit, document ID, date, amount, and "
    "tax-id EXACTLY as printed (do not correct, do not interpret, do not summarize). "
    "Output only the raw transcription as plain text, in roughly top-to-bottom reading "
    "order. No commentary, no markdown, no JSON."
)

EXTRACTION_PROMPT_TEMPLATE = (
    "You are an accounting field extractor. Given the OCR text of a Thai invoice "
    "below, return ONLY the invoice number (เลขที่ใบกำกับ / Invoice No. / Tax Invoice No.) "
    "as plain text. If you cannot find it with high confidence, return exactly the "
    "word UNKNOWN. Do not add explanation, quotation marks, or extra characters.\n\n"
    "=== OCR TEXT ===\n{text}\n=== END ==="
)


@dataclass
class CallResult:
    model: str
    tier: str
    input_source: str  # "transcribed" | "tesseract"
    predicted: str
    raw: str
    error: str
    elapsed_s: float


# ─────────────────────────── helpers ────────────────────────────


def render_page1(pdf_path: Path) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    page = pdf[0]
    image = page.render(scale=RENDER_SCALE).to_pil()
    buf = io.BytesIO()
    image.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def render_all_pages(pdf_path: Path, max_pages: int) -> list[bytes]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    pages: list[bytes] = []
    for i in range(min(len(pdf), max_pages)):
        page = pdf[i]
        image = page.render(scale=RENDER_SCALE).to_pil()
        buf = io.BytesIO()
        image.save(buf, format="PNG", optimize=True)
        pages.append(buf.getvalue())
    return pages


def build_client():
    from openai import OpenAI

    load_llm_keys()
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY missing")
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        default_headers={
            "HTTP-Referer": "https://github.com/Piboonsak/ai-accounting-copilot",
            "X-Title": "ai-accounting-copilot probe",
        },
    )


def transcribe_via_vision(client, images: list[bytes]) -> tuple[str, str]:
    """Returns (raw, transcription_text). Raises on API error."""
    content: list[dict[str, Any]] = [{"type": "text", "text": TRANSCRIBE_PROMPT}]
    for img in images:
        b64 = base64.b64encode(img).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )
    rsp = client.chat.completions.create(
        model=TRANSCRIBE_MODEL,
        messages=[{"role": "user", "content": content}],
        max_tokens=2048,
        temperature=0.0,
    )
    raw = (rsp.choices[0].message.content or "").strip()
    return raw, raw


def run_tesseract_text(image_bytes: bytes) -> str:
    # Match orchestrator's tessdata path handling.
    import shutil
    from io import BytesIO

    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore

    if shutil.which("tesseract") is None:
        windows_default = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
        if windows_default.exists():
            pytesseract.pytesseract.tesseract_cmd = str(windows_default)

    local_tessdata = ROOT / "config" / "tessdata"
    config_args = ""
    if local_tessdata.exists() and (local_tessdata / "tha.traineddata").exists():
        config_args = f"--tessdata-dir {local_tessdata.as_posix()}"

    img = Image.open(BytesIO(image_bytes))
    return pytesseract.image_to_string(img, lang="tha+eng", config=config_args)


def extract_via_text_model(client, model: str, text: str) -> tuple[str, str]:
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(text=text[:8000])
    rsp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=64,
        temperature=0.0,
    )
    raw = (rsp.choices[0].message.content or "").strip()
    return raw, parse_answer(raw)


def parse_answer(raw: str) -> str:
    if not raw:
        return ""
    text = raw.strip().strip("`'\"")
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            for key in ("invoice_number", "invoice_no", "value", "answer"):
                if key in obj and obj[key]:
                    text = str(obj[key]).strip()
                    break
        except Exception:
            pass
    # Some models add prefixes like "Invoice Number: XYZ"
    m = re.search(
        r"(?i)(?:invoice\s*(?:number|no\.?|#)\s*[:\-]\s*)?([A-Za-z0-9][A-Za-z0-9/\-_.]{2,40})",
        text,
    )
    if m:
        cand = m.group(1).strip().rstrip(".,;")
        if cand.upper() == "UNKNOWN":
            return ""
        return cand
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), text)
    if first.upper() == "UNKNOWN":
        return ""
    return first.rstrip(".")


def normalize(s: str) -> str:
    return re.sub(r"[\s\-/_.]+", "", (s or "").upper())


def is_match(predicted: str, expected: str) -> bool:
    if not predicted or not expected:
        return False
    return normalize(predicted) == normalize(expected)


def load_eligible_docs() -> list[dict[str, Any]]:
    rows = [
        json.loads(l)
        for l in EXPECTATIONS_PATH.read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    return [
        r
        for r in rows
        if r.get("include_in_training")
        and r.get("invoice_number")
        and r.get("doc_type") == "Invoice"
    ]


def get_or_create_transcription(client, doc_id: str, pdf_path: Path) -> str:
    cache_path = TRANSCRIPTION_DIR / f"{doc_id}.transcribed.txt"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    images = render_all_pages(pdf_path, TRANSCRIBE_MAX_PAGES)
    _raw, text = transcribe_via_vision(client, images)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text


def get_or_create_tesseract(doc_id: str, pdf_path: Path) -> str:
    cache_path = TRANSCRIPTION_DIR / f"{doc_id}.tesseract.txt"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")
    image = render_page1(pdf_path)
    text = run_tesseract_text(image)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(text, encoding="utf-8")
    return text


# ─────────────────────────── main ────────────────────────────


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--doc-ids", type=str, default="")
    p.add_argument(
        "--skip-tesseract",
        action="store_true",
        help="skip Tesseract input (use only transcribed text)",
    )
    args = p.parse_args()

    eligible = load_eligible_docs()
    if args.doc_ids:
        wanted = set(s.strip() for s in args.doc_ids.split(",") if s.strip())
        docs = [d for d in eligible if d["doc_id"] in wanted]
        # Preserve user-specified order.
        order = {d: i for i, d in enumerate(s.strip() for s in args.doc_ids.split(","))}
        docs.sort(key=lambda d: order.get(d["doc_id"], 999))
    else:
        random.seed(args.seed)
        docs = random.sample(eligible, min(args.n, len(eligible)))
        docs.sort(key=lambda d: d["doc_id"])

    print(
        f"# Text-extraction probe — {len(docs)} docs, "
        f"{len(TEXT_CANDIDATES)} text models, "
        f"2 input sources (transcribed, tesseract)"
    )
    print(
        f"# Transcriber: {TRANSCRIBE_MODEL} (page 1 only, scale={RENDER_SCALE}x, cached)"
    )
    print()

    client = build_client()

    sources = ["transcribed"] if args.skip_tesseract else ["transcribed", "tesseract"]
    per_combo_hits: dict[str, int] = {}
    per_combo_calls: dict[str, int] = {}
    per_combo_total_s: dict[str, float] = {}
    doc_rows: list[dict[str, Any]] = []

    for d in docs:
        pdf_path = DOC_ROOT / d["relative_path"]
        expected = d["invoice_number"]
        print(f"## {d['doc_id']}  expected={expected!r}  path={d['relative_path']}")

        # Step 1: get transcription (cached)
        try:
            transcribed = get_or_create_transcription(client, d["doc_id"], pdf_path)
            print(f"  transcribed: {len(transcribed)} chars")
        except Exception as exc:  # noqa: BLE001
            print(f"  TRANSCRIBE ERROR: {exc}\n")
            continue

        # Step 2: get Tesseract output (cached)
        tesseract_text = ""
        if "tesseract" in sources:
            try:
                tesseract_text = get_or_create_tesseract(d["doc_id"], pdf_path)
                print(f"  tesseract:   {len(tesseract_text)} chars")
            except Exception as exc:  # noqa: BLE001
                print(f"  TESSERACT ERROR: {exc}")
                tesseract_text = ""

        source_to_text = {
            "transcribed": transcribed,
            "tesseract": tesseract_text,
        }

        # Step 3: run each (model, source) combo
        results: list[CallResult] = []
        for tier, model in TEXT_CANDIDATES:
            for src in sources:
                text = source_to_text.get(src, "")
                if not text.strip():
                    results.append(
                        CallResult(
                            model=model,
                            tier=tier,
                            input_source=src,
                            predicted="",
                            raw="",
                            error="empty_text",
                            elapsed_s=0.0,
                        )
                    )
                    continue
                combo_key = f"{model}|{src}"
                per_combo_calls[combo_key] = per_combo_calls.get(combo_key, 0) + 1
                t0 = time.time()
                try:
                    raw, pred = extract_via_text_model(client, model, text)
                    err = ""
                except Exception as exc:  # noqa: BLE001
                    raw, pred = "", ""
                    err_msg = str(exc)[:140]
                    if "404" in err_msg:
                        err = f"404: {err_msg}"
                    elif "429" in err_msg or "rate" in err_msg.lower():
                        err = f"RATE_LIMIT: {err_msg}"
                    else:
                        err = f"{type(exc).__name__}: {err_msg}"
                elapsed = time.time() - t0
                per_combo_total_s[combo_key] = (
                    per_combo_total_s.get(combo_key, 0.0) + elapsed
                )
                hit = is_match(pred, expected)
                if hit:
                    per_combo_hits[combo_key] = per_combo_hits.get(combo_key, 0) + 1
                mark = "OK" if hit else ("ERR" if err else "X")
                print(
                    f"  [{tier:5}] {src:11} {model:55} {mark:3} "
                    f"pred={pred!r} ({elapsed:.1f}s)" + (f"  err={err}" if err else "")
                )
                results.append(
                    CallResult(
                        model=model,
                        tier=tier,
                        input_source=src,
                        predicted=pred,
                        raw=raw,
                        error=err,
                        elapsed_s=elapsed,
                    )
                )

        print()
        doc_rows.append(
            {
                "doc_id": d["doc_id"],
                "expected": expected,
                "transcribed_chars": len(transcribed),
                "tesseract_chars": len(tesseract_text),
                "per_model": [
                    {
                        "model": r.model,
                        "tier": r.tier,
                        "source": r.input_source,
                        "pred": r.predicted,
                        "err": r.error,
                        "hit": is_match(r.predicted, expected),
                        "elapsed_s": round(r.elapsed_s, 2),
                    }
                    for r in results
                ],
            }
        )

    # ── Aggregate table ──
    n_docs = len(doc_rows)
    print("=" * 90)
    print(f"# Aggregate over {n_docs} docs — per (model, input_source) hit rate")
    print()
    print("| Model | Tier | Input | Hits | Calls | Hit% | Avg latency (s) |")
    print("|-------|------|-------|-----:|------:|-----:|----------------:|")
    for tier, model in TEXT_CANDIDATES:
        for src in sources:
            key = f"{model}|{src}"
            calls = per_combo_calls.get(key, 0)
            hits = per_combo_hits.get(key, 0)
            total_s = per_combo_total_s.get(key, 0.0)
            avg = (total_s / calls) if calls else 0.0
            pct = (hits / calls * 100.0) if calls else 0.0
            print(
                f"| `{model}` | {tier} | {src} | {hits} | {calls} | {pct:.1f}% | {avg:.2f} |"
            )

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(doc_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print()
    print(f"# Raw per-doc data saved to {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
