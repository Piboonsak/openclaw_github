"""Initial schema — all Phase II tables.

Revision ID: 001
Revises: None
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("settings", JSONB),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- Companies ---
    op.create_table(
        "companies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("short_name", sa.String(100)),
        sa.Column("tax_id", sa.String(13), unique=True, nullable=False),
        sa.Column("branch_code", sa.String(5), server_default="00000"),
        sa.Column("address", sa.Text),
        sa.Column("business_type", sa.String(50)),
        sa.Column("settings", JSONB),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- Users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("display_name", sa.String(255)),
        sa.Column("role", sa.String(50), server_default="staff"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("last_login", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- User ↔ Company Assignments ---
    op.create_table(
        "user_company_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role_override", sa.String(50)),
        sa.Column("assigned_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "company_id", name="uq_user_company"),
    )

    # --- Documents ---
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "uploaded_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("storage_key", sa.Text),
        sa.Column("file_size_bytes", sa.Integer),
        sa.Column("content_type", sa.String(100)),
        sa.Column("document_type", sa.String(50)),
        sa.Column("status", sa.String(50), server_default="uploaded"),
        sa.Column("sha256", sa.String(64)),
        sa.Column("page_count", sa.Integer),
        # Denormalized extraction fields
        sa.Column("buyer_tax_id", sa.String(13)),
        sa.Column("buyer_name", sa.String(255)),
        sa.Column("seller_tax_id", sa.String(13)),
        sa.Column("seller_name", sa.String(255)),
        sa.Column("invoice_number", sa.String(100)),
        sa.Column("invoice_date", sa.Date),
        sa.Column("net_amount", sa.Numeric(15, 2)),
        sa.Column("vat_amount", sa.Numeric(15, 2)),
        sa.Column("wht_amount", sa.Numeric(15, 2)),
        sa.Column("total_amount", sa.Numeric(15, 2)),
        sa.Column("has_vat", sa.Boolean, server_default=sa.text("false")),
        sa.Column("vat_rate", sa.Numeric(5, 2), server_default="7.00"),
        sa.Column("wht_rate", sa.Numeric(5, 2), server_default="0.00"),
        sa.Column("taxid_match", sa.Boolean),
        sa.Column("overall_confidence", sa.Numeric(5, 4)),
        sa.Column("processing_error", sa.Text),
        sa.Column("batch_id", UUID(as_uuid=True)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_documents_company_status", "documents", ["company_id", "status"]
    )
    op.create_index("ix_documents_sha256", "documents", ["sha256"])

    # --- Extractions ---
    op.create_table(
        "extractions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("extraction_json", JSONB),
        sa.Column("confidence_per_field", JSONB),
        sa.Column("reconciliation", JSONB),
        sa.Column("stage_c_applied", sa.Boolean, server_default=sa.text("false")),
        sa.Column("stage_c_provider", sa.String(50)),
        sa.Column("stage_c_model", sa.String(100)),
        sa.Column("critical_flags", JSONB),
        sa.Column("schema_version", sa.String(10)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- Journal Vouchers ---
    op.create_table(
        "journal_vouchers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("voucher_no", sa.String(50)),
        sa.Column("voucher_date", sa.Date, nullable=False),
        sa.Column("book_code", sa.String(10)),
        sa.Column("rule_id", sa.String(50)),
        sa.Column("status", sa.String(50), server_default="draft"),
        sa.Column("is_balanced", sa.Boolean),
        sa.Column("total_debit", sa.Numeric(15, 2)),
        sa.Column("total_credit", sa.Numeric(15, 2)),
        sa.Column("flags", JSONB),
        sa.Column(
            "confirmed_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("confirmed_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- Journal Lines ---
    op.create_table(
        "journal_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "voucher_id",
            UUID(as_uuid=True),
            sa.ForeignKey("journal_vouchers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("line_order", sa.Integer, nullable=False),
        sa.Column("account_code", sa.String(50), nullable=False),
        sa.Column("account_name", sa.String(150)),
        sa.Column("is_debit", sa.Boolean, nullable=False),
        sa.Column("amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("is_variable", sa.Boolean, server_default=sa.text("false")),
        sa.Column("amount_field", sa.String(50)),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- Chart of Accounts ---
    op.create_table(
        "chart_of_accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_code", sa.String(50), nullable=False),
        sa.Column("account_name", sa.String(150), nullable=False),
        sa.Column("account_type", sa.String(50)),
        sa.Column("parent_code", sa.String(50)),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint(
            "company_id", "account_code", name="uq_company_account_code"
        ),
    )

    # --- Account Mapping Rules (ML Feedback Loop) ---
    op.create_table(
        "account_mapping_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("vendor_name", sa.String(255), nullable=False),
        sa.Column("document_type", sa.String(50)),
        sa.Column("recommended_debit_code", sa.String(50)),
        sa.Column("recommended_account_name", sa.String(150)),
        sa.Column("confirmed_count", sa.Integer, server_default="1"),
        sa.Column("last_confirmed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.UniqueConstraint(
            "company_id",
            "vendor_name",
            "document_type",
            name="uq_company_vendor_doctype",
        ),
    )

    # --- Export Templates ---
    op.create_table(
        "export_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
        ),
        sa.Column("template_name", sa.String(255), nullable=False),
        sa.Column("template_type", sa.String(50), nullable=False),
        sa.Column("columns", JSONB),
        sa.Column("static_values", JSONB),
        sa.Column("header_mappings", JSONB),
        sa.Column("file_format", sa.String(10), server_default="csv"),
        sa.Column("delimiter", sa.String(5), server_default=","),
        sa.Column("encoding", sa.String(20), server_default="utf-8"),
        sa.Column("is_master", sa.Boolean, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column(
            "cloned_from",
            UUID(as_uuid=True),
            sa.ForeignKey("export_templates.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "created_by",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- API Usage (Cost Tracking) ---
    op.create_table(
        "api_usage",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
        ),
        sa.Column("provider", sa.String(50)),
        sa.Column("model", sa.String(100)),
        sa.Column("stage", sa.String(20)),
        sa.Column("input_tokens", sa.Integer),
        sa.Column("output_tokens", sa.Integer),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 6)),
        sa.Column("tier", sa.String(10)),
        sa.Column("was_skipped", sa.Boolean, server_default=sa.text("false")),
        sa.Column("skip_reason", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_api_usage_company_created", "api_usage", ["company_id", "created_at"]
    )

    # --- Budget Limits ---
    op.create_table(
        "budget_limits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        ),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
        ),
        sa.Column("limit_type", sa.String(50), nullable=False),
        sa.Column("tier", sa.String(10), nullable=False),
        sa.Column("max_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("alert_threshold_pct", sa.Integer, server_default="80"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )

    # --- Audit Logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
        ),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", UUID(as_uuid=True)),
        sa.Column("old_values", JSONB),
        sa.Column("new_values", JSONB),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_audit_logs_company_action", "audit_logs", ["company_id", "action"]
    )
    op.create_index("ix_audit_logs_created", "audit_logs", ["created_at"])

    # --- Data Retention Policies (PDPA) ---
    op.create_table(
        "data_retention_policies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
        ),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("retention_days", sa.Integer, server_default="30"),
        sa.Column("action", sa.String(20), server_default="delete"),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("last_run_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("data_retention_policies")
    op.drop_index("ix_audit_logs_created", "audit_logs")
    op.drop_index("ix_audit_logs_company_action", "audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("budget_limits")
    op.drop_index("ix_api_usage_company_created", "api_usage")
    op.drop_table("api_usage")
    op.drop_table("export_templates")
    op.drop_table("account_mapping_rules")
    op.drop_table("chart_of_accounts")
    op.drop_table("journal_lines")
    op.drop_table("journal_vouchers")
    op.drop_index("ix_documents_sha256", "documents")
    op.drop_index("ix_documents_company_status", "documents")
    op.drop_table("extractions")
    op.drop_table("documents")
    op.drop_table("user_company_assignments")
    op.drop_table("users")
    op.drop_table("companies")
    op.drop_table("tenants")
