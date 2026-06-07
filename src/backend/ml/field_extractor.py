"""Field extraction helpers for TASK-502.

Writes extraction artifacts to `src/backend/ml/cache/{sha256}/extraction_output.json`.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

from src.backend.ml.model_router import pick_model, should_escalate_to_sonnet

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CACHE_ROOT = REPO_ROOT / "src" / "backend" / "ml" / "cache"


EXTRACTION_SCHEMA_VERSION = "v8"

INVOICE_RE = re.compile(
    r"(?:invoice|inv|เลขที่ใบ(?:กำกับ|แจ้งหนี้)|เลขที่)\s*[:#-]*\s*([A-Z0-9-]+)", re.IGNORECASE
)
DATE_YMD_RE = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b")
DATE_DMY_RE = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b")
AMOUNT_RE = re.compile(
    r"(?<!\d)(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)(?!\d)"
)
VENDOR_RE = re.compile(r"(?:vendor|supplier|ผู้ขาย|บริษัท)[:\s]*([^\n]+)", re.IGNORECASE)
SELLER_RE = re.compile(
    r"(?:ผู้ขาย|seller|vendor|supplier)\s*[:：]\s*([^\n]+)", re.IGNORECASE
)
BUYER_RE = re.compile(r"(?:ลูกค้า|ผู้ซื้อ|buyer|bill\s*to)\s*[:：]\s*([^\n]+)", re.IGNORECASE)
TAX_ID_RE = re.compile(r"(?<!\d)(\d{13})(?!\d)")
PERCENT_RE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*%")
WHT_RATE_FALLBACK_RE = re.compile(r"หัก\s*(\d{1,2}(?:\.\d+)?)\s*%", re.IGNORECASE)
WHT_LINE_HINT_RE = re.compile(
    r"(?:หัก\s*ณ\s*ที่|ถูกหัก\s*ณ\s*ที่|ภาษีหัก\s*ณ\s*ที่|withholding\s*tax|\bwht\b)",
    re.IGNORECASE,
)
PAID_LINE_HINT_RE = re.compile(
    r"(?:เงิน.*ช(?:ำ|ํา)ระ|ยอด.*ช(?:ำ|ํา)ระ|paid\s*amount|amount\s*paid)",
    re.IGNORECASE,
)
TOTAL_KEYWORDS = (
    "grand total",
    "total amount",
    "amount due",
    "total",
    "จำนวนเงินทั้งสิ้น",
    "รวมทั้งสิ้น",
    "ยอดรวม",
    "ยอดสุทธิ",
    "รวมเป็นเงิน",
)

THAI_PUA_REPLACEMENTS = {
    "\uf701": "ิ",
    "\uf707": "๊",
    "\uf70a": "้",
    "\uf70b": "้",
    "\uf70e": "์",
    "\uf712": "็",
}

DOC_TYPE_HINTS: tuple[tuple[str, str], ...] = (
    ("รายงานรับ", "Receipts Report"),
    ("รายงานจ่าย", "Payments Report"),
    ("payment voucher", "Payment Voucher"),
    ("purchase order", "Purchase Order"),
    ("tax invoice", "Tax Invoice"),
    ("invoice", "Invoice"),
    ("receipt", "Receipt"),
    ("bill", "Bill"),
    ("ใบกำกับภาษี", "Tax Invoice"),
    ("ใบแจ้งหนี้", "Invoice"),
    ("ใบเสร็จ", "Receipt"),
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def _normalize_date(value: str) -> str:
    return value.replace("/", "-")


def _normalize_number(value: str) -> str:
    return value.replace(",", "").strip()


def _normalize_ocr_text(raw_text: str) -> str:
    normalized = unicodedata.normalize("NFC", raw_text or "")
    for bad_char, replacement in THAI_PUA_REPLACEMENTS.items():
        normalized = normalized.replace(bad_char, replacement)
    return normalized


def _extract_invoice_date(raw_text: str) -> str:
    ymd = DATE_YMD_RE.search(raw_text)
    if ymd:
        year, month, day = ymd.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    dmy = DATE_DMY_RE.search(raw_text)
    if dmy:
        day, month, year = dmy.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    return ""


def _extract_total_amount(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    keyword_candidates: list[float] = []
    currency_candidates: list[float] = []
    all_candidates: list[float] = []

    for line in lines:
        normalized_line = line.lower().replace("฿", " ")
        amount_matches = [_normalize_number(match) for match in AMOUNT_RE.findall(line)]
        values = []
        for value in amount_matches:
            try:
                values.append(float(value))
            except ValueError:
                continue

        if not values:
            continue

        all_candidates.extend(values)
        if any(keyword in normalized_line for keyword in TOTAL_KEYWORDS):
            keyword_candidates.extend(values)
        if "บาท" in line or "thb" in normalized_line or "baht" in normalized_line:
            currency_candidates.extend(values)

    if keyword_candidates:
        return f"{max(keyword_candidates):.2f}"
    if currency_candidates:
        return f"{max(currency_candidates):.2f}"
    if all_candidates:
        return f"{max(all_candidates):.2f}"
    return ""


def _extract_amount_from_labeled_lines(raw_text: str, hint_re: re.Pattern[str]) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    candidates: list[float] = []

    for line in lines:
        if not hint_re.search(line):
            continue

        values: list[float] = []
        for match in AMOUNT_RE.findall(line):
            try:
                values.append(float(_normalize_number(match)))
            except ValueError:
                continue

        if not values:
            continue

        likely_amounts = [value for value in values if value >= 10.0]
        if likely_amounts:
            candidates.append(likely_amounts[-1])
        else:
            candidates.append(values[-1])

    return f"{max(candidates):.2f}" if candidates else ""


def _extract_wht_rate(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for line in lines:
        if not WHT_LINE_HINT_RE.search(line):
            continue
        rate_match = PERCENT_RE.search(line)
        if not rate_match:
            continue
        try:
            rate = float(rate_match.group(1))
        except ValueError:
            continue
        if 0 <= rate <= 99:
            return f"{rate:.2f}".rstrip("0").rstrip(".")

    fallback_rates: list[float] = []
    for fallback_match in WHT_RATE_FALLBACK_RE.findall(raw_text):
        try:
            rate = float(fallback_match)
        except ValueError:
            continue
        if 0 <= rate <= 99:
            fallback_rates.append(rate)

    if fallback_rates:
        return f"{max(fallback_rates):.2f}".rstrip("0").rstrip(".")

    return ""


def _extract_party_info(raw_text: str) -> dict[str, str]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    seller_name = ""
    buyer_name = ""
    seller_tax_id = ""
    buyer_tax_id = ""

    seller_match = SELLER_RE.search(raw_text)
    if seller_match:
        seller_name = seller_match.group(1).strip()

    buyer_match = BUYER_RE.search(raw_text)
    if buyer_match:
        buyer_name = buyer_match.group(1).strip()

    for idx, line in enumerate(lines):
        line_context = f"{line} {lines[idx + 1] if idx + 1 < len(lines) else ''}"
        if not seller_tax_id and re.search(
            r"(ผู้ขาย|seller|vendor|supplier)", line, re.IGNORECASE
        ):
            ids = TAX_ID_RE.findall(line_context)
            if ids:
                seller_tax_id = ids[0]

        if not buyer_tax_id and re.search(
            r"(ลูกค้า|ผู้ซื้อ|buyer|bill\s*to)", line, re.IGNORECASE
        ):
            ids = TAX_ID_RE.findall(line_context)
            if ids:
                buyer_tax_id = ids[0]

    unique_tax_ids: list[str] = []
    for tax_id in TAX_ID_RE.findall(raw_text):
        if tax_id not in unique_tax_ids:
            unique_tax_ids.append(tax_id)

    if not seller_tax_id and unique_tax_ids:
        seller_tax_id = unique_tax_ids[0]
    if not buyer_tax_id and len(unique_tax_ids) > 1:
        buyer_tax_id = unique_tax_ids[1]

    return {
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "seller_tax_id": seller_tax_id,
        "buyer_tax_id": buyer_tax_id,
    }


def _join_ocr_text(ocr_output: dict[str, Any]) -> str:
    return "\n".join(
        str(block.get("text", "")).strip() for block in ocr_output.get("blocks", [])
    )


def _extract_with_rules(raw_text: str) -> dict[str, Any]:
    invoice_match = INVOICE_RE.search(raw_text)
    vendor_match = VENDOR_RE.search(raw_text)
    invoice_date = _extract_invoice_date(raw_text)
    total_amount = _extract_total_amount(raw_text)
    party_info = _extract_party_info(raw_text)
    wht_amount = _extract_amount_from_labeled_lines(raw_text, WHT_LINE_HINT_RE)
    wht_rate = _extract_wht_rate(raw_text)
    amount_paid = _extract_amount_from_labeled_lines(raw_text, PAID_LINE_HINT_RE)

    fields = {
        "invoice_number": (invoice_match.group(1).strip() if invoice_match else ""),
        "invoice_date": _normalize_date(invoice_date) if invoice_date else "",
        "vendor_name": (
            party_info["seller_name"]
            or (vendor_match.group(1).strip() if vendor_match else "")
        ),
        "seller_name": party_info["seller_name"],
        "buyer_name": party_info["buyer_name"],
        "seller_tax_id": party_info["seller_tax_id"],
        "buyer_tax_id": party_info["buyer_tax_id"],
        "total_amount": total_amount,
        "wht_rate": wht_rate,
        "wht_amount": wht_amount,
        "amount_paid": amount_paid,
        "source_text": raw_text,
    }

    confidence = {
        "invoice_number": 0.95 if fields["invoice_number"] else 0.35,
        "invoice_date": 0.95 if fields["invoice_date"] else 0.35,
        "vendor_name": 0.9 if fields["vendor_name"] else 0.4,
        "seller_name": 0.9 if fields["seller_name"] else 0.35,
        "buyer_name": 0.9 if fields["buyer_name"] else 0.35,
        "seller_tax_id": 0.95 if fields["seller_tax_id"] else 0.3,
        "buyer_tax_id": 0.95 if fields["buyer_tax_id"] else 0.3,
        "total_amount": 0.9 if fields["total_amount"] else 0.3,
        "wht_rate": 0.9 if fields["wht_rate"] else 0.3,
        "wht_amount": 0.9 if fields["wht_amount"] else 0.3,
        "amount_paid": 0.9 if fields["amount_paid"] else 0.3,
    }
    return {"fields": fields, "confidence": confidence}


def _infer_doc_type(raw_text: str) -> str:
    lowered = raw_text.lower()
    for hint, label in DOC_TYPE_HINTS:
        if hint.lower() in lowered:
            return label
    return "Invoice"


def _multi_pass_agreement(primary: dict[str, Any], secondary: dict[str, Any]) -> float:
    compare_keys = (
        "invoice_number",
        "invoice_date",
        "vendor_name",
        "seller_tax_id",
        "buyer_tax_id",
        "total_amount",
        "wht_amount",
    )
    hits = 0
    total = 0
    for key in compare_keys:
        total += 1
        left = str(primary.get(key, "")).strip().lower()
        right = str(secondary.get(key, "")).strip().lower()
        if left and right and left == right:
            hits += 1
    return round(hits / max(total, 1), 4)


def _compute_cost_thb(input_tokens: int, output_tokens: int, model: str) -> float:
    if "sonnet" in model.lower():
        in_price = 0.105
        out_price = 0.525
    else:
        in_price = 0.028
        out_price = 0.140
    return round(
        (input_tokens * in_price / 1000.0) + (output_tokens * out_price / 1000.0), 6
    )


def run_extraction(
    ocr_output: dict[str, Any],
    cache_root: Path | None = None,
) -> dict[str, Any]:
    """Run extraction and persist `extraction_output.json` under cache/{sha256}/."""
    raw_text = _normalize_ocr_text(_join_ocr_text(ocr_output))
    sha = str(ocr_output.get("sha256") or _sha256_text(raw_text))

    root = cache_root or DEFAULT_CACHE_ROOT
    artifact_dir = root / sha
    artifact_path = artifact_dir / "extraction_output.json"
    if artifact_path.exists():
        cached = json.loads(artifact_path.read_text(encoding="utf-8"))
        if cached.get("schema_version") == EXTRACTION_SCHEMA_VERSION:
            cached["cache_hit"] = True
            return cached

    rule_result = _extract_with_rules(raw_text)
    alt_pass_text = "\n".join(line.strip() for line in raw_text.splitlines() if line.strip())
    alt_result = _extract_with_rules(alt_pass_text)
    agreement_score = _multi_pass_agreement(
        rule_result["fields"], alt_result["fields"]
    )
    rule_result["fields"]["doc_type"] = _infer_doc_type(raw_text)

    low_conf_fields = [
        key for key, value in rule_result["confidence"].items() if float(value) < 0.8
    ]
    if agreement_score < 0.5 and "agreement_score" not in low_conf_fields:
        low_conf_fields.append("agreement_score")

    ocr_conf = float(ocr_output.get("avg_confidence", 0.0))
    page_count = int(ocr_output.get("page_count", 1))
    escalate = should_escalate_to_sonnet(
        page_count=page_count,
        ocr_confidence=ocr_conf,
        low_confidence_fields=len(low_conf_fields),
        rule_conflict=False,
    )
    model = pick_model(escalate)

    input_tokens = max(200, int(len(raw_text) * 0.35))
    output_tokens = 180 if escalate else 120
    cost_thb = _compute_cost_thb(input_tokens, output_tokens, model)

    payload = {
        "schema_version": EXTRACTION_SCHEMA_VERSION,
        "sha256": sha,
        "model": model,
        "fields": rule_result["fields"],
        "confidence_per_field": rule_result["confidence"],
        "low_confidence_fields": low_conf_fields,
        "needs_human_review": bool(low_conf_fields),
        "cache_hit": False,
        "meta": {
            "escalated_to_sonnet": escalate,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_thb": cost_thb,
            "ocr_confidence": ocr_conf,
            "page_count": page_count,
            "agreement_score": agreement_score,
        },
    }

    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return payload


def extract_fields(raw_text: str) -> dict[str, Any]:
    """Backward-compatible extraction API used by legacy endpoints/tests."""
    return _extract_with_rules(_normalize_ocr_text(raw_text))["fields"]
