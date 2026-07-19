from __future__ import annotations

import csv
import io
import unittest
import uuid

from src.backend.db.models import CustomerMaster, VendorMaster
from src.backend.services.master_data_import import (
    deactivate_master_entry,
    import_master_csv,
    list_master_entries,
)


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

    async def deactivate_vendor(
        self, company_id: uuid.UUID, vendor_code: str
    ) -> bool:
        entry = self.vendors.get((company_id, vendor_code))
        if entry is None:
            return False
        entry.is_active = False
        return True

    async def deactivate_customer(
        self, company_id: uuid.UUID, customer_code: str
    ) -> bool:
        entry = self.customers.get((company_id, customer_code))
        if entry is None:
            return False
        entry.is_active = False
        return True


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


def _express_export_bytes(entity_rows: list[list[str]], encoding: str = "cp874") -> bytes:
    """Build a synthetic file matching the real Express Accounting raw report
    export shape (confirmed against the customer's actual AP-CCSS.csv /
    AR-CCSS.csv: fixed 10 columns, a 'ต้องการ Format' placeholder line, a
    company-name+page-number banner line, then master rows mixed with
    per-transaction detail lines that don't start with a bare sequence number).
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["ต้องการ Format", "", "", "", "", "", "", "", "", ""])
    writer.writerow(["0000'", "บริษัท ทดสอบ จำกัด                    หน้า   :        1", "", "", "", "", "", "", "", ""])
    writer.writerow(["", "", "", "", "", "", "", "", "", ""])  # blank separator (AP-style)
    for row in entity_rows:
        writer.writerow(row)
    return buf.getvalue().encode(encoding, errors="replace")


class TestExpressExportAdapter(unittest.IsolatedAsyncioTestCase):
    """TC-RWG01-09/10 (real-workflow gap register RWG-01): the customer's actual
    AP-CCSS.csv / AR-CCSS.csv files are not header-row CSVs — they are Express
    Accounting's raw report export. Every row previously failed
    'vendor_code and vendor_name are required' (0 imported / 0 updated), while
    the UI showed a fake success toast. This adapter makes the real files
    actually import.
    """

    async def test_vendor_express_export_parses_by_position(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryMasterRepository([company_id])
        content = _express_export_bytes(
            [
                ["1", "บริษัท มานา เคมิคอล (ประเทศไทย) จำกัด", "", "", "", "", "0", "", "0", "2120-01"],
                ["2", "หจก. โรเทก", "", "", "", "", "0", "", "0", "2120-01"],
                # a transaction-detail line that must NOT be mistaken for a vendor row
                ["", "invoice detail, not a vendor", "", "", "", "", "", "", "", ""],
            ]
        )

        result = await import_master_csv(repo, company_id, "vendor", content)

        self.assertEqual(result.imported, 2)
        self.assertEqual(result.updated, 0)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(
            repo.vendors[(company_id, "1")].vendor_name, "บริษัท มานา เคมิคอล (ประเทศไทย) จำกัด"
        )
        self.assertEqual(repo.vendors[(company_id, "1")].gl_code, "2120-01")

    async def test_customer_express_export_parses_ar_flag_by_position(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryMasterRepository([company_id])
        content = _express_export_bytes(
            [
                ["0", "บิล เงินสด (ลูกค้าไม่ให้ชื่อที่อยู่)", "", "", "", "", "", "", "0", ""],
                ["1", "บริษัท ฮาร์โมนี่ อินเตอร์ จำกัด", "", "", "", "", "", "", "1", ""],
            ]
        )

        result = await import_master_csv(repo, company_id, "customer", content)

        self.assertEqual(result.imported, 2)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(repo.customers[(company_id, "0")].ar_flag, 0)
        self.assertEqual(repo.customers[(company_id, "1")].ar_flag, 1)

    async def test_express_export_reimport_upserts_not_duplicates(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryMasterRepository([company_id])
        content = _express_export_bytes(
            [["1", "Vendor One", "", "", "", "", "0", "", "0", "2120-01"]]
        )

        first = await import_master_csv(repo, company_id, "vendor", content)
        second = await import_master_csv(repo, company_id, "vendor", content)

        self.assertEqual(first.imported, 1)
        self.assertEqual(second.imported, 0)
        self.assertEqual(second.updated, 1)
        self.assertEqual(len(repo.vendors), 1)

    async def test_normal_header_csv_is_unaffected_by_express_detection(self) -> None:
        """A well-formed header CSV (not Express export) must still parse the old way."""
        company_id = uuid.uuid4()
        repo = InMemoryMasterRepository([company_id])
        content = _csv_bytes(
            ["vendor_code", "vendor_name", "gl_code"],
            [["V001", "Regular Vendor Co", "5100"]],
        )

        result = await import_master_csv(repo, company_id, "vendor", content)

        self.assertEqual(result.imported, 1)
        self.assertEqual(repo.vendors[(company_id, "V001")].vendor_name, "Regular Vendor Co")


class TestMasterDeactivate(unittest.IsolatedAsyncioTestCase):
    """HR-17-07: master-data rows must be deletable (soft-delete/deactivate). No
    delete path existed before; this proves the new deactivate contract."""

    async def _seed_vendor(self, company_id):
        repo = InMemoryMasterRepository([company_id])
        await import_master_csv(
            repo,
            company_id,
            "vendor",
            _csv_bytes(["vendor_code", "vendor_name"], [["V001", "ACME"]]),
        )
        return repo

    async def test_deactivate_marks_vendor_inactive(self) -> None:
        company_id = uuid.uuid4()
        repo = await self._seed_vendor(company_id)
        self.assertTrue(repo.vendors[(company_id, "V001")].is_active)

        await deactivate_master_entry(repo, company_id, "vendor", "V001")

        self.assertFalse(repo.vendors[(company_id, "V001")].is_active)

    async def test_deactivate_unknown_code_raises_valueerror(self) -> None:
        company_id = uuid.uuid4()
        repo = await self._seed_vendor(company_id)
        with self.assertRaises(ValueError):
            await deactivate_master_entry(repo, company_id, "vendor", "NOPE")

    async def test_deactivate_unknown_company_raises_lookuperror(self) -> None:
        repo = InMemoryMasterRepository([])
        with self.assertRaises(LookupError):
            await deactivate_master_entry(repo, uuid.uuid4(), "customer", "C001")


if __name__ == "__main__":
    unittest.main()
