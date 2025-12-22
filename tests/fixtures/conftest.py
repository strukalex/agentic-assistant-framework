"""
Pytest Database Fixtures for Async Testing

This conftest.py provides reusable pytest fixtures for testing code that interacts with
the database using async SQLAlchemy/SQLModel. The fixtures handle database connection
lifecycle, schema creation, and transaction management automatically.

Fixtures provided:
- db_engine: Session-scoped AsyncEngine fixture that:
  * Creates database engine with connection pooling
  * Waits for PostgreSQL to be ready (important for containerized databases)
  * Creates all SQLModel tables before tests run
  * Disposes engine after test session completes

- db_session: Function-scoped AsyncSession fixture that:
  * Provides a fresh database session for each test
  * Automatically rolls back changes after each test (ensures test isolation)
  * Prevents cross-test contamination

Helper functions:
- _wait_for_postgres(): Polls database until responsive, handling startup delays
  in Docker/containerized environments

Usage in tests:
    async def test_create_user(db_session: AsyncSession):
        user = User(name="Test")
        db_session.add(user)
        await db_session.commit()
        # Changes automatically rolled back after test

Note: The db_session rollback ensures tests don't interfere with each other, but
means you need to commit within your test if you want to test commit behavior.
"""

from __future__ import annotations

import asyncio
from typing import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from sqlmodel import SQLModel

from src.core.config import settings


async def _wait_for_postgres(engine: AsyncEngine, retries: int = 30, delay: float = 1.0) -> None:
    """Poll the database until it responds to a simple SELECT."""
    for attempt in range(retries):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                return
        except Exception:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(delay)


@pytest_asyncio.fixture(scope="session")
async def db_engine() -> AsyncGenerator[AsyncEngine, None]:
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
    )
    await _wait_for_postgres(engine)
    async with engine.begin() as conn:
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

