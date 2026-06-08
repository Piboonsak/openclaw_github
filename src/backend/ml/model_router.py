"""Model routing policy for extraction stage (TASK-502, D2)."""

from __future__ import annotations


def should_escalate_to_sonnet(
    *,
    page_count: int,
    ocr_confidence: float,
    low_confidence_fields: int,
    rule_conflict: bool,
) -> bool:
    """Apply D2 escalation gates.

    Escalate when any of the following are true:
    - page_count > 3
    - ocr_confidence < 0.80
    - low_confidence_fields > 2
    - rule_conflict is True
    """
    return (
        page_count > 3
        or ocr_confidence < 0.80
        or low_confidence_fields > 2
        or rule_conflict
    )


def pick_model(escalated_to_sonnet: bool) -> str:
    """Return model id according to routing decision."""
    if escalated_to_sonnet:
        return "claude-sonnet-4-6-20250601"
    return "claude-haiku-4-5-20250514"
