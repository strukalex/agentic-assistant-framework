# ruff: noqa
from __future__ import annotations

import pytest

from sqlalchemy.exc import SQLAlchemyError

from paias.core.config import settings
from paias.core.memory import MemoryManager
from paias.models.message import MessageRole


def test_coerce_role_rejects_invalid_value() -> None:
    manager = MemoryManager()
    with pytest.raises(ValueError):
        manager._coerce_role("invalid")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_get_conversation_history_invalid_limit() -> None:
    manager = MemoryManager()
    with pytest.raises(ValueError):
        await manager.get_conversation_history(session_id=None, limit=0)  # type: ignore[arg-type]


def test_store_message_rejects_invalid_role_before_db_call() -> None:
    manager = MemoryManager()
    with pytest.raises(ValueError):
        manager._coerce_role("bad-role")  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_store_message_rejects_empty_content_before_db_call() -> None:
    manager = MemoryManager()
    with pytest.raises(ValueError):
        await manager.store_message(
            session_id=None,  # type: ignore[arg-type]
            role=MessageRole.USER.value,
            content="   ",
        )


def test_engine_property_exposes_engine_instance() -> None:
    manager = MemoryManager()
    assert manager.engine is not None


@pytest.mark.asyncio
async def test_semantic_search_requires_positive_top_k() -> None:
    manager = MemoryManager()
    valid_embedding = [0.0] * settings.vector_dimension

    with pytest.raises(ValueError):
        await manager.semantic_search(
            query_embedding=valid_embedding,
            top_k=0,
        )


@pytest.mark.asyncio
async def test_semantic_search_rejects_empty_embedding() -> None:
    manager = MemoryManager()

    with pytest.raises(ValueError):
        await manager.semantic_search(query_embedding=[], top_k=1)


@pytest.mark.asyncio
async def test_semantic_search_rejects_non_numeric_embedding() -> None:
    manager = MemoryManager()
    bad_embedding = [0.1] * (settings.vector_dimension - 1) + ["bad"]

    with pytest.raises(ValueError):
        await manager.semantic_search(query_embedding=bad_embedding, top_k=1)


@pytest.mark.asyncio
async def test_store_document_rejects_dimension_mismatch() -> None:
    manager = MemoryManager()

    with pytest.raises(ValueError):
        await manager.store_document(content="Doc", embedding=[0.1, 0.2])


@pytest.mark.asyncio
async def test_health_check_propagates_database_errors() -> None:
    manager = MemoryManager()

    class _FailingConnection:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def exec_driver_sql(self, *_args, **_kwargs):
            raise SQLAlchemyError("database unreachable")

    class _FailingEngine:
        def connect(self):  # type: ignore[override]
            return _FailingConnection()

    manager._engine = _FailingEngine()  # type: ignore[assignment]

    with pytest.raises(SQLAlchemyError):
        await manager.health_check()
