from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import Column, Enum as SAEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlmodel import Field, SQLModel


class MessageRole(str, Enum):
    """Supported message roles for conversations."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(SQLModel, table=True):
    """Persisted conversation message."""

    __tablename__ = "messages"

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True),
    )
    session_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    role: MessageRole = Field(
        sa_column=Column(SAEnum(MessageRole, name="message_role"), nullable=False)
    )
    content: str = Field(sa_column=Column(String, nullable=False))
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False, index=True)
    metadata_: dict = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=True, default=dict),
    )

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        cleaned = value.strip() if value else ""
        if not cleaned:
            raise ValueError("Message content cannot be empty")
        return cleaned

