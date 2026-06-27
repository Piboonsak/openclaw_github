"""SQLAlchemy ORM models for the AI Pre-Accounting Copilot.

Multi-tenant schema:
  Tenant  = accounting firm (top-level entity)
  Company = client company managed by the tenant
  User    = person within a tenant, assigned to one or more companies

All user-data tables carry company_id for row-level isolation.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SqlEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.backend.db.base import Base
from src.backend.db.enums import MatchType


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime, server_default=func.now())


# ---------------------------------------------------------------------------
# Tenant & Company
# ---------------------------------------------------------------------------


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    settings: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = _now()

    companies: Mapped[list[Company]] = relationship(back_populates="tenant")
    users: Mapped[list[User]] = relationship(back_populates="tenant")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(100))
    tax_id: Mapped[str] = mapped_column(String(13), unique=True, nullable=False)
    branch_code: Mapped[str] = mapped_column(String(5), default="00000")
    address: Mapped[str | None] = mapped_column(Text)
    business_type: Mapped[str | None] = mapped_column(String(50))
    settings: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    tenant: Mapped[Tenant] = relationship(back_populates="companies")
    documents: Mapped[list[Document]] = relationship(back_populates="company")
    chart_of_accounts: Mapped[list[ChartOfAccount]] = relationship(
        back_populates="company"
    )
    account_mapping_rules: Mapped[list[AccountMappingRule]] = relationship(
        back_populates="company"
    )
    export_templates: Mapped[list[ExportTemplate]] = relationship(
        back_populates="company"
    )
    document_batches: Mapped[list[DocumentBatch]] = relationship(
        back_populates="company"
    )
    export_jobs: Mapped[list[ExportJob]] = relationship(back_populates="company")
    credit_plans: Mapped[list[CompanyCreditPlan]] = relationship(
        back_populates="company"
    )
    page_credit_usage_entries: Mapped[list[PageCreditUsage]] = relationship(
        back_populates="company"
    )
    vendor_master_entries: Mapped[list[VendorMaster]] = relationship(
        back_populates="company"
    )
    customer_master_entries: Mapped[list[CustomerMaster]] = relationship(
        back_populates="company"
    )
    account_mapping_cache_entries: Mapped[list[AccountMappingCache]] = relationship(
        back_populates="company"
    )


# ---------------------------------------------------------------------------
# Users & RBAC
# ---------------------------------------------------------------------------


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(50), default="staff")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = _now()

    tenant: Mapped[Tenant] = relationship(back_populates="users")
    company_assignments: Mapped[list[UserCompanyAssignment]] = relationship(
        back_populates="user"
    )


class UserCompanyAssignment(Base):
    __tablename__ = "user_company_assignments"

    id: Mapped[uuid.UUID] = _uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    role_override: Mapped[str | None] = mapped_column(String(50))
    assigned_at: Mapped[datetime] = _now()

    user: Mapped[User] = relationship(back_populates="company_assignments")
    company: Mapped[Company] = relationship()

    __table_args__ = (
        UniqueConstraint("user_id", "company_id", name="uq_user_company"),
    )


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class DocumentBatch(Base):
    __tablename__ = "document_batches"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    batch_label: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="draft")
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company] = relationship(back_populates="document_batches")
    documents: Mapped[list[Document]] = relationship(back_populates="batch")

    __table_args__ = (
        Index("ix_batches_company_status", "company_id", "status"),
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    storage_key: Mapped[str | None] = mapped_column(Text)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(100))
    document_type: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="uploaded")
    sha256: Mapped[str | None] = mapped_column(String(64))
    page_count: Mapped[int | None] = mapped_column(Integer)

    # Denormalized extraction header fields for query performance
    buyer_tax_id: Mapped[str | None] = mapped_column(String(13))
    buyer_name: Mapped[str | None] = mapped_column(String(255))
    seller_tax_id: Mapped[str | None] = mapped_column(String(13))
    seller_name: Mapped[str | None] = mapped_column(String(255))
    invoice_number: Mapped[str | None] = mapped_column(String(100))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    net_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    vat_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    wht_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    total_amount: Mapped[float | None] = mapped_column(Numeric(15, 2))
    has_vat: Mapped[bool] = mapped_column(Boolean, default=False)
    vat_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), default=7.00)
    wht_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), default=0.00)
    taxid_match: Mapped[bool | None] = mapped_column(Boolean)
    overall_confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    processing_error: Mapped[str | None] = mapped_column(Text)
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_batches.id", ondelete="SET NULL")
    )
    scan_status: Mapped[str] = mapped_column(String(20), default="pending")
    scan_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    scan_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime)
    processing_progress: Mapped[dict | None] = mapped_column(JSONB)

    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company] = relationship(back_populates="documents")
    batch: Mapped[DocumentBatch | None] = relationship(back_populates="documents")
    extractions: Mapped[list[Extraction]] = relationship(back_populates="document")
    journal_vouchers: Mapped[list[JournalVoucher]] = relationship(
        back_populates="document"
    )
    flags: Mapped[list[DocumentFlag]] = relationship(back_populates="document")
    field_corrections: Mapped[list[FieldCorrection]] = relationship(
        back_populates="document"
    )
    export_job_documents: Mapped[list[ExportJobDocument]] = relationship(
        back_populates="document"
    )
    page_credit_usage_entries: Mapped[list[PageCreditUsage]] = relationship(
        back_populates="document"
    )

    __table_args__ = (
        Index("ix_documents_company_status", "company_id", "status"),
        Index("ix_documents_sha256", "sha256"),
    )


# ---------------------------------------------------------------------------
# Extractions
# ---------------------------------------------------------------------------


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    extraction_json: Mapped[dict | None] = mapped_column(JSONB)
    confidence_per_field: Mapped[dict | None] = mapped_column(JSONB)
    reconciliation: Mapped[dict | None] = mapped_column(JSONB)
    stage_c_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    stage_c_provider: Mapped[str | None] = mapped_column(String(50))
    stage_c_model: Mapped[str | None] = mapped_column(String(100))
    critical_flags: Mapped[dict | None] = mapped_column(JSONB)
    schema_version: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = _now()

    document: Mapped[Document] = relationship(back_populates="extractions")


# ---------------------------------------------------------------------------
# Journal Vouchers & Lines
# ---------------------------------------------------------------------------


class JournalVoucher(Base):
    __tablename__ = "journal_vouchers"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    voucher_no: Mapped[str | None] = mapped_column(String(50))
    voucher_date: Mapped[date] = mapped_column(Date, nullable=False)
    book_code: Mapped[str | None] = mapped_column(String(10))
    rule_id: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50), default="draft")
    is_balanced: Mapped[bool | None] = mapped_column(Boolean)
    total_debit: Mapped[float | None] = mapped_column(Numeric(15, 2))
    total_credit: Mapped[float | None] = mapped_column(Numeric(15, 2))
    flags: Mapped[dict | None] = mapped_column(JSONB)
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = _now()

    document: Mapped[Document] = relationship(back_populates="journal_vouchers")
    lines: Mapped[list[JournalLine]] = relationship(back_populates="voucher")


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id: Mapped[uuid.UUID] = _uuid_pk()
    voucher_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("journal_vouchers.id", ondelete="CASCADE"), nullable=False
    )
    line_order: Mapped[int] = mapped_column(Integer, nullable=False)
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    account_name: Mapped[str | None] = mapped_column(String(150))
    is_debit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(15, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_variable: Mapped[bool] = mapped_column(Boolean, default=False)
    amount_field: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = _now()

    voucher: Mapped[JournalVoucher] = relationship(back_populates="lines")


# ---------------------------------------------------------------------------
# Chart of Accounts
# ---------------------------------------------------------------------------


class ChartOfAccount(Base):
    __tablename__ = "chart_of_accounts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    account_code: Mapped[str] = mapped_column(String(50), nullable=False)
    account_name: Mapped[str] = mapped_column(String(150), nullable=False)
    account_type: Mapped[str | None] = mapped_column(String(50))
    parent_code: Mapped[str | None] = mapped_column(String(50))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _now()

    company: Mapped[Company] = relationship(back_populates="chart_of_accounts")

    __table_args__ = (
        UniqueConstraint(
            "company_id", "account_code", name="uq_company_account_code"
        ),
    )


# ---------------------------------------------------------------------------
# ML Feedback Loop — Account Mapping Rules
# ---------------------------------------------------------------------------


class AccountMappingRule(Base):
    __tablename__ = "account_mapping_rules"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str | None] = mapped_column(String(50))
    recommended_debit_code: Mapped[str | None] = mapped_column(String(50))
    recommended_account_name: Mapped[str | None] = mapped_column(String(150))
    confirmed_count: Mapped[int] = mapped_column(Integer, default=1)
    last_confirmed_at: Mapped[datetime] = _now()
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    company: Mapped[Company] = relationship(back_populates="account_mapping_rules")

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "vendor_name",
            "document_type",
            name="uq_company_vendor_doctype",
        ),
    )


# ---------------------------------------------------------------------------
# Export Templates (Template Engine)
# ---------------------------------------------------------------------------


class ExportTemplate(Base):
    __tablename__ = "export_templates"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    template_name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_type: Mapped[str] = mapped_column(String(50), nullable=False)
    columns: Mapped[dict | None] = mapped_column(JSONB)
    static_values: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    header_mappings: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    file_format: Mapped[str] = mapped_column(String(10), default="csv")
    delimiter: Mapped[str] = mapped_column(String(5), default=",")
    encoding: Mapped[str] = mapped_column(String(20), default="utf-8")
    is_master: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    cloned_from: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("export_templates.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company | None] = relationship(back_populates="export_templates")


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("export_templates.id", ondelete="SET NULL")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    total_documents: Mapped[int] = mapped_column(Integer, default=0)
    file_format: Mapped[str] = mapped_column(String(10), default="csv")
    encoding: Mapped[str] = mapped_column(String(20), default="utf-8")
    created_at: Mapped[datetime] = _now()

    company: Mapped[Company] = relationship(back_populates="export_jobs")
    files: Mapped[list[ExportFile]] = relationship(back_populates="export_job")
    export_documents: Mapped[list[ExportJobDocument]] = relationship(
        back_populates="export_job"
    )

    __table_args__ = (
        Index("ix_export_jobs_company", "company_id"),
    )


class ExportFile(Base):
    __tablename__ = "export_files"

    id: Mapped[uuid.UUID] = _uuid_pk()
    export_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("export_jobs.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer)
    download_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = _now()

    export_job: Mapped[ExportJob] = relationship(back_populates="files")


class ExportJobDocument(Base):
    __tablename__ = "export_job_documents"

    id: Mapped[uuid.UUID] = _uuid_pk()
    export_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("export_jobs.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )

    export_job: Mapped[ExportJob] = relationship(back_populates="export_documents")
    document: Mapped[Document] = relationship(back_populates="export_job_documents")

    __table_args__ = (
        UniqueConstraint(
            "export_job_id",
            "document_id",
            name="uq_export_job_document",
        ),
    )


# ---------------------------------------------------------------------------
# Cost Tracking
# ---------------------------------------------------------------------------


class ApiUsage(Base):
    __tablename__ = "api_usage"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    provider: Mapped[str | None] = mapped_column(String(50))
    model: Mapped[str | None] = mapped_column(String(100))
    stage: Mapped[str | None] = mapped_column(String(20))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6))
    tier: Mapped[str | None] = mapped_column(String(10))
    was_skipped: Mapped[bool] = mapped_column(Boolean, default=False)
    skip_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()

    __table_args__ = (
        Index("ix_api_usage_company_created", "company_id", "created_at"),
    )


class BudgetLimit(Base):
    __tablename__ = "budget_limits"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE")
    )
    limit_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[str] = mapped_column(String(10), nullable=False)
    max_usd: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    alert_threshold_pct: Mapped[int] = mapped_column(Integer, default=80)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class CompanyCreditPlan(Base):
    __tablename__ = "company_credit_plans"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    plan_name: Mapped[str] = mapped_column(String(100), nullable=False)
    billing_model: Mapped[str] = mapped_column(String(30), default="page_credit")
    included_page_credits: Mapped[int] = mapped_column(Integer, default=0)
    price_original_thb: Mapped[float | None] = mapped_column(Numeric(12, 2))
    price_effective_thb: Mapped[float | None] = mapped_column(Numeric(12, 2))
    cycle_start: Mapped[date | None] = mapped_column(Date)
    cycle_end: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    company: Mapped[Company] = relationship(back_populates="credit_plans")

    __table_args__ = (
        Index("ix_credit_plans_company_active", "company_id", "is_active"),
    )


class PageCreditUsage(Base):
    __tablename__ = "page_credit_usage"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    batch_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("document_batches.id", ondelete="SET NULL")
    )
    document_type: Mapped[str | None] = mapped_column(String(50))
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    credits_used: Mapped[int] = mapped_column(Integer, default=1)
    usage_reason: Mapped[str] = mapped_column(String(30), default="scan")
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _now()

    company: Mapped[Company] = relationship(back_populates="page_credit_usage_entries")
    document: Mapped[Document | None] = relationship(
        back_populates="page_credit_usage_entries"
    )
    batch: Mapped[DocumentBatch | None] = relationship()

    __table_args__ = (
        Index("ix_page_credit_company_created", "company_id", "created_at"),
        Index("ix_page_credit_document", "document_id"),
    )


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="SET NULL")
    )
    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL")
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    old_values: Mapped[dict | None] = mapped_column(JSONB)
    new_values: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _now()

    __table_args__ = (
        Index("ix_audit_logs_company_action", "company_id", "action"),
        Index("ix_audit_logs_created", "created_at"),
    )


class DocumentFlag(Base):
    __tablename__ = "document_flags"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    flagged_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open")
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = _now()

    document: Mapped[Document] = relationship(back_populates="flags")

    __table_args__ = (
        Index("ix_flags_document_status", "document_id", "status"),
    )


class FieldCorrection(Base):
    __tablename__ = "field_corrections"

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    corrected_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = _now()

    document: Mapped[Document] = relationship(back_populates="field_corrections")

    __table_args__ = (
        Index("ix_corrections_document", "document_id"),
    )


# ---------------------------------------------------------------------------
# PDPA Data Retention
# ---------------------------------------------------------------------------


class DataRetentionPolicy(Base):
    __tablename__ = "data_retention_policies"

    id: Mapped[uuid.UUID] = _uuid_pk()
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE")
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=30)
    action: Mapped[str] = mapped_column(String(20), default="delete")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = _now()


# ---------------------------------------------------------------------------
# BL-001 Vendor / Customer Master Cache
# ---------------------------------------------------------------------------


class VendorMaster(Base):
    __tablename__ = "vendor_master"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    vendor_code: Mapped[str] = mapped_column(String(20), nullable=False)
    vendor_name: Mapped[str] = mapped_column(Text, nullable=False)
    gl_code: Mapped[str | None] = mapped_column(String(10))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _now()

    company: Mapped[Company] = relationship(back_populates="vendor_master_entries")

    __table_args__ = (
        UniqueConstraint("company_id", "vendor_code", name="uq_vendor_company_code"),
    )


class CustomerMaster(Base):
    __tablename__ = "customer_master"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    customer_code: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_name: Mapped[str] = mapped_column(Text, nullable=False)
    ar_flag: Mapped[int] = mapped_column(SmallInteger, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = _now()

    company: Mapped[Company] = relationship(back_populates="customer_master_entries")

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "customer_code",
            name="uq_customer_company_code",
        ),
    )


class AccountMappingCache(Base):
    __tablename__ = "account_mapping_cache"

    id: Mapped[uuid.UUID] = _uuid_pk()
    company_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    ocr_name: Mapped[str] = mapped_column(Text, nullable=False)
    matched_code: Mapped[str] = mapped_column(String(20), nullable=False)
    match_type: Mapped[MatchType] = mapped_column(
        SqlEnum(
            MatchType,
            name="match_type",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = _now()

    company: Mapped[Company] = relationship(
        back_populates="account_mapping_cache_entries"
    )

    __table_args__ = (
        Index("ix_mapping_company_ocr_name", "company_id", "ocr_name"),
    )
