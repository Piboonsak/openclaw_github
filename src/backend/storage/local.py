"""Local filesystem fallback storage client."""

from __future__ import annotations

from pathlib import Path


class LocalStorageClient:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def ensure_bucket(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def upload_bytes(
        self,
        key: str,
        content: bytes,
        *,
        content_type: str | None = None,
    ) -> str:
        target = self.root / Path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return key

    def download_bytes(self, key: str) -> bytes:
        return (self.root / Path(key)).read_bytes()

    def delete(self, key: str) -> None:
        target = self.root / Path(key)
        if target.exists():
            target.unlink()

    def generate_presigned_url(
        self,
        key: str,
        *,
        expires_in: int = 3600,
        response_content_type: str | None = None,
    ) -> str:
        return (self.root / Path(key)).resolve().as_uri()
