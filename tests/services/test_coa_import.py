"""Tests for Chart of Accounts import services (TASK-1203).

Covers:
  ac_1203_coa_yaml / ac_1203_coa_csv — YAML/CSV parsing
  ac_1203_coa_upsert                 — upsert by account_code
  ac_1203_coa_pdf / ac_1203_coa_review — PDF extraction preview (LLM mocked,
    no real API calls — this is a repo-side unit test, not a live LLM check)
"""

from __future__ import annotations

import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from src.backend.db.models import ChartOfAccount
from src.backend.services.coa_import import (
    extract_coa_preview_from_pdf,
    parse_coa_file,
    upsert_chart_of_accounts,
)


class InMemoryCoaRepository:
    def __init__(self, company_ids: list[uuid.UUID] | None = None) -> None:
        self.company_ids = set(company_ids or [])
        self.accounts: dict[tuple[uuid.UUID, str], ChartOfAccount] = {}

    async def company_exists(self, company_id: uuid.UUID) -> bool:
        return company_id in self.company_ids

    async def get_account_by_code(self, company_id: uuid.UUID, account_code: str):
        return self.accounts.get((company_id, account_code))

    async def add_account(self, entry: ChartOfAccount) -> None:
        self.accounts[(entry.company_id, entry.account_code)] = entry

    async def list_accounts(self, company_id: uuid.UUID):
        return sorted(
            (a for (cid, _), a in self.accounts.items() if cid == company_id),
            key=lambda a: a.account_code,
        )


class TestParseCoaFile(unittest.TestCase):
    def test_parses_csv(self) -> None:
        content = b"account_code,account_name,account_type\n1100,\xe0\xb9\x80\xe0\xb8\x87\xe0\xb8\xb4\xe0\xb8\x99\xe0\xb8\xaa\xe0\xb8\x94,asset\n"
        rows = parse_coa_file(content, "coa.csv")
        self.assertEqual(rows[0]["account_code"], "1100")
        self.assertEqual(rows[0]["account_type"], "asset")

    def test_parses_yaml(self) -> None:
        content = b"accounts:\n  - code: '1100'\n    name: cash\n    type: asset\n"
        rows = parse_coa_file(content, "coa.yaml")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["account_code"], "1100")
        self.assertEqual(rows[0]["account_name"], "cash")

    def test_yaml_defaults_missing_type_to_expense(self) -> None:
        content = b"accounts:\n  - code: '5100'\n    name: office supplies\n"
        rows = parse_coa_file(content, "coa.yml")
        self.assertEqual(rows[0]["account_type"], "expense")


class TestUpsertChartOfAccounts(unittest.IsolatedAsyncioTestCase):
    async def test_creates_new_accounts(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryCoaRepository([company_id])
        rows = [{"account_code": "1100", "account_name": "Cash", "account_type": "asset"}]

        summary = await upsert_chart_of_accounts(repo, company_id, rows)

        self.assertEqual(summary.imported, 1)
        self.assertEqual(summary.updated, 0)
        self.assertEqual(repo.accounts[(company_id, "1100")].account_name, "Cash")

    async def test_reimport_updates_not_duplicates(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryCoaRepository([company_id])
        rows = [{"account_code": "1100", "account_name": "Cash", "account_type": "asset"}]
        await upsert_chart_of_accounts(repo, company_id, rows)

        rows2 = [{"account_code": "1100", "account_name": "Cash On Hand", "account_type": "asset"}]
        summary2 = await upsert_chart_of_accounts(repo, company_id, rows2)

        self.assertEqual(summary2.imported, 0)
        self.assertEqual(summary2.updated, 1)
        self.assertEqual(len(repo.accounts), 1)
        self.assertEqual(repo.accounts[(company_id, "1100")].account_name, "Cash On Hand")

    async def test_missing_code_or_name_collected_as_error(self) -> None:
        company_id = uuid.uuid4()
        repo = InMemoryCoaRepository([company_id])
        rows = [{"account_code": "", "account_name": "No Code", "account_type": "asset"}]

        summary = await upsert_chart_of_accounts(repo, company_id, rows)

        self.assertEqual(summary.imported, 0)
        self.assertEqual(len(summary.errors), 1)

    async def test_unknown_company_raises_lookup_error(self) -> None:
        repo = InMemoryCoaRepository([])
        with self.assertRaises(LookupError):
            await upsert_chart_of_accounts(repo, uuid.uuid4(), [])


class TestExtractCoaPreviewFromPdf(unittest.IsolatedAsyncioTestCase):
    async def test_extraction_uses_ocr_and_llm_helper(self) -> None:
        """No real OCR/LLM call — mocks both so this stays a fast, free unit test."""
        fake_ocr_output = {"blocks": [{"text": "1100 Cash Asset"}]}
        fake_accounts = [{"code": "1100", "name": "Cash", "type": "asset", "confidence": 90}]

        with patch("src.backend.services.coa_import.run_ocr", return_value=fake_ocr_output) as mock_ocr, \
             patch(
                 "src.backend.services.coa_import.extract_chart_of_accounts",
                 return_value=fake_accounts,
             ) as mock_extract:
            result = await extract_coa_preview_from_pdf(
                Path("fake.pdf"), company_name="Test Co", business_type="retail"
            )

        mock_ocr.assert_called_once()
        mock_extract.assert_called_once()
        self.assertEqual(result, fake_accounts)

    async def test_empty_ocr_text_raises(self) -> None:
        with patch("src.backend.services.coa_import.run_ocr", return_value={"blocks": []}):
            with self.assertRaises(RuntimeError):
                await extract_coa_preview_from_pdf(
                    Path("fake.pdf"), company_name="Test Co", business_type="retail"
                )


if __name__ == "__main__":
    unittest.main()
