import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.backend.services.export_service import create_excel_ledger


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


if __name__ == "__main__":
    unittest.main()
