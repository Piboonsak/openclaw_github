import unittest

from src.extraction.fields import extract_fields


class TestExtraction(unittest.TestCase):
    def test_extract_fields_returns_expected_keys(self):
        fields = extract_fields("raw text")
        self.assertIn("invoice_number", fields)
        self.assertIn("invoice_date", fields)
        self.assertIn("vendor_name", fields)
        self.assertIn("total_amount", fields)
        self.assertEqual(fields["source_text"], "raw text")


if __name__ == "__main__":
    unittest.main()
