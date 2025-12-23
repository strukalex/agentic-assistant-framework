from __future__ import annotations

import pytest

from src.core.config import settings
from src.core.memory import MemoryManager


def _embedding(value: float) -> list[float]:
    """
    Helper to create a configured-dimension embedding with the first element set
    to value.
    """
    return [value] + [0.0] * (settings.vector_dimension - 1)


@pytest.mark.asyncio
async def test_semantic_search_orders_by_similarity(db_engine) -> None:
    manager = MemoryManager(engine=db_engine)

    close_doc_id = await manager.store_document(
        content="Async IO patterns",
        metadata={"category": "research"},
        embedding=_embedding(0.9),
    )
    far_doc_id = await manager.store_document(
        content="Unrelated content",
        metadata={"category": "notes"},
        embedding=_embedding(0.1),
    )

    results = await manager.semantic_search(query_embedding=_embedding(1.0), top_k=2)

    assert [doc.id for doc in results] == [close_doc_id, far_doc_id]


@pytest.mark.asyncio
async def test_semantic_search_applies_metadata_filters(db_engine) -> None:
    manager = MemoryManager(engine=db_engine)

    await manager.store_document(
        content="Async guide",
        metadata={"category": "research"},
        embedding=_embedding(0.8),
    )
    await manager.store_document(
        content="Cooking recipe",
        metadata={"category": "culinary"},
        embedding=_embedding(0.7),
    )

    filtered_results = await manager.semantic_search(
        query_embedding=_embedding(0.9),
        top_k=5,
        metadata_filters={"category": "research"},
    )

    assert len(filtered_results) == 1
    assert filtered_results[0].metadata_.get("category") == "research"


@pytest.mark.asyncio
async def test_semantic_search_returns_empty_for_no_matches(db_engine) -> None:
    manager = MemoryManager(engine=db_engine)

    await manager.store_document(
        content="General content",
        metadata={"category": "general"},
        embedding=_embedding(0.3),
    )

    results = await manager.semantic_search(
        query_embedding=_embedding(0.2),
        top_k=3,
        metadata_filters={"category": "nonexistent"},
    )

    assert results == []
