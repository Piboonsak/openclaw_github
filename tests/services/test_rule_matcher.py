from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from src.backend.services.rule_engine import pick_best_rule, run_journal_router
from src.backend.services.rule_loader import load_company_rules


def test_pick_best_rule_prefers_po_specific_rule() -> None:
    with TemporaryDirectory() as tmp:
        rules_root = Path(tmp) / "rules"
        company_root = rules_root / "co_match"
        company_root.mkdir(parents=True, exist_ok=True)
        (rules_root / "global").mkdir(parents=True, exist_ok=True)
        schema_path = Path("d:/01_gitrepo/ai-accounting-copilot/rules/rule_schema.json")
        (rules_root / "rule_schema.json").write_text(
            schema_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        payload = {
            "company": {"name": "Match Co", "business_type": "service"},
            "chart_of_accounts": [
                {"code": "5040-00", "name": "ค่าวัสดุสำนักงาน", "type": "expense"},
                {"code": "2195-00", "name": "เจ้าหนี้การค้า", "type": "liability"},
            ],
            "journal_entry_rules": [
                {
                    "rule_id": "RRL-PURCHASE-SUPPLIES",
                    "name": "Purchase Supplies",
                    "document_types": ["Tax Invoice"],
                    "transaction_type": "purchase",
                    "book_code": "PV",
                    "conditions": {
                        "payment_method": "credit",
                        "source_document": "P/O",
                        "has_vat": True,
                        "vat_type": "normal",
                        "has_wht": False,
                    },
                    "entries": [
                        {
                            "side": "debit",
                            "account_code": "5040-00",
                            "amount_field": "net_amount",
                        },
                        {
                            "side": "credit",
                            "account_code": "2195-00",
                            "amount_field": "payable_amount",
                        },
                    ],
                    "validation": {"balance_check": "debit_total == credit_total"},
                }
            ],
        }
        (company_root / "rule_coa.yaml").write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

        loaded = load_company_rules(
            "co_match",
            rules_root=rules_root,
            schema_path=rules_root / "rule_schema.json",
        )
        extraction = {
            "document_type": "Tax Invoice",
            "payment_method": "credit",
            "source_document": "P/O",
            "has_vat": True,
            "vat_type": "normal",
            "has_wht": False,
        }

        chosen = pick_best_rule(extraction, loaded.journal_rules)

        assert chosen["status"] == "OK"
        assert chosen["rule_id"] == "RRL-PURCHASE-SUPPLIES"
        assert chosen["score"] >= 55


def test_pick_best_rule_uses_specificity_on_score_tie() -> None:
    with TemporaryDirectory() as tmp:
        rules_root = Path(tmp) / "rules"
        company_root = rules_root / "comp_tie"
        company_root.mkdir(parents=True, exist_ok=True)
        (rules_root / "global").mkdir(parents=True, exist_ok=True)
        schema_path = Path("d:/01_gitrepo/ai-accounting-copilot/rules/rule_schema.json")
        (rules_root / "rule_schema.json").write_text(
            schema_path.read_text(encoding="utf-8"), encoding="utf-8"
        )
        payload = {
            "company": {"name": "Tie Co", "business_type": "service"},
            "chart_of_accounts": [
                {"code": "1111-00", "name": "เงินสด", "type": "asset"}
            ],
            "journal_entry_rules": [
                {
                    "rule_id": "RULE-GENERIC",
                    "name": "Generic",
                    "document_types": ["Invoice"],
                    "transaction_type": "generic",
                    "book_code": "PV",
                    "entries": [
                        {
                            "side": "debit",
                            "account_code": "1111-00",
                            "amount_field": "gross_amount",
                        }
                    ],
                    "validation": {"balance_check": "debit_total == credit_total"},
                },
                {
                    "rule_id": "RULE-SPECIFIC",
                    "name": "Specific",
                    "document_types": ["Invoice"],
                    "transaction_type": "specific",
                    "book_code": "PV",
                    "conditions": {"custom_hint": "x"},
                    "entries": [
                        {
                            "side": "debit",
                            "account_code": "1111-00",
                            "amount_field": "gross_amount",
                        }
                    ],
                    "validation": {"balance_check": "debit_total == credit_total"},
                },
            ],
        }
        (company_root / "rule_coa.yaml").write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

        loaded = load_company_rules(
            "comp_tie",
            rules_root=rules_root,
            schema_path=rules_root / "rule_schema.json",
        )
        chosen = pick_best_rule({"document_type": "Invoice"}, loaded.journal_rules)

        assert chosen["status"] == "OK"
        assert chosen["rule_id"] == "RULE-SPECIFIC"
        assert chosen["specificity"] == 1


def test_run_journal_router_marks_unresolved_when_no_rule_matches() -> None:
    extraction_output = {
        "sha256": "receipt-no-match",
        "company_id": "comp_1_ritlerlert",
        "fields": {
            "total_amount": "100.00",
            "source_text": "Receipt without VAT and no purchase order reference",
            "amount_paid": "100.00",
        },
    }

    with TemporaryDirectory() as tmp:
        output = run_journal_router(
            extraction_output,
            company_id="comp_1_ritlerlert",
            cache_root=Path(tmp) / "cache",
            rules_root=Path("d:/01_gitrepo/ai-accounting-copilot/rules"),
        )

    assert output["status"] == "UNRESOLVED_RULE"
    assert "unresolved_rule" in output["flags"]
