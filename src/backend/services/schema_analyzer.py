"""Schema Analyzer — auto-detect template structure from a sample CSV/Excel file.

Analyzes an uploaded file to infer:
- Column headers → LF internal field mapping (with confidence scores)
- Data types and suggested transforms (pad_left, thai_date_short, etc.)
- Template mode (Flat Document vs Flatten Row)
- File encoding (TIS-620 vs UTF-8)

Strategy:
  1. Structural analysis (pure Python, no LLM) — covers ~90% of cases
  2. LLM fallback is intentionally omitted: low-confidence columns produce warnings
     that the user must confirm in the Template Configurator UI.

Task: TASK-1009
Spec: docs/requirement/phaseII/epic-10/EPIC-10-TASKS-DETAIL.md#task-1009
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
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

# Regex patterns for structural type inference — order matters in infer_type_and_transform
_RE_PADDED_CODE = re.compile(r"^0\d+$")              # leading zero → pad_left candidate
_RE_DATE_SHORT  = re.compile(r"^\d{1,2}/\d{1,2}/\d{2}$")   # DD/MM/YY (thai short)
_RE_DATE_FULL   = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")   # D/M/YYYY
_RE_NUMERIC     = re.compile(r"^-?[\d,]+(\.\d+)?$")         # numbers with optional comma separator


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
    unique_account_codes: Optional[int]
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
        pass
    # Fallback without chardet: UTF-8 is strictly self-validating.
    # TIS-620 single-byte Thai values (0xA1-0xFB) are invalid UTF-8 continuation
    # bytes when not preceded by a lead byte, so strict decode catches them.
    # Note: pure byte-range counting is unreliable because UTF-8 Thai sequences
    # also contain bytes in 0xA1-0xFB (e.g., 0xE0 0xB8 0xA7 for ว).
    try:
        raw_bytes[:4096].decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "tis-620"


# ---------------------------------------------------------------------------
# Column matching — alias table lookup
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    return text.strip().lower().replace("_", " ").replace("-", " ")


def match_column_by_alias(header: str) -> tuple[Optional[str], float, str]:
    """Return (lf_field, confidence, method) for a given header string.

    Tries exact alias table match first (0.98), then substring containment (0.72).
    Returns (None, 0.0, 'unmatched') when no match found.
    """
    norm = _normalize(header)
    for lf_field, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            if _normalize(alias) == norm:
                return lf_field, 0.98, "alias_table"
    # Substring containment (lower confidence).
    # Require alias length >= 4 to prevent short tokens like "no", "dr", "cr"
    # from matching inside unrelated column names (e.g., "unknown" contains "no").
    for lf_field, aliases in _FIELD_ALIASES.items():
        for alias in aliases:
            norm_alias = _normalize(alias)
            if len(norm_alias) >= 4 and (norm_alias in norm or norm in norm_alias):
                return lf_field, 0.72, "alias_table"
    return None, 0.0, "unmatched"


# ---------------------------------------------------------------------------
# Structural type + transform inference
# CRITICAL: padded check must come BEFORE numeric — "05100" passes numeric regex
# ---------------------------------------------------------------------------

def infer_type_and_transform(samples: list[str]) -> tuple[str, Optional[str]]:
    """Infer data_type and suggested_transform from sample values.

    Returns (data_type, transform | None).
    """
    non_empty = [s for s in samples if s.strip()]
    if not non_empty:
        return "string", None

    # 1. Date detection (highest priority — precedes all numeric checks)
    if all(_RE_DATE_SHORT.match(s) for s in non_empty):
        return "date", "thai_date_short"
    if all(_RE_DATE_FULL.match(s) for s in non_empty):
        return "date", "thai_date_full"

    # 2. Zero-padded code: check BEFORE numeric so "05100" → pad_left, not number
    max_len = max(len(s) for s in non_empty)
    if all(_RE_PADDED_CODE.match(s) for s in non_empty) and max_len >= 4:
        return "string", f"pad_left:{max_len}:0"

    # 3. Numeric (only after padded check passes)
    if all(_RE_NUMERIC.match(s) for s in non_empty):
        return "number", None

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
# CSV delimiter detection
# ---------------------------------------------------------------------------

def _detect_csv_delimiter(text: str) -> str:
    """Sniff CSV delimiter; default to comma if ambiguous."""
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        return ","


# ---------------------------------------------------------------------------
# Data profile computation
# ---------------------------------------------------------------------------

def _compute_data_profile(
    columns: list[ColumnAnalysis],
    data_rows: list[list[str]],
) -> DataProfile:
    """Compute null rates, date format, debit/credit balance, and unique account codes."""
    total = len(data_rows)

    # Null rate per column
    null_rates: dict[str, float] = {}
    for col in columns:
        idx = col.position - 1
        if total:
            nulls = sum(1 for r in data_rows if idx >= len(r) or not r[idx].strip())
            null_rates[col.original_header] = round(nulls / total, 4)

    # Date format from first date column
    date_fmt: Optional[str] = None
    for col in columns:
        if col.data_type == "date" and col.suggested_transform:
            date_fmt = "DD/MM/YY" if col.suggested_transform == "thai_date_short" else "DD/MM/YYYY"
            break

    # Debit/credit balance check
    balanced: Optional[bool] = None
    debit_idx = credit_idx = None
    for col in columns:
        if col.lf_field == "debit":
            debit_idx = col.position - 1
        elif col.lf_field == "credit":
            credit_idx = col.position - 1

    if debit_idx is not None and credit_idx is not None and total:
        def _parse(s: str) -> float:
            try:
                return float(s.replace(",", ""))
            except ValueError:
                return 0.0

        total_debit  = sum(_parse(r[debit_idx])  for r in data_rows if debit_idx < len(r))
        total_credit = sum(_parse(r[credit_idx]) for r in data_rows if credit_idx < len(r))
        balanced = abs(total_debit - total_credit) < 0.01

    # Unique account codes
    unique_codes: Optional[int] = None
    for col in columns:
        if col.lf_field in ("account_code", "posting_account_code"):
            idx = col.position - 1
            values = {r[idx].strip() for r in data_rows if idx < len(r) and r[idx].strip()}
            unique_codes = len(values)
            break

    return DataProfile(
        date_format_detected=date_fmt,
        debit_credit_balanced=balanced,
        unique_account_codes=unique_codes,
        null_rate_by_column=null_rates,
    )


# ---------------------------------------------------------------------------
# Shared result builder (used by both CSV and Excel parsers)
# ---------------------------------------------------------------------------

def _build_result(
    headers: list[str],
    data_rows: list[list[str]],
    encoding: str,
    filename: str,
    file_size_bytes: int,
) -> AnalysisResult:
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

    data_profile = _compute_data_profile(columns, data_rows)

    return AnalysisResult(
        filename=filename,
        rows_detected=len(data_rows),
        encoding_detected=encoding,
        file_size_kb=round(file_size_bytes / 1024, 1),
        suggested_template_mode=template_mode,
        suggested_row_source=row_source,
        suggested_encoding=encoding,
        columns=columns,
        warnings=warnings,
        data_profile=data_profile,
    )


# ---------------------------------------------------------------------------
# Public parsers
# ---------------------------------------------------------------------------

def analyze_csv(content: bytes, filename: str = "upload.csv") -> AnalysisResult:
    """Parse a raw CSV file (comma or semicolon delimited) and return AnalysisResult."""
    encoding = detect_encoding(content)
    try:
        text = content.decode(encoding, errors="replace")
    except LookupError:
        text = content.decode("utf-8", errors="replace")

    delimiter = _detect_csv_delimiter(text)
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
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
    return _build_result(headers, data_rows, encoding, filename, len(content))


def analyze_excel(content: bytes, filename: str = "upload.xlsx") -> AnalysisResult:
    """Parse an Excel (.xlsx) file using openpyxl (sheet 0) and return AnalysisResult."""
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("openpyxl is required for Excel parsing: pip install openpyxl")

    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    ws = wb.worksheets[0]

    rows_raw: list[list[str]] = []
    for row in ws.iter_rows(values_only=True):
        rows_raw.append([("" if v is None else str(v)) for v in row])

    wb.close()

    if not rows_raw:
        return AnalysisResult(
            filename=filename,
            rows_detected=0,
            encoding_detected="utf-8",
            file_size_kb=round(len(content) / 1024, 1),
            suggested_template_mode="flat_document",
            suggested_row_source="documents",
            suggested_encoding="utf-8",
        )

    headers = rows_raw[0]
    data_rows = rows_raw[1:]
    # Excel files are always decoded as Unicode; report utf-8
    return _build_result(headers, data_rows, "utf-8", filename, len(content))


def analyze_file(content: bytes, filename: str) -> AnalysisResult:
    """Dispatch to CSV or Excel parser based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext in (".xlsx", ".xls"):
        return analyze_excel(content, filename)
    return analyze_csv(content, filename)
