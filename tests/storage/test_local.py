from __future__ import annotations

import shutil
from pathlib import Path

from src.backend.storage import build_storage_key
from src.backend.storage.local import LocalStorageClient


def _workspace_tmp_path(name: str) -> Path:
    root = Path("tmp") / "pytest-storage" / name
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_local_storage_round_trip() -> None:
    tmp_path = _workspace_tmp_path("round-trip")
    client = LocalStorageClient(tmp_path)
    key = "default-tenant/company/2026/06/demo.pdf"
    content = b"hello storage"

    client.upload_bytes(key, content, content_type="application/pdf")

    assert client.download_bytes(key) == content
    assert (tmp_path / key).exists()
    assert client.generate_presigned_url(key).startswith("file:///")


def test_local_storage_delete() -> None:
    tmp_path = _workspace_tmp_path("delete")
    client = LocalStorageClient(tmp_path)
    key = "tenant/company/2026/06/demo.csv"
    client.upload_bytes(key, b"data")

    client.delete(key)

    assert not (tmp_path / key).exists()


def test_build_storage_key_uses_expected_path_structure() -> None:
    key, sha256 = build_storage_key(
        tenant_id="tenant-1",
        company_id="company-1",
        filename="invoice.pdf",
        content=b"abc",
    )

    assert key.startswith("tenant-1/company-1/")
    assert key.endswith(".pdf")
    assert sha256 in key
