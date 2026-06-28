from __future__ import annotations

import csv
import io
import unittest
import uuid

from src.backend.db.models import CustomerMaster, VendorMaster
from src.backend.services.master_data_import import import_master_csv, list_master_entries


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


class TestMasterDataImport(unittest.IsolatedAsyncioTestCase):
    async def test_vendor_import_cp874_creates_records(self) -> None:
        """ac_1207_vendor_import: cp874 CSV import creates vendor records."""
        company_id = uuid.uuid4()
        repo = InMemoryMasterRepository([company_id])
        content = _csv_bytes(
            ["vendor_code", "vendor_name", "gl_code"],
            [["V001", "บริษัท น้ำใส จำกัด", "5100"], ["V002", "Kasikorn Bank", "1100"]],
            encoding="cp874",
        )

        result = await import_master_csv(repo, company_id, "vendor", content)

        self.assertEqual(result.imported, 2)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.encoding_detected, "tis-620")
        self.assertEqual(repo.vendors[(company_id, "V001")].vendor_name, "บริษัท น้ำใส จำกัด")

    async def test_customer_import_upserts_and_collects_errors(self) -> None:
        """ac_1207_upsert: re-import updates existing row and collects row errors."""
        company_id = uuid.uuid4()
        repo = InMemoryMasterRepository([company_id])
        await repo.add_customer(
            CustomerMaster(
                company_id=company_id,
                customer_code="C001",
                customer_name="Old Name",
                ar_flag=0,
                is_active=True,
            )
        )
        content = _csv_bytes(
            ["customer_code", "customer_name", "ar_flag"],
            [["C001", "Updated Name", "1"], ["C002", "New Customer", "0"], ["", "Broken Row", "0"]],
        )

        result = await import_master_csv(repo, company_id, "customer", content)

        self.assertEqual(result.imported, 1)
        self.assertEqual(result.updated, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0].row_number, 4)
        self.assertEqual(repo.customers[(company_id, "C001")].customer_name, "Updated Name")
        self.assertEqual(repo.customers[(company_id, "C001")].ar_flag, 1)

    async def test_vendor_list_filters_and_paginates(self) -> None:
        """ac_1207_list: list endpoint data can be filtered and paginated."""
        company_id = uuid.uuid4()
        repo = InMemoryMasterRepository([company_id])
        await repo.add_vendor(
            VendorMaster(
                company_id=company_id,
                vendor_code="V001",
                vendor_name="Alpha Supplies",
                gl_code="5100",
                is_active=True,
            )
        )
        await repo.add_vendor(
            VendorMaster(
                company_id=company_id,
                vendor_code="V002",
                vendor_name="Beta Trading",
                gl_code="5200",
                is_active=False,
            )
        )
        await repo.add_vendor(
            VendorMaster(
                company_id=company_id,
                vendor_code="V003",
                vendor_name="Alpha Services",
                gl_code=None,
                is_active=True,
            )
        )

        result = await list_master_entries(
            repo,
            company_id,
            "vendor",
            search="alpha",
            page=2,
            page_size=1,
        )

        self.assertEqual(result.total, 2)
        self.assertEqual(result.page, 2)
        self.assertEqual(result.page_size, 1)
        self.assertEqual(len(result.items), 1)
        self.assertEqual(result.items[0].code, "V003")


if __name__ == "__main__":
    unittest.main()
