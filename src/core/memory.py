from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from opentelemetry import trace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.core.telemetry import trace_memory_operation
from src.models.message import Message, MessageRole
from src.models.session import Session

DEFAULT_USER_ID = "auto-created"


class MemoryManager:
    """Async memory abstraction for storing and retrieving conversation history."""

    def __init__(self, engine: Optional[AsyncEngine] = None) -> None:
        self._engine: AsyncEngine = engine or create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )
        self._session_factory: sessionmaker[AsyncSession] = sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    def _get_span(self):
        return trace.get_current_span()

    def _coerce_role(self, role: str | MessageRole) -> MessageRole:
        if isinstance(role, MessageRole):
            return role
        try:
            return MessageRole(role)
        except ValueError as exc:
            raise ValueError(f"Invalid message role: {role}") from exc

    @trace_memory_operation("store_message")
    async def store_message(
        self,
        session_id: UUID,
        role: str | MessageRole,
        content: str,
        metadata: Optional[dict] = None,
    ) -> UUID:
        """Store a message and auto-create the parent session when missing."""
        message_role = self._coerce_role(role)
        cleaned_content = content.strip() if content else ""
        if not cleaned_content:
            raise ValueError("Message content cannot be empty")

        async with self._session_factory() as db:
            session_obj = await db.get(Session, session_id)
            if session_obj is None:
                session_obj = Session(id=session_id, user_id=DEFAULT_USER_ID)
                db.add(session_obj)
            else:
                session_obj.updated_at = datetime.utcnow()

            message = Message(
                session_id=session_id,
                role=message_role,
                content=cleaned_content,
                metadata_=metadata or {},
            )
            db.add(message)
            await db.commit()
            await db.refresh(message)

        span = self._get_span()
        span.set_attribute("session_id", str(session_id))
        span.set_attribute("role", message_role.value)
        span.set_attribute("content_length", len(cleaned_content))
        span.set_attribute("has_metadata", bool(metadata))

        return message.id

    @trace_memory_operation("get_conversation_history")
    async def get_conversation_history(self, session_id: UUID, limit: int = 100) -> list[Message]:
        """Return conversation history for a session in chronological order (oldest first)."""
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        async with self._session_factory() as db:
            stmt = (
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            messages = list(result.scalars().all())

        messages.reverse()

        span = self._get_span()
        span.set_attribute("session_id", str(session_id))
        span.set_attribute("limit", limit)
        span.set_attribute("result_count", len(messages))

        return messages

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

