"""FastAPI dependency for database sessions."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from src.backend.db.base import get_async_session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async DB session for a single request, then close it."""
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
