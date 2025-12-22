from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects.postgresql import JSONB

from src.core.config import settings
from src.models.document import Document
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
        Message.model_validate(
            {"session_id": uuid4(), "role": "invalid", "content": "hello"}
        )


def test_message_rejects_empty_content() -> None:
    with pytest.raises(ValidationError):
        Message.model_validate(
            {"session_id": uuid4(), "role": MessageRole.USER, "content": " "}
        )


def test_message_has_foreign_key_to_sessions() -> None:
    foreign_keys = list(Message.__table__.foreign_keys)
    assert foreign_keys, "expected a foreign key from messages to sessions"

    fk = next(iter(foreign_keys))
    assert fk.column.table.name == "sessions"
    assert fk.column.name == "id"


def test_document_generates_ids_and_defaults() -> None:
    document = Document(content="Doc content")

    assert document.id is not None
    assert document.metadata_ == {}
    assert document.embedding is None


def test_document_enforces_embedding_dimension() -> None:
    embedding = [0.1] * settings.vector_dimension
    document = Document(content="Doc content", embedding=embedding)

    assert document.embedding == embedding


def test_document_rejects_wrong_embedding_dimension() -> None:
    with pytest.raises(ValidationError):
        Document.model_validate({"content": "Doc", "embedding": [0.1, 0.2]})


def test_document_rejects_non_numeric_embedding() -> None:
    bad_embedding = [0.1] * (settings.vector_dimension - 1) + ["bad"]
    with pytest.raises(ValidationError):
        Document.model_validate({"content": "Doc", "embedding": bad_embedding})


def test_document_allows_null_embedding() -> None:
    document = Document(content="Doc", embedding=None)
    assert document.embedding is None


def test_document_metadata_column_uses_jsonb() -> None:
    column = Document.__table__.c.metadata_
    assert isinstance(column.type, JSONB)
