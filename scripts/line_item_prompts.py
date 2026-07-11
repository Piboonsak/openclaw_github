"""Backward-compat shim for the line-item prompt helpers.

The canonical implementation now lives at `src/backend/ml/line_item_prompts.py`
(relocated when the line-item stage was wired into the production pipeline —
W5-EXPORT-LINEITEM-REALDATA-04). This module re-exports it so the TASK-906 PoC
harness (`scripts/line_item_poc.py`, `scripts/line_item_folder_review.py`) keeps
working unchanged.
"""

from __future__ import annotations

from src.backend.ml.line_item_prompts import (  # noqa: F401
    DEFAULT_MODEL_SET,
    build_system_prompt,
    build_user_prompt,
    parse_line_item_response,
)

__all__ = [
    "DEFAULT_MODEL_SET",
    "build_system_prompt",
    "build_user_prompt",
    "parse_line_item_response",
]
