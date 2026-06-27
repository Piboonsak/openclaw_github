"""Health-check helpers for DB, Redis, and storage dependencies."""

from __future__ import annotations

import socket
from dataclasses import dataclass
from time import monotonic
from urllib.parse import urlparse
from urllib.request import urlopen

from sqlalchemy import text

from config.settings import settings
from src.backend.db.base import get_sync_engine

APP_STARTED_AT = monotonic()


@dataclass
class ServiceHealth:
    db: str
    redis: str
    minio: str

    @property
    def overall_status(self) -> str:
        return "healthy" if all(value == "ok" for value in vars(self).values()) else "degraded"


def get_uptime_seconds() -> float:
    return round(monotonic() - APP_STARTED_AT, 3)


def check_db() -> str:
    try:
        engine = get_sync_engine()
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"


def check_redis() -> str:
    try:
        parsed = urlparse(settings.REDIS_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        timeout = settings.REDIS_TIMEOUT_SECONDS
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.sendall(b"*1\r\n$4\r\nPING\r\n")
            response = sock.recv(16)
        return "ok" if response.startswith(b"+PONG") else "error"
    except Exception:
        return "error"


def check_minio() -> str:
    if settings.STORAGE_PROVIDER.lower().strip() != "minio":
        return "ok"
    try:
        endpoint = settings.MINIO_ENDPOINT.rstrip("/") + "/minio/health/live"
        with urlopen(endpoint, timeout=settings.MINIO_TIMEOUT_SECONDS):
            return "ok"
    except Exception:
        return "error"


def collect_service_health() -> ServiceHealth:
    settings.reload()
    return ServiceHealth(
        db=check_db(),
        redis=check_redis(),
        minio=check_minio(),
    )
