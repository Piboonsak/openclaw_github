#!/usr/bin/env python3
"""
format_response.py — OpenClaw Gateway Response Formatter

Extracts human-readable text from OpenClaw gateway JSON responses.
Used by the Flask bridge logging pipeline and regression tests.

Output format:  {text} [{sessionId-8}]
Example:        สวัสดีครับ [abc12345]

Usage:
    echo '{"payloads":[{"text":"hello"}],"meta":{"agentMeta":{"sessionId":"line-abc12345"}}}' | python3 format_response.py
    python3 format_response.py response.json
"""

import json
import sys


def format_response(raw: str) -> str:
    """
    Parse an OpenClaw gateway JSON response and return a compact log line.

    Args:
        raw: JSON string from the gateway response body.

    Returns:
        Formatted string: "{text} [{sessionId-tail-8}]"

    Raises:
        ValueError: If JSON is malformed or required fields are missing.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON: {e}") from e

    # Extract text from payloads
    payloads = data.get("payloads")
    if not payloads or not isinstance(payloads, list):
        raise ValueError("Missing or empty 'payloads' array")

    text = payloads[0].get("text")
    if text is None:
        raise ValueError("Missing 'text' in payloads[0]")

    # Extract sessionId (navigate nested meta structure)
    session_id = ""
    meta = data.get("meta", {})
    agent_meta = meta.get("agentMeta", {})
    session_id = agent_meta.get("sessionId", "")

    # Also check top-level sessionId as fallback
    if not session_id:
        session_id = data.get("sessionId", "")

    # Format: take last 8 chars of sessionId
    session_tail = session_id[-8:] if session_id else "no-session"

    # Truncate text for log output (max 200 chars for log line)
    display_text = text[:200] + "..." if len(text) > 200 else text

    return f"{display_text} [{session_tail}]"


def format_response_full(raw: str) -> dict:
    """
    Parse and return structured data from gateway response.

    Returns:
        dict with keys: text, sessionId, sessionTail, payloadCount
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"Malformed JSON: {e}") from e

    payloads = data.get("payloads", [])
    if not payloads or not isinstance(payloads, list):
        raise ValueError("Missing or empty 'payloads' array")

    text = payloads[0].get("text", "")
    meta = data.get("meta", {})
    agent_meta = meta.get("agentMeta", {})
    session_id = agent_meta.get("sessionId", data.get("sessionId", ""))

    return {
        "text": text,
        "sessionId": session_id,
        "sessionTail": session_id[-8:] if session_id else "",
        "payloadCount": len(payloads),
    }


if __name__ == "__main__":
    # Read from file argument or stdin
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            raw_input = f.read()
    else:
        raw_input = sys.stdin.read()

    if not raw_input.strip():
        print("ERROR: Empty input", file=sys.stderr)
        sys.exit(1)

    try:
        result = format_response(raw_input)
        print(result)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
