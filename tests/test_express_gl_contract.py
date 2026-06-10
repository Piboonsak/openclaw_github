"""D7-02: Test suite for express_gl contract validation."""

import pytest

from src.backend.services.express_gl_contract import (
    ExpressGLContractError,
    is_valid_express_gl,
    validate_express_gl,
)


class TestExpressGLSchema:
    """D7-02: express_gl contract validation tests."""

    def test_baseline_payload_is_valid(self):
        """Test: valid express_gl payload passes validation."""
        payload = {
            "doc_id": "abc123",
            "doc_type": "Invoice",
            "voucher_date": "2026-06-10",
            "reference": "INV-001",
            "book_code": "AP",
            "lines": [
                {"account": "1110", "description": "Expense", "debit": 100.0, "credit": 0.0}
            ],
            "total_debit": 100.0,
            "total_credit": 0.0,
            "balanced": True,
            "status": "posted",
        }

        validate_express_gl(payload)  # Should not raise

    def test_missing_required_field_is_rejected(self):
        """Test: missing required field → ExpressGLContractError."""
        payload = {
            "doc_type": "Invoice",
            "voucher_date": "2026-06-10",
            # Missing doc_id
            "reference": "INV-001",
            "book_code": "AP",
            "lines": [],
            "total_debit": 0.0,
            "total_credit": 0.0,
            "balanced": True,
            "status": "posted",
        }

        with pytest.raises(ExpressGLContractError):
            validate_express_gl(payload)

    def test_invalid_status_value_is_rejected(self):
        """Test: status must be string (type check)."""
        payload = {
            "doc_id": "abc123",
            "doc_type": "Invoice",
            "voucher_date": "2026-06-10",
            "reference": "INV-001",
            "book_code": "AP",
            "lines": [
                {"account": "1110", "description": "Expense", "debit": 100.0, "credit": 0.0}
            ],
            "total_debit": 100.0,
            "total_credit": 0.0,
            "balanced": True,
            "status": 123,  # Should be string
        }

        with pytest.raises(ExpressGLContractError):
            validate_express_gl(payload)

    def test_empty_lines_array_is_rejected(self):
        """Test: lines array minItems=1, empty array rejected."""
        payload = {
            "doc_id": "abc123",
            "doc_type": "Invoice",
            "voucher_date": "2026-06-10",
            "reference": "INV-001",
            "book_code": "AP",
            "lines": [],  # Empty violates minItems
            "total_debit": 0.0,
            "total_credit": 0.0,
            "balanced": True,
            "status": "posted",
        }

        with pytest.raises(ExpressGLContractError):
            validate_express_gl(payload)

    def test_line_missing_account_is_rejected(self):
        """Test: line without account required field → rejected."""
        payload = {
            "doc_id": "abc123",
            "doc_type": "Invoice",
            "voucher_date": "2026-06-10",
            "reference": "INV-001",
            "book_code": "AP",
            "lines": [
                {"description": "Missing account", "debit": 100.0, "credit": 0.0}
            ],
            "total_debit": 100.0,
            "total_credit": 0.0,
            "balanced": True,
            "status": "posted",
        }

        with pytest.raises(ExpressGLContractError):
            validate_express_gl(payload)

    def test_negative_debit_amount_is_rejected(self):
        """Test: negative amounts rejected (minimum: 0)."""
        payload = {
            "doc_id": "abc123",
            "doc_type": "Invoice",
            "voucher_date": "2026-06-10",
            "reference": "INV-001",
            "book_code": "AP",
            "lines": [
                {"account": "1110", "description": "Expense", "debit": -50.0, "credit": 0.0}
            ],
            "total_debit": -50.0,
            "total_credit": 0.0,
            "balanced": False,
            "status": "posted",
        }

        with pytest.raises(ExpressGLContractError):
            validate_express_gl(payload)

    def test_balanced_must_be_boolean(self):
        """Test: balanced field must be boolean."""
        payload = {
            "doc_id": "abc123",
            "doc_type": "Invoice",
            "voucher_date": "2026-06-10",
            "reference": "INV-001",
            "book_code": "AP",
            "lines": [
                {"account": "1110", "description": "Expense", "debit": 100.0, "credit": 0.0}
            ],
            "total_debit": 100.0,
            "total_credit": 0.0,
            "balanced": "yes",  # Should be boolean
            "status": "posted",
        }

        with pytest.raises(ExpressGLContractError):
            validate_express_gl(payload)

    def test_is_valid_express_gl_returns_bool(self):
        """Test: is_valid_express_gl() returns bool without raising."""
        valid_payload = {
            "doc_id": "abc123",
            "doc_type": "Invoice",
            "voucher_date": "2026-06-10",
            "reference": "INV-001",
            "book_code": "AP",
            "lines": [
                {"account": "1110", "description": "Expense", "debit": 100.0, "credit": 0.0}
            ],
            "total_debit": 100.0,
            "total_credit": 0.0,
            "balanced": True,
            "status": "posted",
        }

        assert is_valid_express_gl(valid_payload) is True

        invalid_payload = {**valid_payload, "doc_id": None}
        assert is_valid_express_gl(invalid_payload) is False
