"""SQLAlchemy declarative base and engine configuration.

Provides both async (FastAPI) and sync (Celery) session factories.
Uses the DATABASE_URL from config/settings.py.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config.settings import settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


def _get_database_url() -> str:
    """Return the sync DATABASE_URL from settings."""
    return settings.DATABASE_URL


def _get_async_database_url() -> str:
    """Convert postgresql:// to postgresql+asyncpg:// for async driver."""
    url = _get_database_url()
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    return url


# ---------------------------------------------------------------------------
# Sync engine + session (for Celery workers, scripts, migrations)
# ---------------------------------------------------------------------------

_sync_engine = None
_sync_session_factory = None


def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            _get_database_url(),
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _sync_engine


def get_sync_session_factory() -> sessionmaker[Session]:
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(
            bind=get_sync_engine(),
            expire_on_commit=False,
        )
    return _sync_session_factory


# ---------------------------------------------------------------------------
# Async engine + session (for FastAPI request handlers)
# ---------------------------------------------------------------------------

_async_engine = None
_async_session_factory = None


def get_async_engine():
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            _get_async_database_url(),
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            bind=get_async_engine(),
            expire_on_commit=False,
        )
    return _async_session_factory
