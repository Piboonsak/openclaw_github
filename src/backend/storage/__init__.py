"""Document storage abstraction with MinIO and local fallback."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import settings
from src.backend.storage.local import LocalStorageClient
from src.backend.storage.s3 import S3StorageClient

logger = logging.getLogger(__name__)
_storage_client: Any | None = None


def _normalize_ext(filename: str | None) -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix else ".bin"


def build_storage_key(
    *,
    tenant_id: str,
    company_id: str,
    filename: str | None,
    content: bytes,
    now: datetime | None = None,
) -> tuple[str, str]:
    dt = now or datetime.utcnow()
    sha256 = hashlib.sha256(content).hexdigest()
    extension = _normalize_ext(filename)
    key = f"{tenant_id}/{company_id}/{dt:%Y}/{dt:%m}/{sha256}{extension}"
    return key, sha256


def get_storage_client():
    global _storage_client
    if _storage_client is not None:
        return _storage_client

    settings.reload()
    local_client = LocalStorageClient(settings.STORAGE_LOCAL_ROOT)
    provider = settings.STORAGE_PROVIDER.lower().strip()

    if provider == "minio":
        try:
            client = S3StorageClient(
                endpoint_url=settings.MINIO_ENDPOINT,
                bucket=settings.MINIO_BUCKET,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
            )
            client.ensure_bucket()
            _storage_client = client
            return _storage_client
        except Exception as exc:
            logger.warning("Falling back to local storage: %s", exc)

    local_client.ensure_bucket()
    _storage_client = local_client
    return _storage_client


def bootstrap_storage() -> str:
    client = get_storage_client()
    return client.__class__.__name__


def store_document_bytes(
    *,
    content: bytes,
    filename: str | None,
    company_id: str,
    tenant_id: str | None = None,
    content_type: str | None = None,
) -> dict[str, str]:
    tenant_scope = tenant_id or settings.STORAGE_DEFAULT_TENANT_ID
    key, sha256 = build_storage_key(
        tenant_id=tenant_scope,
        company_id=company_id,
        filename=filename,
        content=content,
    )
    client = get_storage_client()
    client.upload_bytes(key, content, content_type=content_type)
    return {
        "storage_key": key,
        "sha256": sha256,
        "provider": client.__class__.__name__,
    }


def materialize_local_cache(
    *,
    content: bytes,
    filename: str | None,
    sha256: str,
) -> Path:
    suffix = _normalize_ext(filename)
    local_path = settings.UPLOAD_ROOT / f"{sha256}{suffix}"
    local_path.parent.mkdir(parents=True, exist_ok=True)
    local_path.write_bytes(content)
    return local_path
