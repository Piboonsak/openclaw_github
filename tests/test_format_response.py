#!/usr/bin/env python3
"""
Tests for format_response.py — OpenClaw Gateway Response Formatter

Run:  python3 -m pytest tests/test_format_response.py -v
  or: python3 tests/test_format_response.py
"""

import json
import os
import sys
import unittest

# Add parent dir to path so we can import from docker/scripts
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "docker", "scripts"))

from format_response import format_response, format_response_full


class TestFormatResponse(unittest.TestCase):
    """Test format_response() function."""

    def test_happy_path(self):
        """Basic response with text and sessionId."""
        raw = json.dumps({
            "payloads": [{"text": "Hello world"}],
            "meta": {"agentMeta": {"sessionId": "line-U1234567890abcdef"}}
        })
        result = format_response(raw)
        self.assertEqual(result, "Hello world [890abcdef]")

    def test_thai_text(self):
        """Thai (non-ASCII) text in response."""
        raw = json.dumps({
            "payloads": [{"text": "สวัสดีครับ ยินดีต้อนรับ"}],
            "meta": {"agentMeta": {"sessionId": "line-abc12345678"}}
        })
        result = format_response(raw)
        self.assertIn("สวัสดีครับ", result)
        self.assertIn("[12345678]", result)

    def test_short_session_id(self):
        """SessionId shorter than 8 chars."""
        raw = json.dumps({
            "payloads": [{"text": "test"}],
            "meta": {"agentMeta": {"sessionId": "abc"}}
        })
        result = format_response(raw)
        self.assertEqual(result, "test [abc]")

    def test_empty_session_id(self):
        """Missing sessionId falls back to 'no-session'."""
        raw = json.dumps({
            "payloads": [{"text": "orphan response"}],
            "meta": {"agentMeta": {}}
        })
        result = format_response(raw)
        self.assertEqual(result, "orphan response [no-session]")

    def test_no_meta_at_all(self):
        """No meta field at all."""
        raw = json.dumps({
            "payloads": [{"text": "bare response"}]
        })
        result = format_response(raw)
        self.assertEqual(result, "bare response [no-session]")

    def test_top_level_session_id_fallback(self):
        """SessionId at top level (not nested in meta)."""
        raw = json.dumps({
            "payloads": [{"text": "fallback test"}],
            "sessionId": "direct-session-xyz"
        })
        result = format_response(raw)
        self.assertIn("[sion-xyz]", result)

    def test_long_text_truncated(self):
        """Text longer than 200 chars is truncated."""
        long_text = "x" * 250
        raw = json.dumps({
            "payloads": [{"text": long_text}],
            "meta": {"agentMeta": {"sessionId": "line-trunctest"}}
        })
        result = format_response(raw)
        self.assertTrue(result.startswith("x" * 200 + "..."))
        self.assertIn("[runctest]", result)

    def test_multi_payload_uses_first(self):
        """Multiple payloads: only first text is used."""
        raw = json.dumps({
            "payloads": [
                {"text": "first payload"},
                {"text": "second payload"},
                {"text": "third payload"}
            ],
            "meta": {"agentMeta": {"sessionId": "line-multi123"}}
        })
        result = format_response(raw)
        self.assertIn("first payload", result)
        self.assertNotIn("second", result)

    def test_malformed_json(self):
        """Invalid JSON raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            format_response("{not valid json")
        self.assertIn("Malformed JSON", str(ctx.exception))

    def test_missing_payloads(self):
        """No payloads field raises ValueError."""
        raw = json.dumps({"meta": {"agentMeta": {"sessionId": "test"}}})
        with self.assertRaises(ValueError) as ctx:
            format_response(raw)
        self.assertIn("payloads", str(ctx.exception))

    def test_empty_payloads_array(self):
        """Empty payloads array raises ValueError."""
        raw = json.dumps({"payloads": []})
        with self.assertRaises(ValueError) as ctx:
            format_response(raw)
        self.assertIn("payloads", str(ctx.exception))

    def test_missing_text_field(self):
        """Payload without text field raises ValueError."""
        raw = json.dumps({"payloads": [{"type": "image"}]})
        with self.assertRaises(ValueError) as ctx:
            format_response(raw)
        self.assertIn("text", str(ctx.exception))


class TestFormatResponseFull(unittest.TestCase):
    """Test format_response_full() function."""

    def test_full_output_structure(self):
        """Returns dict with expected keys."""
        raw = json.dumps({
            "payloads": [{"text": "hello"}, {"text": "world"}],
            "meta": {"agentMeta": {"sessionId": "line-full123456"}}
        })
        result = format_response_full(raw)
        self.assertEqual(result["text"], "hello")
        self.assertEqual(result["sessionId"], "line-full123456")
        self.assertEqual(result["sessionTail"], "l123456")
        self.assertEqual(result["payloadCount"], 2)

    def test_full_no_session(self):
        """Missing sessionId returns empty strings."""
        raw = json.dumps({"payloads": [{"text": "test"}]})
        result = format_response_full(raw)
        self.assertEqual(result["sessionId"], "")
        self.assertEqual(result["sessionTail"], "")


if __name__ == "__main__":
    unittest.main()
