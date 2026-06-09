"""Pretty-print the raw per-doc x per-model cascade probe results."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tmp" / "probe_pdf_cascade.json"

SHORT = {
    "moonshotai/kimi-vl-a3b-thinking:free": "Kimi-VL (free)",
    "meta-llama/llama-3.2-90b-vision-instruct:free": "Llama3.2-90b (free)",
    "qwen/qwen2.5-vl-72b-instruct:free": "Qwen2.5-VL (free)",
    "google/gemini-2.5-flash-lite": "Gemini-2.5-flash-lite",
    "openai/gpt-4o-mini": "GPT-4o-mini",
    "anthropic/claude-sonnet-4": "Claude-Sonnet-4",
}


def norm(s: str) -> str:
    return re.sub(r"[\s\-/_.]+", "", (s or "").upper())


def cell(pm: dict, expected: str) -> str:
    if pm["err"]:
        return "404" if "404" in pm["err"] else "ERR"
    pred = pm["pred"]
    if not pred:
        return "(empty)"
    ok = norm(pred) == norm(expected)
    return f"`{pred}` {'✓' if ok else '✗'}"


def main() -> int:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    models = [r["model"] for r in data[0]["per_model"]]
    headers = ["Doc", "Expected"] + [SHORT[m] for m in models]

    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for row in data:
        cells = [row["doc_id"], f"`{row['expected']}`"]
        for pm in row["per_model"]:
            cells.append(cell(pm, row["expected"]))
        print("| " + " | ".join(cells) + " |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
