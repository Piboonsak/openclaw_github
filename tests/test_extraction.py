import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.backend.ml.field_extractor import (
    _extract_net_amount,
    _extract_vat_amount,
    _extract_vat_rate,
    extract_fields,
    run_extraction,
)
from src.backend.ml.model_router import pick_model, should_escalate_to_sonnet


class TestExtraction(unittest.TestCase):
    def test_extract_fields_returns_expected_keys(self):
        fields = extract_fields("raw text")
        self.assertIn("invoice_number", fields)
        self.assertIn("invoice_date", fields)
        self.assertIn("vendor_name", fields)
        self.assertIn("total_amount", fields)
        self.assertIn("total_amount", fields)
        self.assertIn("net_amount", fields)
        self.assertIn("vat_amount", fields)
        self.assertIn("vat_rate", fields)
        self.assertEqual(fields["source_text"], "raw text")

    def test_extract_vat_amount_from_labeled_line(self):
        """Test VAT extraction from Thai invoice with labeled VAT row."""
        raw_text = """
        มูลค่าสินค้าก่อนภาษีมูลค่าเพิ่ม 1,859.81 บาท
        ภาษีมูลค่าเพิ่ม 7% 130.19 บาท
        มูลค่ารวม 1,990.00 บาท
        """
        vat = _extract_vat_amount(raw_text)
        self.assertEqual(vat, "130.19")

    def test_extract_net_amount_from_labeled_line(self):
        """Test net amount extraction from Thai invoice."""
        raw_text = """
        มูลค่าสินค้าก่อนภาษีมูลค่าเพิ่ม 1,859.81 บาท
        ภาษีมูลค่าเพิ่ม 7% 130.19 บาท
        มูลค่ารวม 1,990.00 บาท
        """
        net = _extract_net_amount(raw_text)
        self.assertEqual(net, "1859.81")

    def test_extract_vat_rate_default_7_percent(self):
        """Test VAT rate defaults to 7 when VAT context present but rate not explicit."""
        raw_text = """
        มูลค่าสินค้าก่อนภาษีมูลค่าเพิ่ม 1,859.81 บาท
        ภาษีมูลค่าเพิ่ม 130.19 บาท
        """
        rate = _extract_vat_rate(raw_text)
        self.assertEqual(rate, "7")

    def test_extract_vat_rate_explicit_percent(self):
        """Test VAT rate extraction when explicitly marked."""
        raw_text = "ภาษีมูลค่าเพิ่ม 10% 185.00 บาท"
        rate = _extract_vat_rate(raw_text)
        self.assertEqual(rate, "10")

    def test_vat_amount_not_extracted_when_no_vat_context(self):
        """Test that VAT is not extracted when no VAT context present."""
        raw_text = "invoice 001 amount 1000 baht"
        vat = _extract_vat_amount(raw_text)
        self.assertEqual(vat, "")

    def test_model_router_escalates_by_low_ocr_confidence(self):
        escalated = should_escalate_to_sonnet(
            page_count=1,
            ocr_confidence=0.6,
            low_confidence_fields=0,
            rule_conflict=False,
        )
        self.assertTrue(escalated)
        self.assertIn("sonnet", pick_model(escalated).lower())

    def test_run_extraction_writes_cache_artifact(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "cache"
            ocr_output = {
                "sha256": "abc123",
                "avg_confidence": 0.9,
                "page_count": 1,
                "blocks": [
                    {"text": "invoice INV-001"},
                    {"text": "date 2026-06-07"},
                    {"text": "vendor บริษัท ทดสอบ"},
                    {"text": "total 1000"},
                ],
            }

            out = run_extraction(ocr_output, cache_root=cache_root)
            self.assertEqual(out["sha256"], "abc123")
            self.assertIn("meta", out)
            self.assertFalse(out["cache_hit"])

            artifact = cache_root / "abc123" / "extraction_output.json"
            self.assertTrue(artifact.exists())

            cached = run_extraction(ocr_output, cache_root=cache_root)
            self.assertTrue(cached["cache_hit"])


if __name__ == "__main__":
    unittest.main()
