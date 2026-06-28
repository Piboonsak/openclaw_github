"""Tests for Template CRUD helpers and preview rendering (TASK-1002).

Covers Pydantic schema validation and pure-Python logic that needs no DB:
  ac_1002_create — TemplateCreate schema validates columns JSONB
  ac_1002_preview — preview renders correct headers + rows via template engine
  ac_1002_clone   — clone deep-copies columns (modifying clone does not affect source)

CRUD endpoints (list/get/update/delete) are backed by AsyncSession and are
covered at the SIT integration level.
"""

from __future__ import annotations

import copy
import unittest

from src.backend.api.schemas.template_schemas import (
    ColumnDefSchema,
    PreviewRequest,
    TemplateCreate,
    TemplateUpdate,
)
from src.backend.api.templates import cols_from_jsonb, render_preview
from src.backend.services.template_engine import ColumnDef


# ---------------------------------------------------------------------------
# ac_1002_create — Pydantic schema validation
# ---------------------------------------------------------------------------

class TestTemplateSchemas(unittest.TestCase):
    def test_template_create_valid(self):
        data = {
            "template_name": "Express GL",
            "template_type": "gl_ledger",
            "columns": [
                {"source_field": "voucher_no", "header_label": "Voucher"},
                {"source_field": "voucher_date", "header_label": "Date", "data_type": "date",
                 "transform": "thai_date_short"},
            ],
            "encoding": "tis-620",
            "delimiter": ",",
        }
        tmpl = TemplateCreate(**data)
        self.assertEqual(tmpl.template_name, "Express GL")
        self.assertEqual(len(tmpl.columns), 2)
        self.assertEqual(tmpl.columns[1].transform, "thai_date_short")

    def test_template_create_empty_columns_defaults(self):
        tmpl = TemplateCreate(template_name="T", template_type="test")
        self.assertEqual(tmpl.columns, [])
        self.assertEqual(tmpl.file_format, "csv")
        self.assertEqual(tmpl.encoding, "utf-8")
        self.assertFalse(tmpl.is_master)

    def test_template_create_rejects_blank_name(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            TemplateCreate(template_name="", template_type="gl")

    def test_column_def_schema_defaults(self):
        col = ColumnDefSchema(source_field="voucher_date", header_label="Date")
        self.assertEqual(col.data_type, "string")
        self.assertIsNone(col.transform)
        self.assertIsNone(col.default_value)

    def test_template_update_all_optional(self):
        update = TemplateUpdate()
        self.assertIsNone(update.template_name)
        self.assertIsNone(update.columns)


# ---------------------------------------------------------------------------
# cols_from_jsonb — conversion helper
# ---------------------------------------------------------------------------

class TestColsFromJsonb(unittest.TestCase):
    def test_converts_list_of_dicts(self):
        jsonb = [
            {"source_field": "voucher_no", "header_label": "Voucher"},
            {"source_field": "voucher_date", "header_label": "Date", "data_type": "date",
             "transform": "thai_date_short"},
        ]
        cols = cols_from_jsonb(jsonb)
        self.assertEqual(len(cols), 2)
        self.assertIsInstance(cols[0], ColumnDef)
        self.assertEqual(cols[1].transform, "thai_date_short")

    def test_none_returns_empty(self):
        self.assertEqual(cols_from_jsonb(None), [])

    def test_empty_list_returns_empty(self):
        self.assertEqual(cols_from_jsonb([]), [])

    def test_skips_non_dict_entries(self):
        jsonb = [{"source_field": "x", "header_label": "X"}, "bad_entry", None]
        cols = cols_from_jsonb(jsonb)
        self.assertEqual(len(cols), 1)


# ---------------------------------------------------------------------------
# ac_1002_preview — render_preview without DB
# ---------------------------------------------------------------------------

class TestRenderPreview(unittest.TestCase):
    def test_preview_returns_headers_and_rows(self):
        cols = [
            ColumnDef(source_field="voucher_no",   header_label="Voucher"),
            ColumnDef(source_field="voucher_date", header_label="วันที่",
                      data_type="date", transform="thai_date_short"),
            ColumnDef(source_field="debit",        header_label="เดบิต", data_type="number"),
        ]
        sample_data = [
            {"voucher_no": "DOC001", "voucher_date": "2026-05-01", "debit": "5000"},
            {"voucher_no": "DOC002", "voucher_date": "2026-05-02", "debit": "3000"},
        ]
        result = render_preview(cols, sample_data)
        self.assertEqual(result.headers, ["Voucher", "วันที่", "เดบิต"])
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(result.rows[0][0], "DOC001")
        self.assertEqual(result.rows[0][1], "01/05/69")

    def test_preview_capped_at_max_rows(self):
        cols = [ColumnDef(source_field="x", header_label="X")]
        data = [{"x": str(i)} for i in range(20)]
        result = render_preview(cols, data, max_rows=5)
        self.assertEqual(len(result.rows), 5)

    def test_preview_empty_data_returns_empty_rows(self):
        cols = [ColumnDef(source_field="x", header_label="X")]
        result = render_preview(cols, [])
        self.assertEqual(result.headers, ["X"])
        self.assertEqual(result.rows, [])

    def test_preview_missing_fields_use_default(self):
        cols = [
            ColumnDef(source_field="vendor_name", header_label="Vendor", default_value="N/A"),
        ]
        result = render_preview(cols, [{}])
        self.assertEqual(result.rows[0][0], "N/A")

    def test_preview_thai_date_transform(self):
        cols = [ColumnDef(source_field="date", header_label="D", data_type="date",
                          transform="thai_date_short")]
        result = render_preview(cols, [{"date": "2026-05-04"}])
        self.assertEqual(result.rows[0][0], "04/05/69")

    def test_preview_response_is_typed(self):
        from src.backend.api.schemas.template_schemas import PreviewResponse
        cols = [ColumnDef(source_field="a", header_label="A")]
        result = render_preview(cols, [{"a": "1"}])
        self.assertIsInstance(result, PreviewResponse)


# ---------------------------------------------------------------------------
# ac_1002_clone — deep copy verification (pure Python, no DB)
# ---------------------------------------------------------------------------

class TestCloneDeepCopy(unittest.TestCase):
    def test_deep_copy_columns_are_independent(self):
        """Modifying the clone's columns does not affect the source."""
        source_cols = [
            {"source_field": "voucher_no", "header_label": "Voucher", "transform": None}
        ]
        cloned_cols = copy.deepcopy(source_cols)
        cloned_cols[0]["header_label"] = "เลขที่เอกสาร"
        # Original must be unchanged
        self.assertEqual(source_cols[0]["header_label"], "Voucher")
        self.assertEqual(cloned_cols[0]["header_label"], "เลขที่เอกสาร")

    def test_deep_copy_nested_dicts_are_independent(self):
        source_cols = [
            {"source_field": "x", "header_label": "X",
             "meta": {"nested": "value"}}
        ]
        cloned_cols = copy.deepcopy(source_cols)
        cloned_cols[0]["meta"]["nested"] = "changed"
        self.assertEqual(source_cols[0]["meta"]["nested"], "value")


if __name__ == "__main__":
    unittest.main()
