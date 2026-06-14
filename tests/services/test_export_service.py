import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.backend.services.export_service import (
    create_excel_ledger,
    create_purchase_tax_report,
)


class TestExportService(unittest.TestCase):
    def test_create_excel_ledger_generates_valid_workbook(self):
        with TemporaryDirectory() as tmp:
            xlsx_path = Path(tmp) / "test_ledger.xlsx"
            vouchers = [
                {
                    "voucherNo": "AP2605001",
                    "date": "2026-05-12",
                    "vendor": "Test Vendor",
                    "gross": 10700.0,
                    "companyTaxId": "0105559123456",
                    "sellerTaxId": "0105566111111",
                    "lines": [
                        {"type": "Dr", "code": "5040", "label": "ค่าน้ำค่าไฟ", "amount": 10000.0},
                        {"type": "Dr", "code": "1154", "label": "ภาษีซื้อ", "amount": 700.0},
                        {"type": "Cr", "code": "2195", "label": "เจ้าหนี้การค้า", "amount": 10700.0}
                    ]
                }
            ]

            out_path = create_excel_ledger(vouchers, xlsx_path)

            self.assertTrue(out_path.exists())
            self.assertGreater(out_path.stat().st_size, 0)


class TestPurchaseTaxReport(unittest.TestCase):
    """Tests for the purchase tax report (รายงานภาษีซื้อ) Excel export."""

    COMPANY_INFO = {
        "name": "บริษัท ทดสอบ จำกัด",
        "taxId": "0125561025189",
        "branch": "00000",
        "branchName": "สำนักงานใหญ่",
        "address": "123 ถนนทดสอบ กรุงเทพฯ",
    }

    SAMPLE_DOCS = [
        {
            "invNo": "PO-20260300001",
            "invDate": "2026-03-01",
            "sellerName": "บริษัท ABC จำกัด",
            "sellerTax": "0105559123456",
            "sellerBranch": "00000",
            "netAmt": 10000.0,
            "vatRate": 7,
            "vatAmt": 700.0,
            "whtAmt": 300.0,
            "category": "ค่าน้ำค่าไฟ",
            "description": "ค่าน้ำค่าไฟ - บริษัท ABC จำกัด",
            "reference": "",
        },
        {
            "invNo": "PO-20260300002",
            "invDate": "2026-03-05",
            "sellerName": "นาย ทดสอบ",
            "sellerTax": "1234567890123",
            "sellerBranch": "00000",
            "netAmt": 50000.0,
            "vatRate": 0,
            "vatAmt": 0,
            "whtAmt": 1500.0,
            "category": "งานรับเหมา",
            "description": "งานรับเหมา - นาย ทดสอบ",
            "reference": "",
        },
        {
            "invNo": "PO-20260300003",
            "invDate": "2026-03-10",
            "sellerName": "บริษัท XYZ จำกัด",
            "sellerTax": "0105559654321",
            "sellerBranch": "00001",
            "netAmt": 5000.0,
            "vatRate": 7,
            "vatAmt": 350.0,
            "whtAmt": 0,
            "category": "วัสดุสำนักงาน",
            "description": "วัสดุสำนักงาน - บริษัท XYZ จำกัด",
            "reference": "QT-001",
        },
    ]

    def test_creates_valid_workbook(self):
        with TemporaryDirectory() as tmp:
            xlsx_path = Path(tmp) / "test_tax_report.xlsx"
            out = create_purchase_tax_report(
                self.SAMPLE_DOCS, xlsx_path,
                self.COMPANY_INFO, ("01/03/2026", "31/03/2026"),
            )
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)

    def test_empty_documents_creates_file(self):
        with TemporaryDirectory() as tmp:
            xlsx_path = Path(tmp) / "empty_report.xlsx"
            out = create_purchase_tax_report(
                [], xlsx_path, self.COMPANY_INFO, ("01/03/2026", "31/03/2026"),
            )
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)

    def test_vat_bucket_no_vat_item(self):
        """Document with vatRate=0 and vatAmt=0 should go to 'ไม่มี VAT' bucket."""
        # The no-VAT doc (index 1) has netAmt=50000, vatRate=0, vatAmt=0
        doc = self.SAMPLE_DOCS[1]
        self.assertEqual(doc["vatRate"], 0)
        self.assertEqual(doc["vatAmt"], 0)
        self.assertEqual(doc["netAmt"], 50000.0)

    def test_vat_bucket_7pct_item(self):
        """Document with vatRate=7 should go to 'VAT 7%' bucket."""
        doc = self.SAMPLE_DOCS[0]
        self.assertEqual(doc["vatRate"], 7)
        self.assertGreater(doc["vatAmt"], 0)


if __name__ == "__main__":
    unittest.main()
