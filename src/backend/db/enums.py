"""Application status enums used as DB/API source-of-truth constants."""

from __future__ import annotations

from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    REVIEW_SCAN = "review_scan"
    SCAN_APPROVED = "scan_approved"
    SCAN_FLAGGED = "scan_flagged"
    REVIEW_MAPPING = "review_mapping"
    MAPPING_CONFIRMED = "mapping_confirmed"
    EXPORTED = "exported"
    FAILED = "failed"


class BatchStatus(StrEnum):
    DRAFT = "draft"
    UPLOADING = "uploading"
    PROCESSING = "processing"
    REVIEW_SCAN = "review_scan"
    REVIEW_MAPPING = "review_mapping"
    READY_EXPORT = "ready_export"
    EXPORTED = "exported"
    FAILED = "failed"
    ARCHIVED = "archived"


class VoucherStatus(StrEnum):
    DRAFT = "draft"
    REVIEW = "review"
    CONFIRMED = "confirmed"
    EXPORTED = "exported"


class ExportJobStatus(StrEnum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    DOWNLOADED = "downloaded"


class MatchType(StrEnum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    LLM = "llm"
    MANUAL = "manual"


class ExportStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class FlagStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"
