"""D4-02: Test matrix for rule matching policy — score, tie-break, unresolved, rejected."""

import pytest

from src.backend.services.rule_engine import JournalRule, pick_best_rule


class MockJournalRule:
    """Mock for testing rule matching logic."""

    def __init__(
        self,
        rule_id: str,
        document_type: str,
        score: int,
        specificity: int,
        reject: bool = False,
    ):
        self.rule_id = rule_id
        self.document_type = document_type
        self.score = score
        self.specificity = specificity
        self.reject = reject

    def __repr__(self):
        return f"MockRule({self.rule_id}, score={self.score}, specificity={self.specificity})"


class TestRuleMatchingDecisions:
    """D4-02: Rule matching tie-break and ambiguity detection."""

    def test_returns_unresolved_when_no_rule_matches(self):
        """Test: no rules → UNRESOLVED_RULE status with needs_review=True."""
        payload = {"extraction": {"document_type": "Unknown"}}
        rules = []

        result = pick_best_rule(payload, rules)

        assert result["rule_id"] == "UNRESOLVED_RULE"
        assert result["needs_review"] is True
        assert result["ambiguous"] is False

    def test_winner_by_score(self):
        """Test: winner selected by highest score when scores differ."""
        payload = {"extraction": {"document_type": "Invoice"}}
        rules = [
            MockJournalRule("r1", "Invoice", score=80, specificity=5),
            MockJournalRule("r2", "Invoice", score=60, specificity=5),
            MockJournalRule("r3", "Invoice", score=90, specificity=5),
        ]

        result = pick_best_rule(payload, rules)

        assert result["rule_id"] == "r3"
        assert result["needs_review"] is False

    def test_tie_break_by_specificity_when_scores_match(self):
        """Test: when scores tie, specificity wins."""
        payload = {"extraction": {"document_type": "PO"}}
        rules = [
            MockJournalRule("r1", "PO", score=75, specificity=3),
            MockJournalRule("r2", "PO", score=75, specificity=7),
            MockJournalRule("r3", "PO", score=75, specificity=5),
        ]

        result = pick_best_rule(payload, rules)

        assert result["rule_id"] == "r2"
        assert result["needs_review"] is False

    def test_full_tie_flags_needs_review_with_ambiguous_signal(self):
        """Test: score + specificity both tie → ambiguous=True, needs_review=True."""
        payload = {"extraction": {"document_type": "Receipt"}}
        rules = [
            MockJournalRule("r1", "Receipt", score=70, specificity=4),
            MockJournalRule("r2", "Receipt", score=70, specificity=4),
        ]

        result = pick_best_rule(payload, rules)

        assert result["needs_review"] is True
        assert result["ambiguous"] is True

    def test_rejected_rule_is_excluded(self):
        """Test: rejected rules excluded from candidate set."""
        payload = {"extraction": {"document_type": "Invoice"}}
        rules = [
            MockJournalRule("r1", "Invoice", score=85, specificity=5, reject=True),
            MockJournalRule("r2", "Invoice", score=70, specificity=5, reject=False),
        ]

        result = pick_best_rule(payload, rules)

        assert result["rule_id"] == "r2"

    def test_document_type_mismatch_rejects_rule(self):
        """Test: rule with mismatched document_type rejected."""
        payload = {"extraction": {"document_type": "Invoice"}}
        rules = [
            MockJournalRule("r1", "PO", score=95, specificity=10),
            MockJournalRule("r2", "Invoice", score=75, specificity=5),
        ]

        result = pick_best_rule(payload, rules)

        assert result["rule_id"] == "r2"

    def test_unresolved_extraction_flags_payload(self):
        """Test: missing extraction or document_type → unresolved."""
        payload = {}
        rules = [MockJournalRule("r1", "Invoice", score=80, specificity=5)]

        result = pick_best_rule(payload, rules)

        assert result["rule_id"] == "UNRESOLVED_RULE"
        assert result["needs_review"] is True
