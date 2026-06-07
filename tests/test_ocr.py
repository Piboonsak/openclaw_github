import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from src.backend.ml import ocr as processor


class TestOCR(unittest.TestCase):
    def test_run_ocr_writes_artifact_for_text_input(self):
        with TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            sample = tmp_dir / "sample.txt"
            sample.write_text("invoice A\namount 1200\n", encoding="utf-8")

            out = processor.run_ocr(str(sample), cache_root=tmp_dir / "cache")

            self.assertIn("sha256", out)
            self.assertIn("blocks", out)
            self.assertIn("layout_zones", out)
            self.assertIn("avg_confidence", out)
            self.assertFalse(out["cache_hit"])

            artifact_path = tmp_dir / "cache" / out["sha256"] / "ocr_output.json"
            self.assertTrue(artifact_path.exists())

    def test_run_ocr_returns_cache_hit_on_second_run(self):
        with TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            sample = tmp_dir / "sample.txt"
            sample.write_text("line-1\nline-2\n", encoding="utf-8")

            first = processor.run_ocr(str(sample), cache_root=tmp_dir / "cache")
            second = processor.run_ocr(str(sample), cache_root=tmp_dir / "cache")

            self.assertFalse(first["cache_hit"])
            self.assertTrue(second["cache_hit"])
            self.assertEqual(first["sha256"], second["sha256"])

    def test_process_document_keeps_legacy_text_output(self):
        with TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            sample = tmp_dir / "sample.txt"
            sample.write_text("first\nsecond\n", encoding="utf-8")

            result = processor.process_document(str(sample))
            self.assertEqual(result, "first\nsecond")

    def test_ocr_render_scale_env_override(self):
        with mock.patch.dict(os.environ, {"OCR_RENDER_SCALE": "4.5"}, clear=False):
            reloaded = importlib.reload(processor)
            self.assertEqual(reloaded.OCR_RENDER_SCALE, 4.5)

        # Restore module constants for subsequent tests.
        importlib.reload(processor)

    def test_run_ocr_uses_length_weighted_avg_confidence(self):
        with TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            sample = tmp_dir / "sample.txt"
            sample.write_text("placeholder\n", encoding="utf-8")

            fake_blocks = [
                {"id": 1, "text": "a", "confidence": 0.0, "bbox": [0, 0, 1, 1]},
                {
                    "id": 2,
                    "text": "longer_text",
                    "confidence": 0.9,
                    "bbox": [0, 0, 10, 1],
                },
            ]
            with mock.patch.object(
                processor,
                "_extract_text_blocks_for_text_file",
                return_value=fake_blocks,
            ):
                out = processor.run_ocr(str(sample), cache_root=tmp_dir / "cache")

            expected = round((0.0 * 1 + 0.9 * len("longer_text")) / (1 + len("longer_text")), 4)
            self.assertEqual(out["avg_confidence"], expected)


if __name__ == "__main__":
    unittest.main()
