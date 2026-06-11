"""
D5-01: Reporting branch classifier — separate รายงานรับ/รายงานจ่าย detection from routing.

Classifies documents as RECEIPTS_REPORT or PAYMENTS_REPORT independent of journal
routing logic. Single source of truth for downstream report exporters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ReportingBranch(Enum):
    """Reporting branch classification."""

    NONE = "none"
    RECEIPTS = "receipts_report"
    PAYMENTS = "payments_report"


@dataclass
class ReportingClassification:
    """Classification result for a document."""

    branch: ReportingBranch
    matched_term: Optional[str]
    source: str  # "document_type" or "source_text"


# Thai and English text markers for reporting documents
_TEXT_TERMS = [
    ("รายงานรับ", ReportingBranch.RECEIPTS),
    ("รายงานจ่าย", ReportingBranch.PAYMENTS),
    ("receipt report", ReportingBranch.RECEIPTS),
    ("payment report", ReportingBranch.PAYMENTS),
    ("receipts report", ReportingBranch.RECEIPTS),
    ("payments report", ReportingBranch.PAYMENTS),
]


def classify_reporting_branch(
    source_text: Optional[str] = None, document_type: Optional[str] = None
) -> ReportingClassification:
    """
    Classify document as RECEIPTS_REPORT, PAYMENTS_REPORT, or NONE.

    Resolution order:
    1. Explicit document_type matches (e.g., "Receipts Report")
    2. Free-text scan of source_text for Thai/English terms

    Args:
        source_text: OCR/extraction source text or vendor name
        document_type: Extracted document type field

    Returns:
        ReportingClassification with branch, matched_term, source
    """
    # Priority 1: Explicit document_type
    if document_type:
        dt_lower = document_type.strip().lower()
        for term, branch in _TEXT_TERMS:
            if term in dt_lower:
                return ReportingClassification(
                    branch=branch, matched_term=term, source="document_type"
                )

    # Priority 2: Source text scan
    if source_text:
        text_lower = source_text.strip().lower()
        for term, branch in _TEXT_TERMS:
            if term in text_lower:
                return ReportingClassification(
                    branch=branch, matched_term=term, source="source_text"
                )

    return ReportingClassification(
        branch=ReportingBranch.NONE, matched_term=None, source=""
    )


def is_reporting_document(
    source_text: Optional[str] = None, document_type: Optional[str] = None
) -> bool:
    """
    Check if document is a reporting document (receipts or payments report).

    Args:
        source_text: Source text
        document_type: Document type field

    Returns:
        True if RECEIPTS or PAYMENTS, False if NONE
    """
    result = classify_reporting_branch(source_text, document_type)
    return result.branch in (ReportingBranch.RECEIPTS, ReportingBranch.PAYMENTS)
