from __future__ import annotations

import unittest
import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.api.export_preview import router
from src.backend.auth.dependencies import get_current_active_user
from src.backend.db.session import get_db


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _template_record(
    template_id: uuid.UUID,
    *,
    file_format: str = "csv",
    encoding: str = "utf-8",
    delimiter: str = ",",
    template_name: str = "Express GL",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=template_id,
        template_name=template_name,
        template_type="gl_export",
        columns=[
            {
                "source_field": "voucher_no",
                "header_label": "Voucher No",
                "data_type": "string",
                "transform": None,
                "format_pattern": None,
                "default_value": None,
            },
            {
                "source_field": "debit",
                "header_label": "Debit",
                "data_type": "number",
                "transform": None,
                "format_pattern": None,
                "default_value": None,
            },
        ],
        file_format=file_format,
        encoding=encoding,
        delimiter=delimiter,
        is_active=True,
    )


class FakeAsyncSession:
    def __init__(self, templates: dict[uuid.UUID, SimpleNamespace]) -> None:
        self.templates = templates

    async def get(self, _model, key):  # noqa: ANN001
        return self.templates.get(key)


class TestExportApi(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _build_app()
        self.client = TestClient(self.app)
        self.template_id = uuid.uuid4()
        self.templates = {
            self.template_id: _template_record(self.template_id),
        }

        async def fake_get_db():
            yield FakeAsyncSession(self.templates)

        async def fake_current_user():
            return SimpleNamespace(id=uuid.uuid4(), username="admin", role="admin")

        self.app.dependency_overrides[get_db] = fake_get_db
        self.app.dependency_overrides[get_current_active_user] = fake_current_user

    def test_export_csv_from_saved_template(self) -> None:
        response = self.client.post(
            "/v1/export",
            json={
                "template_id": str(self.template_id),
                "sample_data": [{"voucher_no": "PV-001", "debit": "123.45"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers["content-type"].startswith("text/csv"))
        self.assertIn('filename="Express GL.csv"', response.headers["content-disposition"])
        text = response.content.decode("utf-8")
        self.assertIn("Voucher No,Debit", text)
        self.assertIn("PV-001,123.45", text)

    def test_live_export_denies_foreign_company_for_unassigned_staff(self) -> None:
        # W5-12-F1: a staff user not assigned to company B must not be able to
        # preview or download B's live export data by posting company_id=B.
        from unittest import mock

        async def staff_user():
            return SimpleNamespace(id=uuid.uuid4(), username="staff", role="staff")

        async def _no_companies(_db, _user_id):
            return set()

        self.app.dependency_overrides[get_current_active_user] = staff_user
        foreign_company = str(uuid.uuid4())
        columns = [{
            "source_field": "invoice_number", "header_label": "Invoice No.",
            "data_type": "string", "transform": None, "format_pattern": None,
            "default_value": None,
        }]
        with mock.patch(
            "src.backend.auth.dependencies.get_user_company_ids", _no_companies
        ):
            preview = self.client.post(
                "/v1/export/preview",
                json={"column_overrides": columns, "company_id": foreign_company},
            )
            download = self.client.post(
                "/v1/export",
                json={"column_overrides": columns, "company_id": foreign_company},
            )

        self.assertEqual(preview.status_code, 403)
        self.assertEqual(download.status_code, 403)

    def test_export_uses_template_default_xlsx_when_format_omitted(self) -> None:
        xlsx_template_id = uuid.uuid4()
        self.templates[xlsx_template_id] = _template_record(
            xlsx_template_id,
            file_format="xlsx",
        )

        response = self.client.post(
            "/v1/export",
            json={
                "template_id": str(xlsx_template_id),
                "sample_data": [{"voucher_no": "PV-002", "debit": "999.00"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["content-type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn(
            'filename="Express GL.xlsx"',
            response.headers["content-disposition"],
        )
        self.assertTrue(response.content.startswith(b"PK"))

    def test_export_csv_with_column_overrides_without_template(self) -> None:
        response = self.client.post(
            "/v1/export",
            json={
                "column_overrides": [
                    {
                        "source_field": "invoice_number",
                        "header_label": "Invoice",
                        "data_type": "string",
                    }
                ],
                "sample_data": [{"invoice_number": "INV-1001"}],
                "filename": "custom-export",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn('filename="custom-export.csv"', response.headers["content-disposition"])
        self.assertEqual(response.content.decode("utf-8").strip(), "Invoice\r\nINV-1001")

    def test_export_sanitizes_download_filename(self) -> None:
        weird_template_id = uuid.uuid4()
        self.templates[weird_template_id] = _template_record(
            weird_template_id,
            template_name='Bad\r\nName"Here',
        )

        response = self.client.post(
            "/v1/export",
            json={
                "template_id": str(weird_template_id),
                "sample_data": [{"voucher_no": "PV-004", "debit": "10.00"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["content-disposition"],
            'attachment; filename="Bad Name_Here.csv"',
        )

    def test_export_cp874_sets_matching_charset(self) -> None:
        cp874_template_id = uuid.uuid4()
        self.templates[cp874_template_id] = _template_record(
            cp874_template_id,
            encoding="tis-620",
        )

        response = self.client.post(
            "/v1/export",
            json={
                "template_id": str(cp874_template_id),
                "sample_data": [{"voucher_no": "PV-005", "debit": "77.00"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["content-type"],
            "text/csv; charset=windows-874",
        )

    def test_export_requires_template_or_column_overrides(self) -> None:
        response = self.client.post("/v1/export", json={"sample_data": []})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            "Provide template_id or column_overrides for export",
        )

    def test_export_rejects_invalid_template_uuid(self) -> None:
        response = self.client.post(
            "/v1/export",
            json={
                "template_id": "not-a-uuid",
                "sample_data": [{"voucher_no": "PV-003"}],
            },
        )

        self.assertEqual(response.status_code, 422)

    # -- /v1/export/preview: null-template Quick Export path (TASK-W4-BACKEND-FOLLOWUP) --

    def test_preview_uses_saved_template_when_no_overrides(self) -> None:
        response = self.client.post(
            "/v1/export/preview",
            json={
                "template_id": str(self.template_id),
                "sample_data": [{"voucher_no": "PV-010", "debit": "50.00"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["headers"], ["Voucher No", "Debit"])
        self.assertEqual(body["rows"], [["PV-010", "50.00"]])

    def test_preview_quick_export_without_template(self) -> None:
        response = self.client.post(
            "/v1/export/preview",
            json={
                "column_overrides": [
                    {
                        "source_field": "invoice_number",
                        "header_label": "Invoice",
                        "data_type": "string",
                    }
                ],
                "sample_data": [{"invoice_number": "INV-2001"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["headers"], ["Invoice"])
        self.assertEqual(body["rows"], [["INV-2001"]])

    def test_preview_column_overrides_take_precedence_over_template(self) -> None:
        response = self.client.post(
            "/v1/export/preview",
            json={
                "template_id": str(self.template_id),
                "column_overrides": [
                    {
                        "source_field": "invoice_number",
                        "header_label": "Invoice Only",
                        "data_type": "string",
                    }
                ],
                "sample_data": [{"invoice_number": "INV-3003", "voucher_no": "PV-999"}],
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["headers"], ["Invoice Only"])
        self.assertEqual(body["rows"], [["INV-3003"]])

    def test_preview_requires_template_or_column_overrides(self) -> None:
        response = self.client.post("/v1/export/preview", json={"sample_data": []})

        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.json()["detail"],
            "Provide template_id or column_overrides for preview",
        )

    def test_preview_rejects_missing_template(self) -> None:
        response = self.client.post(
            "/v1/export/preview",
            json={
                "template_id": str(uuid.uuid4()),
                "sample_data": [],
            },
        )

        self.assertEqual(response.status_code, 404)

    def test_preview_rejects_invalid_template_uuid(self) -> None:
        response = self.client.post(
            "/v1/export/preview",
            json={
                "template_id": "not-a-uuid",
                "sample_data": [{"voucher_no": "PV-011"}],
            },
        )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
