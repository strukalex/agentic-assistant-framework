from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from pydantic import field_validator
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import Field, SQLModel

from src.core.config import settings


class Document(SQLModel, table=True):
    """Persisted document with optional vector embedding for semantic search."""

    __tablename__ = "documents"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    content: str = Field(
        sa_column=Column(String, nullable=False),
        min_length=1,
    )
    embedding: Optional[list[float]] = Field(
        default=None,
        sa_column=Column(Vector(settings.vector_dimension), nullable=True),
    )
    metadata_: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True, default=dict),
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
        index=True,
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        nullable=False,
    )

    @field_validator("content", mode="before")
    @classmethod
    def validate_content(cls, value: str) -> str:
        cleaned = value.strip() if value else ""
        if not cleaned:
            raise ValueError("Document content cannot be empty")
        return cleaned

    @field_validator("embedding", mode="before")
    @classmethod
    def validate_embedding(cls, value: Optional[list[float]]) -> Optional[list[float]]:
        if value is None:
            return None
        if len(value) != settings.vector_dimension:
            raise ValueError(
                f"Embedding must be {settings.vector_dimension}-dimensional"
            )
        if not all(isinstance(x, (int, float)) for x in value):
            raise ValueError("Embedding must contain only numeric values")
        return value
