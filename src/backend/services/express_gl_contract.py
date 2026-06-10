"""D7-02: express_gl boundary contract schema and validator."""

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, ValidationError


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
