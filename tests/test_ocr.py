import unittest

from src.ocr.processor import process_document


class TestOCR(unittest.TestCase):
    def test_process_document_returns_placeholder_text(self):
        result = process_document("sample.png")
        self.assertEqual(result, "processed:sample.png")


if __name__ == "__main__":
    unittest.main()
