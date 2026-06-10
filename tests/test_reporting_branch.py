"""D5-01: Test suite for reporting branch classifier."""

import pytest

from src.backend.services.reporting_branch import (
    ReportingBranch,
    classify_reporting_branch,
    is_reporting_document,
)


class TestReportingBranchClassifier:
    """D5-01: Reporting branch classification tests."""

    # Thai document_type tests
    def test_thai_receipts_report_via_document_type(self):
        """Test: Thai 'รายงานรับ' in document_type → RECEIPTS."""
        result = classify_reporting_branch(document_type="รายงานรับ ประจำเดือน")
        assert result.branch == ReportingBranch.RECEIPTS
        assert result.matched_term == "รายงานรับ"
        assert result.source == "document_type"

    def test_thai_payments_report_via_document_type(self):
        """Test: Thai 'รายงานจ่าย' in document_type → PAYMENTS."""
        result = classify_reporting_branch(document_type="รายงานจ่าย สำหรับ CEO")
        assert result.branch == ReportingBranch.PAYMENTS
        assert result.matched_term == "รายงานจ่าย"
        assert result.source == "document_type"

    # English document_type tests
    def test_english_receipt_report_via_document_type(self):
        """Test: English 'receipt report' in document_type → RECEIPTS."""
        result = classify_reporting_branch(document_type="Receipt Report - Monthly")
        assert result.branch == ReportingBranch.RECEIPTS
        assert result.matched_term == "receipt report"
        assert result.source == "document_type"

    def test_english_payment_report_via_document_type(self):
        """Test: English 'payment report' in document_type → PAYMENTS."""
        result = classify_reporting_branch(document_type="Payment Report Summary")
        assert result.branch == ReportingBranch.PAYMENTS
        assert result.matched_term == "payment report"
        assert result.source == "document_type"

    # Thai source_text tests
    def test_thai_receipts_report_via_source_text(self):
        """Test: Thai 'รายงานรับ' in source_text → RECEIPTS."""
        result = classify_reporting_branch(
            source_text="รายงานรับสินค้าประจำวันที่ 10 มิถุนายน 2026"
        )
        assert result.branch == ReportingBranch.RECEIPTS
        assert result.source == "source_text"

    def test_thai_payments_report_via_source_text(self):
        """Test: Thai 'รายงานจ่าย' in source_text → PAYMENTS."""
        result = classify_reporting_branch(
            source_text="รายงานจ่ายค่าใช้บริการเดือนนี้"
        )
        assert result.branch == ReportingBranch.PAYMENTS
        assert result.source == "source_text"

    # Priority tests
    def test_document_type_priority_over_source_text(self):
        """Test: document_type match wins over source_text."""
        result = classify_reporting_branch(
            document_type="Receipt Report",  # Will match
            source_text="general invoice text with no report markers",
        )
        assert result.branch == ReportingBranch.RECEIPTS
        assert result.source == "document_type"

    # Negative tests
    def test_invoice_is_not_reporting_document(self):
        """Test: standard invoice is NONE."""
        result = classify_reporting_branch(
            document_type="Invoice",
            source_text="Standard tax invoice from vendor",
        )
        assert result.branch == ReportingBranch.NONE
        assert result.matched_term is None

    def test_empty_input_returns_none(self):
        """Test: empty/None input → NONE."""
        result = classify_reporting_branch()
        assert result.branch == ReportingBranch.NONE

    # is_reporting_document helper tests
    def test_is_reporting_document_true_for_receipts(self):
        """Test: is_reporting_document() returns True for RECEIPTS."""
        assert is_reporting_document(document_type="Receipt Report") is True

    def test_is_reporting_document_true_for_payments(self):
        """Test: is_reporting_document() returns True for PAYMENTS."""
        assert is_reporting_document(document_type="Payment Report") is True

    def test_is_reporting_document_false_for_none(self):
        """Test: is_reporting_document() returns False for NONE."""
        assert is_reporting_document(document_type="Invoice") is False

    # Case insensitivity test
    def test_classification_is_case_insensitive(self):
        """Test: uppercase/mixed-case 'RECEIPT REPORT' still matches."""
        result = classify_reporting_branch(document_type="RECEIPT REPORT MONTHLY")
        assert result.branch == ReportingBranch.RECEIPTS
