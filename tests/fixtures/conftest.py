from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from src.core.memory import MemoryManager
from tests.fixtures.sample_documents import generate_sample_documents


@pytest.fixture
def sample_documents():
    """Provide a reusable collection of 100+ sample documents with embeddings."""
    return generate_sample_documents()


@pytest_asyncio.fixture
async def memory_manager(db_engine):
    """MemoryManager wired to the shared async engine for integration tests."""
    yield MemoryManager(engine=db_engine)


@pytest_asyncio.fixture
async def clean_db_session(db_engine):
    """
    Function-scoped database session that rolls back after each test.
    Mirrors db_session but co-located here for fixture-oriented workflows.
    """
    session_factory = sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def docker_services_ready(db_engine):
    """
    Lightweight readiness check for Docker Compose services (PostgreSQL / Jaeger).
    """
    async with db_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True

