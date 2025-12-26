"""
Alembic Migration Environment Configuration

This script is executed every time you run an Alembic command (e.g., `alembic upgrade head`,
`alembic revision --autogenerate`). It configures how Alembic connects to your database
and runs migrations.

Key responsibilities:
- Loads database configuration from your application settings
- Configures SQLModel metadata for autogeneration (comparing models vs. database schema)
- Provides two execution modes:
  * Online mode: Creates async database connection and applies migrations directly
  * Offline mode: Generates SQL scripts without connecting to database (for manual deployment)

Components:
- get_url(): Retrieves database URL from application settings
- run_migrations_offline(): Generates SQL scripts without database connection
- run_migrations_online(): Connects to database via AsyncEngine and runs migrations in transaction
- do_run_migrations(): Helper that configures context and executes migration operations

The conditional at the bottom determines which mode to use based on how Alembic was invoked.
You can customize this file to add logging, connection pooling, or multi-database support.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import SQLModel

from paias.core.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def get_url() -> str:
    return settings.database_url


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable: AsyncEngine = create_async_engine(get_url(), pool_pre_ping=True)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

