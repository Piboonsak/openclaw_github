from __future__ import annotations

import csv
import io
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.api import master_import as master_import_module
from src.backend.api.master_import import router
from src.backend.auth.dependencies import get_current_active_user
from src.backend.db.models import CustomerMaster, VendorMaster
from src.backend.db.session import get_db


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


class InMemoryMasterRepository:
    def __init__(self, company_ids: list[uuid.UUID] | None = None) -> None:
        self.company_ids = set(company_ids or [])
        self.vendors: dict[tuple[uuid.UUID, str], VendorMaster] = {}
        self.customers: dict[tuple[uuid.UUID, str], CustomerMaster] = {}

    async def company_exists(self, company_id: uuid.UUID) -> bool:
        return company_id in self.company_ids

    async def get_vendor_by_code(
        self,
        company_id: uuid.UUID,
        vendor_code: str,
    ) -> VendorMaster | None:
        return self.vendors.get((company_id, vendor_code))

    async def get_customer_by_code(
        self,
        company_id: uuid.UUID,
        customer_code: str,
    ) -> CustomerMaster | None:
        return self.customers.get((company_id, customer_code))

    async def add_vendor(self, entry: VendorMaster) -> None:
        self.vendors[(entry.company_id, entry.vendor_code)] = entry

    async def add_customer(self, entry: CustomerMaster) -> None:
        self.customers[(entry.company_id, entry.customer_code)] = entry

    async def list_vendors(
        self,
        company_id: uuid.UUID,
        search: str | None,
    ) -> list[VendorMaster]:
        items = [
            row
            for (row_company_id, _), row in self.vendors.items()
            if row_company_id == company_id
        ]
        if search:
            needle = search.lower()
            items = [
                row
                for row in items
                if needle in row.vendor_code.lower() or needle in row.vendor_name.lower()
            ]
        return sorted(items, key=lambda row: row.vendor_code)

    async def list_customers(
        self,
        company_id: uuid.UUID,
        search: str | None,
    ) -> list[CustomerMaster]:
        items = [
            row
            for (row_company_id, _), row in self.customers.items()
            if row_company_id == company_id
        ]
        if search:
            needle = search.lower()
            items = [
                row
                for row in items
                if needle in row.customer_code.lower()
                or needle in row.customer_name.lower()
            ]
        return sorted(items, key=lambda row: row.customer_code)


class TestMasterImportApi(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _build_app()
        self.client = TestClient(self.app)
        self.company_id = uuid.uuid4()
        self.repo = InMemoryMasterRepository([self.company_id])

        async def fake_get_db():
            yield SimpleNamespace()

        async def fake_current_user():
            return SimpleNamespace(id=uuid.uuid4(), username="admin", role="admin")

        self.app.dependency_overrides[get_db] = fake_get_db
        self.app.dependency_overrides[get_current_active_user] = fake_current_user
        self.repo_patch = patch.object(
            master_import_module,
            "SqlAlchemyMasterRepository",
            new=lambda db: self.repo,
        )
        self.repo_patch.start()

    def tearDown(self) -> None:
        self.repo_patch.stop()

    def test_vendor_import_endpoint_returns_summary(self) -> None:
        """ac_1207_vendor_import: vendor import endpoint returns import counts."""
        content = _csv_bytes(
            ["vendor_code", "vendor_name", "gl_code"],
            [["V001", "บริษัท ทดสอบ จำกัด", "5100"]],
            encoding="cp874",
        )

        resp = self.client.post(
            f"/v1/companies/{self.company_id}/vendor-master/import",
            files={"file": ("vendors.csv", content, "text/csv")},
        )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["imported"], 1)
        self.assertEqual(body["updated"], 0)
        self.assertEqual(body["encoding_detected"], "tis-620")

    def test_customer_import_unknown_company_404(self) -> None:
        """Unknown company returns 404 instead of creating stray data."""
        content = _csv_bytes(
            ["customer_code", "customer_name"],
            [["C001", "Test Customer"]],
        )

        resp = self.client.post(
            f"/v1/companies/{uuid.uuid4()}/customer-master/import",
            files={"file": ("customers.csv", content, "text/csv")},
        )

        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.json()["detail"], "Company not found")

    def test_vendor_list_endpoint_filters_results(self) -> None:
        """ac_1207_list: vendor list endpoint applies search and pagination."""
        self.repo.vendors[(self.company_id, "V001")] = VendorMaster(
            company_id=self.company_id,
            vendor_code="V001",
            vendor_name="Alpha Supply",
            gl_code="5100",
            is_active=True,
        )
        self.repo.vendors[(self.company_id, "V002")] = VendorMaster(
            company_id=self.company_id,
            vendor_code="V002",
            vendor_name="Beta Goods",
            gl_code=None,
            is_active=True,
        )

        resp = self.client.get(
            f"/v1/companies/{self.company_id}/vendor-master",
            params={"q": "alpha", "page": 1, "page_size": 10},
        )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(len(body["items"]), 1)
        self.assertEqual(body["items"][0]["code"], "V001")


if __name__ == "__main__":
    unittest.main()
