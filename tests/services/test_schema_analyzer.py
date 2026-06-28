"""Unit tests for src/backend/services/schema_analyzer.py

Covers all TASK-1009 acceptance criteria:
  ac_1009_upload   — CSV and Excel files parse without error
  ac_1009_encoding — TIS-620 and UTF-8 files both handled
  ac_1009_type_date    — DD/MM/YY → date + thai_date_short
  ac_1009_type_padded  — "05100" → string + pad_left:5:0 (NOT number)
  ac_1009_thai_header  — Thai headers → correct LF fields
  ac_1009_confidence   — unmatched columns produce warnings
  ac_1009_mode         — double-entry data → flatten_row suggested
  ac_1009_profile      — data_profile: date_format, balance, unique codes, null rates
"""

from __future__ import annotations

import io
import csv
import unittest

from src.backend.services.schema_analyzer import (
    AnalysisResult,
    analyze_csv,
    analyze_excel,
    detect_encoding,
    detect_template_mode,
    infer_type_and_transform,
    match_column_by_alias,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _csv_bytes(headers: list[str], rows: list[list[str]], encoding: str = "utf-8", delimiter: str = ",") -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=delimiter)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode(encoding, errors="replace")


def _xlsx_bytes(headers: list[str], rows: list[list]) -> bytes:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# detect_encoding
# ---------------------------------------------------------------------------

class TestDetectEncoding(unittest.TestCase):
    def test_utf8_ascii_detected(self):
        content = b"header,value\n1,2\n"
        self.assertEqual(detect_encoding(content), "utf-8")

    def test_tis620_detected_via_byte_range(self):
        # Thai characters in TIS-620 range 0xA1-0xFB: ว=0xC7, ั=0xD1, น=0xB9, ท=0xB7, ี=0xD5, ่=0xE8
        thai_bytes = bytes([0xC7, 0xD1, 0xB9, 0xB7, 0xD5, 0xE8, 0xC7, 0xD1, 0xB9])
        self.assertEqual(detect_encoding(thai_bytes), "tis-620")

    def test_encoding_on_cp874_csv(self):
        content = _csv_bytes(["วันที่", "รหัสบัญชี"], [["04/05/69", "1001"]], encoding="cp874")
        result = detect_encoding(content)
        self.assertEqual(result, "tis-620")


# ---------------------------------------------------------------------------
# match_column_by_alias
# ---------------------------------------------------------------------------

class TestMatchColumnByAlias(unittest.TestCase):
    def test_exact_thai_date(self):
        lf_field, conf, method = match_column_by_alias("วันที่")
        self.assertEqual(lf_field, "invoice_date")
        self.assertGreaterEqual(conf, 0.95)
        self.assertEqual(method, "alias_table")

    def test_exact_thai_account_code(self):
        lf_field, conf, _ = match_column_by_alias("รหัสบัญชี")
        self.assertEqual(lf_field, "account_code")
        self.assertGreaterEqual(conf, 0.95)

    def test_exact_thai_debit(self):
        lf_field, conf, _ = match_column_by_alias("เดบิต")
        self.assertEqual(lf_field, "debit")
        self.assertGreaterEqual(conf, 0.95)

    def test_exact_thai_credit(self):
        lf_field, conf, _ = match_column_by_alias("เครดิต")
        self.assertEqual(lf_field, "credit")
        self.assertGreaterEqual(conf, 0.95)

    def test_english_exact_match(self):
        lf_field, conf, _ = match_column_by_alias("description")
        self.assertEqual(lf_field, "description")
        self.assertGreaterEqual(conf, 0.95)

    def test_unmatched_returns_none(self):
        # Use a string that shares no alias exact match or 4-char substring
        lf_field, conf, method = match_column_by_alias("ZZZZQQQQ9999XYZW")
        self.assertIsNone(lf_field)
        self.assertEqual(conf, 0.0)
        self.assertEqual(method, "unmatched")

    def test_case_insensitive_english(self):
        lf_field, _, _ = match_column_by_alias("DESCRIPTION")
        self.assertEqual(lf_field, "description")


# ---------------------------------------------------------------------------
# infer_type_and_transform — ac_1009_type_date, ac_1009_type_padded
# ---------------------------------------------------------------------------

class TestInferTypeAndTransform(unittest.TestCase):
    def test_date_short_thai(self):
        """ac_1009_type_date: DD/MM/YY → date + thai_date_short."""
        dtype, transform = infer_type_and_transform(["04/05/69", "05/05/69", "06/05/69"])
        self.assertEqual(dtype, "date")
        self.assertEqual(transform, "thai_date_short")

    def test_date_full(self):
        dtype, transform = infer_type_and_transform(["04/05/2026", "05/05/2026"])
        self.assertEqual(dtype, "date")
        self.assertEqual(transform, "thai_date_full")

    def test_padded_5digit_not_number(self):
        """ac_1009_type_padded: "05100" must NOT be classified as number."""
        dtype, transform = infer_type_and_transform(["05100", "05200", "05300"])
        self.assertEqual(dtype, "string")
        self.assertEqual(transform, "pad_left:5:0")

    def test_padded_4digit(self):
        dtype, transform = infer_type_and_transform(["0100", "0200", "0300"])
        self.assertEqual(dtype, "string")
        self.assertEqual(transform, "pad_left:4:0")

    def test_numeric_with_commas(self):
        dtype, transform = infer_type_and_transform(["1,000.00", "2,500.50", "3,000.00"])
        self.assertEqual(dtype, "number")
        self.assertIsNone(transform)

    def test_plain_numeric(self):
        dtype, transform = infer_type_and_transform(["5000", "3000", "8000"])
        self.assertEqual(dtype, "number")
        self.assertIsNone(transform)

    def test_string_fallback(self):
        dtype, transform = infer_type_and_transform(["ABC", "DEF", "GHI"])
        self.assertEqual(dtype, "string")
        self.assertIsNone(transform)

    def test_empty_samples(self):
        dtype, transform = infer_type_and_transform([])
        self.assertEqual(dtype, "string")
        self.assertIsNone(transform)

    def test_all_empty_strings(self):
        dtype, transform = infer_type_and_transform(["", "  ", ""])
        self.assertEqual(dtype, "string")
        self.assertIsNone(transform)


# ---------------------------------------------------------------------------
# detect_template_mode — ac_1009_mode
# ---------------------------------------------------------------------------

class TestDetectTemplateMode(unittest.TestCase):
    def test_flat_document_all_unique(self):
        rows = [["DOC001", "data"], ["DOC002", "data"], ["DOC003", "data"]]
        mode, source = detect_template_mode(rows)
        self.assertEqual(mode, "flat_document")
        self.assertEqual(source, "documents")

    def test_flatten_row_repeated_first_col(self):
        """ac_1009_mode: same voucher number repeated → flatten_row + journal_lines."""
        rows = [["DOC001", "data"]] * 5 + [["DOC002", "data"]] * 5
        mode, source = detect_template_mode(rows)
        self.assertEqual(mode, "flatten_row")
        self.assertEqual(source, "journal_lines")

    def test_empty_rows(self):
        mode, source = detect_template_mode([])
        self.assertEqual(mode, "flat_document")
        self.assertEqual(source, "documents")


# ---------------------------------------------------------------------------
# analyze_csv — integration of all structural components
# ---------------------------------------------------------------------------

class TestAnalyzeCsv(unittest.TestCase):
    def test_ac_1009_upload_csv_basic(self):
        """ac_1009_upload: CSV accepted, correct column count and row count."""
        headers = ["วันที่", "รหัสบัญชี", "คำอธิบาย", "จำนวนเงินก่อนภาษี"]
        rows = [["04/05/69", "05100", "ค่าเช่า", "10000.00"]] * 5
        result = analyze_csv(_csv_bytes(headers, rows))
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(result.rows_detected, 5)
        self.assertEqual(len(result.columns), 4)

    def test_ac_1009_encoding_tis620(self):
        """ac_1009_encoding: cp874 file detected as tis-620."""
        headers = ["วันที่", "รหัสบัญชี"]
        rows = [["04/05/69", "1001"]] * 3
        content = _csv_bytes(headers, rows, encoding="cp874")
        result = analyze_csv(content, "express.csv")
        self.assertEqual(result.encoding_detected, "tis-620")
        self.assertEqual(result.rows_detected, 3)

    def test_ac_1009_encoding_utf8(self):
        """ac_1009_encoding: UTF-8 file detected as utf-8."""
        content = _csv_bytes(["วันที่"], [["04/05/69"]])
        result = analyze_csv(content)
        self.assertEqual(result.encoding_detected, "utf-8")

    def test_ac_1009_type_date_column(self):
        """ac_1009_type_date: date column correctly inferred with transform."""
        headers = ["วันที่", "จำนวน"]
        rows = [["04/05/69", "1000"]] * 3
        result = analyze_csv(_csv_bytes(headers, rows))
        date_col = result.columns[0]
        self.assertEqual(date_col.data_type, "date")
        self.assertEqual(date_col.suggested_transform, "thai_date_short")

    def test_ac_1009_type_padded_column(self):
        """ac_1009_type_padded: zero-padded account codes → pad_left, not number."""
        headers = ["รหัสบัญชี"]
        rows = [["05100"], ["05200"], ["05300"]]
        result = analyze_csv(_csv_bytes(headers, rows))
        col = result.columns[0]
        self.assertEqual(col.data_type, "string")
        self.assertEqual(col.suggested_transform, "pad_left:5:0")

    def test_ac_1009_thai_header_matching(self):
        """ac_1009_thai_header: all 4 common Thai headers matched to correct LF fields."""
        headers = ["วันที่", "รหัสบัญชี", "เดบิต", "เครดิต"]
        rows = [["04/05/69", "1001", "10000", "0"],
                ["04/05/69", "2001", "0", "10000"]]
        result = analyze_csv(_csv_bytes(headers, rows))
        fields = {col.original_header: col.lf_field for col in result.columns}
        self.assertEqual(fields["วันที่"], "invoice_date")
        self.assertEqual(fields["รหัสบัญชี"], "account_code")
        self.assertEqual(fields["เดบิต"], "debit")
        self.assertEqual(fields["เครดิต"], "credit")

    def test_ac_1009_confidence_warning_for_unmatched(self):
        """ac_1009_confidence: unmatched column < 80% → warning generated."""
        headers = ["SomeCompletelyUnknownColumn999"]
        rows = [["val1"], ["val2"]]
        result = analyze_csv(_csv_bytes(headers, rows))
        self.assertGreaterEqual(len(result.warnings), 1)
        self.assertTrue(any("Low confidence" in w.message for w in result.warnings))

    def test_ac_1009_mode_flatten_row(self):
        """ac_1009_mode: repeated first column → flatten_row + journal_lines."""
        headers = ["voucher no", "รหัสบัญชี", "เดบิต", "เครดิต"]
        rows = (
            [["DOC001", "1001", "10000", "0"]] * 4 +
            [["DOC001", "2001", "0", "10000"]] * 4
        )
        result = analyze_csv(_csv_bytes(headers, rows))
        self.assertEqual(result.suggested_template_mode, "flatten_row")
        self.assertEqual(result.suggested_row_source, "journal_lines")

    def test_ac_1009_profile_full(self):
        """ac_1009_profile: data_profile has date_format, balance, unique codes, null rates."""
        headers = ["วันที่", "รหัสบัญชี", "เดบิต", "เครดิต"]
        rows = [
            ["04/05/69", "1001", "5000", "0"],
            ["04/05/69", "2001", "0", "5000"],
            ["05/05/69", "1001", "3000", "0"],
            ["05/05/69", "2001", "0", "3000"],
        ]
        result = analyze_csv(_csv_bytes(headers, rows))
        profile = result.data_profile
        self.assertIsNotNone(profile)
        self.assertEqual(profile.date_format_detected, "DD/MM/YY")
        self.assertTrue(profile.debit_credit_balanced)
        self.assertEqual(profile.unique_account_codes, 2)
        self.assertIsInstance(profile.null_rate_by_column, dict)
        # All columns fully populated → zero null rates
        for rate in profile.null_rate_by_column.values():
            self.assertEqual(rate, 0.0)

    def test_profile_unbalanced_debit_credit(self):
        headers = ["เดบิต", "เครดิต"]
        rows = [["5000", "0"], ["0", "3000"]]  # 5000 debit, 3000 credit → unbalanced
        result = analyze_csv(_csv_bytes(headers, rows))
        self.assertFalse(result.data_profile.debit_credit_balanced)

    def test_profile_null_rate_calculation(self):
        headers = ["วันที่", "รายละเอียด"]
        rows = [["04/05/69", "desc1"], ["05/05/69", ""], ["06/05/69", ""]]
        result = analyze_csv(_csv_bytes(headers, rows))
        profile = result.data_profile
        # รายละเอียด has 2 out of 3 rows empty → null_rate ≈ 0.6667
        self.assertAlmostEqual(profile.null_rate_by_column.get("รายละเอียด", 0), 2/3, places=3)

    def test_semicolon_delimiter(self):
        headers = ["วันที่", "รหัสบัญชี"]
        rows = [["04/05/69", "1001"]] * 3
        result = analyze_csv(_csv_bytes(headers, rows, delimiter=";"), "test.csv")
        self.assertEqual(result.rows_detected, 3)
        self.assertEqual(len(result.columns), 2)

    def test_empty_file(self):
        result = analyze_csv(b"", "empty.csv")
        self.assertEqual(result.rows_detected, 0)
        self.assertEqual(len(result.columns), 0)


# ---------------------------------------------------------------------------
# analyze_excel — ac_1009_upload (xlsx path)
# ---------------------------------------------------------------------------

class TestAnalyzeExcel(unittest.TestCase):
    def test_ac_1009_upload_xlsx(self):
        """ac_1009_upload: Excel file accepted and parsed correctly."""
        headers = ["วันที่", "รหัสบัญชี", "เดบิต"]
        rows = [["04/05/69", "05100", 5000]] * 3
        content = _xlsx_bytes(headers, rows)
        result = analyze_excel(content, "test.xlsx")
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(result.rows_detected, 3)
        self.assertEqual(len(result.columns), 3)

    def test_xlsx_padded_code_not_number(self):
        """ac_1009_type_padded via Excel path."""
        headers = ["รหัสบัญชี"]
        rows = [["05100"], ["05200"], ["05300"]]
        content = _xlsx_bytes(headers, rows)
        result = analyze_excel(content, "test.xlsx")
        col = result.columns[0]
        self.assertEqual(col.data_type, "string")
        self.assertEqual(col.suggested_transform, "pad_left:5:0")

    def test_xlsx_thai_headers(self):
        """ac_1009_thai_header via Excel path."""
        headers = ["วันที่", "รหัสบัญชี"]
        rows = [["04/05/69", "1001"]] * 2
        content = _xlsx_bytes(headers, rows)
        result = analyze_excel(content, "test.xlsx")
        fields = {col.original_header: col.lf_field for col in result.columns}
        self.assertEqual(fields["วันที่"], "invoice_date")
        self.assertEqual(fields["รหัสบัญชี"], "account_code")

    def test_xlsx_encoding_reported_as_utf8(self):
        headers = ["header"]
        rows = [["value"]]
        content = _xlsx_bytes(headers, rows)
        result = analyze_excel(content, "test.xlsx")
        self.assertEqual(result.encoding_detected, "utf-8")

    def test_xlsx_empty_workbook(self):
        import openpyxl
        wb = openpyxl.Workbook()
        buf = io.BytesIO()
        wb.save(buf)
        result = analyze_excel(buf.getvalue(), "empty.xlsx")
        self.assertEqual(result.rows_detected, 0)


if __name__ == "__main__":
    unittest.main()
