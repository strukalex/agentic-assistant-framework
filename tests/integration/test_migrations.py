from __future__ import annotations

import asyncio

import alembic.command
import alembic.config
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from paias.core.config import settings

pytestmark = pytest.mark.asyncio


def _alembic_config() -> alembic.config.Config:
    config = alembic.config.Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", settings.database_url)
    return config


async def _reset_database() -> None:
    """Drop known objects to ensure migrations start from a clean slate."""
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS messages CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS documents CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS sessions CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS alembic_version CASCADE"))
        await conn.execute(text("DROP EXTENSION IF EXISTS vector CASCADE"))
    await engine.dispose()


async def _upgrade_head(config: alembic.config.Config) -> None:
    await _reset_database()
    await asyncio.to_thread(alembic.command.downgrade, config, "base")
    await asyncio.to_thread(alembic.command.upgrade, config, "head")


async def _downgrade_base(config: alembic.config.Config) -> None:
    await asyncio.to_thread(alembic.command.downgrade, config, "base")


async def _table_exists(engine, table_name: str) -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT to_regclass(:tbl)"), {"tbl": f"public.{table_name}"}
        )
        return result.scalar() is not None


async def _get_extension_version(engine, extension: str) -> str | None:
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT extversion FROM pg_extension WHERE extname=:name"),
            {"name": extension},
        )
        return result.scalar_one_or_none()


async def test_migration_creates_tables() -> None:
    config = _alembic_config()
    await _upgrade_head(config)

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    assert await _table_exists(engine, "sessions")
    assert await _table_exists(engine, "messages")
    assert await _table_exists(engine, "documents")
    await engine.dispose()


async def test_migration_rollback_drops_tables() -> None:
    config = _alembic_config()
    await _upgrade_head(config)
    await _downgrade_base(config)

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    assert not await _table_exists(engine, "sessions")
    assert not await _table_exists(engine, "messages")
    assert not await _table_exists(engine, "documents")
    await engine.dispose()


async def test_pgvector_extension_enabled() -> None:
    config = _alembic_config()
    await _upgrade_head(config)

    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    vector_version = await _get_extension_version(engine, "vector")
    await engine.dispose()

    assert vector_version is not None
