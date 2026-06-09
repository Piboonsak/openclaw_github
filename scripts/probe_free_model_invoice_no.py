"""Single-field probe: ask each model for invoice_number only.

Sends one document to each model via OpenRouter in two modes:
  1. OCR text only (matches current Stage C pipeline)
  2. Page-1 image as base64 PNG (vision path)

Run:
    python scripts/probe_free_model_invoice_no.py --doc-id comp1-0002
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.settings import settings  # noqa: E402
from src.backend.ml.field_extractor import run_extraction  # noqa: E402
from src.backend.ml.ocr import run_ocr  # noqa: E402
from src.backend.services.secrets_loader import load_llm_keys  # noqa: E402

BASE = Path("private_data/poc/Comp_1")
EXPECT = BASE / "expectations.filled.jsonl"

MODELS: list[tuple[str, str]] = [
    ("free", "google/gemini-2.5-flash-lite"),
    ("free", "openai/gpt-4.1-nano"),
    ("paid", "anthropic/claude-3.5-haiku"),
    ("paid", "anthropic/claude-sonnet-4"),
]

SYSTEM_PROMPT = (
    "You are an expert Thai accounting document field extractor. "
    "Return ONLY a JSON object with a single key 'invoice_number'. "
    "No explanation. Use the exact characters as they appear in the document."
)


def load_doc(doc_id: str) -> dict:
    for line in EXPECT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("doc_id") == doc_id:
            return row
    raise SystemExit(f"doc_id not found in expectations: {doc_id}")


def render_page1_png(pdf_path: Path) -> bytes:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    if len(pdf) == 0:
        raise SystemExit(f"PDF has no pages: {pdf_path}")
    page = pdf[0]
    image = page.render(scale=2.5).to_pil()
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def build_openrouter_client():
    load_llm_keys()
    api_key = os.environ.get("OPENROUTER_API_KEY", "") or settings.OPENROUTER_API_KEY
    if not api_key:
        raise SystemExit("OPENROUTER_API_KEY not set")
    from openai import OpenAI

    return OpenAI(
        api_key=api_key,
        base_url=settings.OPENROUTER_BASE_URL,
        default_headers={
            "HTTP-Referer": "https://github.com/Piboonsak/ai-accounting-copilot",
            "X-Title": "AI Pre-Accounting Copilot",
        },
    )


def call_text(client, model: str, ocr_text: str) -> tuple[str, str]:
    user = (
        "=== RAW OCR TEXT ===\n"
        + ocr_text[:6000]
        + '\n\nReturn ONLY: {"invoice_number": "..."}'
    )
    try:
        rsp = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ],
        )
        return rsp.choices[0].message.content or "", ""
    except Exception as exc:
        return "", f"{type(exc).__name__}: {exc}"


def call_image(client, model: str, png_bytes: bytes) -> tuple[str, str]:
    b64 = base64.b64encode(png_bytes).decode("ascii")
    user_block = [
        {
            "type": "text",
            "text": 'Read the invoice number on this document. Return ONLY: {"invoice_number": "..."}',
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        },
    ]
    try:
        rsp = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_block},
            ],
        )
        return rsp.choices[0].message.content or "", ""
    except Exception as exc:
        return "", f"{type(exc).__name__}: {exc}"


def parse_invoice_number(text: str) -> str:
    if not text:
        return ""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 2:
            cleaned = parts[1]
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        obj = json.loads(cleaned)
        return str(obj.get("invoice_number") or "").strip()
    except json.JSONDecodeError:
        return cleaned[:80]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--doc-id", default="comp1-0002")
    args = parser.parse_args()

    row = load_doc(args.doc_id)
    pdf_path = BASE / row["relative_path"]
    expected = str(row.get("invoice_number") or "")
    print(f"# Doc: {args.doc_id}")
    print(f"# Path: {pdf_path}")
    print(f"# Expected invoice_number: {expected}\n")

    ocr_output = run_ocr(str(pdf_path))
    extraction = run_extraction(ocr_output)
    ocr_text = str(extraction.get("fields", {}).get("source_text") or "")
    print(f"# OCR text length: {len(ocr_text)} chars")
    print(
        f"# Rule-based predicted: {extraction.get('fields', {}).get('invoice_number', '')!r}\n"
    )

    png = render_page1_png(pdf_path)
    client = build_openrouter_client()

    rows: list[dict] = []
    for tier, model in MODELS:
        for mode in ("ocr_text", "image"):
            t0 = time.time()
            if mode == "ocr_text":
                raw, err = call_text(client, model, ocr_text)
            else:
                raw, err = call_image(client, model, png)
            elapsed = time.time() - t0
            pred = parse_invoice_number(raw) if not err else ""
            match = "OK" if pred == expected else "X"
            rows.append(
                {
                    "tier": tier,
                    "model": model,
                    "mode": mode,
                    "predicted": pred or err or "(empty)",
                    "match": match,
                    "elapsed_s": round(elapsed, 2),
                }
            )
            print(
                f"[{tier}|{mode}] {model}: pred={pred!r} err={err!r} ({elapsed:.2f}s)"
            )

    print("\n## Summary table\n")
    print("| Tier | Model | Input | Predicted invoice_number | Match | Elapsed (s) |")
    print("|------|-------|-------|--------------------------|:-----:|------------:|")
    for r in rows:
        print(
            f"| {r['tier']} | `{r['model']}` | {r['mode']} | `{r['predicted']}` | {r['match']} | {r['elapsed_s']} |"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
