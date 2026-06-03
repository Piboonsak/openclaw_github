"""Field extraction helpers."""


def extract_fields(raw_text: str) -> dict:
    """Extract minimal placeholder fields from OCR text."""
    return {
        "invoice_number": "",
        "invoice_date": "",
        "vendor_name": "",
        "total_amount": "",
        "source_text": raw_text,
    }
