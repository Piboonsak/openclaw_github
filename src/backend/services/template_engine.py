"""Template Engine — render document data into formatted CSV/Excel output.

Maps source fields (extraction data, journal data, computed fields) to output
columns per a template definition. Supports 8 transforms, configurable
CSV/Excel output, TIS-620/UTF-8/UTF-8-BOM encoding, and date-as-text
behavior for Express Accounting compatibility.

Task: TASK-1001
Spec: docs/requirement/phaseII/epic-10/EPIC-10-TASKS-DETAIL.md#task-1001
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

import xlsxwriter


# ---------------------------------------------------------------------------
# Column definition
# ---------------------------------------------------------------------------

@dataclass
class ColumnDef:
    """Defines one output column in a template."""

    source_field: str
    header_label: str
    data_type: str = "string"          # "string" | "number" | "date"
    format_pattern: Optional[str] = None
    default_value: Optional[str] = None
    transform: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ColumnDef":
        return cls(
            source_field=d["source_field"],
            header_label=d["header_label"],
            data_type=d.get("data_type", "string"),
            format_pattern=d.get("format_pattern"),
            default_value=d.get("default_value"),
            transform=d.get("transform"),
        )


# ---------------------------------------------------------------------------
# Express Transaction field aliases
# Allow templates to use semantic aliases that map to extraction/journal fields
# ---------------------------------------------------------------------------

_FIELD_ALIASES: dict[str, str] = {
    "amount_before_tax":    "net_amount",
    "amount_including_tax": "total_amount",
    "tax_invoice_number":   "invoice_number",
    "transaction_desc":     "description",
}

# Product fields deferred to TASK-1013 — return default gracefully
_PRODUCT_FIELDS = frozenset({
    "product_code", "product_name", "product_unit", "product_unit_price",
})


# ---------------------------------------------------------------------------
# Date parsing helpers
# ---------------------------------------------------------------------------

_RE_ISO   = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_RE_FULL  = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$")
_RE_SHORT = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{2})$")


def _parse_ce_date(value: str) -> Optional[date]:
    """Parse a date string (ISO, CE, or BE) and return a CE date object.

    Handles:
    - YYYY-MM-DD (ISO / CE)
    - DD/MM/YYYY (CE or BE — year > 2400 → BE, subtract 543)
    - DD/MM/YY   (Thai short: YY interpreted as BE 25YY)
    """
    s = value.strip()
    if m := _RE_ISO.match(s):
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    if m := _RE_FULL.match(s):
        year = int(m[3])
        if year > 2400:
            year -= 543
        try:
            return date(year, int(m[2]), int(m[1]))
        except ValueError:
            return None
    if m := _RE_SHORT.match(s):
        yy = int(m[3])
        be_year = 2500 + yy
        try:
            return date(be_year - 543, int(m[2]), int(m[1]))
        except ValueError:
            return None
    return None


def _to_thai_date_short(value: str) -> str:
    """ISO / CE / BE date → DD/MM/YY (พ.ศ. 2-digit year).

    Example: "2026-05-01" → "01/05/69"
    """
    d = _parse_ce_date(value)
    if d is None:
        return value
    be_year = d.year + 543
    return f"{d.day:02d}/{d.month:02d}/{be_year % 100:02d}"


def _to_thai_date_full(value: str) -> str:
    """ISO / CE / BE date → D/M/YYYY (พ.ศ. 4-digit year).

    Example: "2026-05-01" → "1/5/2569"
    """
    d = _parse_ce_date(value)
    if d is None:
        return value
    be_year = d.year + 543
    return f"{d.day}/{d.month}/{be_year}"


# ---------------------------------------------------------------------------
# Document number pattern renderer
# ---------------------------------------------------------------------------

def _apply_doc_number(pattern: str, record: dict[str, Any]) -> str:
    """Render a document number from a pattern using date + row_sequence.

    Token rules:
    - YYMM         → Thai BE year 2-digit + month 2-digit (e.g., "6905")
    - N+ (NNN)     → row_sequence zero-padded to match N count
    - #+  (######) → row_sequence zero-padded to match # count
    """
    date_str = str(record.get("voucher_date") or record.get("invoice_date") or "")
    ce_date = _parse_ce_date(date_str) if date_str else None
    seq = int(record.get("row_sequence", 1))

    result = pattern
    if ce_date:
        be_yy = (ce_date.year + 543) % 100
        result = result.replace("YYMM", f"{be_yy:02d}{ce_date.month:02d}")

    result = re.sub(r"N+", lambda m: str(seq).zfill(len(m.group())), result)
    result = re.sub(r"#+", lambda m: str(seq).zfill(len(m.group())), result)
    return result


# ---------------------------------------------------------------------------
# Template Engine
# ---------------------------------------------------------------------------

class TemplateEngine:
    """Core column-mapping and output engine for template-driven CSV/Excel export.

    Usage::

        engine = TemplateEngine(columns=[...], encoding="tis-620")
        headers, rows = engine.render(records)
        csv_bytes = engine.write_csv(headers, rows, engine.columns)
    """

    def __init__(
        self,
        columns: list[ColumnDef],
        encoding: str = "utf-8",
        delimiter: str = ",",
        file_format: str = "csv",
    ) -> None:
        self.columns = columns
        self.encoding = encoding.lower()
        self.delimiter = delimiter
        self.file_format = file_format

    # ── Public API ────────────────────────────────────────────────────────────

    def render(
        self,
        records: list[dict[str, Any]],
        column_overrides: Optional[list[ColumnDef]] = None,
    ) -> tuple[list[str], list[list[str]]]:
        """Render records into (headers, data_rows).

        Each record is a flat dict {source_field: value}.
        `row_sequence` is injected automatically (1-based per call).
        `column_overrides` replaces self.columns for this render only (per-run
        Export page adjustments from ExportColumnState).
        """
        cols = column_overrides or self.columns
        headers = [col.header_label for col in cols]
        rows: list[list[str]] = []
        for seq_num, record in enumerate(records, 1):
            augmented = {**record, "row_sequence": str(seq_num)}
            row = [
                self.apply_transform(
                    self._resolve_field(augmented, col.source_field, col.default_value),
                    col.transform,
                    augmented,
                )
                for col in cols
            ]
            rows.append(row)
        return headers, rows

    def apply_transform(
        self,
        value: str,
        transform: Optional[str],
        record: Optional[dict[str, Any]] = None,
    ) -> str:
        """Apply a single named transform to value.

        Supported transforms:
        - uppercase
        - pad_left:N:CHAR   (e.g., pad_left:5:0)
        - thai_date          → D/M/YYYY BE (same as thai_date_full)
        - thai_date_short    → DD/MM/YY BE
        - thai_date_full     → D/M/YYYY BE
        - strip_dash
        - prefix:STR         (e.g., prefix:OE)
        - doc_number:PATTERN (e.g., doc_number:YYMM/NNN)
        """
        if not transform:
            return value
        record = record or {}

        if transform == "uppercase":
            return value.upper()

        if transform.startswith("pad_left:"):
            parts = transform.split(":")
            try:
                length = int(parts[1])
                pad_char = parts[2] if len(parts) > 2 else "0"
                return value.rjust(length, pad_char)
            except (IndexError, ValueError):
                return value

        if transform in ("thai_date", "thai_date_full"):
            return _to_thai_date_full(value)

        if transform == "thai_date_short":
            return _to_thai_date_short(value)

        if transform == "strip_dash":
            return value.replace("-", "")

        if transform.startswith("prefix:"):
            return transform[7:] + value

        if transform.startswith("doc_number:"):
            pattern = transform[11:]
            return _apply_doc_number(pattern, record)

        return value

    def resolve_field(
        self,
        record: dict[str, Any],
        source_field: str,
        default_value: Optional[str] = None,
    ) -> str:
        """Public wrapper for field resolution (for testing/external use)."""
        return self._resolve_field(record, source_field, default_value)

    def write_csv(
        self,
        headers: list[str],
        rows: list[list[str]],
        columns: Optional[list[ColumnDef]] = None,
        date_as_excel_text: bool = True,
    ) -> bytes:
        """Return CSV bytes with configured encoding and delimiter.

        When date_as_excel_text=True (default), date column values are wrapped
        as ='DD/MM/YY' so Excel treats them as text formulas and does NOT
        auto-convert to date objects. This is critical for Express Accounting
        compatibility (see CLIENT-TEMPLATE-ANALYSIS.md §3).
        """
        date_indices: set[int] = set()
        if date_as_excel_text and columns:
            for i, col in enumerate(columns):
                if col.data_type == "date":
                    date_indices.add(i)

        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=self.delimiter)
        writer.writerow(headers)
        for row in rows:
            out_row: list[str] = []
            for i, cell in enumerate(row):
                if i in date_indices and cell:
                    out_row.append(f'="{cell}"')
                else:
                    out_row.append(cell)
            writer.writerow(out_row)

        text = buf.getvalue()
        enc = self.encoding
        if enc in ("tis-620", "cp874"):
            return text.encode("cp874", errors="replace")
        if enc == "utf-8-bom":
            return text.encode("utf-8-sig")
        return text.encode("utf-8")

    def write_excel(
        self,
        headers: list[str],
        rows: list[list[str]],
        columns: Optional[list[ColumnDef]] = None,
    ) -> bytes:
        """Return Excel bytes using xlsxwriter with styled headers.

        Date columns use `@` (text) cell format so DD/MM/YY strings are never
        auto-converted by Excel.  Number columns use #,##0.00 formatting.
        """
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {"in_memory": True})
        ws = wb.add_worksheet("Export")

        header_fmt = wb.add_format({
            "bold": True,
            "bg_color": "#1F4E78",
            "font_color": "#FFFFFF",
            "border": 1,
            "align": "center",
            "valign": "vcenter",
        })
        text_fmt   = wb.add_format({"num_format": "@"})
        number_fmt = wb.add_format({"num_format": "#,##0.00"})

        # Build per-column format list
        col_fmts: list[Any] = []
        if columns:
            for col in columns:
                if col.data_type == "date":
                    col_fmts.append(text_fmt)
                elif col.data_type == "number":
                    col_fmts.append(number_fmt)
                else:
                    col_fmts.append(None)
        else:
            col_fmts = [None] * len(headers)

        # Write header row
        for j, h in enumerate(headers):
            ws.write(0, j, h, header_fmt)

        # Write data rows
        for i, row in enumerate(rows, 1):
            for j, cell in enumerate(row):
                fmt = col_fmts[j] if j < len(col_fmts) else None
                if fmt is number_fmt:
                    try:
                        ws.write_number(i, j, float(cell.replace(",", "")), fmt)
                        continue
                    except (ValueError, AttributeError):
                        pass
                ws.write(i, j, cell, fmt)

        wb.close()
        buf.seek(0)
        return buf.getvalue()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _resolve_field(
        self,
        record: dict[str, Any],
        source_field: str,
        default_value: Optional[str],
    ) -> str:
        """Return string value for source_field from record, with fallbacks.

        Resolution order:
        1. Direct key in record
        2. Express Transaction field alias
        3. Product fields (TASK-1013) — graceful empty until resolver is wired
        4. default_value or ""
        """
        if source_field in record and record[source_field] is not None:
            return str(record[source_field])

        alias = _FIELD_ALIASES.get(source_field)
        if alias and alias in record and record[alias] is not None:
            return str(record[alias])

        if source_field in _PRODUCT_FIELDS:
            return default_value if default_value is not None else ""

        return default_value if default_value is not None else ""
