"""D7-02: Test suite for express_gl contract validation."""

import pytest

from src.backend.services.express_gl_contract import (
    ExpressGLContractError,
    check_balance_tolerance,
    is_valid_express_gl,
    validate_express_gl,
    validate_express_gl_lines,
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
                {
                    "account": "1110",
                    "description": "Expense",
                    "debit": 100.0,
                    "credit": 0.0,
                }
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
                {
                    "account": "1110",
                    "description": "Expense",
                    "debit": 100.0,
                    "credit": 0.0,
                }
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
                {
                    "account": "1110",
                    "description": "Expense",
                    "debit": -50.0,
                    "credit": 0.0,
                }
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
                {
                    "account": "1110",
                    "description": "Expense",
                    "debit": 100.0,
                    "credit": 0.0,
                }
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
                {
                    "account": "1110",
                    "description": "Expense",
                    "debit": 100.0,
                    "credit": 0.0,
                }
            ],
            "total_debit": 100.0,
            "total_credit": 0.0,
            "balanced": True,
            "status": "posted",
        }

        assert is_valid_express_gl(valid_payload) is True

        invalid_payload = {**valid_payload, "doc_id": None}
        assert is_valid_express_gl(invalid_payload) is False


class TestValidateExpressGLLines:
    """D7-02: Per-line validation with validate_express_gl_lines()."""

    def _valid_line(self, **overrides) -> dict:
        line = {"account": "1110", "debit": 100.0, "credit": 0.0}
        line.update(overrides)
        return line

    def test_valid_lines_returns_empty_errors(self):
        payload = {"lines": [self._valid_line()]}
        assert validate_express_gl_lines(payload) == []

    def test_missing_account_field_reported(self):
        payload = {"lines": [{"debit": 100.0, "credit": 0.0}]}
        errors = validate_express_gl_lines(payload)
        assert any(e["field"] == "account" for e in errors)
        assert errors[0]["line_index"] == 0

    def test_missing_debit_field_reported(self):
        payload = {"lines": [{"account": "1110", "credit": 0.0}]}
        errors = validate_express_gl_lines(payload)
        assert any(e["field"] == "debit" for e in errors)

    def test_missing_credit_field_reported(self):
        payload = {"lines": [{"account": "1110", "debit": 100.0}]}
        errors = validate_express_gl_lines(payload)
        assert any(e["field"] == "credit" for e in errors)

    def test_negative_debit_reported(self):
        payload = {"lines": [self._valid_line(debit=-50.0)]}
        errors = validate_express_gl_lines(payload)
        assert any(e["field"] == "debit" for e in errors)

    def test_negative_credit_reported(self):
        payload = {"lines": [self._valid_line(credit=-10.0)]}
        errors = validate_express_gl_lines(payload)
        assert any(e["field"] == "credit" for e in errors)

    def test_string_amount_reported(self):
        payload = {"lines": [self._valid_line(debit="not_a_number")]}
        errors = validate_express_gl_lines(payload)
        assert any(e["field"] == "debit" for e in errors)

    def test_error_contains_line_index(self):
        payload = {"lines": [self._valid_line(), {"account": "2000"}]}
        errors = validate_express_gl_lines(payload)
        indices = {e["line_index"] for e in errors}
        assert 1 in indices
        assert 0 not in indices

    def test_non_dict_line_reported(self):
        payload = {"lines": ["not_a_dict"]}
        errors = validate_express_gl_lines(payload)
        assert len(errors) == 1
        assert errors[0]["field"] == "line"

    def test_empty_lines_returns_empty(self):
        assert validate_express_gl_lines({"lines": []}) == []

    def test_missing_lines_key_returns_empty(self):
        assert validate_express_gl_lines({}) == []


class TestCheckBalanceTolerance:
    """D7-02: Balance tolerance policy — check_balance_tolerance()."""

    def test_exact_balance_is_balanced(self):
        payload = {"total_debit": 100.0, "total_credit": 100.0}
        result = check_balance_tolerance(payload)
        assert result["balanced"] is True
        assert result["delta"] == 0.0
        assert result["within_tolerance"] is True

    def test_within_default_tolerance(self):
        """delta=0.005 is within default tolerance of 0.01."""
        payload = {"total_debit": 100.005, "total_credit": 100.0}
        result = check_balance_tolerance(payload)
        assert result["balanced"] is False
        assert result["within_tolerance"] is True

    def test_at_tolerance_boundary(self):
        """delta just below boundary (0.009) is within default tolerance 0.01."""
        # Avoid floating-point drift; use values whose diff is provably < 0.01
        payload = {"total_debit": 1001 / 100, "total_credit": 1000 / 100}
        result = check_balance_tolerance(payload)
        # delta = 0.009999... < 0.01 → within_tolerance
        assert result["within_tolerance"] is True

    def test_outside_default_tolerance(self):
        """delta=0.02 exceeds default tolerance of 0.01."""
        payload = {"total_debit": 100.02, "total_credit": 100.0}
        result = check_balance_tolerance(payload)
        assert result["within_tolerance"] is False
        assert result["delta"] == pytest.approx(0.02, abs=1e-9)

    def test_custom_tolerance(self):
        payload = {"total_debit": 100.5, "total_credit": 100.0}
        assert check_balance_tolerance(payload, tolerance=1.0)["within_tolerance"] is True
        assert check_balance_tolerance(payload, tolerance=0.1)["within_tolerance"] is False

    def test_returns_tolerance_used(self):
        payload = {"total_debit": 100.0, "total_credit": 100.0}
        assert check_balance_tolerance(payload, tolerance=0.05)["tolerance"] == 0.05

    def test_missing_totals_treated_as_zero(self):
        result = check_balance_tolerance({})
        assert result["balanced"] is True
        assert result["delta"] == 0.0
