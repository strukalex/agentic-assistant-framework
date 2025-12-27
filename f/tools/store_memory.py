"""Windmill tool: Store new research findings in memory.

Standalone tool for use in Windmill AI agent steps.
Persists documents to the PostgreSQL vector database for future retrieval.

Usage in Windmill:
    - Registered at path: f/tools/store_memory
    - Can be used as a tool in AI agent steps
    - Arguments: content (str), topic (str), sources (list[str], optional)
"""
# requirements:
# file:///app

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

# Import from pre-installed paias package
from paias.core.memory import MemoryManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(
    content: str,
    topic: str,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Store new research findings in long-term memory.

    Persists verified facts and synthesized answers to the vector database
    for future retrieval. Only store meaningful research findings, not
    queries or status messages.

    Args:
        content: The research content to store (verified facts or answers)
        topic: Brief topic description for categorization
        sources: Optional list of source identifiers (e.g., ["web_search", "fetch_url"])

    Returns:
        Dict with 'document_id' and 'status' keys

    Example:
        >>> result = main(
        ...     content="AI research trends in 2024 include...",
        ...     topic="AI research trends",
        ...     sources=["web_search"]
        ... )
        >>> print(result["document_id"])
    """
    import asyncio

    return asyncio.run(_async_main(content, topic, sources))


async def _async_main(
    content: str,
    topic: str,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Async implementation of memory storage."""
    logger.info("Storing memory: topic=%s, content_length=%d", topic, len(content))

    # Validation: Skip meta/log/no-result entries
    lowered = content.lower()
    skip_phrases = [
        "no results found",
        "no_results",
        "initial query",
        "status:",
        "query:",
        "error:",
    ]
    if any(phrase in lowered for phrase in skip_phrases):
        logger.warning("Skipping storage of meta/log content")
        return {
            "document_id": None,
            "status": "skipped",
            "reason": "Content appears to be meta/log data, not research findings",
        }

    # Build metadata
    metadata = {
        "topic": topic,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources": sources or [],
        "stored_by": "windmill_tool",
    }

    try:
        memory_manager = MemoryManager()
        doc_id = await memory_manager.store_document(
            content=content,
            metadata=metadata,
        )

        logger.info("Stored document with ID: %s", doc_id)
        return {
            "document_id": str(doc_id),
            "status": "success",
            "topic": topic,
        }

    except Exception as e:
        logger.error("Memory storage failed: %s", str(e))
        raise


# Windmill script metadata
__windmill__ = {
    "description": "Store new research findings in long-term memory",
    "summary": "Memory Store Tool",
    "schema": {
        "properties": {
            "content": {
                "type": "string",
                "description": "Research content to store (verified facts or synthesized answers)",
                "minLength": 10,
                "maxLength": 50000,
            },
            "topic": {
                "type": "string",
                "description": "Brief topic description for categorization",
                "minLength": 1,
                "maxLength": 200,
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of source identifiers",
            },
        },
        "required": ["content", "topic"],
    },
}
