"""
Global test fixtures for async database setup.

Provides:
- db_engine: session-scoped AsyncEngine that waits for Postgres and creates all
  SQLModel tables.
- db_session: function-scoped AsyncSession with automatic rollback for isolation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from src.core.config import settings
from src.models.document import Document  # noqa: F401 - ensure model is registered
from src.models.message import Message  # noqa: F401 - ensure model is registered
from src.models.session import Session  # noqa: F401 - ensure model is registered

LOGGER = logging.getLogger("tests.db")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)


async def _wait_for_postgres(engine: AsyncEngine, timeout: float = 3.0) -> None:
    """
    Single-attempt readiness check with a short timeout.
    Fails fast so integration tests don't hang.
    """
    print(
        f"[tests.db] Waiting for Postgres at {settings.database_url} "
        f"(timeout={timeout}s)"
    )
    try:
        async with asyncio.timeout(timeout):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                LOGGER.info("Postgres ready")
                return
    except Exception as exc:
        LOGGER.error("Postgres not ready: %s", exc)
        raise RuntimeError(
            "Postgres not reachable; check DATABASE_URL and container health"
        ) from exc


@pytest_asyncio.fixture
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        connect_args={"timeout": 3},
    )
    LOGGER.info("Connecting to database_url=%s", settings.database_url)
    print(f"[tests.db] Connecting using database_url={settings.database_url}")
    await _wait_for_postgres(engine)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(SQLModel.metadata.drop_all)
        await conn.run_sync(SQLModel.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()
