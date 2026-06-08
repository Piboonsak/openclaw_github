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


EXTRACTION_SCHEMA_VERSION = "v19"

INVOICE_RE = re.compile(
    r"(?:invoice|inv|เลขที่ใบ(?:กำกับ|แจ้งหนี้)|เลขที่)\s*[:#-]*\s*([A-Z0-9-]+)", re.IGNORECASE
)
DOC_NO_STRONG_RE = re.compile(
    r"(?:เลขที่เอกสาร|เลขที่ใบ(?:กำกับ|แจ้งหนี้)?|document\s*no\.?|doc(?:ument)?\s*no\.?|invoice\s*no\.?|inv\.?\s*no\.?|voucher\s*no\.?)\s*[:：#-]?\s*([A-Za-z0-9ก-๙][A-Za-z0-9ก-๙\-_/\.]{2,40})",
    re.IGNORECASE,
)
DOC_NO_WEAK_RE = re.compile(
    r"(?:เลขที่|no\.?)\s*[:：#-]\s*([A-Za-z0-9ก-๙][A-Za-z0-9ก-๙\-_/\.]{2,40})",
    re.IGNORECASE,
)
DOC_NO_SOFT_RE = re.compile(
    r"(?:เลขที่|inv(?:oice)?\.?\s*no\.?|no\.?)\s*([A-Za-z0-9ก-๙][A-Za-z0-9ก-๙\-_/\.]{2,40})",
    re.IGNORECASE,
)
BILL_NO_RE = re.compile(
    r"(?:bill\s*no\.?|doc\s*no\.?|reference\s*no\.?|ref\.?\s*no\.?)\s*[:：#-]?\s*([A-Za-z0-9][A-Za-z0-9\-_/\.]{2,40})",
    re.IGNORECASE,
)
DATE_LABEL_RE = re.compile(
    r"(?:วันที่ออก|วันที่เอกสาร|วันที่|date\s*issued|invoice\s*date|document\s*date|date)\s*[:：]?\s*",
    re.IGNORECASE,
)
DATE_YMD_RE = re.compile(r"\b(20\d{2})[-/](\d{1,2})[-/](\d{1,2})\b")
DATE_DMY_RE = re.compile(r"\b(\d{1,2})[-/](\d{1,2})[-/](20\d{2})\b")
DATE_NUMERIC_RE = re.compile(r"(?<!\d)(\d{1,4})[-/](\d{1,2})[-/](\d{1,4})(?!\d)")
DATE_THAI_MONTH_RE = re.compile(r"(?<!\d)(\d{1,2})\s*([ก-๙\.]{2,16})\s*(\d{2,4})(?!\d)")
DATE_ENG_MONTH_RE = re.compile(
    r"(?i)(?<!\w)(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*,?\s*(\d{2,4})(?!\w)"
)
DATE_ENG_MONTH_RE_REV = re.compile(
    r"(?i)(?<!\w)(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{1,2})\s*,?\s*(\d{2,4})(?!\w)"
)
AMOUNT_RE = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+\.\d{1,2}|\d{1,9})(?!\d)")
VENDOR_RE = re.compile(r"(?:vendor|supplier|ผู้ขาย|บริษัท)[:\s]*([^\n]+)", re.IGNORECASE)
SELLER_RE = re.compile(
    r"(?:ผู้ขาย|seller|vendor|supplier|from|จาก)\s*[:：]?\s*([^\n]+)", re.IGNORECASE
)
BUYER_RE = re.compile(
    r"(?:ลูกค้า|ผู้ซื้อ|นามลูกค้า|buyer|bill\s*to|sold\s*to|customer\s*name|customer)\s*[:：]?\s*([^\n]+)",
    re.IGNORECASE,
)
TAX_ID_RE = re.compile(r"(?<!\d)(\d{13})(?!\d)")
COMPANY_HEADER_RE = re.compile(
    r"^(?:บริษัท|ห้างหุ้นส่วน|ห้าง|ร้าน|โรงงาน|company|co\.?,?\s*ltd|partnership|p\.?l\.?c\.?)\b.*",
    re.IGNORECASE,
)
COMPANY_NAME_LINE_RE = re.compile(
    r"(?:จำกัด|จํากัด|มหาชน|co\.?\s*,?\s*ltd\.?|company\s+limited|public\s+company\s+limited|p\.?l\.?c\.?)",
    re.IGNORECASE,
)
LABEL_PREFIX_STRIP_RE = re.compile(
    r"^\s*(?:ผู้ขาย|ลูกค้า|ผู้ซื้อ|นามลูกค้า|seller|buyer|customer(?:\s*name)?|bill\s*to|sold\s*to|from)\s*[:：]?\s*",
    re.IGNORECASE,
)
NAME_NOISE_PREFIX_RE = re.compile(r"^(?:[A-Z]{1,4}\d{2,}|C\d{3,}|CUS\d+)\s*", re.IGNORECASE)
NAME_TRAILING_NOISE_RE = re.compile(
    r"\s*(?:=|:)?\s*(?:เลขที่เอกสาร|เลขที่ภาษี|ที่อยู่|โทรศัพท์|อีเมล|email|tel|วันที่ออก|tax\s*id)\b.*$",
    re.IGNORECASE,
)
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
WHT_BASE_HINT_RE = re.compile(
    r"(?:มูลค่า(?:ที่)?คำนวณภาษี|มูลค่า(?:ที่)?คํานวณภาษี|ฐานภาษี|taxable\s*amount|before\s*tax)",
    re.IGNORECASE,
)
VAT_LINE_HINT_RE = re.compile(
    r"(?:ภาษีมูลค่าเพิ่ม|ภาษี\s*มูลค่าเพิ่ม|vat|ภาษีขาย|ภาษีซื้อ|ภาษี\s*\d+\s*%)",
    re.IGNORECASE,
)
NET_LINE_HINT_RE = re.compile(
    r"(?:มูลค่าสินค้าก่อนภาษี|มูลค่าก่อนภาษี|net\s*amount|amount\s*before\s*tax|subtotal|รวมสินค้า)",
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

COMPANY_NAME_CORRECTIONS: tuple[tuple[str, str], ...] = (
    ("บริษัทฤทธิ์ล้าเลิศเอ็นจิเนียริ่ง", "บริษัทฤทธิ์ล้ำเลิศเอ็นจิเนียริ่ง"),
    ("บริษัท ฤทธิ์ล้าเลิศเอ็นจิเนียริ่ง", "บริษัท ฤทธิ์ล้ำเลิศเอ็นจิเนียริ่ง"),
    ("บรษัท", "บริษัท"),
    ("บริษ ท", "บริษัท"),
)

TAX_ID_CANONICAL_COMPANIES: dict[str, str] = {
    "0125561025189": "บริษัท ฤทธิ์ล้ำเลิศ เอ็นจิเนียริ่ง จำกัด",
    "0105565189488": "บริษัท ทีเค.นอนสติ๊ก จำกัด",
    "0107544000043": "บริษัท โฮม โปรดักส์ เซ็นเตอร์ จำกัด (มหาชน)",
}

KNOWN_TEMPLATE_TAX_IDS: set[str] = {
    "0125561025189",
    "0105565189488",
    "0107544000043",
}

COMMON_WHT_RATES: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 15.0)
THAI_MONTHS: dict[str, int] = {
    "มค": 1,
    "มกราคม": 1,
    "กพ": 2,
    "กุมภาพันธ์": 2,
    "มีค": 3,
    "มีนาคม": 3,
    "เมย": 4,
    "เมษายน": 4,
    "พค": 5,
    "พฤษภาคม": 5,
    "มิย": 6,
    "มิถุนายน": 6,
    "กค": 7,
    "กรกฎาคม": 7,
    "สค": 8,
    "สิงหาคม": 8,
    "กย": 9,
    "กันยายน": 9,
    "ตค": 10,
    "ตุลาคม": 10,
    "พย": 11,
    "พฤศจิกายน": 11,
    "ธค": 12,
    "ธันวาคม": 12,
}
ENG_MONTHS: dict[str, int] = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


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


def _looks_like_id_token(token: str) -> bool:
    cleaned = token.replace(",", "").strip()
    if not cleaned:
        return True
    if "." in cleaned:
        return False
    return cleaned.isdigit() and len(cleaned) >= 12


def _line_amount_candidates(line: str) -> list[float]:
    values: list[float] = []
    for raw_match in AMOUNT_RE.findall(line):
        if _looks_like_id_token(raw_match):
            continue
        try:
            value = float(_normalize_number(raw_match))
        except ValueError:
            continue
        if value >= 1e10:
            continue
        values.append(value)
    return values


def _extract_invoice_date(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    for line in lines[:60]:
        if not DATE_LABEL_RE.search(line):
            continue
        labeled_date = _extract_date_from_snippet(line)
        if labeled_date:
            return labeled_date

    for line in lines[:60]:
        candidate = _extract_date_from_snippet(line)
        if candidate:
            return candidate

    ymd = DATE_YMD_RE.search(raw_text)
    if ymd:
        year, month, day = ymd.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    dmy = DATE_DMY_RE.search(raw_text)
    if dmy:
        day, month, year = dmy.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    return ""


def _normalize_year(year: int, prefer_buddhist_suffix: bool = False) -> int:
    if year >= 2400:
        return year - 543
    if year < 100:
        if prefer_buddhist_suffix and year >= 50:
            return (2500 + year) - 543
        return 2000 + year
    return year


def _safe_date(year: int, month: int, day: int) -> str:
    if not (1 <= month <= 12 and 1 <= day <= 31 and 1900 <= year <= 2100):
        return ""
    return f"{year:04d}-{month:02d}-{day:02d}"


def _extract_date_from_snippet(text: str) -> str:
    prefer_buddhist_suffix = bool(re.search(r"[ก-๙]|พ\.?ศ\.?", text, re.IGNORECASE))

    numeric = DATE_NUMERIC_RE.search(text)
    if numeric:
        a, b, c = [int(x) for x in numeric.groups()]
        if a > 31:
            return _safe_date(_normalize_year(a, prefer_buddhist_suffix), b, c)
        return _safe_date(_normalize_year(c, prefer_buddhist_suffix), b, a)

    thai_date = DATE_THAI_MONTH_RE.search(text)
    if thai_date:
        day_str, month_token, year_str = thai_date.groups()
        month_key = re.sub(r"[^ก-๙]", "", month_token)
        month = THAI_MONTHS.get(month_key, 0)
        if month:
            return _safe_date(
                _normalize_year(int(year_str), prefer_buddhist_suffix),
                month,
                int(day_str),
            )

    eng_date = DATE_ENG_MONTH_RE.search(text)
    if eng_date:
        day_str, month_token, year_str = eng_date.groups()
        month = ENG_MONTHS.get(month_token.lower()[:3], 0)
        if month:
            return _safe_date(
                _normalize_year(int(year_str), prefer_buddhist_suffix),
                month,
                int(day_str),
            )

    eng_date_rev = DATE_ENG_MONTH_RE_REV.search(text)
    if eng_date_rev:
        month_token, day_str, year_str = eng_date_rev.groups()
        month = ENG_MONTHS.get(month_token.lower()[:3], 0)
        if month:
            return _safe_date(
                _normalize_year(int(year_str), prefer_buddhist_suffix),
                month,
                int(day_str),
            )

    return ""


def _clean_invoice_number(value: str) -> str:
    candidate = (value or "").strip().strip(" .,:;|=")
    candidate = re.split(
        r"\s*(?:วันที่ออก|วันที่|date|อ้างอิง|ref(?:erence)?|ที่อยู่|โทร|email)\b",
        candidate,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" .,:;|=")
    return candidate


def _is_tax_id_like(value: str) -> bool:
    cleaned = re.sub(r"\D", "", value or "")
    return len(cleaned) == 13


def _valid_invoice_no_candidate(line: str, candidate: str) -> bool:
    cand = _clean_invoice_number(candidate)
    if not cand or not re.search(r"\d", cand):
        return False
    if len(cand) < 4:
        return False

    line_l = line.lower()
    if _is_tax_id_like(cand) and (
        "taxid" in line_l
        or "เลขประจําตัวผู้เสียภาษี" in line
        or "เลขประจำตัวผู้เสียภาษี" in line
        or "ผู้เสียภาษี" in line
    ):
        return False

    # Avoid obvious address numbers captured from noisy OCR.
    if any(token in line for token in ("ถนน", "แขวง", "เขต", "จังหวัด", "อำเภอ", "ตำบล", "หมู่", "ซอย")):
        if len(cand) <= 8 and re.fullmatch(r"[A-Za-z0-9]+", cand):
            return False

    return True


def _extract_invoice_number(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    for line in lines[:120]:
        for match in DOC_NO_STRONG_RE.finditer(line):
            candidate = _clean_invoice_number(match.group(1))
            if _valid_invoice_no_candidate(line, candidate):
                return candidate

    for line in lines[:120]:
        for match in BILL_NO_RE.finditer(line):
            candidate = _clean_invoice_number(match.group(1))
            if _valid_invoice_no_candidate(line, candidate):
                return candidate

    weak_address_noise = ("ถนน", "แขวง", "เขต", "จังหวัด", "อำเภอ", "ตำบล", "หมู่", "ซอย")
    for line in lines[:120]:
        if any(token in line for token in weak_address_noise):
            continue
        for match in DOC_NO_WEAK_RE.finditer(line):
            candidate = _clean_invoice_number(match.group(1))
            if _valid_invoice_no_candidate(line, candidate):
                return candidate

    for line in lines[:120]:
        line_l = line.lower()
        if "taxid" in line_l or "ผู้เสียภาษี" in line:
            continue
        for match in DOC_NO_SOFT_RE.finditer(line):
            candidate = _clean_invoice_number(match.group(1))
            if _valid_invoice_no_candidate(line, candidate):
                return candidate

    invoice_match = INVOICE_RE.search(raw_text)
    if invoice_match:
        candidate = _clean_invoice_number(invoice_match.group(1))
        if _valid_invoice_no_candidate(raw_text, candidate):
            return candidate

    return ""


def _extract_total_amount(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    keyword_candidates: list[float] = []
    currency_candidates: list[float] = []
    for line in lines:
        normalized_line = line.lower().replace("฿", " ")
        values = _line_amount_candidates(line)

        if not values:
            continue

        if any(keyword in normalized_line for keyword in TOTAL_KEYWORDS):
            keyword_candidates.extend(values)
        if "บาท" in line or "thb" in normalized_line or "baht" in normalized_line:
            currency_candidates.extend(values)

    if keyword_candidates:
        return f"{max(keyword_candidates):.2f}"
    if currency_candidates:
        return f"{max(currency_candidates):.2f}"
    return ""


def _extract_amount_from_labeled_lines(raw_text: str, hint_re: re.Pattern[str]) -> str:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    candidates: list[float] = []

    for line in lines:
        if not hint_re.search(line):
            continue

        values = _line_amount_candidates(line)

        if not values:
            continue

        likely_amounts = [value for value in values if value >= 10.0]
        if likely_amounts:
            candidates.append(likely_amounts[-1])
        else:
            candidates.append(values[-1])

    return f"{max(candidates):.2f}" if candidates else ""


def _extract_vat_amount(raw_text: str) -> str:
    """Extract VAT amount from labeled lines, excluding net/subtotal rows (ก่อนภาษี).
    
    Searches for lines matching VAT_LINE_HINT_RE but filters out lines containing
    ก่อนภาษี (before tax/net) to avoid extracting net amount.
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    candidates: list[float] = []

    for line in lines:
        # Skip lines that mention "before tax" (net amount, not VAT)
        if "ก่อนภาษี" in line or "ก่อนค่าภาษี" in line or "before tax" in line.lower():
            continue

        if not VAT_LINE_HINT_RE.search(line):
            continue

        values = _line_amount_candidates(line)
        if not values:
            continue

        likely_amounts = [value for value in values if value >= 1.0]
        if likely_amounts:
            candidates.append(likely_amounts[-1])
        else:
            candidates.append(values[-1])

    return f"{max(candidates):.2f}" if candidates else ""


def _extract_net_amount(raw_text: str) -> str:
    """Extract net amount (before VAT) from labeled lines.
    
    Searches for lines mentioning มูลค่าสินค้าก่อนภาษี, net amount, subtotal, etc.
    Returns the largest amount found on matching lines.
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    candidates: list[float] = []

    for line in lines:
        if not NET_LINE_HINT_RE.search(line):
            continue

        values = _line_amount_candidates(line)
        if not values:
            continue

        likely_amounts = [value for value in values if value >= 10.0]
        if likely_amounts:
            candidates.append(likely_amounts[-1])
        else:
            candidates.append(values[-1])

    return f"{max(candidates):.2f}" if candidates else ""


def _extract_vat_rate(raw_text: str) -> str:
    """Extract VAT rate percentage.
    
    Looks for explicit VAT rate mentions (e.g., "ภาษี 7%", "VAT 7%").
    Returns "7" as default if VAT context is present but no explicit rate found.
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    for line in lines:
        if not VAT_LINE_HINT_RE.search(line):
            continue

        rate_match = PERCENT_RE.search(line)
        if rate_match:
            try:
                rate_val = float(rate_match.group(1))
                if 0.0 < rate_val < 100.0:
                    return f"{rate_val:.2f}".rstrip("0").rstrip(".")
            except ValueError:
                pass

    # Default to 7% if VAT context present but no explicit rate
    if VAT_LINE_HINT_RE.search(raw_text):
        return "7"

    return ""


def _has_vat_context(raw_text: str) -> bool:
    """Check if document has VAT-related keywords suggesting VAT is applicable."""
    return bool(VAT_LINE_HINT_RE.search(raw_text))


def _clean_party_name(value: str) -> str:
    name = (value or "").strip()
    name = name.lstrip(" :：-=.\t")
    name = LABEL_PREFIX_STRIP_RE.sub("", name).strip()
    name = NAME_NOISE_PREFIX_RE.sub("", name)
    name = NAME_TRAILING_NOISE_RE.sub("", name)
    name = TAX_ID_RE.sub("", name).strip(" \t:.-")
    name = re.sub(r"\s+[A-Z]{2,5}$", "", name).strip()
    return name


def _canonicalize_company_name(name: str, tax_id: str = "") -> str:
    normalized = re.sub(r"\s+", " ", (name or "")).strip()
    mapped = TAX_ID_CANONICAL_COMPANIES.get((tax_id or "").strip(), "")
    if not normalized and mapped:
        return mapped
    if not normalized:
        return ""

    normalized = normalized.replace("จํากัด", "จำกัด")
    for broken, fixed in COMPANY_NAME_CORRECTIONS:
        if broken in normalized:
            normalized = normalized.replace(broken, fixed)

    if mapped:
        # Check if extracted name is significantly different from canonical name.
        # Only use canonical if they are similar (share > 50% of words).
        normalized_lower = normalized.lower()
        mapped_lower = mapped.lower()
        
        # Simple word overlap check: if most words in normalized are in mapped, use canonical.
        normalized_words = set(normalized_lower.split())
        mapped_words = set(mapped_lower.split())
        
        if normalized_words and mapped_words:
            overlap = len(normalized_words & mapped_words) / max(len(normalized_words), len(mapped_words))
            if overlap >= 0.5:
                # High similarity: use canonical legal name for stability.
                return mapped
        # Low similarity: keep extracted name to preserve OCR signal (avoid silent correction).
        # Caller may add warning via name_canonical_mismatch flag.
        return normalized

    return normalized


def _extract_base_amount_candidates(raw_text: str) -> list[float]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    candidates: list[float] = []
    for line in lines:
        if not WHT_BASE_HINT_RE.search(line):
            continue
        for value in _line_amount_candidates(line):
            if value > 0:
                candidates.append(value)
    return candidates


def _infer_wht_rate_from_amounts(raw_text: str, wht_amount: str, total_amount: str) -> str:
    if not wht_amount:
        return ""

    try:
        wht_value = float(_normalize_number(wht_amount))
    except ValueError:
        return ""
    if wht_value <= 0:
        return ""

    base_candidates = _extract_base_amount_candidates(raw_text)
    if total_amount:
        try:
            total_value = float(_normalize_number(total_amount))
        except ValueError:
            total_value = 0.0
        if total_value > wht_value:
            base_candidates.append(total_value)

    best_rate: float | None = None
    best_distance = 999.0
    for base in base_candidates:
        if base <= wht_value:
            continue
        raw_rate = (wht_value / base) * 100.0
        for expected in COMMON_WHT_RATES:
            distance = abs(raw_rate - expected)
            if distance < best_distance:
                best_distance = distance
                best_rate = expected

    if best_rate is None or best_distance > 0.5:
        return ""
    return f"{best_rate:.2f}".rstrip("0").rstrip(".")


def _has_wht_context(raw_text: str) -> bool:
    if WHT_LINE_HINT_RE.search(raw_text):
        return True
    compact = re.sub(r"\s+", "", raw_text)
    return any(
        keyword in compact
        for keyword in (
            "หักณที่จ่าย",
            "ถูกหักณที่จ่าย",
            "ภาษีหักณที่จ่าย",
            "withholdingtax",
        )
    )


def _has_paid_context(raw_text: str) -> bool:
    if PAID_LINE_HINT_RE.search(raw_text):
        return True
    compact = re.sub(r"\s+", "", raw_text)
    return any(
        keyword in compact
        for keyword in (
            "จำนวนเงินที่ชำระ",
            "ยอดชำระ",
            "amountpaid",
        )
    )


def _looks_like_company_name(line: str) -> bool:
    if not line:
        return False
    return bool(COMPANY_HEADER_RE.match(line) or COMPANY_NAME_LINE_RE.search(line))


def _looks_like_noise_party_name(line: str) -> bool:
    lowered = (line or "").strip().lower()
    if not lowered:
        return True
    return any(
        token in lowered
        for token in (
            "terms",
            "condition",
            "insurance",
            "policy",
            "period of",
            "address",
            "โทร",
            "fax",
            "email",
        )
    )


def _extract_name_near_tax_id(
    lines: list[str],
    tax_id: str,
    lookback: int = 8,
    lookahead: int = 2,
) -> str:
    if not tax_id:
        return ""
    for idx, line in enumerate(lines):
        if tax_id not in line:
            continue

        same_line = _clean_party_name(line.replace(tax_id, ""))
        if _looks_like_company_name(same_line) and len(same_line) >= 4:
            return same_line

        for offset in range(1, lookback + 1):
            check_idx = idx - offset
            if check_idx < 0:
                break
            candidate = _clean_party_name(lines[check_idx])
            if _looks_like_company_name(candidate) and len(candidate) >= 4:
                return candidate

        for offset in range(1, lookahead + 1):
            check_idx = idx + offset
            if check_idx >= len(lines):
                break
            candidate = _clean_party_name(lines[check_idx])
            if _looks_like_company_name(candidate) and len(candidate) >= 4:
                return candidate

    return ""


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
        seller_name = _clean_party_name(seller_match.group(1))

    buyer_match = BUYER_RE.search(raw_text)
    if buyer_match:
        buyer_name = _clean_party_name(buyer_match.group(1))

    for idx, line in enumerate(lines):
        line_context = f"{line} {lines[idx + 1] if idx + 1 < len(lines) else ''}"
        if not seller_tax_id and re.search(
            r"(ผู้ขาย|seller|vendor|supplier|from|จาก)", line, re.IGNORECASE
        ):
            ids = TAX_ID_RE.findall(line_context)
            if ids:
                seller_tax_id = ids[0]

        if not buyer_tax_id and re.search(
            r"(ลูกค้า|ผู้ซื้อ|นามลูกค้า|buyer|bill\s*to|sold\s*to|customer)", line, re.IGNORECASE
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

    if not seller_name and seller_tax_id:
        seller_name = _extract_name_near_tax_id(lines, seller_tax_id)
    if not buyer_name and buyer_tax_id:
        buyer_name = _extract_name_near_tax_id(lines, buyer_tax_id)

    if not seller_name:
        for line in lines[:25]:
            candidate = _clean_party_name(line)
            if _looks_like_company_name(candidate) and len(candidate) >= 4:
                seller_name = candidate
                break

    if buyer_name and seller_name and buyer_name.strip() == seller_name.strip():
        buyer_name = ""

    return {
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "seller_tax_id": seller_tax_id,
        "buyer_tax_id": buyer_tax_id,
    }


def _line_join_with_bbox_tokens(tokens: list[dict[str, Any]]) -> str:
    if not tokens:
        return ""

    ordered = sorted(tokens, key=lambda item: int(item.get("bbox", [0, 0, 0, 0])[0]))
    parts: list[str] = []
    prev_bbox: list[int] | None = None

    for token in ordered:
        text = str(token.get("text", "")).strip()
        bbox = token.get("bbox", [0, 0, 0, 0])
        if not text or len(bbox) < 4:
            continue

        if prev_bbox is not None and parts:
            gap = int(bbox[0]) - int(prev_bbox[2])
            prev_h = max(int(prev_bbox[3]) - int(prev_bbox[1]), 1)
            curr_h = max(int(bbox[3]) - int(bbox[1]), 1)
            # Insert space only when there is a clear visual gap.
            if gap > max(10, int(min(prev_h, curr_h) * 0.8)):
                parts.append(" ")

        parts.append(text)
        prev_bbox = [int(v) for v in bbox[:4]]

    return "".join(parts).strip()


def _reconstruct_lines_from_blocks(blocks: list[dict[str, Any]]) -> list[str]:
    prepared: list[dict[str, Any]] = []
    for block in blocks:
        text = str(block.get("text", "")).strip()
        bbox = block.get("bbox")
        if not text or not isinstance(bbox, list) or len(bbox) < 4:
            continue

        x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
        prepared.append(
            {
                "text": text,
                "bbox": [x1, y1, x2, y2],
                "page": int(block.get("page", 1)),
                "yc": (y1 + y2) / 2.0,
            }
        )

    if not prepared:
        return []

    lines: list[str] = []
    pages = sorted({item["page"] for item in prepared})
    for page in pages:
        page_blocks = [item for item in prepared if item["page"] == page]
        page_blocks.sort(key=lambda item: (item["yc"], item["bbox"][0]))

        line_groups: list[dict[str, Any]] = []
        for token in page_blocks:
            if not line_groups:
                line_groups.append({"yc": token["yc"], "tokens": [token]})
                continue

            current = line_groups[-1]
            heights = [
                max(int(t["bbox"][3]) - int(t["bbox"][1]), 1)
                for t in current["tokens"]
            ]
            median_h = sorted(heights)[len(heights) // 2]
            y_tolerance = max(10.0, median_h * 0.55)

            if abs(token["yc"] - float(current["yc"])) <= y_tolerance:
                current["tokens"].append(token)
                # Keep centroid stable as we append more tokens in same visual line.
                current["yc"] = (
                    float(current["yc"]) * (len(current["tokens"]) - 1) + token["yc"]
                ) / len(current["tokens"])
            else:
                line_groups.append({"yc": token["yc"], "tokens": [token]})

        for group in line_groups:
            line_text = _line_join_with_bbox_tokens(group["tokens"])
            if line_text:
                lines.append(line_text)

    return lines


def _join_ocr_text(ocr_output: dict[str, Any]) -> str:
    blocks = [
        block
        for block in ocr_output.get("blocks", [])
        if str(block.get("text", "")).strip()
    ]
    reconstructed = _reconstruct_lines_from_blocks(blocks)
    if reconstructed:
        return "\n".join(reconstructed)
    return "\n".join(str(block.get("text", "")).strip() for block in blocks)


def _extract_with_rules(raw_text: str) -> dict[str, Any]:
    invoice_number = _extract_invoice_number(raw_text)
    vendor_match = VENDOR_RE.search(raw_text)
    invoice_date = _extract_invoice_date(raw_text)
    total_amount = _extract_total_amount(raw_text)
    net_amount = _extract_net_amount(raw_text)
    vat_amount = _extract_vat_amount(raw_text)
    vat_rate = _extract_vat_rate(raw_text)
    party_info = _extract_party_info(raw_text)
    wht_amount = _extract_amount_from_labeled_lines(raw_text, WHT_LINE_HINT_RE)
    wht_rate = _extract_wht_rate(raw_text)
    amount_paid = _extract_amount_from_labeled_lines(raw_text, PAID_LINE_HINT_RE)
    if not wht_rate and _has_wht_context(raw_text):
        wht_rate = _infer_wht_rate_from_amounts(raw_text, wht_amount, total_amount)

    seller_name = _canonicalize_company_name(
        party_info["seller_name"],
        party_info["seller_tax_id"],
    )
    buyer_name = _canonicalize_company_name(
        party_info["buyer_name"],
        party_info["buyer_tax_id"],
    )
    vendor_from_label = vendor_match.group(1).strip() if vendor_match else ""
    vendor_name = _canonicalize_company_name(
        seller_name or vendor_from_label,
        party_info["seller_tax_id"],
    )

    # Detect cross-field conflicts: |net + vat - total| > 1.00 THB
    cross_field_conflict = False
    cross_field_error = ""
    if net_amount and vat_amount and total_amount:
        try:
            net_val = float(_normalize_number(net_amount))
            vat_val = float(_normalize_number(vat_amount))
            total_val = float(_normalize_number(total_amount))
            
            calculated_total = round(net_val + vat_val, 2)
            if abs(calculated_total - total_val) > 1.0:
                cross_field_conflict = True
                cross_field_error = f"net({net_val}) + vat({vat_val}) = {calculated_total} != total({total_val})"
        except ValueError:
            pass

    fields = {
        "invoice_number": invoice_number,
        "invoice_date": _normalize_date(invoice_date) if invoice_date else "",
        "vendor_name": vendor_name,
        "seller_name": seller_name,
        "buyer_name": buyer_name,
        "seller_tax_id": party_info["seller_tax_id"],
        "buyer_tax_id": party_info["buyer_tax_id"],
        "net_amount": net_amount,
        "vat_amount": vat_amount,
        "vat_rate": vat_rate,
        "total_amount": total_amount,
        "wht_rate": wht_rate,
        "wht_amount": wht_amount,
        "amount_paid": amount_paid,
        "cross_field_conflict": cross_field_conflict,
        "cross_field_error": cross_field_error,
        "source_text": raw_text,
    }

    seller_name_conf = 0.35
    if fields["seller_name"]:
        seller_name_conf = (
            0.9
            if _looks_like_company_name(fields["seller_name"])
            and not _looks_like_noise_party_name(fields["seller_name"])
            else 0.45
        )

    buyer_name_conf = 0.35
    if fields["buyer_name"]:
        buyer_name_conf = (
            0.9
            if _looks_like_company_name(fields["buyer_name"])
            and not _looks_like_noise_party_name(fields["buyer_name"])
            else 0.45
        )

    # VAT amount confidence: high if present, but flag for review if VAT context exists but amount is 0
    vat_amount_conf = 0.3
    if fields["vat_amount"]:
        vat_amount_conf = 0.9
    elif _has_vat_context(raw_text):
        # VAT context present but amount not extracted: flag for human review
        vat_amount_conf = 0.4
    
    # Net amount confidence: high if present, lower if only inferred from VAT context
    net_amount_conf = 0.3
    if fields["net_amount"]:
        net_amount_conf = 0.9
    elif fields["vat_amount"] and fields["total_amount"]:
        net_amount_conf = 0.6  # Can be inferred from vat + total
    
    vat_rate_conf = 0.3
    if fields["vat_rate"]:
        vat_rate_conf = 0.9 if fields["vat_amount"] else 0.6

    confidence = {
        "invoice_number": 0.95 if fields["invoice_number"] else 0.35,
        "invoice_date": 0.95 if fields["invoice_date"] else 0.35,
        "vendor_name": 0.9 if fields["vendor_name"] else 0.4,
        "seller_name": seller_name_conf,
        "buyer_name": buyer_name_conf,
        "seller_tax_id": 0.95 if fields["seller_tax_id"] else 0.3,
        "buyer_tax_id": 0.95 if fields["buyer_tax_id"] else 0.3,
        "net_amount": net_amount_conf,
        "vat_amount": vat_amount_conf,
        "vat_rate": vat_rate_conf,
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
    alt_pass_text = "\n".join(
        line.strip() for line in raw_text.splitlines() if line.strip()
    )
    alt_result = _extract_with_rules(alt_pass_text)
    agreement_score = _multi_pass_agreement(rule_result["fields"], alt_result["fields"])
    rule_result["fields"]["doc_type"] = _infer_doc_type(raw_text)

    optional_expected = {
        "wht_rate": _has_wht_context(raw_text),
        "wht_amount": _has_wht_context(raw_text),
        "amount_paid": _has_paid_context(raw_text),
    }
    low_conf_fields: list[str] = []
    for key, value in rule_result["confidence"].items():
        if float(value) >= 0.8:
            continue
        if key in optional_expected and not optional_expected[key]:
            continue
        low_conf_fields.append(key)

    if agreement_score < 0.5 and "agreement_score" not in low_conf_fields:
        low_conf_fields.append("agreement_score")

    ocr_conf = float(ocr_output.get("avg_confidence", 0.0))
    page_count = int(ocr_output.get("page_count", 1))
    rule_conflict = agreement_score < 0.5

    seller_tax_id = str(rule_result["fields"].get("seller_tax_id") or "").strip()
    stage_c_triggers = {
        "template_unknown": bool(seller_tax_id not in KNOWN_TEMPLATE_TAX_IDS),
        "field_confidence_low": bool(low_conf_fields),
        "rule_conflict": bool(rule_conflict),
        "variable_account_needed": False,
    }
    stage_c_reasons = [
        key for key, triggered in stage_c_triggers.items() if triggered
    ]
    stage_c = {
        "triggered": bool(stage_c_reasons),
        "reasons": stage_c_reasons,
        "recommended_route": "rule_extractor" if stage_c_reasons else "standard_pipeline",
    }

    escalate = should_escalate_to_sonnet(
        page_count=page_count,
        ocr_confidence=ocr_conf,
        low_confidence_fields=len(low_conf_fields),
        rule_conflict=rule_conflict,
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
        "stage_c": stage_c,
        "cache_hit": False,
        "meta": {
            "escalated_to_sonnet": escalate,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_thb": cost_thb,
            "ocr_confidence": ocr_conf,
            "page_count": page_count,
            "agreement_score": agreement_score,
            "optional_fields_expected": optional_expected,
            "triggers": stage_c_triggers,
            "decision": stage_c,
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
