"""Tests for product/price-list master API endpoints (Pack C)."""

from __future__ import annotations

import csv
import io
import unittest
import unittest.mock
import uuid
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.backend.api.product_master import router
from src.backend.auth.dependencies import get_current_active_user
from src.backend.db.session import get_db


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


def _admin_user():
    return SimpleNamespace(id=uuid.uuid4(), username="admin", role="admin")


class InMemoryRepository:
    def __init__(self, company_ids):
        self.company_ids = set(company_ids)
        self.products: dict = {}

    async def company_exists(self, cid):
        return cid in self.company_ids

    async def get_by_code(self, cid, code):
        return self.products.get((cid, code))

    async def add_product(self, entry):
        self.products[(entry.company_id, entry.product_code)] = entry

    async def list_products(self, cid, search):
        return [p for (c, _), p in self.products.items() if c == cid]


def _clean_csv(rows) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["product_code", "product_name", "unit", "unit_cost", "category"])
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


class TestProductMasterApi(unittest.TestCase):
    def setUp(self) -> None:
        self.app = _build_app()
        self.client = TestClient(self.app)
        self.company_id = uuid.uuid4()
        self.repo = InMemoryRepository([self.company_id])

        from src.backend.api import product_master as module

        self.patch = unittest.mock.patch.object(
            module, "SqlAlchemyProductMasterRepository", new=lambda db: self.repo
        )
        self.patch.start()

        async def fake_get_db():
            yield SimpleNamespace()

        self.app.dependency_overrides[get_db] = fake_get_db
        self.app.dependency_overrides[get_current_active_user] = lambda: _admin_user()

    def tearDown(self) -> None:
        self.patch.stop()

    def test_import_creates_products(self) -> None:
        content = _clean_csv([["P001", "Widget", "EA", "12.5", "Widgets"]])

        resp = self.client.post(
            f"/v1/companies/{self.company_id}/product-master/import",
            files={"file": ("products.csv", content, "text/csv")},
        )

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["imported"], 1)
        self.assertEqual(body["updated"], 0)

    def test_rejects_unsupported_extension(self) -> None:
        resp = self.client.post(
            f"/v1/companies/{self.company_id}/product-master/import",
            files={"file": ("products.xlsx", io.BytesIO(b"whatever"), "application/vnd.ms-excel")},
        )
        self.assertEqual(resp.status_code, 400)

    def test_list_returns_imported_products(self) -> None:
        content = _clean_csv([["P001", "Widget", "EA", "12.5", "Widgets"]])
        self.client.post(
            f"/v1/companies/{self.company_id}/product-master/import",
            files={"file": ("products.csv", content, "text/csv")},
        )

        resp = self.client.get(f"/v1/companies/{self.company_id}/product-master")

        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(body["items"][0]["code"], "P001")


if __name__ == "__main__":
    unittest.main()
