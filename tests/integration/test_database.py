from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.core.config import settings
from src.core.memory import MemoryManager
from src.core.telemetry import set_span_exporter
from src.models.document import Document
from src.models.message import Message, MessageRole
from src.models.session import Session


@pytest.mark.asyncio
async def test_store_message_persists_and_auto_creates_session(
    db_engine: AsyncEngine, db_session: AsyncSession
) -> None:
    manager = MemoryManager(engine=db_engine)

    session_id = uuid4()
    message_id = await manager.store_message(
        session_id=session_id,
        role=MessageRole.USER.value,
        content="Hello from test",
    )

    stored_session = await db_session.get(Session, session_id)
    assert stored_session is not None
    assert stored_session.user_id

    result = await db_session.execute(select(Message).where(Message.id == message_id))
    stored_message = result.scalar_one()
    assert stored_message.session_id == session_id
    assert stored_message.content == "Hello from test"
    assert stored_message.role == MessageRole.USER


@pytest.mark.asyncio
async def test_get_conversation_history_respects_limit_and_order(
    db_engine: AsyncEngine, db_session: AsyncSession
) -> None:
    manager = MemoryManager(engine=db_engine)
    session_id = uuid4()
    other_session_id = uuid4()

    await manager.store_message(session_id, MessageRole.USER.value, "first")
    await asyncio.sleep(0.01)
    await manager.store_message(session_id, MessageRole.ASSISTANT.value, "second")
    await asyncio.sleep(0.01)
    await manager.store_message(session_id, MessageRole.ASSISTANT.value, "third")
    await manager.store_message(other_session_id, MessageRole.USER.value, "other")

    history = await manager.get_conversation_history(session_id, limit=2)

    assert [msg.content for msg in history] == ["second", "third"]
    assert all(msg.session_id == session_id for msg in history)


@pytest.mark.asyncio
async def test_store_document_persists_and_allows_missing_embedding(
    db_engine: AsyncEngine, db_session: AsyncSession
) -> None:
    manager = MemoryManager(engine=db_engine)

    doc_id = await manager.store_document(
        content="Async programming allows concurrent I/O.",
        metadata={"category": "research"},
        embedding=None,
    )

    result = await db_session.execute(select(Document).where(Document.id == doc_id))
    stored_doc = result.scalar_one()

    assert stored_doc.content.startswith("Async programming")
    assert stored_doc.metadata_["category"] == "research"
    assert stored_doc.embedding is None


@pytest.mark.asyncio
async def test_temporal_query_filters_by_date_range(
    db_engine: AsyncEngine, db_session: AsyncSession
) -> None:
    manager = MemoryManager(engine=db_engine)
    now = datetime.utcnow()
    old_date = now - timedelta(days=10)
    recent_date = now - timedelta(days=1)

    old_doc_id = await manager.store_document(
        content="Old research doc",
        metadata={"category": "research"},
        embedding=[0.1] * settings.vector_dimension,
    )
    recent_doc_id = await manager.store_document(
        content="Recent research doc",
        metadata={"category": "research"},
        embedding=[0.2] * settings.vector_dimension,
    )

    await db_session.execute(
        update(Document).where(Document.id == old_doc_id).values(created_at=old_date)
    )
    await db_session.execute(
        update(Document)
        .where(Document.id == recent_doc_id)
        .values(created_at=recent_date)
    )
    await db_session.commit()

    results = await manager.temporal_query(
        start_date=now - timedelta(days=5),
        end_date=now,
        metadata_filters={"category": "research"},
    )

    assert [doc.id for doc in results] == [recent_doc_id]


@pytest.mark.asyncio
async def test_temporal_query_rejects_invalid_range(db_engine: AsyncEngine) -> None:
    manager = MemoryManager(engine=db_engine)
    now = datetime.utcnow()
    with pytest.raises(ValueError):
        await manager.temporal_query(start_date=now, end_date=now - timedelta(days=1))


@pytest.mark.asyncio
async def test_semantic_search_supports_combined_filters(
    db_engine: AsyncEngine,
) -> None:
    manager = MemoryManager(engine=db_engine)
    now = datetime.utcnow()
    yesterday = now - timedelta(days=1)
    embedding = [0.9] + [0.0] * (settings.vector_dimension - 1)

    doc_id = await manager.store_document(
        content="Async patterns",
        metadata={"category": "research"},
        embedding=embedding,
    )
    await manager.store_document(
        content="Old unrelated",
        metadata={"category": "notes"},
        embedding=[0.1] + [0.0] * (settings.vector_dimension - 1),
    )

    await manager.store_document(
        content="Future doc",
        metadata={"category": "research"},
        embedding=embedding,
    )

    await manager.store_document(
        content="Metadata mismatch",
        metadata={"category": "other"},
        embedding=embedding,
    )

    async with AsyncSession(db_engine) as session:
        await session.execute(
            update(Document).where(Document.id == doc_id).values(created_at=yesterday)
        )
        await session.commit()

    results = await manager.semantic_search(
        query_embedding=embedding,
        top_k=5,
        metadata_filters={"category": "research"},
        start_date=now - timedelta(days=2),
        end_date=now,
    )

    assert results
    assert results[0].id == doc_id


@pytest.mark.asyncio
async def test_health_check_returns_versions(db_engine: AsyncEngine) -> None:
    manager = MemoryManager(engine=db_engine)
    health = await manager.health_check()

    assert health["status"] == "healthy"
    assert "PostgreSQL" in health["postgres_version"]
    assert "pgvector_version" in health


@pytest.mark.asyncio
async def test_traces_emitted_for_memory_operations(db_engine: AsyncEngine) -> None:
    exporter = InMemorySpanExporter()
    set_span_exporter(exporter)
    exporter.clear()

    manager = MemoryManager(engine=db_engine)
    session_id = uuid4()
    await manager.store_message(session_id, MessageRole.USER.value, "traced message")
    await manager.store_document(
        content="Traced doc",
        metadata={"category": "trace"},
        embedding=[0.1] * settings.vector_dimension,
    )
    await manager.semantic_search(
        query_embedding=[0.1] * settings.vector_dimension,
        top_k=1,
        metadata_filters={"category": "trace"},
    )

    trace.get_tracer_provider().force_flush()
    span_names = [span.name for span in exporter.get_finished_spans()]

    assert "memory.store_message" in span_names
    assert "memory.semantic_search" in span_names


@pytest.mark.asyncio
async def test_concurrent_sessions_do_not_deadlock(db_engine: AsyncEngine) -> None:
    manager = MemoryManager(engine=db_engine)
    session_ids = [uuid4() for _ in range(10)]

    async def _write_session(session_id):
        messages = [f"{session_id}-m{i}" for i in range(3)]
        for index, content in enumerate(messages):
            role = (
                MessageRole.USER.value
                if index % 2 == 0
                else MessageRole.ASSISTANT.value
            )
            await manager.store_message(session_id, role, content)
        history = await manager.get_conversation_history(session_id, limit=5)
        return session_id, messages, history

    results = await asyncio.gather(
        *(_write_session(session_id) for session_id in session_ids)
    )

    for session_id, expected_messages, history in results:
        assert len(history) == len(expected_messages)
        assert all(message.session_id == session_id for message in history)
        assert [message.content for message in history] == expected_messages
