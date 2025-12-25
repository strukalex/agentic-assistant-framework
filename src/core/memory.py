from __future__ import annotations

from datetime import datetime
from time import perf_counter
from typing import Any, Optional, cast
from uuid import UUID

from opentelemetry import trace
from opentelemetry.trace import Span
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings
from .telemetry import trace_memory_operation
from ..models.document import Document
from ..models.message import Message, MessageRole
from ..models.session import Session

DEFAULT_USER_ID = "auto-created"


class MemoryManager:
    """Async memory abstraction for storing and retrieving conversation history."""

    def __init__(self, engine: Optional[AsyncEngine] = None) -> None:
        """
        Build a MemoryManager backed by an async SQLAlchemy engine.

        Args:
            engine: Optional preconfigured AsyncEngine. If omitted, an engine is created
                using settings.database_url and pool parameters from config.
        """
        self._engine: AsyncEngine = engine or create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )
        self._session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine,
            expire_on_commit=False,
        )

    def _get_span(self) -> Span:
        """Return the current OpenTelemetry span for attribute enrichment."""
        return trace.get_current_span()

    def _validate_embedding(
        self, embedding: Optional[list[float]]
    ) -> Optional[list[float]]:
        if embedding is None:
            return None
        if len(embedding) != settings.vector_dimension:
            raise ValueError(
                "Embedding must match configured dimension "
                f"{settings.vector_dimension} for model {settings.embedding_model_name}"
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
        metadata_filters: Optional[dict[str, Any]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[Any]:
        """
        Build SQLAlchemy filter conditions for document queries.

        Args:
            metadata_filters: Optional key/value filters applied to metadata_ JSONB.
            start_date: Inclusive lower bound for created_at.
            end_date: Inclusive upper bound for created_at.

        Raises:
            ValueError: When end_date precedes start_date.

        Returns:
            List of SQLAlchemy expressions to apply to a query.
        """
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
        metadata: Optional[dict[str, Any]] = None,
    ) -> UUID:
        """
        Store a message and auto-create the parent session when missing.

        Args:
            session_id: Target session identifier.
            role: Message role ('user', 'assistant', 'system').
            content: Message text; must be non-empty after trimming.
            metadata: Optional metadata stored in metadata_ column.

        Returns:
            UUID of the persisted message.

        Raises:
            ValueError: If role is invalid or content is empty.
            sqlalchemy.exc.SQLAlchemyError: Propagated database issues.
        """
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
        span.set_attribute(
            "db.statement", "INSERT messages (with optional session creation)"
        )

        return message.id

    @trace_memory_operation("get_conversation_history")
    async def get_conversation_history(
        self, session_id: UUID, limit: int = 100
    ) -> list[Message]:
        """
        Return conversation history for a session in chronological order (oldest first).

        Args:
            session_id: Session identifier to query.
            limit: Maximum number of messages to return (default 100).

        Returns:
            Ordered list of Message objects. Empty list if no rows found.

        Raises:
            ValueError: When limit <= 0.
        """
        if limit <= 0:
            raise ValueError("limit must be greater than 0")

        async with self._session_factory() as db:
            session_id_column = cast(Any, Message.session_id)
            created_at_column = cast(Any, Message.created_at)
            stmt = (
                select(Message)
                .where(session_id_column == session_id)
                .order_by(created_at_column.desc())
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
        metadata: Optional[dict[str, Any]] = None,
        embedding: Optional[list[float]] = None,
    ) -> UUID:
        """
        Persist a document with optional pgvector embedding.

        Args:
            content: Document text; must be non-empty after trimming.
            metadata: Optional JSON-serializable metadata.
            embedding: Optional vector embedding that must match configured dimension.

        Returns:
            UUID of the stored document.

        Raises:
            ValueError: When content is empty or embedding is invalid.
        """
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
        metadata_filters: Optional[dict[str, Any]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[Document]:
        """
        Perform cosine-distance semantic search with optional metadata and
        temporal filters.

        Args:
            query_embedding: Query vector; must match configured dimension.
            top_k: Maximum results to return (default 10).
            metadata_filters: Optional metadata_ filters applied as equality matches.
            start_date: Inclusive created_at lower bound.
            end_date: Inclusive created_at upper bound.

        Returns:
            List of Documents ordered by similarity.

        Raises:
            ValueError: When top_k <= 0, embedding is invalid, or date range is
            inverted.
        """
        if top_k <= 0:
            raise ValueError("top_k must be greater than 0")
        validated_embedding = self._validate_embedding(query_embedding)

        conditions = self._build_document_conditions(
            metadata_filters=metadata_filters,
            start_date=start_date,
            end_date=end_date,
        )

        vector_column = cast(Any, Document.embedding)
        stmt = select(Document)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = stmt.order_by(
            vector_column.cosine_distance(validated_embedding),
            cast(Any, Document.created_at).asc(),
        ).limit(top_k)

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
        metadata_filters: Optional[dict[str, Any]] = None,
    ) -> list[Document]:
        """
        Query documents by created_at range with optional metadata filters.

        Args:
            start_date: Inclusive lower bound for created_at.
            end_date: Inclusive upper bound for created_at.
            metadata_filters: Optional metadata_ equality filters.

        Returns:
            Documents ordered by newest first that satisfy the constraints.

        Raises:
            ValueError: When end_date precedes start_date.
        """
        conditions = self._build_document_conditions(
            metadata_filters=metadata_filters,
            start_date=start_date,
            end_date=end_date,
        )
        created_at_column = cast(Any, Document.created_at)
        stmt = (
            select(Document).where(and_(*conditions)).order_by(created_at_column.desc())
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
        """
        Verify database connectivity and pgvector availability.

        Returns:
            Mapping containing status, postgres_version, and optionally
            pgvector_version.

        Raises:
            sqlalchemy.exc.SQLAlchemyError: When the database is unreachable.
        """
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
        span.set_attribute(
            "db.statement", "SELECT version(); SELECT extversion FROM pg_extension"
        )

        return response

    @property
    def engine(self) -> AsyncEngine:
        return self._engine
