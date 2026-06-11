"""D7-02: express_gl boundary contract schema and validator."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

# Load schema at module import time
_SCHEMA_PATH = Path(__file__).parent.parent.parent / "rules" / "express_gl.schema.json"


def _load_schema() -> dict[str, Any]:
    """Load express_gl schema from rules/express_gl.schema.json."""
    if _SCHEMA_PATH.exists():
        with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback schema if file not found
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "Express GL Journal Voucher Contract",
        "type": "object",
        "required": [
            "doc_id",
            "doc_type",
            "voucher_date",
            "reference",
            "book_code",
            "lines",
            "total_debit",
            "total_credit",
            "balanced",
            "status",
        ],
        "properties": {
            "doc_id": {"type": "string"},
            "doc_type": {"type": "string"},
            "voucher_date": {"type": "string"},
            "reference": {"type": "string"},
            "book_code": {"type": "string"},
            "lines": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "required": ["account", "debit", "credit"],
                    "properties": {
                        "account": {"type": "string"},
                        "description": {"type": "string"},
                        "debit": {"type": "number", "minimum": 0},
                        "credit": {"type": "number", "minimum": 0},
                    },
                },
            },
            "total_debit": {"type": "number", "minimum": 0},
            "total_credit": {"type": "number", "minimum": 0},
            "balanced": {"type": "boolean"},
            "status": {"type": "string"},
        },
    }


_SCHEMA = _load_schema()


class ExpressGLContractError(Exception):
    """Raised when payload violates express_gl contract."""

    pass


def _get_validator():
    """Cached validator instance."""
    return Draft202012Validator(_SCHEMA)


def validate_express_gl(payload: dict[str, Any]) -> None:
    """
    Validate payload against express_gl schema.

    Raises ExpressGLContractError if validation fails.

    Args:
        payload: Journal voucher payload to validate

    Raises:
        ExpressGLContractError: On schema violation
    """
    validator = _get_validator()
    errors = list(validator.iter_errors(payload))
    if errors:
        msg = "; ".join(
            [f"{e.absolute_path}: {e.message}" for e in errors[:3]]
        )  # First 3 errors
        raise ExpressGLContractError(f"Schema violation: {msg}")


def is_valid_express_gl(payload: dict[str, Any]) -> bool:
    """
    Check if payload is valid against express_gl schema.

    Args:
        payload: Payload to check

    Returns:
        True if valid, False otherwise
    """
    try:
        validate_express_gl(payload)
        return True
    except ExpressGLContractError:
        return False


def validate_express_gl_lines(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Validate individual lines in an express_gl payload.

    Returns a list of per-line error dicts (empty list if all lines valid).
    Each error contains: line_index (int), field (str), message (str).

    Args:
        payload: Journal voucher payload whose lines[] to inspect

    Returns:
        List of error dicts, empty if no errors found
    """
    lines = payload.get("lines", [])
    errors: list[dict[str, Any]] = []
    for i, line in enumerate(lines):
        if not isinstance(line, dict):
            errors.append({"line_index": i, "field": "line", "message": "Line must be an object"})
            continue
        for required_field in ("account", "debit", "credit"):
            if required_field not in line:
                errors.append({
                    "line_index": i,
                    "field": required_field,
                    "message": f"Missing required field '{required_field}'",
                })
        for amount_field in ("debit", "credit"):
            val = line.get(amount_field)
            if val is not None and (not isinstance(val, (int, float)) or val < 0):
                errors.append({
                    "line_index": i,
                    "field": amount_field,
                    "message": f"'{amount_field}' must be a non-negative number, got {val!r}",
                })
    return errors


def check_balance_tolerance(
    payload: dict[str, Any], tolerance: float = 0.01
) -> dict[str, Any]:
    """
    Check if total_debit and total_credit are balanced within tolerance.

    Args:
        payload: Journal voucher payload with total_debit / total_credit fields
        tolerance: Maximum allowed absolute difference (default 0.01)

    Returns:
        Dict with keys:
          balanced (bool): exact equality,
          delta (float): abs(debit - credit),
          within_tolerance (bool): delta <= tolerance,
          tolerance (float): the tolerance value used
    """
    total_debit = float(payload.get("total_debit", 0))
    total_credit = float(payload.get("total_credit", 0))
    delta = abs(total_debit - total_credit)
    return {
        "balanced": total_debit == total_credit,
        "delta": round(delta, 6),
        "within_tolerance": delta <= tolerance,
        "tolerance": tolerance,
    }
