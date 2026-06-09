"""Probe PDF -> vision cascade across free → paid models for invoice_number.

Sends rendered PDF pages (PNG, up to MAX_PAGES) as ``image_url`` content to each
model in the cascade order. Captures each model's answer plus elapsed time, then
prints a per-doc table and a final aggregate hit-rate per model.

Usage:
    python scripts/probe_pdf_vision_cascade.py --n 10 --seed 42

Requires OpenRouter key in env (auto-loaded from D:\\key\\ALL-Openclaw-keys.txt
via secrets_loader if missing).
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
MAX_PAGES = 3  # cap pages per doc to keep cost predictable
RENDER_SCALE = 2.0

# Cascade order: cheap free → expensive paid
CASCADE: list[tuple[str, str]] = [
    ("free", "moonshotai/kimi-vl-a3b-thinking:free"),
    ("free", "meta-llama/llama-3.2-90b-vision-instruct:free"),
    ("free", "qwen/qwen2.5-vl-72b-instruct:free"),
    ("cheap", "google/gemini-2.5-flash-lite"),
    ("cheap", "openai/gpt-4o-mini"),
    ("paid", "anthropic/claude-sonnet-4"),
]

PROMPT = (
    "You are an accounting OCR assistant. Look at the attached invoice image(s) "
    "and return ONLY the invoice number (เลขที่ใบกำกับ / Invoice No.) as plain text. "
    "If you cannot find it with high confidence, return exactly the word UNKNOWN. "
    "Do not add any explanation, quotation marks, or extra characters."
)


@dataclass
class CallResult:
    model: str
    tier: str
    predicted: str
    raw: str
    error: str
    elapsed_s: float


def render_pdf_pages(pdf_path: Path, max_pages: int) -> list[bytes]:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    pages: list[bytes] = []
    n = min(len(pdf), max_pages)
    for i in range(n):
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


def parse_answer(raw: str) -> str:
    if not raw:
        return ""
    text = raw.strip().strip("`'\"")
    # If model returned JSON-ish, try to extract value.
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            for key in ("invoice_number", "invoice_no", "value", "answer"):
                if key in obj and obj[key]:
                    text = str(obj[key]).strip()
                    break
        except Exception:
            pass
    # Take first non-empty line.
    first = next((ln.strip() for ln in text.splitlines() if ln.strip()), text)
    if first.upper() == "UNKNOWN":
        return ""
    # Strip a trailing period.
    return first.rstrip(".")


def call_model(client, model: str, images: list[bytes]) -> tuple[str, str]:
    content: list[dict[str, Any]] = [{"type": "text", "text": PROMPT}]
    for img in images:
        b64 = base64.b64encode(img).decode("ascii")
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )
    rsp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        max_tokens=64,
        temperature=0.0,
    )
    raw = (rsp.choices[0].message.content or "").strip()
    return raw, parse_answer(raw)


def normalize(s: str) -> str:
    return re.sub(r"[\s\-/_.]+", "", (s or "").upper())


def is_match(predicted: str, expected: str) -> bool:
    if not predicted or not expected:
        return False
    return normalize(predicted) == normalize(expected)


def cascade_decision(results: list[CallResult], expected: str) -> tuple[str, str]:
    """Pick first model in order whose answer "passes" a simple validator.

    Validator here: non-empty + looks like an invoice number
    (mix of letters/digits or pure digits ≥ 4 chars, with limited noise).
    """
    pat = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-/\. ]{2,30}$")
    for r in results:
        if r.error or not r.predicted:
            continue
        if pat.match(r.predicted):
            return r.model, r.predicted
    return "", ""


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


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=10, help="number of docs to sample")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--doc-ids", type=str, default="", help="comma-separated doc_ids; overrides --n"
    )
    args = p.parse_args()

    eligible = load_eligible_docs()
    if args.doc_ids:
        wanted = set(s.strip() for s in args.doc_ids.split(",") if s.strip())
        docs = [d for d in eligible if d["doc_id"] in wanted]
    else:
        random.seed(args.seed)
        docs = random.sample(eligible, min(args.n, len(eligible)))
        docs.sort(key=lambda d: d["doc_id"])

    print(
        f"# Cascade probe — {len(docs)} docs, {len(CASCADE)} models, max {MAX_PAGES} pages/doc"
    )
    print(f"# Render scale: {RENDER_SCALE}x")
    print()

    client = build_client()

    per_model_hits: dict[str, int] = {m: 0 for _, m in CASCADE}
    per_model_calls: dict[str, int] = {m: 0 for _, m in CASCADE}
    per_model_total_s: dict[str, float] = {m: 0.0 for _, m in CASCADE}
    cascade_hits = 0
    cascade_winners: dict[str, int] = {m: 0 for _, m in CASCADE}
    cascade_winners["(none)"] = 0
    doc_rows: list[dict[str, Any]] = []

    for d in docs:
        pdf_path = DOC_ROOT / d["relative_path"]
        expected = d["invoice_number"]
        print(f"## {d['doc_id']}  expected={expected!r}  path={d['relative_path']}")
        try:
            images = render_pdf_pages(pdf_path, MAX_PAGES)
        except Exception as exc:  # noqa: BLE001
            print(f"  render error: {exc}\n")
            continue
        print(f"  pages_rendered={len(images)}")

        results: list[CallResult] = []
        for tier, model in CASCADE:
            t0 = time.time()
            try:
                raw, pred = call_model(client, model, images)
                err = ""
            except Exception as exc:  # noqa: BLE001
                raw, pred, err = "", "", f"{type(exc).__name__}: {str(exc)[:140]}"
            elapsed = time.time() - t0
            results.append(
                CallResult(
                    model=model,
                    tier=tier,
                    predicted=pred,
                    raw=raw,
                    error=err,
                    elapsed_s=elapsed,
                )
            )
            per_model_calls[model] += 1
            per_model_total_s[model] += elapsed
            hit = is_match(pred, expected)
            if hit:
                per_model_hits[model] += 1
            mark = "OK" if hit else ("ERR" if err else "X")
            print(
                f"  [{tier:5}] {model:50} {mark:3} pred={pred!r}  ({elapsed:.1f}s){'  err=' + err if err else ''}"
            )

        winner_model, winner_pred = cascade_decision(results, expected)
        winner_hit = is_match(winner_pred, expected)
        if winner_hit:
            cascade_hits += 1
        cascade_winners[winner_model or "(none)"] += 1
        print(
            f"  -> cascade winner: {winner_model or '(none)':50} pred={winner_pred!r}  match={'OK' if winner_hit else 'X'}"
        )
        print()

        doc_rows.append(
            {
                "doc_id": d["doc_id"],
                "expected": expected,
                "winner_model": winner_model,
                "winner_pred": winner_pred,
                "winner_match": winner_hit,
                "per_model": [
                    {
                        "model": r.model,
                        "pred": r.predicted,
                        "err": r.error,
                        "hit": is_match(r.predicted, expected),
                    }
                    for r in results
                ],
            }
        )

    # ---- Aggregate ----
    n_docs = len(doc_rows)
    print("=" * 80)
    print(f"# Aggregate over {n_docs} docs")
    print()
    print("## Per-model hit rate (correct invoice_number / calls)")
    print()
    print("| Model | Tier | Hits | Calls | Hit% | Avg latency (s) |")
    print("|-------|------|-----:|------:|-----:|----------------:|")
    for tier, model in CASCADE:
        calls = per_model_calls[model]
        hits = per_model_hits[model]
        avg = (per_model_total_s[model] / calls) if calls else 0.0
        pct = (hits / calls * 100.0) if calls else 0.0
        print(f"| `{model}` | {tier} | {hits} | {calls} | {pct:.1f}% | {avg:.2f} |")

    print()
    print(
        f"## Cascade overall: {cascade_hits}/{n_docs} = {(cascade_hits / n_docs * 100.0) if n_docs else 0:.1f}%"
    )
    print()
    print("## Cascade winners (which tier resolved each doc)")
    print()
    print("| Model | Times chosen |")
    print("|-------|-------------:|")
    for model in [m for _, m in CASCADE] + ["(none)"]:
        n = cascade_winners.get(model, 0)
        if n:
            print(f"| `{model}` | {n} |")

    # Save JSON for later analysis
    out_path = ROOT / "tmp" / "probe_pdf_cascade.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(doc_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print()
    print(f"# Raw per-doc data saved to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
