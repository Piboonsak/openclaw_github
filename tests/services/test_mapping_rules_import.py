"""Tests for Mapping Rules import services (TASK-1203 company settings
document-ingestion workflow) — the previously-unused `AccountMappingRule`
table finally gets a real read/write path.
"""

from __future__ import annotations

import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from src.backend.db.models import AccountMappingRule
from src.backend.services.mapping_rules_import import (
    extract_mapping_rules_preview_from_docx,
    upsert_mapping_rules,
)


class InMemoryMappingRuleRepository:
    def __init__(self, company_ids: list[uuid.UUID] | None = None) -> None:
        self.company_ids = set(company_ids or [])
        self.rules: dict[tuple[uuid.UUID, str, str | None], AccountMappingRule] = {}

    async def company_exists(self, company_id: uuid.UUID) -> bool:
        return company_id in self.company_ids

    async def get_by_vendor_doctype(self, company_id, vendor_name, document_type):
        return self.rules.get((company_id, vendor_name, document_type))

    async def add_rule(self, entry: AccountMappingRule) -> None:
        self.rules[(entry.company_id, entry.vendor_name, entry.document_type)] = entry

    async def list_rules(self, company_id: uuid.UUID):
        return [r for (cid, _, _), r in self.rules.items() if cid == company_id]

    async def get_rule(self, company_id, rule_id):
        for r in self.rules.values():
            if r.company_id == company_id and getattr(r, "id", None) == rule_id:
                return r
        return None

    async def delete_rule(self, entry) -> None:
        key = next(k for k, v in self.rules.items() if v is entry)
        del self.rules[key]


class TestUpsertMappingRules(unittest.IsolatedAsyncioTestCase):
    async def test_creates_new_rule(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryMappingRuleRepository([company_id])
        rows = [
            {
                "vendor_name": "OfficeMate",
                "document_type": "Invoice",
                "recommended_debit_code": "5100",
                "recommended_account_name": "Office Supplies",
            }
        ]

        summary = await upsert_mapping_rules(repo, company_id, rows)

        self.assertEqual(summary.imported, 1)
        self.assertEqual(summary.updated, 0)
        saved = repo.rules[(company_id, "OfficeMate", "Invoice")]
        self.assertEqual(saved.recommended_debit_code, "5100")
        self.assertEqual(saved.confirmed_count, 1)

    async def test_reconfirm_increments_confirmed_count(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryMappingRuleRepository([company_id])
        rows = [{"vendor_name": "OfficeMate", "document_type": "Invoice",
                  "recommended_debit_code": "5100", "recommended_account_name": "Office Supplies"}]
        await upsert_mapping_rules(repo, company_id, rows)

        summary2 = await upsert_mapping_rules(repo, company_id, rows)

        self.assertEqual(summary2.imported, 0)
        self.assertEqual(summary2.updated, 1)
        self.assertEqual(repo.rules[(company_id, "OfficeMate", "Invoice")].confirmed_count, 2)

    async def test_missing_vendor_name_collected_as_error(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryMappingRuleRepository([company_id])

        summary = await upsert_mapping_rules(repo, company_id, [{"vendor_name": ""}])

        self.assertEqual(len(summary.errors), 1)

    async def test_unknown_company_raises_lookup_error(self) -> None:
        repo = InMemoryMappingRuleRepository([])
        with self.assertRaises(LookupError):
            await upsert_mapping_rules(repo, uuid.uuid4(), [])


class TestExtractMappingRulesPreviewFromDocx(unittest.IsolatedAsyncioTestCase):
    async def test_extraction_uses_docx_text_and_llm_helper(self) -> None:
        fake_rules = [
            {
                "vendor_name": "OfficeMate",
                "document_type": "Invoice",
                "recommended_debit_code": "5100",
                "recommended_account_name": "Office Supplies",
            }
        ]
        with patch(
            "src.backend.services.mapping_rules_import._extract_docx_text",
            return_value="ซื้อของใช้สำนักงานจาก OfficeMate บันทึกบัญชี 5100",
        ) as mock_docx, patch(
            "src.backend.services.mapping_rules_import.extract_mapping_rules",
            return_value=fake_rules,
        ) as mock_extract:
            rules, preview = await extract_mapping_rules_preview_from_docx(
                Path("fake.docx"),
                company_name="Test Co",
                business_type="retail",
                chart_of_accounts=[{"code": "5100", "name": "Office Supplies"}],
            )

        mock_docx.assert_called_once()
        mock_extract.assert_called_once()
        self.assertEqual(rules, fake_rules)
        self.assertIn("OfficeMate", preview)


if __name__ == "__main__":
    unittest.main()
