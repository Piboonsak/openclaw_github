"""Classify failed runs into a narrow remediation scope.

This utility supports PP-13 (wrong-fix loop prevention) by converting raw
failure logs into a compact JSON classification payload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

PATTERN_MAP = [
    (re.compile(r"\b(hmac|signature|jwt|token)\b", re.IGNORECASE), "security"),
    (re.compile(r"\b(alembic|migration|schema)\b", re.IGNORECASE), "db_migration"),
    (re.compile(r"\b(module not found|modulenotfounderror|importerror)\b", re.IGNORECASE), "dependency"),
    (re.compile(r"\b(assertionerror|expected .* got)\b", re.IGNORECASE), "test_assertion"),
    (re.compile(r"\b(timeout|timed out)\b", re.IGNORECASE), "timeout"),
    (re.compile(r"\b(permission denied|access denied)\b", re.IGNORECASE), "permissions"),
]


def _stage_from_files(changed_files: list[str]) -> str:
    joined = "\n".join(changed_files).lower()
    if "src/ocr/" in joined:
        return "ocr"
    if "src/extraction/" in joined:
        return "extraction"
    if "src/validation/" in joined:
        return "validation"
    if "scripts/" in joined:
        return "governance"
    return "unknown"


def _error_type(log_text: str) -> str:
    for pattern, label in PATTERN_MAP:
        if pattern.search(log_text):
            return label
    return "generic_failure"


def _top_trace_line(log_text: str) -> str:
    for line in log_text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        if "error" in clean.lower() or "failed" in clean.lower() or "exception" in clean.lower():
            return clean
    return "no_error_line_detected"


def _fingerprint(stage: str, error_type: str, top_line: str) -> str:
    basis = f"{stage}|{error_type}|{top_line}".encode("utf-8", errors="ignore")
    return hashlib.sha256(basis).hexdigest()[:16]


def classify_failure(log_text: str, changed_files: list[str]) -> dict[str, object]:
    stage = _stage_from_files(changed_files)
    error_type = _error_type(log_text)
    top_line = _top_trace_line(log_text)
    fingerprint = _fingerprint(stage, error_type, top_line)

    suggested_scope = list(dict.fromkeys(changed_files))
    if not suggested_scope:
        if stage == "ocr":
            suggested_scope = ["src/ocr/**", "tests/test_ocr.py"]
        elif stage == "extraction":
            suggested_scope = ["src/extraction/**", "tests/test_extraction.py"]
        elif stage == "validation":
            suggested_scope = ["src/validation/**", "tests/test_validation.py"]

    return {
        "stage": stage,
        "error_type": error_type,
        "top_trace_line": top_line,
        "fingerprint": fingerprint,
        "suggested_scope": suggested_scope,
    }


def _read_log_text(args: argparse.Namespace) -> str:
    if args.input:
        return Path(args.input).read_text(encoding="utf-8", errors="ignore")
    if args.text:
        return args.text
    return sys.stdin.read()


def _parse_changed_files(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify run failures and narrow fix scope")
    parser.add_argument("--input", help="Path to log file")
    parser.add_argument("--text", help="Raw log text")
    parser.add_argument(
        "--changed-files",
        default="",
        help="Comma-separated changed files used as scope hints",
    )
    parser.add_argument("--out", help="Optional output JSON path")
    args = parser.parse_args(argv)

    log_text = _read_log_text(args)
    if not log_text.strip():
        print("ERROR: empty log input", file=sys.stderr)
        return 2

    payload = classify_failure(log_text, _parse_changed_files(args.changed_files))
    text = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.out:
        path = Path(args.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")

    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
