"""Routine document workflow routes (W4 SIT closure Pack B — Upload -> Process
-> Review Scan -> Review Mapping, `TASK-W4-SIT-E2E-CLAUDE-IMPLEMENT-ROUTINE-
OPS-05`).

Routes:
  POST /v1/companies/{id}/documents/upload        — real multi-file upload
  GET  /v1/companies/{id}/documents               — list (optional ?status=)
  GET  /v1/documents/{id}                         — detail incl. extraction + voucher
  POST /v1/documents/{id}/process                 — run the real OCR/extraction/
                                                     journal-routing pipeline
  POST /v1/documents/{id}/approve                 — Review Scan approve
  POST /v1/companies/{id}/documents/approve-all   — Review Scan approve all
  POST /v1/documents/{id}/flag                    — Review Scan flag
  PUT  /v1/documents/{id}/fields                  — Review Scan header-field edit
  GET  /v1/documents/{id}/file                    — real stored-file bytes for preview/download
  PUT  /v1/journal-vouchers/{id}/lines/{line_id}  — Review Mapping account-code edit
  POST /v1/journal-vouchers/{id}/confirm          — Review Mapping confirm
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from src.backend.api.schemas.document_schemas import (
    ApproveAllRequest,
    ApproveAllResult,
    DocumentDetailResponse,
    DocumentFieldsUpdateRequest,
    DocumentResponse,
    DocumentUploadResult,
    FlagRequest,
    JournalLineResponse,
    JournalLineUpdateRequest,
    JournalVoucherResponse,
)
from src.backend.auth.dependencies import ensure_company_access, get_current_active_user
from src.backend.db.models import Document, JournalVoucher, User
from src.backend.db.session import get_db
from src.backend.pipeline.orchestrator import run_pipeline
from src.backend.services.document_workflow import (
    SqlAlchemyDocumentRepository,
    approve_document,
    apply_pipeline_result,
    confirm_journal_voucher,
    create_document,
    flag_document,
    update_document_fields,
    update_journal_line,
)
from src.backend.storage import get_storage_client, materialize_local_cache, store_document_bytes

router = APIRouter()
logger = logging.getLogger(__name__)

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024
_ALLOWED_UPLOAD_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def _document_to_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=str(document.id),
        filename=document.filename,
        original_filename=document.original_filename,
        status=document.status,
        scan_status=document.scan_status,
        content_type=document.content_type,
        file_size_bytes=document.file_size_bytes,
        invoice_number=document.invoice_number,
        invoice_date=document.invoice_date.isoformat() if document.invoice_date else None,
        seller_name=document.seller_name,
        buyer_tax_id=document.buyer_tax_id,
        taxid_match=document.taxid_match,
        net_amount=float(document.net_amount) if document.net_amount is not None else None,
        vat_amount=float(document.vat_amount) if document.vat_amount is not None else None,
        wht_amount=float(document.wht_amount) if document.wht_amount is not None else None,
        total_amount=float(document.total_amount) if document.total_amount is not None else None,
        overall_confidence=(
            float(document.overall_confidence) if document.overall_confidence is not None else None
        ),
        processing_error=document.processing_error,
        created_at=document.created_at.isoformat() if document.created_at else "",
    )


def _voucher_to_response(voucher: JournalVoucher) -> JournalVoucherResponse:
    return JournalVoucherResponse(
        id=str(voucher.id),
        voucher_no=voucher.voucher_no,
        voucher_date=voucher.voucher_date.isoformat() if voucher.voucher_date else "",
        book_code=voucher.book_code,
        rule_id=voucher.rule_id,
        status=voucher.status,
        is_balanced=voucher.is_balanced,
        total_debit=float(voucher.total_debit) if voucher.total_debit is not None else None,
        total_credit=float(voucher.total_credit) if voucher.total_credit is not None else None,
        flags=(voucher.flags or {}).get("flags", []),
        lines=[
            JournalLineResponse(
                id=str(line.id),
                line_order=line.line_order,
                account_code=line.account_code,
                account_name=line.account_name,
                is_debit=line.is_debit,
                amount=float(line.amount),
                description=line.description,
            )
            for line in sorted(voucher.lines, key=lambda ln: ln.line_order)
        ],
    )


def _document_to_detail_response(document: Document) -> DocumentDetailResponse:
    base = _document_to_response(document).model_dump()
    latest_extraction = document.extractions[-1] if document.extractions else None
    voucher = document.journal_vouchers[0] if document.journal_vouchers else None
    return DocumentDetailResponse(
        **base,
        extraction_fields=(
            (latest_extraction.extraction_json or {}).get("fields", {}) if latest_extraction else {}
        ),
        confidence_per_field=(latest_extraction.confidence_per_field or {}) if latest_extraction else {},
        critical_flags=(latest_extraction.critical_flags or {}) if latest_extraction else {},
        voucher=_voucher_to_response(voucher) if voucher else None,
    )


async def _get_document_or_404(repo: SqlAlchemyDocumentRepository, document_id: uuid.UUID) -> Document:
    document = await repo.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


async def _get_voucher_or_404(
    repo: SqlAlchemyDocumentRepository, voucher_id: uuid.UUID
) -> JournalVoucher:
    voucher = await repo.get_voucher(voucher_id)
    if voucher is None:
        raise HTTPException(status_code=404, detail="Journal voucher not found")
    return voucher


@router.post(
    "/v1/companies/{company_id}/documents/upload", response_model=DocumentUploadResult
)
async def upload_documents(
    company_id: uuid.UUID,
    files: list[UploadFile] = File(..., description="One or more document files"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DocumentUploadResult:
    await ensure_company_access(db, current_user, company_id)
    repo = SqlAlchemyDocumentRepository(db)
    if not await repo.company_exists(company_id):
        raise HTTPException(status_code=404, detail="Company not found")

    created: list[Document] = []
    for upload in files:
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in _ALLOWED_UPLOAD_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type '{ext}' for '{upload.filename}'. "
                f"Accepted: pdf, jpg, jpeg, png",
            )

        try:
            content = await upload.read()
            if not content:
                raise HTTPException(status_code=400, detail=f"'{upload.filename}' is empty")
            if len(content) > _MAX_UPLOAD_BYTES:
                raise HTTPException(status_code=413, detail=f"'{upload.filename}' exceeds 20 MB")

            stored = store_document_bytes(
                content=content,
                filename=upload.filename,
                company_id=str(company_id),
                content_type=upload.content_type,
            )
            materialize_local_cache(
                content=content,
                filename=upload.filename,
                sha256=stored["sha256"],
            )

            document = await create_document(
                repo,
                company_id,
                filename=upload.filename or stored["sha256"],
                original_filename=upload.filename,
                storage_key=stored["storage_key"],
                sha256=stored["sha256"],
                file_size_bytes=len(content),
                content_type=upload.content_type,
                uploaded_by=current_user.id,
            )
            created.append(document)
        except HTTPException:
            raise
        except Exception:
            logger.exception(
                "Document upload failed company_id=%s user_id=%s filename=%s content_type=%s storage_provider=%s upload_root=%s",
                company_id,
                current_user.id,
                upload.filename,
                upload.content_type,
                settings.STORAGE_PROVIDER,
                settings.UPLOAD_ROOT,
            )
            raise

    return DocumentUploadResult(documents=[_document_to_response(d) for d in created])


@router.get("/v1/companies/{company_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    company_id: uuid.UUID,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[DocumentResponse]:
    await ensure_company_access(db, current_user, company_id)
    repo = SqlAlchemyDocumentRepository(db)
    if not await repo.company_exists(company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    documents = await repo.list_documents(company_id, status)
    return [_document_to_response(d) for d in documents]


@router.get("/v1/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document_detail(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DocumentDetailResponse:
    repo = SqlAlchemyDocumentRepository(db)
    document = await _get_document_or_404(repo, document_id)
    await ensure_company_access(db, current_user, document.company_id)
    return _document_to_detail_response(document)


@router.post("/v1/documents/{document_id}/process", response_model=DocumentDetailResponse)
async def process_document_now(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DocumentDetailResponse:
    """Run the real OCR -> extraction -> Stage C -> journal-routing pipeline
    (the same `run_pipeline` the pre-existing `/process` endpoint uses)
    synchronously and persist the result. A live Celery/Redis broker is not
    assumed to be running, so this is a direct, real, non-background call —
    see the Pack B completion report for what Copilot must re-verify for true
    async/background behavior on SIT.
    """
    repo = SqlAlchemyDocumentRepository(db)
    document = await _get_document_or_404(repo, document_id)
    await ensure_company_access(db, current_user, document.company_id)
    company = await repo.get_company(document.company_id)

    ext = Path(document.filename or "").suffix.lower() or ".bin"
    local_path = settings.UPLOAD_ROOT / f"{document.sha256}{ext}"
    if not local_path.exists():
        logger.warning(
            "Document process blocked missing local cache document_id=%s company_id=%s local_path=%s storage_provider=%s",
            document.id,
            document.company_id,
            local_path,
            settings.STORAGE_PROVIDER,
        )
        raise HTTPException(status_code=409, detail="Source file is no longer available for processing")

    document.status = "processing"
    await repo.flush()

    try:
        ctx = await run_pipeline(
            str(local_path),
            company_id=str(document.company_id),
            company_tax_id=company.tax_id if company else None,
        )
        await apply_pipeline_result(repo, document, ctx)
    except Exception:
        logger.exception(
            "Document process failed document_id=%s company_id=%s local_path=%s ocr_engine=%s stage_c_provider=%s openrouter_key_present=%s",
            document.id,
            document.company_id,
            local_path,
            settings.OCR_ENGINE,
            settings.STAGE_C_PROVIDER,
            bool(settings.OPENROUTER_API_KEY),
        )
        raise

    document = await _get_document_or_404(repo, document_id)
    return _document_to_detail_response(document)


@router.post("/v1/documents/{document_id}/approve", response_model=DocumentResponse)
async def approve_document_scan(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DocumentResponse:
    repo = SqlAlchemyDocumentRepository(db)
    document = await _get_document_or_404(repo, document_id)
    await ensure_company_access(db, current_user, document.company_id)
    document = await approve_document(repo, document, current_user.id)
    return _document_to_response(document)


@router.post(
    "/v1/companies/{company_id}/documents/approve-all", response_model=ApproveAllResult
)
async def approve_all_documents(
    company_id: uuid.UUID,
    body: ApproveAllRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> ApproveAllResult:
    await ensure_company_access(db, current_user, company_id)
    repo = SqlAlchemyDocumentRepository(db)
    if body.document_ids:
        try:
            doc_uuids = [uuid.UUID(doc_id) for doc_id in body.document_ids]
        except ValueError:
            raise HTTPException(status_code=400, detail="document_ids must be valid UUIDs")
        targets = [await _get_document_or_404(repo, doc_uuid) for doc_uuid in doc_uuids]
        for document in targets:
            if document.company_id != company_id:
                raise HTTPException(status_code=403, detail="Document does not belong to this company")
    else:
        targets = await repo.list_documents(company_id, "review_scan")

    for document in targets:
        await approve_document(repo, document, current_user.id)
    return ApproveAllResult(approved=len(targets))


@router.post("/v1/documents/{document_id}/flag", response_model=DocumentResponse)
async def flag_document_scan(
    document_id: uuid.UUID,
    body: FlagRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DocumentResponse:
    repo = SqlAlchemyDocumentRepository(db)
    document = await _get_document_or_404(repo, document_id)
    await ensure_company_access(db, current_user, document.company_id)
    document = await flag_document(
        repo, document, current_user.id, reason=body.reason, comment=body.comment
    )
    return _document_to_response(document)


@router.put("/v1/documents/{document_id}/fields", response_model=DocumentResponse)
async def update_document_header_fields(
    document_id: uuid.UUID,
    body: DocumentFieldsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> DocumentResponse:
    """Review Scan header-field correction (`TC-RWG03-04`) — persists edits to
    the core extracted fields shown on that screen, recording a
    `FieldCorrection` per changed value."""
    repo = SqlAlchemyDocumentRepository(db)
    document = await _get_document_or_404(repo, document_id)
    await ensure_company_access(db, current_user, document.company_id)
    document = await update_document_fields(
        repo, document, current_user.id, body.model_dump(exclude_unset=True)
    )
    return _document_to_response(document)


@router.get("/v1/documents/{document_id}/file")
async def get_document_file(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Response:
    """Real stored-file bytes for the Review Scan/Mapping in-page preview or
    download — not a placeholder. Fetched by the frontend via `apiFetch` (so
    the auth header attaches) and rendered from a blob URL."""
    repo = SqlAlchemyDocumentRepository(db)
    document = await _get_document_or_404(repo, document_id)
    await ensure_company_access(db, current_user, document.company_id)
    if not document.storage_key:
        raise HTTPException(status_code=404, detail="No stored file for this document")
    try:
        content = get_storage_client().download_bytes(document.storage_key)
    except Exception as exc:  # storage backends raise different types (local: FileNotFoundError; S3/MinIO: ClientError)
        raise HTTPException(status_code=404, detail=f"Stored file is missing: {exc}")
    return Response(content=content, media_type=document.content_type or "application/octet-stream")


@router.put(
    "/v1/journal-vouchers/{voucher_id}/lines/{line_id}",
    response_model=JournalVoucherResponse,
)
async def update_voucher_line(
    voucher_id: uuid.UUID,
    line_id: uuid.UUID,
    body: JournalLineUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JournalVoucherResponse:
    repo = SqlAlchemyDocumentRepository(db)
    voucher = await _get_voucher_or_404(repo, voucher_id)
    document = await _get_document_or_404(repo, voucher.document_id)
    await ensure_company_access(db, current_user, document.company_id)
    line = next((ln for ln in voucher.lines if ln.id == line_id), None)
    if line is None:
        raise HTTPException(status_code=404, detail="Journal line not found on this voucher")

    voucher = await update_journal_line(
        repo,
        voucher,
        line,
        current_user.id,
        account_code=body.account_code,
        account_name=body.account_name,
        amount=body.amount,
    )
    return _voucher_to_response(voucher)


@router.post(
    "/v1/journal-vouchers/{voucher_id}/confirm", response_model=JournalVoucherResponse
)
async def confirm_voucher(
    voucher_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> JournalVoucherResponse:
    repo = SqlAlchemyDocumentRepository(db)
    voucher = await _get_voucher_or_404(repo, voucher_id)
    document = await _get_document_or_404(repo, voucher.document_id)
    await ensure_company_access(db, current_user, document.company_id)
    try:
        voucher = await confirm_journal_voucher(repo, voucher, document, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _voucher_to_response(voucher)
