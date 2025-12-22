from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.core.memory import MemoryManager
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

