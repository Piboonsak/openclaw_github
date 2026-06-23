"""Schema Analyzer — auto-detect template structure from a sample CSV/Excel file.

Analyzes an uploaded file to infer:
- Column headers → LF internal field mapping (with confidence scores)
- Data types and suggested transforms (pad_left, thai_date_short, etc.)
- Template mode (Flat Document vs Flatten Row)
- File encoding (TIS-620 vs UTF-8)

Strategy:
  1. Structural analysis (pure Python, no LLM) — covers ~90% of cases
  2. LLM fallback (claude-haiku-4-5) only for ambiguous column headers (<70% similarity)

Task: TASK-1009
Spec: docs/requirement/phaseII/epic-10/EPIC-10-TASKS-DETAIL.md#task-1009
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Thai column header → LF field alias table
# Covers headers found in the 6 Express Accounting import templates
# ---------------------------------------------------------------------------
_FIELD_ALIASES: dict[str, list[str]] = {
    "row_sequence":           ["ลำดับ", "ลำดับที่", "sequence", "no.", "no"],
    "invoice_date":           ["วันที่", "ว/ด/ป", "date"],
    "voucher_date":           ["วันที่เอกสาร", "voucher date"],
    "document_number":        ["เลขที่เอกสาร", "document no.", "document no", "doc no"],
    "invoice_number":         ["เลขที่ใบกำกับภาษี", "tax invoice no.", "tax invoice no"],
    "net_amount":             ["จำนวนเงินก่อนภาษี", "ก่อนภาษี", "amount before tax"],
    "total_amount":           ["จำนวนเงินรวมภาษี", "รวมภาษี", "amount including tax"],
    "description":            ["คำอธิบาย", "รายละเอียด", "description"],
    "transaction_desc":       ["คำอธิบายรายการ", "transaction description"],
    "vendor_code":            ["รหัสผู้จำหน่าย", "vendor code"],
    "vendor_name":            ["ชื่อผู้จำหน่าย", "vendor name"],
    "customer_code":          ["รหัสลูกค้า", "customer code"],
    "customer_name":          ["ชื่อลูกค้า", "customer name"],
    "account_code":           ["รหัสบัญชี", "account code"],
    "posting_account_code":   ["รหัสลงบัญชี", "posting account code"],
    "formula_doc_number":     ["เลขที่เอกสาร(สูตร)", "formula doc no."],
    "book_code":              ["สมุด", "book code"],
    "debit":                  ["เดบิต", "dr", "debit"],
    "credit":                 ["เครดิต", "cr", "credit"],
    "voucher_no":             ["voucher_no", "voucher no", "เลขที่เอกสาร"],
}

# Confidence threshold below which we add a warning and require user confirmation
_LOW_CONFIDENCE_THRESHOLD = 0.80

# Regex patterns for structural type inference
_RE_PADDED_CODE = re.compile(r"^0\d+$")               # leading zero → pad_left candidate
_RE_DATE_SHORT  = re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$")   # DD/MM/YY
_RE_DATE_FULL   = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")   # D/M/YYYY


# ---------------------------------------------------------------------------
# Data classes for the API response (AnalysisResult)
# ---------------------------------------------------------------------------

@dataclass
class ColumnAnalysis:
    position: int
    original_header: str
    lf_field: Optional[str]
    confidence: float
    data_type: str                   # "string" | "number" | "date"
    suggested_transform: Optional[str]
    match_method: str                # "alias_table" | "fuzzy" | "llm" | "unmatched"
    sample_values: list[str] = field(default_factory=list)


@dataclass
class AnalysisWarning:
    column: str
    message: str
    alternatives: list[str] = field(default_factory=list)


@dataclass
class DataProfile:
    date_format_detected: Optional[str]
    debit_credit_balanced: Optional[bool]
    null_rate_by_column: dict[str, float] = field(default_factory=dict)


@dataclass
class AnalysisResult:
    filename: str
    rows_detected: int
    encoding_detected: str
    file_size_kb: float
    suggested_template_mode: str     # "flat_document" | "flatten_row"
    suggested_row_source: str        # "documents" | "journal_lines"
    suggested_encoding: str
    columns: list[ColumnAnalysis] = field(default_factory=list)
    warnings: list[AnalysisWarning] = field(default_factory=list)
    data_profile: Optional[DataProfile] = None


# ---------------------------------------------------------------------------
# Encoding detection
# ---------------------------------------------------------------------------

def detect_encoding(raw_bytes: bytes) -> str:
    """Return 'tis-620' or 'utf-8' based on byte-level heuristics.

    Uses chardet when available; falls back to a simple Thai byte-range check.
    TIS-620 Thai characters live in 0xA1-0xFB; UTF-8 Thai is 3-byte sequences.
    """
    try:
        import chardet
        result = chardet.detect(raw_bytes[:4096])
        encoding = (result.get("encoding") or "utf-8").lower()
        if "tis" in encoding or "874" in encoding or "cp874" in encoding:
            return "tis-620"
        return "utf-8"
    except ImportError:
        # Fallback: if any byte is in TIS-620 Thai range (0xA1-0xFB) → tis-620
        thai_bytes = sum(1 for b in raw_bytes[:2000] if 0xA1 <= b <= 0xFB)
        return "tis-620" if thai_bytes > 5 else "utf-8"


# ---------------------------------------------------------------------------
# Column matching — alias table lookup (Strategy A)
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return text.strip().lower().replace("_", " ").replace("-", " ")


def match_column_by_alias(header: str) -> tuple[Optional[str], float, str]:
    """Return (lf_field, confidence, method) for a given header string.

    Tries exact alias table match first, then simple substring containment.
    Returns (None, 0.0, 'unmatched') when no match found.
    """
    norm = _normalize(header)
    for lf_field, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if _normalize(alias) == norm:
                return lf_field, 0.98, "alias_table"
    # Substring containment (lower confidence)
    for lf_field, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if _normalize(alias) in norm or norm in _normalize(alias):
                return lf_field, 0.72, "alias_table"
    return None, 0.0, "unmatched"


# ---------------------------------------------------------------------------
# Structural type + transform inference
# ---------------------------------------------------------------------------

def infer_type_and_transform(
    samples: list[str],
) -> tuple[str, Optional[str]]:
    """Infer data_type and suggested_transform from sample values.

    Returns (data_type, transform | None).
    """
    non_empty = [s for s in samples if s.strip()]
    if not non_empty:
        return "string", None

    # Date detection
    if all(_RE_DATE_SHORT.match(s) for s in non_empty):
        return "date", "thai_date_short"
    if all(_RE_DATE_FULL.match(s) for s in non_empty):
        return "date", "thai_date_full"

    # Numeric (with optional comma thousands separator)
    numeric_re = re.compile(r"^-?[\d,]+(\.\d+)?$")
    if all(numeric_re.match(s) for s in non_empty):
        return "number", None

    # Zero-padded code → pad_left
    max_len = max(len(s) for s in non_empty)
    if all(_RE_PADDED_CODE.match(s) for s in non_empty) and max_len >= 4:
        return "string", f"pad_left:{max_len}:0"

    return "string", None


# ---------------------------------------------------------------------------
# Template mode detection
# ---------------------------------------------------------------------------

def detect_template_mode(rows: list[list[str]]) -> tuple[str, str]:
    """Return (template_mode, row_source) by inspecting the first column.

    If the first column has repeated values → multiple rows per document
    → Flatten Row + journal_lines.  Otherwise → Flat Document + documents.
    """
    if not rows:
        return "flat_document", "documents"
    first_col = [r[0] for r in rows if r]
    unique_ratio = len(set(first_col)) / len(first_col) if first_col else 1.0
    if unique_ratio < 0.9:
        return "flatten_row", "journal_lines"
    return "flat_document", "documents"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def analyze_csv(
    content: bytes,
    filename: str = "upload.csv",
) -> AnalysisResult:
    """Parse a raw CSV file and return an AnalysisResult.

    This is the primary analysis path.  Excel (.xlsx) support will be added
    in a follow-up using openpyxl (see TASK-1009 acceptance criteria).
    """
    encoding = detect_encoding(content)
    try:
        text = content.decode(encoding, errors="replace")
    except LookupError:
        text = content.decode("utf-8", errors="replace")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return AnalysisResult(
            filename=filename,
            rows_detected=0,
            encoding_detected=encoding,
            file_size_kb=round(len(content) / 1024, 1),
            suggested_template_mode="flat_document",
            suggested_row_source="documents",
            suggested_encoding=encoding,
        )

    headers = rows[0]
    data_rows = rows[1:]
    template_mode, row_source = detect_template_mode(data_rows)

    columns: list[ColumnAnalysis] = []
    warnings: list[AnalysisWarning] = []

    for i, header in enumerate(headers):
        samples = [r[i] for r in data_rows if i < len(r)][:20]
        lf_field, confidence, method = match_column_by_alias(header)
        data_type, transform = infer_type_and_transform(samples)

        col = ColumnAnalysis(
            position=i + 1,
            original_header=header,
            lf_field=lf_field,
            confidence=confidence,
            data_type=data_type,
            suggested_transform=transform,
            match_method=method,
            sample_values=samples[:5],
        )
        columns.append(col)

        if confidence < _LOW_CONFIDENCE_THRESHOLD:
            warnings.append(AnalysisWarning(
                column=header,
                message="Low confidence match — please confirm LF field",
                alternatives=[lf_field] if lf_field else [],
            ))

    return AnalysisResult(
        filename=filename,
        rows_detected=len(data_rows),
        encoding_detected=encoding,
        file_size_kb=round(len(content) / 1024, 1),
        suggested_template_mode=template_mode,
        suggested_row_source=row_source,
        suggested_encoding=encoding,
        columns=columns,
        warnings=warnings,
    )
