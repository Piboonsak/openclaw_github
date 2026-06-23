"""Book Router — classify OCR documents to Express Accounting book types.

Routes each document to one of 6 Express books:
  12  ซื้อสด        Cash Purchase
  14  ซื้อเชื่อ      Credit Purchase
  15  ค่าใช้จ่าย    Other Expenses
  15W ค่าใช้จ่าย+WHT  Expenses with Withholding Tax (3%)
  22  ขายสด         Cash Sales
  24  ขายเชื่อ       Credit Sales

Routing rules are loaded from config/book_routing_rules.yaml so they can be
adjusted without a code change.

Task: TASK-1010
Spec: docs/requirement/phaseII/epic-10/EPIC-10-TASKS-DETAIL.md#task-1010
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class BookAssignment:
    book_id: str                 # "12" | "14" | "15" | "15W" | "22" | "24"
    template_name: str           # matches master template name in DB
    doc_number_series: str       # "YYMM/NNN" or "YYMM######"


class UnroutedDocumentError(Exception):
    """Raised when no routing rule matches the document's type."""


# ---------------------------------------------------------------------------
# Default routing rules (override via book_routing_rules.yaml)
# Open question: confirm purchase_cash vs purchase_credit distinction with client
# ---------------------------------------------------------------------------

_DEFAULT_RULES: dict[str, BookAssignment] = {
    "purchase_cash": BookAssignment(
        book_id="12",
        template_name="Express ซื้อสด (Cash Purchase)",
        doc_number_series="YYMM/NNN",
    ),
    "purchase_credit": BookAssignment(
        book_id="14",
        template_name="Express ซื้อเชื่อ (Credit Purchase)",
        doc_number_series="YYMM/NNN",
    ),
    "expense": BookAssignment(
        book_id="15",
        template_name="Express ค่าใช้จ่ายอื่นๆ (Other Expenses)",
        doc_number_series="YYMM/NNN",
    ),
    "service": BookAssignment(
        book_id="15",
        template_name="Express ค่าใช้จ่ายอื่นๆ (Other Expenses)",
        doc_number_series="YYMM/NNN",
    ),
    "sale_cash": BookAssignment(
        book_id="22",
        template_name="Express ขายสด (Cash Sales)",
        doc_number_series="YYMM######",
    ),
    "sale_credit": BookAssignment(
        book_id="24",
        template_name="Express ขายเชื่อ (Credit Sales)",
        doc_number_series="YYMM######",
    ),
}

# Book override when WHT is present (expense/service documents only)
_WHT_OVERRIDE = BookAssignment(
    book_id="15W",
    template_name="Express ค่าใช้จ่าย+หัก ณ ที่จ่าย (Expenses+WHT 3%)",
    doc_number_series="YYMM/NNN",
)


# ---------------------------------------------------------------------------
# BookRouter
# ---------------------------------------------------------------------------

class BookRouter:
    """Route a document dict to a BookAssignment.

    Usage::
        router = BookRouter()
        assignment = router.route(doc)
    """

    def __init__(self, rules: Optional[dict[str, BookAssignment]] = None) -> None:
        self._rules = rules or _DEFAULT_RULES

    def route(self, doc: dict) -> BookAssignment:
        """Return the BookAssignment for *doc*, or raise UnroutedDocumentError.

        Applies WHT override: if document_type is an expense/service type
        AND wht_amount > 0, routes to Book 15W instead of Book 15.
        """
        doc_type = (doc.get("document_type") or "").lower().strip()
        wht_amount = float(doc.get("wht_amount") or 0)

        assignment = self._rules.get(doc_type)
        if assignment is None:
            raise UnroutedDocumentError(
                f"No routing rule for document_type={doc_type!r}. "
                "Add a rule to book_routing_rules.yaml or confirm the type with the client."
            )

        # WHT override: expense/service documents with withholding tax → Book 15W
        if assignment.book_id == "15" and wht_amount > 0:
            return _WHT_OVERRIDE

        return assignment

    @classmethod
    def from_yaml(cls, path: str) -> "BookRouter":
        """Load routing rules from a YAML config file.

        YAML format::
            purchase_cash:
              book_id: "12"
              template_name: "Express ซื้อสด (Cash Purchase)"
              doc_number_series: "YYMM/NNN"

        Raises FileNotFoundError if path does not exist.
        """
        # TODO: implement YAML loading (TASK-1010 follow-up)
        raise NotImplementedError("YAML config loading not yet implemented (TASK-1010)")
