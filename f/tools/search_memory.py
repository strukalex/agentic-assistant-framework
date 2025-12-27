"""Windmill tool: Search semantic memory for relevant past knowledge.

Standalone tool for use in Windmill AI agent steps.
Queries the PostgreSQL vector database for semantically similar documents.

Usage in Windmill:
    - Registered at path: f/tools/search_memory
    - Can be used as a tool in AI agent steps
    - Arguments: query (str), top_k (int, optional)
"""
# requirements:
# file:///app

from __future__ import annotations

import logging
from typing import Any

# Import from pre-installed paias package
from paias.core.memory import MemoryManager
from paias.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Search semantic memory for relevant past knowledge.

    This tool queries the vector database for documents semantically similar
    to the provided query. Use this to check if information has been
    previously researched and stored.

    Args:
        query: Search query string describing what to look for
        top_k: Maximum number of results to return (default: 5)

    Returns:
        List of documents with 'content' and 'metadata' keys.
        Returns empty list if no relevant documents found.

    Example:
        >>> results = main("latest trends in AI research", top_k=3)
        >>> for doc in results:
        ...     print(doc["content"][:100])
    """
    import asyncio

    return asyncio.run(_async_main(query, top_k))


async def _async_main(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """Async implementation of memory search."""
    logger.info("Searching memory for: %s (top_k=%d)", query[:100], top_k)

    try:
        memory_manager = MemoryManager()
        documents = await memory_manager.semantic_search(query, top_k=top_k)

        if not documents:
            logger.info("No results found in memory")
            return []

        results = [
            {"content": doc.content, "metadata": doc.metadata_}
            for doc in documents
        ]

        logger.info("Found %d documents in memory", len(results))
        return results

    except Exception as e:
        logger.error("Memory search failed: %s", str(e))
        raise


# Windmill script metadata
__windmill__ = {
    "description": "Search semantic memory for relevant past knowledge",
    "summary": "Memory Search Tool",
    "schema": {
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query describing what to look for",
                "minLength": 1,
                "maxLength": 1000,
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of results to return",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
            },
        },
        "required": ["query"],
    },
}
