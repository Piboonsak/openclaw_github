"""Routine document workflow persistence (W4 SIT closure Pack B — Upload ->
Process -> Review Scan -> Review Mapping, `TASK-W4-SIT-E2E-CLAUDE-IMPLEMENT-
ROUTINE-OPS-05`).

This module does not implement OCR/extraction/journal-routing itself — it
persists the output of the already-proven `src.backend.pipeline.orchestrator.
run_pipeline()` (the same function the pre-existing `/process` endpoint calls)
into the `Document`/`Extraction`/`JournalVoucher`/`JournalLine` tables, and
manages the review-state transitions those tables were designed for
(`DocumentStatus`: uploaded -> processing -> review_scan -> scan_approved /
scan_flagged -> review_mapping -> mapping_confirmed).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.backend.db.enums import DocumentStatus
from src.backend.db.models import (
    Company,
    Document,
    DocumentFlag,
    Extraction,
    FieldCorrection,
    JournalLine,
    JournalVoucher,
)


def _to_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _to_amount(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class DocumentRepository(Protocol):
    async def company_exists(self, company_id: uuid.UUID) -> bool: ...

    async def get_company(self, company_id: uuid.UUID) -> Company | None: ...

    async def add_document(self, document: Document) -> None: ...

    async def get_document(self, document_id: uuid.UUID) -> Document | None: ...

    async def list_documents(
        self, company_id: uuid.UUID, status: str | None
    ) -> list[Document]: ...

    async def add_extraction(self, extraction: Extraction) -> None: ...

    async def add_voucher(self, voucher: JournalVoucher) -> None: ...

    async def add_line(self, line: JournalLine) -> None: ...

    async def get_voucher(self, voucher_id: uuid.UUID) -> JournalVoucher | None: ...

    async def get_line(self, line_id: uuid.UUID) -> JournalLine | None: ...

    async def add_flag(self, flag: DocumentFlag) -> None: ...

    async def add_field_correction(self, correction: FieldCorrection) -> None: ...

    async def flush(self) -> None: ...


class SqlAlchemyDocumentRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def company_exists(self, company_id: uuid.UUID) -> bool:
        return await self.db.get(Company, company_id) is not None

    async def get_company(self, company_id: uuid.UUID) -> Company | None:
        return await self.db.get(Company, company_id)

    async def add_document(self, document: Document) -> None:
        self.db.add(document)
        await self.db.flush()

    async def get_document(self, document_id: uuid.UUID) -> Document | None:
        stmt = (
            select(Document)
            .where(Document.id == document_id)
            .options(
                selectinload(Document.extractions),
                selectinload(Document.journal_vouchers).selectinload(
                    JournalVoucher.lines
                ),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_documents(
        self, company_id: uuid.UUID, status: str | None = None
    ) -> list[Document]:
        stmt = select(Document).where(Document.company_id == company_id)
        if status:
            stmt = stmt.where(Document.status == status)
        stmt = stmt.order_by(Document.created_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_extraction(self, extraction: Extraction) -> None:
        self.db.add(extraction)
        await self.db.flush()

    async def add_voucher(self, voucher: JournalVoucher) -> None:
        self.db.add(voucher)
        await self.db.flush()

    async def add_line(self, line: JournalLine) -> None:
        self.db.add(line)

    async def get_voucher(self, voucher_id: uuid.UUID) -> JournalVoucher | None:
        stmt = (
            select(JournalVoucher)
            .where(JournalVoucher.id == voucher_id)
            .options(selectinload(JournalVoucher.lines))
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_line(self, line_id: uuid.UUID) -> JournalLine | None:
        return await self.db.get(JournalLine, line_id)

    async def add_flag(self, flag: DocumentFlag) -> None:
        self.db.add(flag)
        await self.db.flush()

    async def add_field_correction(self, correction: FieldCorrection) -> None:
        self.db.add(correction)

    async def flush(self) -> None:
        await self.db.flush()


async def create_document(
    repo: DocumentRepository,
    company_id: uuid.UUID,
    *,
    filename: str,
    original_filename: str | None,
    storage_key: str | None,
    sha256: str | None,
    file_size_bytes: int | None,
    content_type: str | None,
    uploaded_by: uuid.UUID | None,
) -> Document:
    if not await repo.company_exists(company_id):
        raise LookupError("Company not found")
    document = Document(
        company_id=company_id,
        filename=filename,
        original_filename=original_filename,
        storage_key=storage_key,
        sha256=sha256,
        file_size_bytes=file_size_bytes,
        content_type=content_type,
        uploaded_by=uploaded_by,
        status=DocumentStatus.UPLOADED.value,
    )
    await repo.add_document(document)
    return document


@dataclass
class ProcessOutcome:
    document: Document
    extraction: Extraction | None
    voucher: JournalVoucher | None


@dataclass
class PipelinePersistencePlan:
    """Pure, I/O-free mapping from a `PipelineContext` to the fields/rows that
    need persisting. Shared by both real runtime paths that call
    `run_pipeline` — the synchronous `POST /v1/documents/{id}/process` API
    (async SQLAlchemy) and the Celery `process_document` task (sync
    SQLAlchemy) — so the two never drift into different business rules about
    what a pipeline result means for the DB, only how it's written."""

    status: str
    processing_error: str | None
    document_fields: dict[str, Any]
    extraction_kwargs: dict[str, Any] | None
    voucher_kwargs: dict[str, Any] | None
    line_specs: list[dict[str, Any]]


def build_pipeline_persistence_plan(ctx: Any) -> PipelinePersistencePlan:
    if ctx.error:
        return PipelinePersistencePlan(
            status=DocumentStatus.FAILED.value,
            processing_error=str(ctx.error),
            document_fields={},
            extraction_kwargs=None,
            voucher_kwargs=None,
            line_specs=[],
        )

    extraction_output = ctx.extraction_output or {}
    fields = extraction_output.get("fields", {})
    invoice_date = _to_date(fields.get("invoice_date"))

    document_fields = {
        "buyer_tax_id": fields.get("buyer_tax_id"),
        "buyer_name": fields.get("buyer_name"),
        "seller_tax_id": fields.get("seller_tax_id"),
        "seller_name": fields.get("seller_name"),
        "invoice_number": fields.get("invoice_number"),
        "invoice_date": invoice_date,
        "net_amount": _to_amount(fields.get("net_amount")),
        "vat_amount": _to_amount(fields.get("vat_amount")),
        "wht_amount": _to_amount(fields.get("wht_amount")),
        "total_amount": _to_amount(fields.get("total_amount")),
        "has_vat": bool(_to_amount(fields.get("vat_amount"))),
        "taxid_match": extraction_output.get("tax_id_match"),
        "overall_confidence": ctx.overall_confidence,
        "scan_status": "pending",
    }

    extraction_kwargs = {
        "extraction_json": extraction_output,
        "confidence_per_field": extraction_output.get("confidence_per_field") or {},
        "reconciliation": extraction_output.get("reconciliation"),
        "stage_c_applied": bool(ctx.stage_c_applied),
        "stage_c_provider": extraction_output.get("stage_c_provider"),
        "stage_c_model": extraction_output.get("stage_c_model"),
        "critical_flags": extraction_output.get("critical_flags"),
    }

    voucher_kwargs: dict[str, Any] | None = None
    line_specs: list[dict[str, Any]] = []
    journal_output = ctx.journal_output or {}
    postings = journal_output.get("postings") or []
    if postings:
        totals = journal_output.get("totals") or {}
        voucher_kwargs = {
            "voucher_date": invoice_date or date.today(),
            "book_code": journal_output.get("journal_code"),
            "rule_id": journal_output.get("rule_id"),
            "status": "draft",
            "is_balanced": journal_output.get("is_balanced"),
            "total_debit": _to_amount(totals.get("debit")),
            "total_credit": _to_amount(totals.get("credit")),
            "flags": {"flags": journal_output.get("flags", [])},
        }
        for index, posting in enumerate(postings, start=1):
            debit = _to_amount(posting.get("debit")) or 0.0
            credit = _to_amount(posting.get("credit")) or 0.0
            is_debit = debit > 0
            line_specs.append(
                {
                    "line_order": index,
                    "account_code": str(posting.get("account_code") or "0000"),
                    "account_name": posting.get("account_name"),
                    "is_debit": is_debit,
                    "amount": debit if is_debit else credit,
                    "description": posting.get("description") or posting.get("line_type"),
                    "is_variable": bool(posting.get("is_variable")),
                    "amount_field": posting.get("amount_field"),
                }
            )

    return PipelinePersistencePlan(
        status=DocumentStatus.REVIEW_SCAN.value,
        processing_error=None,
        document_fields=document_fields,
        extraction_kwargs=extraction_kwargs,
        voucher_kwargs=voucher_kwargs,
        line_specs=line_specs,
    )


async def apply_pipeline_result(
    repo: DocumentRepository, document: Document, ctx: Any
) -> ProcessOutcome:
    """Persist a `PipelineContext` (from `run_pipeline`) onto `document`:
    denormalized header fields + a new `Extraction` row, plus a
    `JournalVoucher`/`JournalLine` set built from `ctx.journal_output`'s
    `postings` when journal routing produced any. Advances `document.status`
    to `review_scan`, or to `failed` with `processing_error` set on pipeline
    error — never leaves a document stuck in `processing`.
    """
    plan = build_pipeline_persistence_plan(ctx)
    document.status = plan.status
    document.processing_error = plan.processing_error
    for field_name, value in plan.document_fields.items():
        setattr(document, field_name, value)

    if plan.extraction_kwargs is None:
        await repo.flush()
        return ProcessOutcome(document=document, extraction=None, voucher=None)

    extraction = Extraction(document_id=document.id, **plan.extraction_kwargs)
    await repo.add_extraction(extraction)

    voucher: JournalVoucher | None = None
    if plan.voucher_kwargs is not None:
        voucher = JournalVoucher(document_id=document.id, **plan.voucher_kwargs)
        await repo.add_voucher(voucher)
        for spec in plan.line_specs:
            await repo.add_line(JournalLine(voucher_id=voucher.id, **spec))
        await repo.flush()

    return ProcessOutcome(document=document, extraction=extraction, voucher=voucher)


_EDITABLE_DOCUMENT_FIELDS = (
    "invoice_number",
    "invoice_date",
    "seller_name",
    "buyer_tax_id",
    "net_amount",
    "vat_amount",
    "wht_amount",
    "total_amount",
)


async def update_document_fields(
    repo: DocumentRepository,
    document: Document,
    user_id: uuid.UUID | None,
    updates: dict[str, Any],
) -> Document:
    """Apply human corrections to the core extracted header fields shown on
    the Review Scan screen, recording a `FieldCorrection` per changed value —
    the same before/after audit trail Review Mapping's account-code edit
    already uses."""
    for field_name in _EDITABLE_DOCUMENT_FIELDS:
        if field_name not in updates:
            continue
        raw_value = updates[field_name]
        if field_name == "invoice_date":
            new_value = _to_date(raw_value)
        elif field_name in ("net_amount", "vat_amount", "wht_amount", "total_amount"):
            new_value = _to_amount(raw_value)
        else:
            new_value = raw_value or None

        old_value = getattr(document, field_name)
        if old_value != new_value:
            await repo.add_field_correction(
                FieldCorrection(
                    document_id=document.id,
                    field_name=field_name,
                    old_value=str(old_value) if old_value is not None else None,
                    new_value=str(new_value) if new_value is not None else None,
                    corrected_by=user_id,
                )
            )
            setattr(document, field_name, new_value)
    await repo.flush()
    return document


async def approve_document(repo: DocumentRepository, document: Document, user_id: uuid.UUID) -> Document:
    document.status = DocumentStatus.SCAN_APPROVED.value
    document.scan_status = "approved"
    document.scan_reviewed_by = user_id
    document.scan_reviewed_at = datetime.now(timezone.utc)
    await repo.flush()
    return document


async def flag_document(
    repo: DocumentRepository,
    document: Document,
    user_id: uuid.UUID,
    *,
    reason: str,
    comment: str | None,
) -> Document:
    document.status = DocumentStatus.SCAN_FLAGGED.value
    document.scan_status = "flagged"
    flag = DocumentFlag(
        document_id=document.id,
        flagged_by=user_id,
        reason=reason,
        comment=comment,
    )
    await repo.add_flag(flag)
    return document


def _recompute_voucher_totals(voucher: JournalVoucher) -> None:
    total_debit = sum(float(line.amount) for line in voucher.lines if line.is_debit)
    total_credit = sum(float(line.amount) for line in voucher.lines if not line.is_debit)
    voucher.total_debit = round(total_debit, 2)
    voucher.total_credit = round(total_credit, 2)
    voucher.is_balanced = abs(total_debit - total_credit) < 0.01


async def update_journal_line(
    repo: DocumentRepository,
    voucher: JournalVoucher,
    line: JournalLine,
    user_id: uuid.UUID | None,
    *,
    account_code: str,
    account_name: str | None,
    amount: float | None,
) -> JournalVoucher:
    if line.account_code != account_code:
        await repo.add_field_correction(
            FieldCorrection(
                document_id=voucher.document_id,
                field_name=f"journal_line.{line.id}.account_code",
                old_value=line.account_code,
                new_value=account_code,
                corrected_by=user_id,
            )
        )
    line.account_code = account_code
    if account_name is not None:
        line.account_name = account_name
    if amount is not None:
        line.amount = amount
    _recompute_voucher_totals(voucher)
    await repo.flush()
    return voucher


async def confirm_journal_voucher(
    repo: DocumentRepository, voucher: JournalVoucher, document: Document, user_id: uuid.UUID
) -> JournalVoucher:
    if not voucher.is_balanced:
        raise ValueError("Voucher is not balanced — Dr and Cr totals must match before confirming")
    voucher.status = "confirmed"
    voucher.confirmed_by = user_id
    voucher.confirmed_at = datetime.now(timezone.utc)
    document.status = DocumentStatus.MAPPING_CONFIRMED.value
    await repo.flush()
    return voucher
