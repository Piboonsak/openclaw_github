import unittest

from src.validation.rules import validate_required_fields


class TestValidation(unittest.TestCase):
    def test_validate_required_fields_reports_missing(self):
        result = validate_required_fields({"invoice_number": "INV-1"}, ["invoice_number", "total_amount"])
        self.assertEqual(result["missing_fields"], ["total_amount"])
        self.assertFalse(result["is_valid"])


if __name__ == "__main__":
    unittest.main()
