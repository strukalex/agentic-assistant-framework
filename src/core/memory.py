from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Optional
from uuid import UUID

from opentelemetry import trace
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.core.config import settings
from src.core.telemetry import trace_memory_operation
from src.models.document import Document
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

    def _validate_embedding(self, embedding: Optional[list[float]]) -> Optional[list[float]]:
        if embedding is None:
            return None
        if len(embedding) != settings.vector_dimension:
            raise ValueError(
                f"Embedding must match configured dimension {settings.vector_dimension} "
                f"for model {settings.embedding_model_name}"
            )
        if not all(isinstance(x, (int, float)) for x in embedding):
            raise ValueError("Embedding must contain only numeric values")
        return embedding

    def _coerce_role(self, role: str | MessageRole) -> MessageRole:
        if isinstance(role, MessageRole):
            return role
        try:
            return MessageRole(role)
        except ValueError as exc:
            raise ValueError(f"Invalid message role: {role}") from exc

    def _build_document_conditions(
        self,
        metadata_filters: Optional[dict] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list:
        conditions = []
        if start_date and end_date and end_date < start_date:
            raise ValueError("end_date must be greater than or equal to start_date")
        if start_date:
            conditions.append(Document.created_at >= start_date)
        if end_date:
            conditions.append(Document.created_at <= end_date)
        if metadata_filters:
            for key, value in metadata_filters.items():
                conditions.append(Document.metadata_[key].astext == str(value))
        return conditions

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
                await db.flush()  # persist session so FK insert below succeeds
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
        span.set_attribute("db.statement", "INSERT messages (with optional session creation)")

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
        span.set_attribute("db.statement", str(stmt))

        return messages

    @trace_memory_operation("store_document")
    async def store_document(
        self,
        content: str,
        metadata: Optional[dict] = None,
        embedding: Optional[list[float]] = None,
    ) -> UUID:
        cleaned_content = content.strip() if content else ""
        if not cleaned_content:
            raise ValueError("Document content cannot be empty")

        validated_embedding = self._validate_embedding(embedding)

        async with self._session_factory() as db:
            document = Document(
                content=cleaned_content,
                metadata_=metadata or {},
                embedding=validated_embedding,
            )
            db.add(document)
            await db.commit()
            await db.refresh(document)

        span = self._get_span()
        span.set_attribute("content_length", len(cleaned_content))
        span.set_attribute("has_embedding", validated_embedding is not None)
        span.set_attribute("metadata_keys", len((metadata or {}).keys()))
        span.set_attribute("db.statement", "INSERT documents")

        return document.id

    @trace_memory_operation("semantic_search")
    async def semantic_search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        metadata_filters: Optional[dict] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[Document]:
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        validated_embedding = self._validate_embedding(query_embedding)

        conditions = self._build_document_conditions(
            metadata_filters=metadata_filters,
            start_date=start_date,
            end_date=end_date,
        )

        stmt = select(Document)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(Document.embedding.cosine_distance(validated_embedding)).limit(top_k)

        start_time = perf_counter()
        async with self._session_factory() as db:
            result = await db.execute(stmt)
            documents = list(result.scalars().all())
        duration_ms = (perf_counter() - start_time) * 1000

        span = self._get_span()
        span.set_attribute("top_k", top_k)
        span.set_attribute("filter_count", len(metadata_filters or {}))
        span.set_attribute("result_count", len(documents))
        span.set_attribute("query_time_ms", round(duration_ms, 4))
        if start_date:
            span.set_attribute("start_date", start_date.isoformat())
        if end_date:
            span.set_attribute("end_date", end_date.isoformat())
        span.set_attribute("db.statement", str(stmt))

        return documents

    @trace_memory_operation("temporal_query")
    async def temporal_query(
        self,
        start_date: datetime,
        end_date: datetime,
        metadata_filters: Optional[dict] = None,
    ) -> list[Document]:
        conditions = self._build_document_conditions(
            metadata_filters=metadata_filters,
            start_date=start_date,
            end_date=end_date,
        )
        stmt = (
            select(Document)
            .where(and_(*conditions))
            .order_by(Document.created_at.desc())
        )

        async with self._session_factory() as db:
            result = await db.execute(stmt)
            documents = list(result.scalars().all())

        span = self._get_span()
        span.set_attribute("start_date", start_date.isoformat())
        span.set_attribute("end_date", end_date.isoformat())
        span.set_attribute("filter_count", len(metadata_filters or {}))
        span.set_attribute("result_count", len(documents))
        span.set_attribute("db.statement", str(stmt))

        return documents

    @trace_memory_operation("health_check")
    async def health_check(self) -> dict[str, str]:
        async with self._engine.connect() as conn:
            version_result = await conn.exec_driver_sql("SELECT version()")
            postgres_version = version_result.scalar_one()
            vector_result = await conn.exec_driver_sql(
                "SELECT extversion FROM pg_extension WHERE extname='vector'"
            )
            pgvector_version = vector_result.scalar_one_or_none()

        response = {
            "status": "healthy",
            "postgres_version": postgres_version,
        }
        if pgvector_version:
            response["pgvector_version"] = pgvector_version

        span = self._get_span()
        span.set_attribute("status", response["status"])
        span.set_attribute("postgres_version", postgres_version)
        if pgvector_version:
            span.set_attribute("pgvector_version", pgvector_version)
        span.set_attribute("db.statement", "SELECT version(); SELECT extversion FROM pg_extension")

        return response

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

