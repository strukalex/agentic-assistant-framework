from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.config import settings
from src.core.memory import MemoryManager
from src.models.message import MessageRole


async def main() -> int:
    """Run the core quickstart flow to verify the stack is healthy."""
    manager = MemoryManager()

    print("Step 1: Checking database health...")
    health = await manager.health_check()
    print(f"  ✓ Status: {health['status']} | Postgres: {health['postgres_version']}")
    if "pgvector_version" in health:
        print(f"  ✓ pgvector: {health['pgvector_version']}")

    session_id = uuid4()
    print("\nStep 2: Storing and retrieving conversation messages...")
    await manager.store_message(
        session_id=session_id,
        role=MessageRole.USER.value,
        content="Quickstart hello",
        metadata={"source": "quickstart"},
    )
    await manager.store_message(
        session_id=session_id,
        role=MessageRole.ASSISTANT.value,
        content="Quickstart response",
        metadata={"source": "quickstart"},
    )
    history = await manager.get_conversation_history(session_id, limit=10)
    print(f"  ✓ Retrieved {len(history)} messages for session {session_id}")

    print("\nStep 3: Storing a document and running semantic search...")
    embedding = [0.0] * settings.vector_dimension
    document_id = await manager.store_document(
        content="Quickstart validation document",
        metadata={"source": "quickstart", "category": "validation"},
        embedding=embedding,
    )
    results = await manager.semantic_search(
        query_embedding=embedding,
        top_k=1,
        metadata_filters={"source": "quickstart"},
    )
    if not results:
        raise RuntimeError("Semantic search returned no results")
    print(f"  ✓ Stored document {document_id} and retrieved {results[0].id}")

    print("\n✅ Quickstart validation succeeded.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except Exception as exc:  # noqa: BLE001 - show clear failure context
        print(f"Quickstart validation failed: {exc}")
        raise SystemExit(1)

