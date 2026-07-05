"""Mapping Rules import services (TASK-1203 company settings document-
ingestion workflow): DOCX AI-extraction preview + manual CRUD + upsert save,
backed by the previously-unused `AccountMappingRule` table.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pathlib import Path

from src.backend.db.models import AccountMappingRule, Company
from src.backend.services.rule_generator import _extract_docx_text, extract_mapping_rules


@dataclass
class MappingRuleErrorDetail:
    row_number: int
    message: str


@dataclass
class MappingRuleImportSummary:
    imported: int
    updated: int
    errors: list[MappingRuleErrorDetail] = field(default_factory=list)


class MappingRuleRepository(Protocol):
    async def company_exists(self, company_id: uuid.UUID) -> bool: ...

    async def get_by_vendor_doctype(
        self, company_id: uuid.UUID, vendor_name: str, document_type: str | None
    ) -> AccountMappingRule | None: ...

    async def add_rule(self, entry: AccountMappingRule) -> None: ...

    async def list_rules(self, company_id: uuid.UUID) -> list[AccountMappingRule]: ...

    async def get_rule(
        self, company_id: uuid.UUID, rule_id: uuid.UUID
    ) -> AccountMappingRule | None: ...

    async def delete_rule(self, entry: AccountMappingRule) -> None: ...


class SqlAlchemyMappingRuleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def company_exists(self, company_id: uuid.UUID) -> bool:
        return await self.db.get(Company, company_id) is not None

    async def get_by_vendor_doctype(
        self, company_id: uuid.UUID, vendor_name: str, document_type: str | None
    ) -> AccountMappingRule | None:
        stmt = select(AccountMappingRule).where(
            AccountMappingRule.company_id == company_id,
            AccountMappingRule.vendor_name == vendor_name,
            AccountMappingRule.document_type == document_type,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_rule(self, entry: AccountMappingRule) -> None:
        self.db.add(entry)
        await self.db.flush()

    async def list_rules(self, company_id: uuid.UUID) -> list[AccountMappingRule]:
        stmt = (
            select(AccountMappingRule)
            .where(AccountMappingRule.company_id == company_id)
            .order_by(AccountMappingRule.vendor_name.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_rule(
        self, company_id: uuid.UUID, rule_id: uuid.UUID
    ) -> AccountMappingRule | None:
        rule = await self.db.get(AccountMappingRule, rule_id)
        if rule is None or rule.company_id != company_id:
            return None
        return rule

    async def delete_rule(self, entry: AccountMappingRule) -> None:
        await self.db.delete(entry)
        await self.db.flush()


async def upsert_mapping_rules(
    repo: MappingRuleRepository,
    company_id: uuid.UUID,
    rows: list[dict[str, str | None]],
    created_by: uuid.UUID | None = None,
) -> MappingRuleImportSummary:
    if not await repo.company_exists(company_id):
        raise LookupError("Company not found")

    summary = MappingRuleImportSummary(imported=0, updated=0)
    for index, row in enumerate(rows, start=1):
        vendor_name = str(row.get("vendor_name") or "").strip()
        if not vendor_name:
            summary.errors.append(
                MappingRuleErrorDetail(row_number=index, message="vendor_name is required")
            )
            continue
        document_type = (row.get("document_type") or "").strip() or None
        debit_code = (row.get("recommended_debit_code") or "").strip() or None
        account_name = (row.get("recommended_account_name") or "").strip() or None

        existing = await repo.get_by_vendor_doctype(company_id, vendor_name, document_type)
        if existing is None:
            await repo.add_rule(
                AccountMappingRule(
                    company_id=company_id,
                    vendor_name=vendor_name,
                    document_type=document_type,
                    recommended_debit_code=debit_code,
                    recommended_account_name=account_name,
                    confirmed_count=1,
                    created_by=created_by,
                )
            )
            summary.imported += 1
        else:
            existing.recommended_debit_code = debit_code
            existing.recommended_account_name = account_name
            existing.confirmed_count += 1
            existing.last_confirmed_at = datetime.now(timezone.utc)
            summary.updated += 1

    return summary


async def extract_mapping_rules_preview_from_docx(
    docx_path: Path,
    company_name: str,
    business_type: str,
    chart_of_accounts: list[dict[str, object]],
) -> tuple[list[dict[str, str | None]], str]:
    """Extract raw text from an uploaded Mapping Rules DOCX and run the LLM
    rule-extraction pass (review-before-save, mirroring the COA PDF flow).
    Returns (rules, source_text_preview) — nothing is written to the database.
    """
    mapping_text = _extract_docx_text(docx_path)
    rules = extract_mapping_rules(
        company_name=company_name,
        business_type=business_type,
        mapping_text=mapping_text,
        chart_of_accounts=chart_of_accounts,
    )
    return rules, mapping_text[:2000]
