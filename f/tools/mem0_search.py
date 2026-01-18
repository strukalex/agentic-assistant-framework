# requirements:
# ^ Empty requirements directive disables Windmill's import inference.
# The paias package and all dependencies are pre-installed at container startup
# via `pip install -e /opt/paias_project` in docker-compose.override.yml.
"""Windmill tool: Search user memories in Mem0.

Standalone tool for use in Windmill AI agent steps.
Queries Qdrant via Mem0 for semantically similar user memories.

Usage in Windmill:
    - Registered at path: f/tools/mem0_search
    - Can be used as a tool in AI agent steps
    - Arguments: query (str), user_id (str), top_k (int, optional)

MCP Exposure:
    - Enable MCP in Windmill to expose as tool to LibreChat/other MCP clients
    - Tool name: mem0_search
"""

from __future__ import annotations

import logging
from typing import Any

# Import from pre-installed paias package
from paias.core.mem0 import get_memory_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(
    query: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Retrieve past memories.

    Searches for semantically similar memories.
    Use this to recall preferences, facts, or past interactions.

    Args:
        query: Search query (e.g., "food preferences", "allergies", "work")
        top_k: Maximum number of memories to return (default: 10)

    Returns:
        List of memory objects with 'id', 'memory', 'score', and 'metadata'

    Example:
        >>> results = main(query="dietary restrictions")
        >>> for mem in results:
        ...     print(mem["memory"])
    """
    user_id = "local_user"

    logger.info(
        "Searching memories: %s (top_k=%d)",
        query[:50] + "..." if len(query) > 50 else query,
        top_k,
    )

    try:
        client = get_memory_client()

        response = client.search(
            query,
            user_id=user_id,
            limit=top_k,
        )
        memories = response.get("results", [])

        logger.info("Found %d memories", len(memories))

        # Return simplified format
        return [
            {
                "id": m.get("id"),
                "memory": m.get("memory"),
                "score": m.get("score"),
                "metadata": m.get("metadata", {}),
                "created_at": m.get("created_at"),
            }
            for m in memories
        ]

    except Exception as e:
        logger.error("Memory search failed: %s", str(e))
        raise


# Windmill script metadata
__windmill__ = {
    "description": "Retrieve past memories (Mem0)",
    "summary": "Search Memory",
    "schema": {
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for memories (e.g., 'food preferences')",
                "minLength": 1,
                "maxLength": 1000,
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of memories to return",
                "default": 10,
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["query"],
    },
}
