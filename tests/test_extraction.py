import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.backend.ml.field_extractor import (
    _extract_net_amount,
    _extract_total_amount,
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

    def test_extract_vat_amount_skips_before_calculation_line(self):
        """VAT extractor must not take net amount from 'ก่อนคำนวณภาษี' lines."""
        raw_text = """
        มูลค่าสินค้าก่อนคำนวณภาษีมูลค่าเพิ่ม 1,859.81 บาท
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

    def test_extract_net_amount_from_ruam_kha_sinkha_line(self):
        raw_text = "หนึ่งพันสี่ร้อยสี่สิบสี่บาทห้าสิบสตางค์ รวมค่าสินค้า 1,350.00"
        net = _extract_net_amount(raw_text)
        self.assertEqual(net, "1350.00")

    def test_extract_total_amount_from_ruam_ngoen_with_ocr_separators(self):
        raw_text = "รวมค่าสินค้า 1,350.00\nVAT 7% 94.50\nรวมเงิน 1.444.50"
        total = _extract_total_amount(raw_text)
        self.assertEqual(total, "1444.50")

    def test_extract_vat_amount_from_noisy_thai_vat_label(self):
        raw_text = "Total/รวมเงิน 17,950.00\nกภาษมูลศาเทิม 1,256.50\nGrandTotal/รวมเป็นเงินทั้งสิ้น 19,206.50"
        vat = _extract_vat_amount(raw_text)
        self.assertEqual(vat, "1256.50")

    def test_extract_net_amount_from_total_and_grand_total(self):
        raw_text = "Total/รวมเงิน 17,950.00\nภาษีมูลค่าเพิ่ม 1,256.50\nGrandTotal/รวมเป็นเงินทั้งสิ้น 19,206.50"
        net = _extract_net_amount(raw_text)
        self.assertEqual(net, "17950.00")

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

    def test_short_buyer_name_has_low_confidence(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "cache"
            ocr_output = {
                "sha256": "short-buyer-name",
                "avg_confidence": 0.92,
                "page_count": 1,
                "blocks": [
                    {"text": "ผู้ขาย: บริษัท ทดสอบ จำกัด เลขผู้เสียภาษี 0999999999999"},
                    {"text": "ผู้ซื้อ: บริษัท เลขผู้เสียภาษี 0888888888888"},
                    {"text": "มูลค่าสินค้าก่อนคำนวณภาษีมูลค่าเพิ่ม 1,859.81"},
                    {"text": "ภาษีมูลค่าเพิ่ม 7% 130.19"},
                    {"text": "มูลค่ารวม 1,990.00"},
                ],
            }

            out = run_extraction(ocr_output, cache_root=cache_root)
            self.assertLess(out["confidence_per_field"]["buyer_name"], 0.6)
            warnings = out["fields"].get("field_validation_warnings", [])
            self.assertTrue(any(w.startswith("buyer_name:") for w in warnings))

    def test_vat_math_mismatch_sets_flag_and_lowers_confidence(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "cache"
            ocr_output = {
                "sha256": "vat-math-mismatch",
                "avg_confidence": 0.9,
                "page_count": 1,
                "blocks": [
                    {"text": "มูลค่าสินค้าก่อนภาษีมูลค่าเพิ่ม 100.00"},
                    {"text": "ภาษีมูลค่าเพิ่ม 7% 50.00"},
                    {"text": "มูลค่ารวม 130.00"},
                ],
            }

            out = run_extraction(ocr_output, cache_root=cache_root)
            self.assertTrue(out["fields"]["vat_math_mismatch"])
            self.assertLessEqual(out["confidence_per_field"]["vat_amount"], 0.4)

    def test_canonical_buyer_name_shortcut_applies(self):
        with TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "cache"
            ocr_output = {
                "sha256": "canonical-buyer-shortcut",
                "avg_confidence": 0.91,
                "page_count": 1,
                "blocks": [
                    {"text": "ผู้ขาย: บริษัท ทีเค.นอนสติ๊ก จำกัด เลขผู้เสียภาษี 0105565189488"},
                    {"text": "ผู้ซื้อ: บริษัท เลขผู้เสียภาษี 0125561025189"},
                    {"text": "ภาษีมูลค่าเพิ่ม 7% 373.10"},
                    {"text": "มูลค่ารวม 5703.10"},
                ],
            }

            out = run_extraction(ocr_output, cache_root=cache_root)
            self.assertEqual(
                out["fields"]["buyer_name"],
                "บริษัท ฤทธิ์ล้ำเลิศ เอ็นจิเนียริ่ง จำกัด",
            )
            self.assertTrue(out["fields"]["canonical_buyer_applied"])
            self.assertGreaterEqual(out["confidence_per_field"]["buyer_name"], 0.95)


if __name__ == "__main__":
    unittest.main()
