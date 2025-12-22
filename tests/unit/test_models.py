from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import JSONB

from src.models.message import Message, MessageRole
from src.models.session import Session


def test_session_generates_ids_and_defaults() -> None:
    session = Session(user_id="user-123")

    assert isinstance(session.id, UUID)
    assert isinstance(session.created_at, datetime)
    assert isinstance(session.updated_at, datetime)
    assert session.metadata_ == {}


def test_session_rejects_empty_user_id() -> None:
    with pytest.raises(ValidationError):
        Session.model_validate({"user_id": ""})


def test_session_rejects_overlong_user_id() -> None:
    with pytest.raises(ValidationError):
        Session.model_validate({"user_id": "x" * 256})


def test_session_metadata_column_uses_jsonb() -> None:
    column = Session.__table__.c.metadata_
    assert isinstance(column.type, JSONB)


def test_message_enforces_role_enum() -> None:
    with pytest.raises(ValidationError):
        Message.model_validate({"session_id": uuid4(), "role": "invalid", "content": "hello"})


def test_message_rejects_empty_content() -> None:
    with pytest.raises(ValidationError):
        Message.model_validate({"session_id": uuid4(), "role": MessageRole.USER, "content": " "})


def test_message_has_foreign_key_to_sessions() -> None:
    foreign_keys = list(Message.__table__.foreign_keys)
    assert foreign_keys, "expected a foreign key from messages to sessions"

    fk = next(iter(foreign_keys))
    assert fk.column.table.name == "sessions"
    assert fk.column.name == "id"

