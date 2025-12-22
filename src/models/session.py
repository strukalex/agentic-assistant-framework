from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlmodel import Field, SQLModel


class Session(SQLModel, table=True):
    """Conversation session container."""

    __tablename__ = "sessions"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    user_id: str = Field(
        sa_column=Column(String(255), nullable=False, index=True),
        min_length=1,
        max_length=255,
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    metadata_: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True, default=dict),
    )

    @field_validator("user_id", mode="before")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        cleaned = value.strip() if value else ""
        if not cleaned:
            raise ValueError("user_id cannot be empty")
        if len(cleaned) > 255:
            raise ValueError("user_id must be at most 255 characters")
        return cleaned

