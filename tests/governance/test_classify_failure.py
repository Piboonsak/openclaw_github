"""Tests for `scripts/classify_failure.py`."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def test_classify_failure_detects_ocr_dependency_error():
    module = importlib.import_module("classify_failure")
    payload = module.classify_failure(
        "ModuleNotFoundError: No module named 'pytesseract'",
        ["src/ocr/processor.py", "tests/test_ocr.py"],
    )

    assert payload["stage"] == "ocr"
    assert payload["error_type"] == "dependency"
    assert payload["suggested_scope"] == ["src/ocr/processor.py", "tests/test_ocr.py"]
    assert len(payload["fingerprint"]) == 16


def test_classify_failure_fingerprint_is_deterministic():
    module = importlib.import_module("classify_failure")
    log = "AssertionError: expected 2 got 3"
    changed = ["src/validation/rules.py"]

    first = module.classify_failure(log, changed)
    second = module.classify_failure(log, changed)

    assert first["stage"] == "validation"
    assert first["error_type"] == "test_assertion"
    assert first["fingerprint"] == second["fingerprint"]
