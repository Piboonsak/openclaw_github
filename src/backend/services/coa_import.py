"""Chart of Accounts import services (TASK-1203): YAML/CSV upsert + PDF
AI-extraction preview. Reuses the existing, proven `rule_generator` OCR/LLM
helpers rather than re-implementing PDF text extraction or prompt-building.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.models import ChartOfAccount, Company
from src.backend.ml.ocr import run_ocr
from src.backend.services.rule_generator import extract_chart_of_accounts


@dataclass
class CoaImportErrorDetail:
    row_number: int
    message: str


@dataclass
class CoaImportSummary:
    imported: int
    updated: int
    errors: list[CoaImportErrorDetail] = field(default_factory=list)


def _normalize_type(value: str | None) -> str:
    normalized = str(value or "").strip().lower()
    return normalized or "expense"


def parse_coa_file(content: bytes, filename: str) -> list[dict[str, str]]:
    """Parse a COA import file as YAML (`accounts: [...]`) or CSV
    (`account_code,account_name,account_type` header row required).
    """
    suffix = Path(filename or "").suffix.lower()
    text = content.decode("utf-8-sig", errors="replace")

    if suffix in {".yaml", ".yml"}:
        payload = yaml.safe_load(text) or {}
        accounts = payload.get("accounts", []) if isinstance(payload, dict) else []
        if not isinstance(accounts, list):
            raise ValueError("YAML file must have a top-level 'accounts' list")
        rows = []
        for entry in accounts:
            if not isinstance(entry, dict):
                continue
            rows.append(
                {
                    "account_code": str(entry.get("code", "")).strip(),
                    "account_name": str(entry.get("name", "")).strip(),
                    "account_type": _normalize_type(entry.get("type")),
                }
            )
        return rows

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV header row is required (account_code,account_name,account_type)")
    rows = []
    for row in reader:
        rows.append(
            {
                "account_code": str(row.get("account_code", "")).strip(),
                "account_name": str(row.get("account_name", "")).strip(),
                "account_type": _normalize_type(row.get("account_type")),
            }
        )
    return rows


class CoaRepository(Protocol):
    async def company_exists(self, company_id: uuid.UUID) -> bool: ...

    async def get_account_by_code(
        self, company_id: uuid.UUID, account_code: str
    ) -> ChartOfAccount | None: ...

    async def add_account(self, entry: ChartOfAccount) -> None: ...

    async def list_accounts(self, company_id: uuid.UUID) -> list[ChartOfAccount]: ...


class SqlAlchemyCoaRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def company_exists(self, company_id: uuid.UUID) -> bool:
        return await self.db.get(Company, company_id) is not None

    async def get_account_by_code(
        self, company_id: uuid.UUID, account_code: str
    ) -> ChartOfAccount | None:
        stmt = select(ChartOfAccount).where(
            ChartOfAccount.company_id == company_id,
            ChartOfAccount.account_code == account_code,
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def add_account(self, entry: ChartOfAccount) -> None:
        self.db.add(entry)
        await self.db.flush()

    async def list_accounts(self, company_id: uuid.UUID) -> list[ChartOfAccount]:
        stmt = (
            select(ChartOfAccount)
            .where(ChartOfAccount.company_id == company_id)
            .order_by(ChartOfAccount.account_code.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


async def upsert_chart_of_accounts(
    repo: CoaRepository,
    company_id: uuid.UUID,
    rows: list[dict[str, str]],
) -> CoaImportSummary:
    """Upsert COA rows by account_code (ac_1203_coa_upsert): update existing
    accounts, create new ones, reject rows missing code/name.
    """
    if not await repo.company_exists(company_id):
        raise LookupError("Company not found")

    summary = CoaImportSummary(imported=0, updated=0)
    for index, row in enumerate(rows, start=2):
        code = str(row.get("account_code", "")).strip()
        name = str(row.get("account_name", "")).strip()
        account_type = _normalize_type(row.get("account_type"))
        if not code or not name:
            summary.errors.append(
                CoaImportErrorDetail(
                    row_number=index, message="account_code and account_name are required"
                )
            )
            continue

        existing = await repo.get_account_by_code(company_id, code)
        if existing is None:
            await repo.add_account(
                ChartOfAccount(
                    company_id=company_id,
                    account_code=code,
                    account_name=name,
                    account_type=account_type,
                    is_active=True,
                )
            )
            summary.imported += 1
        else:
            existing.account_name = name
            existing.account_type = account_type
            summary.updated += 1

    return summary


def ocr_pdf_to_text(pdf_path: Path | str) -> str:
    """OCR a COA PDF into plain text. Split out of
    `extract_coa_preview_from_pdf` so the Celery worker can report OCR and
    LLM as separate progress stages (W4-SIT-E2E-COA-ASYNC-10).
    """
    ocr_output = run_ocr(str(pdf_path))
    return "\n".join(
        str(block.get("text", "")).strip()
        for block in ocr_output.get("blocks", [])
        if str(block.get("text", "")).strip()
    )


async def extract_coa_preview_from_pdf(
    pdf_path: Path,
    company_name: str,
    business_type: str,
) -> list[dict[str, object]]:
    """Run OCR + LLM extraction on an uploaded COA PDF and return a
    review-before-save preview (ac_1203_coa_pdf / ac_1203_coa_review). Does
    not touch the database — the caller must POST the (possibly edited)
    result to the confirm/upsert endpoint to persist it.
    """
    coa_text = ocr_pdf_to_text(pdf_path)
    if not coa_text.strip():
        raise RuntimeError("COA PDF yielded no readable text.")

    return extract_chart_of_accounts(
        company_name=company_name,
        business_type=business_type,
        coa_text=coa_text,
    )
