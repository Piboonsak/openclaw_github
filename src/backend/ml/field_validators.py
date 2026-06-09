"""Field-level validators used to gate LLM outputs before merge."""

from __future__ import annotations

import re
from typing import Any

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TAX_ID_RE = re.compile(r"^\d{13}$")
_INVOICE_NO_RE = re.compile(r"^[A-Za-z0-9ก-๙][A-Za-z0-9ก-๙\-_/\.]{3,29}$")
_INVOICE_NO_BLOCK_RE = re.compile(r"^(?:PO|P/O|SO|REF|RFQ)", re.IGNORECASE)
_INVOICE_NO_SLASH_NUM_RE = re.compile(r"^\d{1,4}/\d{1,4}$")

_NUMERIC_FIELDS = {
    "net_amount",
    "vat_amount",
    "total_amount",
    "wht_amount",
    "wht_rate",
    "amount_paid",
}


def _normalize_match_text(value: str) -> str:
    return "".join(str(value or "").lower().split())


def _value_in_ocr(value: str, raw_text: str) -> bool:
    left = _normalize_match_text(value)
    right = _normalize_match_text(raw_text)
    if not left or not right:
        return False
    return left in right


def _valid_invoice_number(value: str) -> bool:
    if not value:
        return False
    token = re.sub(r"\s+", "", value)
    if not _INVOICE_NO_RE.fullmatch(token):
        return False
    if _INVOICE_NO_BLOCK_RE.match(token):
        return False
    if _INVOICE_NO_SLASH_NUM_RE.fullmatch(token):
        return False
    if token.isdigit() and len(token) >= 12:
        return False
    if not any(ch.isdigit() for ch in token):
        return False
    return True


def _valid_invoice_date(value: str) -> bool:
    if not _DATE_RE.fullmatch(value or ""):
        return False
    year = int(value[:4])
    month = int(value[5:7])
    day = int(value[8:10])
    if year < 2020 or year > 2030:
        return False
    if month < 1 or month > 12:
        return False
    if day < 1 or day > 31:
        return False
    return True


def _valid_numeric(value: str) -> bool:
    cleaned = str(value or "").replace(",", "").strip()
    if not cleaned:
        return False
    try:
        amount = float(cleaned)
    except ValueError:
        return False
    return 0 < amount < 1e10


def validate_field(field_name: str, value: Any, raw_text: str) -> tuple[bool, bool]:
    """Return (is_valid, evidence_in_ocr) for a candidate field value."""
    text = str(value or "").strip()
    if not text:
        return False, False

    if field_name == "invoice_number":
        valid = _valid_invoice_number(text)
    elif field_name == "invoice_date":
        valid = _valid_invoice_date(text)
    elif field_name in {"seller_tax_id", "buyer_tax_id"}:
        valid = bool(_TAX_ID_RE.fullmatch(text))
    elif field_name in _NUMERIC_FIELDS:
        valid = _valid_numeric(text)
    else:
        # Unknown fields are allowed, but still reported with OCR evidence.
        valid = True

    return valid, _value_in_ocr(text, raw_text)
