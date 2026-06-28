"""Integration tests for POST /v1/templates/analyze (TASK-1009).

Uses FastAPI TestClient with a minimal app to avoid dependency on the full
production lifespan (DB, Redis, Celery, etc.).
"""

from __future__ import annotations

import io
import csv
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.api.schema_analyze import router


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _csv_bytes(headers: list[str], rows: list[list[str]], encoding: str = "utf-8") -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
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


class TestSchemaAnalyzeEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(_build_app())
        self.url = "/v1/templates/analyze"

    # ── ac_1009_upload ───────────────────────────────────────────────────────

    def test_upload_csv_200(self):
        """ac_1009_upload: CSV upload returns 200 with expected structure."""
        content = _csv_bytes(
            ["วันที่", "รหัสบัญชี", "เดบิต", "เครดิต"],
            [["04/05/69", "1001", "5000", "0"],
             ["04/05/69", "2001", "0", "5000"]],
        )
        resp = self.client.post(self.url, files={"file": ("test.csv", content, "text/csv")})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("file_info", body)
        self.assertEqual(body["file_info"]["filename"], "test.csv")
        self.assertEqual(body["file_info"]["rows_detected"], 2)
        self.assertIn("columns", body)
        self.assertEqual(len(body["columns"]), 4)

    def test_upload_xlsx_200(self):
        """ac_1009_upload: Excel upload returns 200 with correct row count."""
        content = _xlsx_bytes(
            ["วันที่", "รหัสบัญชี"],
            [["04/05/69", "1001"], ["05/05/69", "2001"]],
        )
        resp = self.client.post(
            self.url,
            files={"file": ("test.xlsx", content,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["file_info"]["rows_detected"], 2)

    # ── Input validation ─────────────────────────────────────────────────────

    def test_unsupported_file_type_400(self):
        """Unsupported extension rejected with 400."""
        resp = self.client.post(
            self.url,
            files={"file": ("test.pdf", b"fake pdf bytes", "application/pdf")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Unsupported file type", resp.json()["detail"])

    def test_empty_file_400(self):
        """Empty upload rejected with 400."""
        resp = self.client.post(
            self.url,
            files={"file": ("test.csv", b"", "text/csv")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("empty", resp.json()["detail"].lower())

    # ── ac_1009_encoding ─────────────────────────────────────────────────────

    def test_tis620_encoding_detected(self):
        """ac_1009_encoding: cp874 file encoding_detected == 'tis-620'."""
        content = _csv_bytes(
            ["วันที่", "รหัสบัญชี"],
            [["04/05/69", "1001"]],
            encoding="cp874",
        )
        resp = self.client.post(self.url, files={"file": ("express.csv", content, "text/csv")})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["file_info"]["encoding_detected"], "tis-620")

    def test_utf8_encoding_detected(self):
        """ac_1009_encoding: UTF-8 file encoding_detected == 'utf-8'."""
        content = _csv_bytes(["วันที่"], [["04/05/69"]])
        resp = self.client.post(self.url, files={"file": ("utf8.csv", content, "text/csv")})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["file_info"]["encoding_detected"], "utf-8")

    # ── ac_1009_thai_header ──────────────────────────────────────────────────

    def test_thai_headers_matched(self):
        """ac_1009_thai_header: Thai column headers map to correct LF fields."""
        content = _csv_bytes(
            ["วันที่", "รหัสบัญชี", "เดบิต", "เครดิต"],
            [["04/05/69", "1001", "5000", "0"]],
        )
        resp = self.client.post(self.url, files={"file": ("test.csv", content, "text/csv")})
        self.assertEqual(resp.status_code, 200)
        cols = {c["original_header"]: c["lf_field"] for c in resp.json()["columns"]}
        self.assertEqual(cols["วันที่"], "invoice_date")
        self.assertEqual(cols["รหัสบัญชี"], "account_code")
        self.assertEqual(cols["เดบิต"], "debit")
        self.assertEqual(cols["เครดิต"], "credit")

    # ── ac_1009_confidence ───────────────────────────────────────────────────

    def test_low_confidence_warning_generated(self):
        """ac_1009_confidence: unmatched column produces a warning."""
        content = _csv_bytes(["CompletelyUnknownColumnXYZ999"], [["val1"], ["val2"]])
        resp = self.client.post(self.url, files={"file": ("test.csv", content, "text/csv")})
        self.assertEqual(resp.status_code, 200)
        warnings = resp.json()["warnings"]
        self.assertGreaterEqual(len(warnings), 1)
        self.assertTrue(any("Low confidence" in w["message"] for w in warnings))

    def test_known_header_no_warning(self):
        """Known Thai headers should not generate warnings."""
        content = _csv_bytes(["วันที่", "รหัสบัญชี"], [["04/05/69", "1001"]])
        resp = self.client.post(self.url, files={"file": ("test.csv", content, "text/csv")})
        self.assertEqual(resp.status_code, 200)
        warnings = resp.json()["warnings"]
        headers_warned = {w["column"] for w in warnings}
        self.assertNotIn("วันที่", headers_warned)
        self.assertNotIn("รหัสบัญชี", headers_warned)

    # ── ac_1009_mode ─────────────────────────────────────────────────────────

    def test_flatten_row_mode_detected(self):
        """ac_1009_mode: repeated voucher numbers → flatten_row + journal_lines."""
        rows = [["DOC001", "1001", "5000", "0"]] * 4 + [["DOC001", "2001", "0", "5000"]] * 4
        content = _csv_bytes(["voucher no", "รหัสบัญชี", "เดบิต", "เครดิต"], rows)
        resp = self.client.post(self.url, files={"file": ("gl.csv", content, "text/csv")})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["suggested_template_mode"], "flatten_row")
        self.assertEqual(body["suggested_row_source"], "journal_lines")

    def test_flat_document_mode_detected(self):
        """Unique first column → flat_document + documents."""
        rows = [["DOC001", "data"], ["DOC002", "data"], ["DOC003", "data"]]
        content = _csv_bytes(["voucher no", "คำอธิบาย"], rows)
        resp = self.client.post(self.url, files={"file": ("docs.csv", content, "text/csv")})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["suggested_template_mode"], "flat_document")
        self.assertEqual(body["suggested_row_source"], "documents")

    # ── ac_1009_profile ──────────────────────────────────────────────────────

    def test_data_profile_present(self):
        """ac_1009_profile: data_profile contains all required keys."""
        rows = [
            ["04/05/69", "1001", "5000", "0"],
            ["04/05/69", "2001", "0", "5000"],
        ]
        content = _csv_bytes(["วันที่", "รหัสบัญชี", "เดบิต", "เครดิต"], rows)
        resp = self.client.post(self.url, files={"file": ("test.csv", content, "text/csv")})
        self.assertEqual(resp.status_code, 200)
        profile = resp.json()["data_profile"]
        self.assertIsNotNone(profile)
        self.assertEqual(profile["date_format_detected"], "DD/MM/YY")
        self.assertTrue(profile["debit_credit_balanced"])
        self.assertEqual(profile["unique_account_codes"], 2)
        self.assertIsInstance(profile["null_rate_by_column"], dict)

    def test_response_structure_complete(self):
        """All required top-level keys present in response."""
        content = _csv_bytes(["วันที่"], [["04/05/69"]])
        resp = self.client.post(self.url, files={"file": ("test.csv", content, "text/csv")})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        for key in ("file_info", "suggested_template_mode", "suggested_row_source",
                    "suggested_encoding", "columns", "warnings", "data_profile"):
            self.assertIn(key, body, f"Missing key: {key}")

    def test_column_structure(self):
        """Each column object has required fields."""
        content = _csv_bytes(["วันที่", "จำนวน"], [["04/05/69", "5000"]])
        resp = self.client.post(self.url, files={"file": ("test.csv", content, "text/csv")})
        col = resp.json()["columns"][0]
        for field in ("position", "original_header", "lf_field", "confidence",
                      "data_type", "suggested_transform", "match_method", "sample_values"):
            self.assertIn(field, col, f"Column missing field: {field}")


if __name__ == "__main__":
    unittest.main()
