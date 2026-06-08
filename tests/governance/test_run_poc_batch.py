import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scripts.run_poc_batch import find_document_files, generate_synthesized_expectations


class TestRunPoCBatch(unittest.TestCase):
    def test_find_document_files_gathers_valid_extensions(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Create a sample document
            doc_file = tmp_path / "valid_doc.pdf"
            doc_file.write_text("fake pdf data", encoding="utf-8")

            # Create ignored files
            ignored_1 = tmp_path / "expectations.template.jsonl"
            ignored_1.write_text("{}", encoding="utf-8")
            ignored_2 = tmp_path / "manifest.jsonl"
            ignored_2.write_text("{}", encoding="utf-8")

            found = find_document_files(tmp_path)
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].name, "valid_doc.pdf")

    def test_generate_synthesized_expectations_matches_schema(self):
        file_path = Path("some_parent/invoice_doc.pdf")
        expectations = generate_synthesized_expectations(file_path)

        self.assertEqual(expectations["invoice_number"], "INV-INVOICE_")
        self.assertEqual(expectations["invoice_date"], "2026-05-12")
        self.assertEqual(expectations["supplier_name"], "some_parent")
        self.assertEqual(expectations["amounts"]["gross_amount"], 10000.0)


if __name__ == "__main__":
    unittest.main()
