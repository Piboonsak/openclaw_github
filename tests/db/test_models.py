from __future__ import annotations

from src.backend.db.base import Base
from src.backend.db.enums import (
    BatchStatus,
    DocumentStatus,
    ExportJobStatus,
    FlagStatus,
    MatchType,
    VoucherStatus,
)
from src.backend.db import models


def test_status_enums_match_workflow_contract() -> None:
    assert DocumentStatus.UPLOADED.value == "uploaded"
    assert DocumentStatus.REVIEW_MAPPING.value == "review_mapping"
    assert BatchStatus.READY_EXPORT.value == "ready_export"
    assert VoucherStatus.CONFIRMED.value == "confirmed"
    assert ExportJobStatus.DOWNLOADED.value == "downloaded"
    assert FlagStatus.RESOLVED.value == "resolved"


def test_new_tables_are_registered_in_metadata() -> None:
    expected_tables = {
        "document_batches",
        "document_flags",
        "field_corrections",
        "export_jobs",
        "export_files",
        "export_job_documents",
        "company_credit_plans",
        "page_credit_usage",
        "data_retention_policies",
        "vendor_master",
        "customer_master",
        "account_mapping_cache",
    }

    assert expected_tables.issubset(Base.metadata.tables.keys())


def test_document_batch_relationship_and_review_columns_exist() -> None:
    document_table = models.Document.__table__

    assert "scan_status" in document_table.c
    assert "scan_reviewed_by" in document_table.c
    assert "scan_reviewed_at" in document_table.c
    assert "processing_progress" in document_table.c

    batch_foreign_keys = {
        fk.target_fullname for fk in document_table.c.batch_id.foreign_keys
    }
    assert batch_foreign_keys == {"document_batches.id"}
    assert document_table.c.batch_id.nullable is True


def test_expected_indexes_and_unique_constraints_exist() -> None:
    batch_indexes = {index.name for index in models.DocumentBatch.__table__.indexes}
    page_credit_indexes = {
        index.name for index in models.PageCreditUsage.__table__.indexes
    }
    flag_indexes = {index.name for index in models.DocumentFlag.__table__.indexes}
    export_job_indexes = {index.name for index in models.ExportJob.__table__.indexes}
    correction_indexes = {
        index.name for index in models.FieldCorrection.__table__.indexes
    }
    export_job_document_constraints = {
        constraint.name
        for constraint in models.ExportJobDocument.__table__.constraints
        if getattr(constraint, "name", None)
    }

    assert "ix_batches_company_status" in batch_indexes
    assert "ix_page_credit_company_created" in page_credit_indexes
    assert "ix_page_credit_document" in page_credit_indexes
    assert "ix_flags_document_status" in flag_indexes
    assert "ix_export_jobs_company" in export_job_indexes
    assert "ix_corrections_document" in correction_indexes
    assert "uq_export_job_document" in export_job_document_constraints


def test_model_imports_expose_task_801a_classes() -> None:
    assert models.DocumentBatch.__tablename__ == "document_batches"
    assert models.ExportJob.__tablename__ == "export_jobs"
    assert models.CompanyCreditPlan.__tablename__ == "company_credit_plans"
    assert models.VendorMaster.__tablename__ == "vendor_master"
    assert models.CustomerMaster.__tablename__ == "customer_master"
    assert models.AccountMappingCache.__tablename__ == "account_mapping_cache"


def test_vendor_and_customer_codes_are_varchar_columns() -> None:
    assert str(models.VendorMaster.__table__.c.vendor_code.type) == "VARCHAR(20)"
    assert str(models.CustomerMaster.__table__.c.customer_code.type) == "VARCHAR(20)"


def test_company_credit_plan_hides_internal_provider_fields() -> None:
    column_names = set(models.CompanyCreditPlan.__table__.c.keys())
    assert "provider" not in column_names
    assert "model" not in column_names
    assert "token" not in column_names


def test_account_mapping_cache_uses_match_type_enum() -> None:
    match_type_column = models.AccountMappingCache.__table__.c.match_type
    assert sorted(match_type_column.type.enums) == sorted([item.value for item in MatchType])
