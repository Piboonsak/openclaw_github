from __future__ import annotations

from unittest.mock import Mock

from src.backend.storage.s3 import S3StorageClient


def test_s3_upload_download_delete_and_presign(monkeypatch) -> None:
    mock_client = Mock()
    mock_client.get_object.return_value = {"Body": Mock(read=Mock(return_value=b"abc"))}
    mock_client.generate_presigned_url.return_value = "https://example.test/file"

    monkeypatch.setattr("src.backend.storage.s3.boto3.client", lambda *a, **k: mock_client)

    client = S3StorageClient(
        endpoint_url="http://localhost:9000",
        bucket="test-bucket",
        access_key="minioadmin",
        secret_key="minioadmin",
    )

    client.upload_bytes("tenant/company/file.pdf", b"abc", content_type="application/pdf")
    downloaded = client.download_bytes("tenant/company/file.pdf")
    presigned = client.generate_presigned_url("tenant/company/file.pdf")
    client.delete("tenant/company/file.pdf")

    assert downloaded == b"abc"
    assert presigned == "https://example.test/file"
    mock_client.put_object.assert_called_once()
    mock_client.get_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="tenant/company/file.pdf",
    )
    mock_client.delete_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="tenant/company/file.pdf",
    )


def test_s3_ensure_bucket_creates_missing_bucket(monkeypatch) -> None:
    mock_client = Mock()
    mock_client.list_buckets.return_value = {"Buckets": []}
    monkeypatch.setattr("src.backend.storage.s3.boto3.client", lambda *a, **k: mock_client)

    client = S3StorageClient(
        endpoint_url="http://localhost:9000",
        bucket="new-bucket",
        access_key="minioadmin",
        secret_key="minioadmin",
    )
    client.ensure_bucket()

    mock_client.create_bucket.assert_called_once_with(Bucket="new-bucket")
