"""D4-02: Tie-break and edge-case test matrix for pick_best_rule()."""

from __future__ import annotations

from src.backend.services.rule_engine import (
    SCORE_WEIGHTS,
    count_defined_conditions,
    pick_best_rule,
    score_rule,
)
from src.backend.services.rule_loader import JournalRule, RuleEntry


# ---------------------------------------------------------------------------
# Helper to build minimal JournalRule fixtures
# ---------------------------------------------------------------------------

def _make_rule(
    rule_id: str,
    document_types: list[str] | None = None,
    conditions: dict | None = None,
    entries: list | None = None,
) -> JournalRule:
    raw_entries = entries or []
    rule_entries = tuple(
        RuleEntry(
            side=e.get("side", "debit"),
            account_code=e.get("account_code", "5040"),
            amount_field=e.get("amount_field", "net_amount"),
            account_name=e.get("account_name", ""),
            description=e.get("description", ""),
            condition=e.get("condition", ""),
            is_variable=e.get("is_variable", False),
            alternatives=tuple(e.get("alternatives", [])),
        )
        for e in raw_entries
    )
    return JournalRule(
        rule_id=rule_id,
        name=rule_id,
        description="",
        document_types=tuple(document_types or []),
        transaction_type="",
        book_code="PV",
        conditions=conditions or {},
        entries=rule_entries,
        validation={},
        raw={},
    )


# ---------------------------------------------------------------------------
# SCORE_WEIGHTS contract
# ---------------------------------------------------------------------------

class TestScoreWeights:
    """Verify the declared score weight table matches spec."""

    def test_document_type_weight(self):
        assert SCORE_WEIGHTS["document_type"] == 20

    def test_payment_method_weight(self):
        assert SCORE_WEIGHTS["payment_method"] == 20

    def test_source_document_weight(self):
        assert SCORE_WEIGHTS["source_document"] == 25

    def test_has_vat_weight(self):
        assert SCORE_WEIGHTS["has_vat"] == 10

    def test_has_wht_weight(self):
        assert SCORE_WEIGHTS["has_wht"] == 10


# ---------------------------------------------------------------------------
# score_rule()
# ---------------------------------------------------------------------------

class TestScoreRule:
    """score_rule() — scoring and rejection logic."""

    def test_no_conditions_scores_zero(self):
        rule = _make_rule("R1")
        score, matched, rejected = score_rule(rule, {"document_type": "Invoice"})
        assert score == 0
        assert matched == []
        assert rejected is False

    def test_matching_document_type_adds_weight(self):
        rule = _make_rule("R1", document_types=["Invoice"])
        score, matched, rejected = score_rule(rule, {"document_type": "Invoice"})
        assert score == SCORE_WEIGHTS["document_type"]
        assert "document_type" in matched
        assert rejected is False

    def test_mismatched_document_type_rejects(self):
        rule = _make_rule("R1", document_types=["Receipt"])
        score, _, rejected = score_rule(rule, {"document_type": "Invoice"})
        assert rejected is True
        assert score == 0

    def test_matching_condition_adds_weight(self):
        rule = _make_rule("R1", conditions={"payment_method": "cash"})
        score, matched, rejected = score_rule(rule, {"payment_method": "cash"})
        assert score == SCORE_WEIGHTS["payment_method"]
        assert "payment_method" in matched

    def test_mismatched_condition_rejects(self):
        rule = _make_rule("R1", conditions={"payment_method": "cash"})
        _, _, rejected = score_rule(rule, {"payment_method": "credit"})
        assert rejected is True

    def test_missing_condition_field_not_penalised(self):
        """If extraction doesn't have the condition field, rule is not rejected."""
        rule = _make_rule("R1", conditions={"payment_method": "cash"})
        score, _, rejected = score_rule(rule, {})
        assert rejected is False
        assert score == 0

    def test_boolean_condition_matching(self):
        rule = _make_rule("R1", conditions={"has_vat": True})
        score, _, rejected = score_rule(rule, {"has_vat": True})
        assert rejected is False
        assert score > 0

    def test_boolean_condition_mismatch_rejects(self):
        rule = _make_rule("R1", conditions={"has_vat": True})
        _, _, rejected = score_rule(rule, {"has_vat": False})
        assert rejected is True


# ---------------------------------------------------------------------------
# count_defined_conditions()
# ---------------------------------------------------------------------------

class TestCountDefinedConditions:
    def test_zero_conditions(self):
        rule = _make_rule("R1", conditions={})
        assert count_defined_conditions(rule) == 0

    def test_counts_non_empty_conditions(self):
        rule = _make_rule("R1", conditions={"payment_method": "cash", "has_vat": True, "vat_type": ""})
        # vat_type is "" — should not be counted
        assert count_defined_conditions(rule) == 2


# ---------------------------------------------------------------------------
# pick_best_rule()
# ---------------------------------------------------------------------------

class TestPickBestRuleNoCandidate:
    """No rules at all → UNRESOLVED_RULE."""

    def test_empty_rules_returns_unresolved(self):
        result = pick_best_rule({}, ())
        assert result["status"] == "UNRESOLVED_RULE"
        assert result["needs_review"] is True

    def test_all_rules_rejected_returns_unresolved(self):
        rule = _make_rule("R1", document_types=["Receipt"])
        result = pick_best_rule({"document_type": "Invoice"}, (rule,))
        assert result["status"] == "UNRESOLVED_RULE"


class TestPickBestRuleSingleWinner:
    def test_single_matching_rule_wins(self):
        rule = _make_rule("R1", document_types=["Invoice"])
        result = pick_best_rule({"document_type": "Invoice"}, (rule,))
        assert result["status"] == "OK"
        assert result["rule_id"] == "R1"
        assert result["needs_review"] is False

    def test_higher_score_wins(self):
        # R1: matches doc_type only (score=20)
        # R2: matches doc_type + payment_method (score=40)
        r1 = _make_rule("R1", document_types=["Invoice"])
        r2 = _make_rule("R2", document_types=["Invoice"], conditions={"payment_method": "cash"})
        extraction = {"document_type": "Invoice", "payment_method": "cash"}
        result = pick_best_rule(extraction, (r1, r2))
        assert result["rule_id"] == "R2"
        assert result["score"] == SCORE_WEIGHTS["document_type"] + SCORE_WEIGHTS["payment_method"]


class TestPickBestRuleTieBreak:
    """Equal score → specificity (more conditions) wins."""

    def test_higher_specificity_wins_on_equal_score(self):
        # Both score the same, but R2 has more defined conditions
        r1 = _make_rule("R1", conditions={"payment_method": "cash"})
        r2 = _make_rule("R2", conditions={"payment_method": "cash", "has_wht": False})
        extraction = {"payment_method": "cash"}
        result = pick_best_rule(extraction, (r1, r2))
        assert result["rule_id"] == "R2"
        assert result["needs_review"] is False

    def test_ambiguous_when_score_and_specificity_equal(self):
        """Tie on both score and specificity → ambiguous_rule flag."""
        r1 = _make_rule("R1", conditions={"payment_method": "cash"})
        r2 = _make_rule("R2", conditions={"payment_method": "cash"})
        extraction = {"payment_method": "cash"}
        result = pick_best_rule(extraction, (r1, r2))
        assert result["status"] == "OK"
        assert result["needs_review"] is True

    def test_ambiguous_flag_present_in_result(self):
        r1 = _make_rule("R1", document_types=["Invoice"])
        r2 = _make_rule("R2", document_types=["Invoice"])
        result = pick_best_rule({"document_type": "Invoice"}, (r1, r2))
        assert result["needs_review"] is True

    def test_clear_winner_not_ambiguous(self):
        r1 = _make_rule("R1", document_types=["Invoice"])
        r2 = _make_rule("R2", document_types=["Invoice"], conditions={"payment_method": "cash"})
        result = pick_best_rule({"document_type": "Invoice", "payment_method": "cash"}, (r1, r2))
        assert result["needs_review"] is False


class TestPickBestRuleScoreMatrix:
    """Full score weight matrix integration tests."""

    def test_source_document_highest_single_weight(self):
        """source_document weight 25 > document_type 20."""
        r_doc = _make_rule("R_DOC", document_types=["Invoice"])           # score=20
        r_src = _make_rule("R_SRC", conditions={"source_document": "P/O"})  # score=25
        extraction = {"document_type": "Invoice", "source_document": "P/O"}
        result = pick_best_rule(extraction, (r_doc, r_src))
        # R_SRC scores 25, R_DOC scores 20 (doc_type match rejected since no doc_type on rule)
        # Actually R_DOC would score 20, R_SRC would score 25 → R_SRC wins
        assert result["rule_id"] == "R_SRC"

    def test_combined_score_accumulates_all_matched_conditions(self):
        r = _make_rule(
            "R_FULL",
            document_types=["Invoice"],
            conditions={"payment_method": "cash", "source_document": "P/O", "has_vat": True, "has_wht": True},
        )
        extraction = {
            "document_type": "Invoice",
            "payment_method": "cash",
            "source_document": "P/O",
            "has_vat": True,
            "has_wht": True,
        }
        result = pick_best_rule(extraction, (r,))
        expected_score = (
            SCORE_WEIGHTS["document_type"]
            + SCORE_WEIGHTS["payment_method"]
            + SCORE_WEIGHTS["source_document"]
            + SCORE_WEIGHTS["has_vat"]
            + SCORE_WEIGHTS["has_wht"]
        )
        assert result["score"] == expected_score

    def test_zero_score_rule_still_qualifies_as_fallback(self):
        """Rule with no conditions and no doc_type constraint scores 0 but is not rejected."""
        fallback = _make_rule("FALLBACK")
        result = pick_best_rule({"document_type": "Invoice"}, (fallback,))
        assert result["status"] == "OK"
        assert result["score"] == 0
