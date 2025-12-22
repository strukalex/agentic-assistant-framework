from __future__ import annotations

import pytest

from src.core.memory import MemoryManager
from src.models.message import MessageRole


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
