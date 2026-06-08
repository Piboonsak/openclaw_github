#!/usr/bin/env python3
"""
Standalone script to relabel all PDFs in Comp_1 using Claude Haiku 4.5.
Does NOT import from src/backend/ml.
Sends PDF as base64 document block to Anthropic API.
"""

import base64
import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import anthropic

# ============================================================================
# Configuration
# ============================================================================
SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
PRIVATE_DATA_DIR = REPO_ROOT / "private_data" / "poc" / "Comp_1"
PDF_DIR = PRIVATE_DATA_DIR / "ฤทธิ์ล้ำเลิศ บิลซื้อ RRL"
JSONL_PATH = PRIVATE_DATA_DIR / "expectations.filled.jsonl"

# Schema version (must match backend)
EXTRACTION_SCHEMA_VERSION = "v26"

# System prompt for Haiku (request JSON-only response)
SYSTEM_PROMPT = """You are an expert Thai accounting document processor. 
Analyze the provided document and extract all fields in strict JSON format.

SCHEMA (all fields required, use empty string "" for unknown/not found):
{
  "doc_type": "Invoice|Receipt|Bill|DebitNote|CreditNote|PurchaseOrder|Other|Unknown",
  "party_type": "purchase|sales|expense|empty",
  "invoice_number": "string (e.g., INV-2024-001) or empty",
  "invoice_date": "YYYY-MM-DD or empty",
  "due_date": "YYYY-MM-DD or empty",
  "seller_name": "string or empty",
  "seller_tax_id": "string (13 digits for Thai ID) or empty",
  "buyer_name": "string or empty",
  "buyer_tax_id": "string (13 digits for Thai ID) or empty",
  "branch_code": "string or empty",
  "currency": "THB|USD|other or empty",
  "net_amount": "numeric string, no commas (e.g., '1000.00') or empty",
  "vat_rate": "numeric string percentage without % (e.g., '7' for 7%) or empty",
  "vat_amount": "numeric string, no commas or empty",
  "wht_rate": "numeric string percentage without % or empty",
  "wht_amount": "numeric string, no commas or empty",
  "total_amount": "numeric string, no commas or empty",
  "payment_terms": "string (e.g., '30D', 'NET30') or empty",
  "po_number": "string or empty",
  "reference_number": "string or empty",
  "page_count": "numeric string (e.g., '1', '2') or empty",
  "is_multi_page": "true|false or empty"
}

CRITICAL RULES:
1. All amounts must be numeric strings WITHOUT commas (e.g., "12345.67" not "12,345.67")
2. All dates must be ISO format (YYYY-MM-DD) or empty
3. All numeric percentages without % symbol
4. Tax ID fields accept Thai 13-digit format or empty
5. Use empty string "" for any field you cannot confidently read
6. Validate: net_amount + vat_amount should approximately equal total_amount
7. VAT rate should be consistent (typically 7% in Thailand)

RESPOND WITH JSON ONLY. No markdown, no code blocks, no explanation."""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load JSONL file."""
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def save_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Save JSONL file atomically."""
    tmp_path = path.with_suffix(".jsonl.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # Atomic move
    tmp_path.replace(path)


def load_pdf_as_base64(pdf_path: Path) -> str:
    """Load PDF and encode as base64."""
    with open(pdf_path, "rb") as f:
        return base64.standard_b64encode(f.read()).decode("utf-8")


def call_haiku(
    client: anthropic.Anthropic, pdf_base64: str, doc_id: str
) -> Optional[dict[str, Any]]:
    """
    Call Claude Haiku with PDF document block.
    Returns parsed JSON or None on error.
    """
    try:
        message = client.messages.create(
            model="claude-opus-4-1-20250805",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extract all fields from this accounting document. Respond with JSON only.",
                        },
                    ],
                }
            ],
        )

        # Parse JSON from response
        response_text = message.content[0].text
        extracted = json.loads(response_text)
        return extracted
    except json.JSONDecodeError as e:
        print(f"  ERROR {doc_id}: Failed to parse JSON response: {e}")
        print(f"    Response text: {response_text[:200]}")
        return None
    except anthropic.APIError as e:
        print(f"  ERROR {doc_id}: API error: {e}")
        return None


def merge_extraction(row: dict[str, Any], extracted: dict[str, Any]) -> dict[str, Any]:
    """Merge extracted fields into row, preserving metadata."""
    # Fields to preserve
    preserve_fields = {
        "doc_id",
        "split",
        "include_in_training",
        "exclusion_reason",
        "file_name",
        "relative_path",
    }

    # Fields to extract/update
    extraction_fields = {
        "doc_type",
        "party_type",
        "invoice_number",
        "invoice_date",
        "due_date",
        "seller_name",
        "seller_tax_id",
        "buyer_name",
        "buyer_tax_id",
        "branch_code",
        "currency",
        "net_amount",
        "vat_rate",
        "vat_amount",
        "wht_rate",
        "wht_amount",
        "total_amount",
        "payment_terms",
        "po_number",
        "reference_number",
        "page_count",
        "is_multi_page",
    }

    # Start with preserved fields
    result = {k: row[k] for k in preserve_fields if k in row}

    # Add extracted fields
    for field in extraction_fields:
        result[field] = extracted.get(field, "")

    # Update metadata
    result["labeling_status"] = "ai_haiku_ground_truth"
    result["reviewer"] = "claude-opus-4-1-20250805"
    result["review_note"] = "Re-labeled by claude-opus-4-1-20250805 on 2026-06-09"

    return result


def main():
    """Main entry point."""
    # Verify paths
    if not JSONL_PATH.exists():
        print(f"ERROR: JSONL not found: {JSONL_PATH}")
        sys.exit(1)
    if not PDF_DIR.exists():
        print(f"ERROR: PDF directory not found: {PDF_DIR}")
        sys.exit(1)

    # Initialize Anthropic client
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)
    print(f"✓ Anthropic client initialized")

    # Load JSONL
    rows = load_jsonl(JSONL_PATH)
    print(f"✓ Loaded {len(rows)} rows from JSONL")

    # Filter to non-excluded rows
    to_relabel = [
        (i, row)
        for i, row in enumerate(rows)
        if row.get("labeling_status") != "excluded"
    ]
    print(f"✓ {len(to_relabel)} rows to relabel (excluding 2 excluded)")

    # Process each PDF
    success_count = 0
    fail_count = 0

    for idx, (row_idx, row) in enumerate(to_relabel, 1):
        doc_id = row["doc_id"]
        relative_path = row["relative_path"]
        pdf_path = PRIVATE_DATA_DIR / relative_path

        if not pdf_path.exists():
            print(f"[{idx}/{len(to_relabel)}] ✗ {doc_id}: PDF not found at {pdf_path}")
            fail_count += 1
            continue

        print(
            f"[{idx}/{len(to_relabel)}] Processing {doc_id} ({relative_path.split('/')[-1]})...",
            end=" ",
            flush=True,
        )

        # Load PDF and call Haiku
        try:
            pdf_base64 = load_pdf_as_base64(pdf_path)
            extracted = call_haiku(client, pdf_base64, doc_id)

            if extracted:
                # Merge and update row
                new_row = merge_extraction(row, extracted)
                rows[row_idx] = new_row
                success_count += 1
                print(f"✓ ({extracted.get('invoice_number', 'N/A')})")
            else:
                fail_count += 1
                print(f"✗ (failed to extract)")
        except Exception as e:
            print(f"✗ (error: {e})")
            fail_count += 1

    # Save updated JSONL
    print(f"\nSaving {len(rows)} rows back to JSONL...", end=" ", flush=True)
    save_jsonl(JSONL_PATH, rows)
    print(f"✓")

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Summary:")
    print(f"  Total rows processed: {len(to_relabel)}")
    print(f"  Success: {success_count}")
    print(f"  Failed: {fail_count}")
    print(f"  Preserved (excluded): 2")
    print(f"  Total rows in JSONL: {len(rows)}")
    print(f"{'=' * 60}")

    if fail_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
