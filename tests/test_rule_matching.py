"""D4-02: Test matrix for rule matching policy — score, tie-break, unresolved, rejected.

These tests exercise pick_best_rule() and score_rule() using flat extraction dicts
(the same format that _derive_routing_context() produces in production) and lightweight
rule objects whose attributes match those accessed by the engine.
"""

from src.backend.services.rule_engine import pick_best_rule


def _make_rule(rule_id: str, document_type: str = "", conditions: dict | None = None):
    """Build a minimal rule object compatible with score_rule() and count_defined_conditions().

    The engine reads:
      rule.rule_id          — identifier
      rule.document_types   — tuple of accepted doc types
      rule.conditions       — dict of field → expected_value used for scoring
    """

    class _R:
        pass

    r = _R()
    r.rule_id = rule_id
    r.document_types = (document_type,) if document_type else ()
    r.conditions = conditions or {}
    return r


class TestRuleMatchingDecisions:
    """D4-02: Rule matching tie-break and ambiguity detection."""

    def test_returns_unresolved_when_no_rule_matches(self):
        """No rules → UNRESOLVED_RULE status with needs_review=True."""
        extraction = {"document_type": "Unknown"}
        rules = ()

        result = pick_best_rule(extraction, rules)

        assert result["status"] == "UNRESOLVED_RULE"
        assert result["needs_review"] is True

    def test_winner_by_score(self):
        """Winner selected by highest score when multiple rules match."""
        # r3 matches document_type + 2 extra conditions → highest score
        # r1 matches document_type + 1 condition
        # r2 matches document_type only
        extraction = {"document_type": "Invoice", "has_vat": True, "has_wht": True}
        rules = (
            _make_rule("r1", "Invoice", {"has_vat": True}),
            _make_rule("r2", "Invoice"),
            _make_rule("r3", "Invoice", {"has_vat": True, "has_wht": True}),
        )

        result = pick_best_rule(extraction, rules)

        assert result["status"] == "OK"
        assert result["rule_id"] == "r3"
        assert result["needs_review"] is False

    def test_tie_break_by_specificity_when_scores_match(self):
        """When scores tie, rule with more defined conditions (higher specificity) wins."""
        # All three rules match the same fields so their SCORES are equal.
        # Specificity = number of non-empty conditions entries.
        # r2 has the most conditions → wins tie.
        extraction = {"document_type": "PO"}
        rules = (
            _make_rule("r1", "PO", {"cond_a": "x", "cond_b": "x", "cond_c": "x"}),
            _make_rule("r2", "PO", {"cond_a": "x", "cond_b": "x", "cond_c": "x",
                                    "cond_d": "x", "cond_e": "x", "cond_f": "x",
                                    "cond_g": "x"}),
            _make_rule("r3", "PO", {"cond_a": "x", "cond_b": "x", "cond_c": "x",
                                    "cond_d": "x", "cond_e": "x"}),
        )

        result = pick_best_rule(extraction, rules)

        assert result["status"] == "OK"
        assert result["rule_id"] == "r2"
        assert result["needs_review"] is False

    def test_full_tie_flags_needs_review_with_ambiguous_signal(self):
        """Score + specificity both equal → needs_review=True (ambiguous routing)."""
        extraction = {"document_type": "Receipt"}
        rules = (
            _make_rule("r1", "Receipt", {"cond_a": "x", "cond_b": "x"}),
            _make_rule("r2", "Receipt", {"cond_a": "x", "cond_b": "x"}),
        )

        result = pick_best_rule(extraction, rules)

        assert result["status"] == "OK"
        assert result["needs_review"] is True

    def test_rejected_rule_is_excluded(self):
        """Rule whose document_type mismatches extraction is rejected; lower-score match wins."""
        # r1 has a richer condition set but its document_type doesn't match → rejected.
        # r2 matches → wins despite fewer conditions.
        extraction = {"document_type": "Invoice"}
        rules = (
            _make_rule("r1", "PO", {"has_vat": True, "has_wht": True}),  # rejected
            _make_rule("r2", "Invoice"),                                   # accepted
        )

        result = pick_best_rule(extraction, rules)

        assert result["status"] == "OK"
        assert result["rule_id"] == "r2"

    def test_document_type_mismatch_rejects_rule(self):
        """Rule with mismatched document_type is excluded; correct-type rule wins."""
        extraction = {"document_type": "Invoice"}
        rules = (
            _make_rule("r1", "PO"),       # mismatched → rejected
            _make_rule("r2", "Invoice"),  # match
        )

        result = pick_best_rule(extraction, rules)

        assert result["status"] == "OK"
        assert result["rule_id"] == "r2"

    def test_unresolved_extraction_flags_payload(self):
        """All rules rejected (doc-type mismatch) → UNRESOLVED_RULE."""
        # The only rule requires document_type "Invoice" but extraction says "PO".
        extraction = {"document_type": "PO"}
        rules = (_make_rule("r1", "Invoice"),)

        result = pick_best_rule(extraction, rules)

        assert result["status"] == "UNRESOLVED_RULE"
        assert result["needs_review"] is True
