"""Prompt helpers for TASK-906 line-item extraction PoC."""

from __future__ import annotations

import json
import re
from typing import Any

DEFAULT_MODEL_SET = [
    "google/gemini-2.5-flash-lite",
    "google/gemini-2.5-flash",
    "anthropic/claude-sonnet-4",
]

_RESPONSE_SCHEMA = {
    "document_total": "numeric string or empty",
    "currency": "THB|USD|other or empty",
    "line_items": [
        {
            "product_name": "string",
            "qty": "numeric string or empty",
            "unit": "string or empty",
            "unit_price": "numeric string or empty",
            "line_amount": "numeric string or empty",
            "line_type": "stock_item|part_or_material|labor|service|office_supply|unknown",
            "line_type_confidence": "number 0.0-1.0",
            "stock_candidate": "boolean",
            "confidence_reasons": ["short reason strings"],
        }
    ],
    "notes": ["optional warnings as strings"],
}


def build_system_prompt() -> str:
    return (
        "You extract invoice line items from Thai accounting documents. "
        "Return JSON only. Never add markdown, code fences, or prose. "
        "Use the document image/PDF as the authoritative source and use OCR text "
        "only as fallback reference when the visual evidence is unclear."
    )


def build_user_prompt(metadata: dict[str, Any], ocr_text: str) -> str:
    header = {
        "doc_id": metadata.get("doc_id", ""),
        "invoice_number": metadata.get("invoice_number", ""),
        "invoice_date": metadata.get("invoice_date", ""),
        "seller_name": metadata.get("seller_name", ""),
        "expected_total_amount": metadata.get("total_amount", ""),
        "currency": metadata.get("currency", "THB") or "THB",
    }
    return (
        "Extract every invoice line item you can see.\n"
        "Return exactly this JSON schema:\n"
        f"{json.dumps(_RESPONSE_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        "Rules:\n"
        "1. Keep one row per invoice line.\n"
        "2. Do not invent rows that are not visible.\n"
        "3. Preserve product names as printed.\n"
        "4. Use numeric strings without commas for qty, unit_price, line_amount.\n"
        "5. If a field is not visible, use an empty string.\n"
        "6. Line_amount usually reconciles to net/subtotal before VAT, not gross total.\n"
        "7. Do not include VAT, withholding tax, gross total, net total, payment total, or footer summary rows as line items.\n"
        "8. Classify each row into line_type. Use labor/service for fee, wage, delivery, transport, repair, installation, and Thai ค่า/ค่าแรง/ค่าบริการ/ค่าส่ง/ค่าขนส่ง rows.\n"
        "9. Use part_or_material for spare parts, materials, machine parts, and rows with stock-like units such as pcs, pc, set, ชิ้น, ตัว, เส้น, ท่อน.\n"
        "10. Use office_supply for paper, pen, notebook, stationery, toner, and similar consumables unless clearly part of the company's stock master.\n"
        "11. stock_candidate should be true only for likely stock/product/material rows, not labor, service, tax, totals, or generic office supplies.\n"
        "12. If a row is ambiguous, keep it but lower line_type_confidence and explain in confidence_reasons.\n"
        "13. If the document has no visible line-item table, return an empty line_items array and explain briefly in notes.\n\n"
        "Document metadata:\n"
        f"{json.dumps(header, ensure_ascii=False, indent=2)}\n\n"
        "OCR fallback text follows. It may contain OCR errors.\n"
        "=== OCR TEXT START ===\n"
        f"{ocr_text[:12000]}\n"
        "=== OCR TEXT END ==="
    )


def parse_line_item_response(text: str) -> dict[str, Any]:
    cleaned = _strip_code_fence(text.strip())
    if not cleaned:
        return {"document_total": "", "currency": "", "line_items": [], "notes": []}

    candidate = _extract_json_block(cleaned)
    payload = json.loads(candidate)
    if not isinstance(payload, dict):
        raise ValueError("Line-item response root must be a JSON object")
    payload.setdefault("document_total", "")
    payload.setdefault("currency", "")
    payload.setdefault("line_items", [])
    payload.setdefault("notes", [])
    if not isinstance(payload["line_items"], list):
        raise ValueError("line_items must be a JSON array")
    if not isinstance(payload["notes"], list):
        payload["notes"] = [str(payload["notes"])]
    return payload


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    text = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json_block(text: str) -> str:
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in model response")
    return text[start : end + 1]
