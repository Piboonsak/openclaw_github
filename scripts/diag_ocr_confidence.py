"""Diagnostic: measure OCR confidence distribution on a folder of PDFs.

Usage:
    python scripts/diag_ocr_confidence.py <folder> [--n 5] [--seed 42] [--no-cache]

Prints per-file and aggregate confidence stats. Used to validate OCR pipeline
changes against real scanned documents (see plan: Raise OCR confidence on
Comp_1 RRL scanned bills).
"""

from __future__ import annotations

import argparse
import random
import shutil
import statistics
import sys
from pathlib import Path

# Ensure stdout can emit Thai/Unicode when piped through `Tee-Object` etc.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.backend.ml.ocr import DEFAULT_CACHE_ROOT, _sha256_file, run_ocr  # noqa: E402


def _weighted_avg(blocks: list[dict]) -> float:
    total_chars = sum(len(str(b.get("text", ""))) for b in blocks) or 1
    weighted = sum(
        float(b.get("confidence", 0.0)) * len(str(b.get("text", ""))) for b in blocks
    )
    return weighted / total_chars


def _invalidate_cache(file_path: Path) -> None:
    sha = _sha256_file(file_path)
    cache_dir = DEFAULT_CACHE_ROOT / sha
    if cache_dir.exists():
        shutil.rmtree(cache_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, help="Folder containing PDFs to sample")
    parser.add_argument("--n", type=int, default=5, help="Number of files to sample")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Invalidate cached OCR output for sampled files before running",
    )
    args = parser.parse_args()

    folder: Path = args.folder
    if not folder.is_dir():
        print(f"ERROR: {folder} is not a directory", file=sys.stderr)
        return 2

    files = sorted(folder.glob("*.pdf"))
    if not files:
        print(f"ERROR: no PDFs found in {folder}", file=sys.stderr)
        return 2

    random.seed(args.seed)
    samples = random.sample(files, min(args.n, len(files)))

    per_file_avg = []
    per_file_weighted = []
    needs_review_count = 0

    for path in samples:
        if args.no_cache:
            _invalidate_cache(path)

        out = run_ocr(str(path))
        blocks = out.get("blocks", [])
        confs = [float(b["confidence"]) for b in blocks]
        avg = float(out.get("avg_confidence", 0.0))
        weighted = round(_weighted_avg(blocks), 4)
        low = [b for b in blocks if float(b["confidence"]) < 0.6]
        per_file_avg.append(avg)
        per_file_weighted.append(weighted)
        if out.get("needs_human_review"):
            needs_review_count += 1

        print("=" * 80)
        print(f"FILE: {path.name}")
        print(f"  cache_hit          : {out.get('cache_hit')}")
        print(f"  blocks             : {len(blocks)}")
        print(f"  avg_conf (current) : {avg:.4f}")
        print(f"  avg_conf (weighted): {weighted:.4f}")
        if confs:
            print(
                f"  conf min/med/max   : {min(confs):.3f} / "
                f"{statistics.median(confs):.3f} / {max(confs):.3f}"
            )
        print(
            f"  low(<0.6)          : {len(low)} "
            f"({100 * len(low) / max(len(blocks), 1):.1f}%)"
        )
        print(f"  needs_human_review : {out.get('needs_human_review')}")
        print(f"  warnings           : {out.get('warnings')}")

        if low:
            print("  bottom 5 conf blocks:")
            for b in sorted(low, key=lambda b: float(b["confidence"]))[:5]:
                print(f"    [{float(b['confidence']):.2f}] {str(b['text'])[:80]!r}")
        if blocks:
            print("  top 5 conf blocks:")
            for b in sorted(blocks, key=lambda b: -float(b["confidence"]))[:5]:
                print(f"    [{float(b['confidence']):.2f}] {str(b['text'])[:80]!r}")

    print("=" * 80)
    print("AGGREGATE")
    print(f"  files sampled              : {len(samples)}")
    print(
        f"  mean avg_conf (current)    : "
        f"{statistics.mean(per_file_avg):.4f}"
    )
    print(
        f"  mean avg_conf (weighted)   : "
        f"{statistics.mean(per_file_weighted):.4f}"
    )
    print(f"  needs_human_review count   : {needs_review_count}/{len(samples)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
