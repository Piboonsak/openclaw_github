"""Tests for product/price-list master import (Pack C product-master
foundation, separate from `enable_stock`).
"""

from __future__ import annotations

import csv
import io
import unittest
import uuid

from src.backend.db.models import ProductMaster
from src.backend.services.product_master_import import (
    deactivate_product_master_entry,
    import_product_master_csv,
    list_product_master_entries,
    parse_product_master_csv,
)


class InMemoryProductMasterRepository:
    def __init__(self, company_ids: list[uuid.UUID] | None = None) -> None:
        self.company_ids = set(company_ids or [])
        self.products: dict[tuple[uuid.UUID, str], ProductMaster] = {}

    async def company_exists(self, company_id: uuid.UUID) -> bool:
        return company_id in self.company_ids

    async def get_by_code(self, company_id: uuid.UUID, product_code: str):
        return self.products.get((company_id, product_code))

    async def add_product(self, entry: ProductMaster) -> None:
        self.products[(entry.company_id, entry.product_code)] = entry

    async def deactivate_product(
        self, company_id: uuid.UUID, product_code: str
    ) -> bool:
        entry = self.products.get((company_id, product_code))
        if entry is None:
            return False
        entry.is_active = False
        return True

    async def list_products(self, company_id: uuid.UUID, search: str | None):
        items = [p for (cid, _), p in self.products.items() if cid == company_id]
        if search:
            needle = search.lower()
            items = [
                p for p in items
                if needle in p.product_code.lower() or needle in p.product_name.lower()
            ]
        return sorted(items, key=lambda p: p.product_code)


def _express_inventory_bytes(rows: list[list[str]], category: str = "BOX") -> bytes:
    """Synthetic file matching the real Express inventory-by-category export
    shape (confirmed against the customer's actual TMD.csv): banner rows,
    a two-row header, a `หมวด : <category>` section marker, then product rows
    (code at index 3, name at 4, unit at 13, unit_cost at 14).
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["", "บริษัท ทดสอบ จำกัด                    หน้า   :        1"])
    writer.writerow(["", "  สินค้าคงเหลือ แยกตามหมวดสินค้า"])
    writer.writerow(["", "", "ชื่อหมวด", "รหัสสินค้า", "ชื่อสินค้า"])
    writer.writerow(["", "หมวด :", category])
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("cp874", errors="replace")


def _clean_csv_bytes(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["product_code", "product_name", "unit", "unit_cost", "category"])
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


class TestParseProductMasterCsv(unittest.TestCase):
    def test_parses_express_inventory_export_by_position(self) -> None:
        content = _express_inventory_bytes(
            [
                ["", "", "", "118-P15-R", "2x4", "", "", "", "", "", "", "", "39.000", "PCS.", "1.6008", "", "62.43", "39.000"],
                # a subtotal/detail line that must NOT be mistaken for a product
                ["", "รวมหมวดสินค้", "BOX", "", "", "", "", "1", "สินค้า"],
            ]
        )

        rows, encoding = parse_product_master_csv(content)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product_code"], "118-P15-R")
        self.assertEqual(rows[0]["product_name"], "2x4")
        self.assertEqual(rows[0]["unit"], "PCS.")
        self.assertEqual(rows[0]["unit_cost"], 1.6008)
        self.assertEqual(rows[0]["category"], "BOX")
        self.assertEqual(encoding, "tis-620")

    def test_tracks_category_across_multiple_sections(self) -> None:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["", "บริษัท ทดสอบ จำกัด หน้า : 1"])
        writer.writerow(["", "หมวด :", "BOX"])
        writer.writerow(["", "", "", "P001", "Product One", "", "", "", "", "", "", "", "1", "PCS.", "10", "", "10", "1"])
        writer.writerow(["", "หมวด :", "SWITCH"])
        writer.writerow(["", "", "", "P002", "Product Two", "", "", "", "", "", "", "", "1", "PCS.", "20", "", "20", "1"])
        content = buf.getvalue().encode("cp874", errors="replace")

        rows, _ = parse_product_master_csv(content)

        self.assertEqual(rows[0]["category"], "BOX")
        self.assertEqual(rows[1]["category"], "SWITCH")

    def test_falls_back_to_clean_header_csv(self) -> None:
        content = _clean_csv_bytes([["P100", "Widget", "EA", "12.5", "Widgets"]])

        rows, _ = parse_product_master_csv(content)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["product_code"], "P100")
        self.assertEqual(rows[0]["unit_cost"], 12.5)


class TestImportProductMasterCsv(unittest.IsolatedAsyncioTestCase):
    async def test_creates_new_products(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryProductMasterRepository([company_id])
        content = _express_inventory_bytes(
            [["", "", "", "118-P15-R", "2x4", "", "", "", "", "", "", "", "39.000", "PCS.", "1.6008", "", "62.43", "39.000"]]
        )

        summary = await import_product_master_csv(repo, company_id, content)

        self.assertEqual(summary.imported, 1)
        self.assertEqual(summary.updated, 0)
        self.assertEqual(len(summary.errors), 0)
        self.assertEqual(repo.products[(company_id, "118-P15-R")].category, "BOX")

    async def test_reimport_upserts_not_duplicates(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryProductMasterRepository([company_id])
        content = _express_inventory_bytes(
            [["", "", "", "118-P15-R", "2x4", "", "", "", "", "", "", "", "39.000", "PCS.", "1.6008", "", "62.43", "39.000"]]
        )

        first = await import_product_master_csv(repo, company_id, content)
        second = await import_product_master_csv(repo, company_id, content)

        self.assertEqual(first.imported, 1)
        self.assertEqual(second.imported, 0)
        self.assertEqual(second.updated, 1)
        self.assertEqual(len(repo.products), 1)

    async def test_unknown_company_raises_lookup_error(self) -> None:
        repo = InMemoryProductMasterRepository([])
        with self.assertRaises(LookupError):
            await import_product_master_csv(repo, uuid.uuid4(), b"")


class TestListProductMasterEntries(unittest.IsolatedAsyncioTestCase):
    async def test_filters_and_paginates(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryProductMasterRepository([company_id])
        await repo.add_product(
            ProductMaster(company_id=company_id, product_code="P001", product_name="Alpha Widget", unit="PCS.", unit_cost=1.0, category="BOX", is_active=True)
        )
        await repo.add_product(
            ProductMaster(company_id=company_id, product_code="P002", product_name="Beta Widget", unit="PCS.", unit_cost=2.0, category="BOX", is_active=True)
        )

        result = await list_product_master_entries(repo, company_id, search="alpha", page=1, page_size=10)

        self.assertEqual(result.total, 1)
        self.assertEqual(result.items[0].code, "P001")


class TestDeactivateProduct(unittest.IsolatedAsyncioTestCase):
    """HR-17-07: product master rows must be soft-deletable."""

    async def test_deactivate_marks_product_inactive(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryProductMasterRepository([company_id])
        await repo.add_product(
            ProductMaster(company_id=company_id, product_code="P001", product_name="Alpha", is_active=True)
        )

        await deactivate_product_master_entry(repo, company_id, "P001")

        self.assertFalse(repo.products[(company_id, "P001")].is_active)

    async def test_deactivate_unknown_product_raises(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryProductMasterRepository([company_id])
        with self.assertRaises(ValueError):
            await deactivate_product_master_entry(repo, company_id, "GHOST")


if __name__ == "__main__":
    unittest.main()
