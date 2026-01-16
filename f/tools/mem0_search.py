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
# requirements:
# mem0ai>=1.0.0
# qdrant-client>=1.16.0

from __future__ import annotations

import logging
from typing import Any

# Import from pre-installed paias package
from paias.core.mem0 import get_memory_client
from paias.core.telemetry import trace_tool_call

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@trace_tool_call
def main(
    query: str,
    user_id: str,
    top_k: int = 10,
) -> list[dict[str, Any]]:
    """Retrieve past memories about the user.

    Searches for semantically similar memories stored for this user.
    Use this to recall user preferences, facts, or past interactions.

    Args:
        query: Search query (e.g., "food preferences", "allergies", "work")
        user_id: The unique ID of the user (UUID string)
        top_k: Maximum number of memories to return (default: 10)

    Returns:
        List of memory objects with 'id', 'memory', 'score', and 'metadata'

    Example:
        >>> results = main(
        ...     query="dietary restrictions",
        ...     user_id="550e8400-e29b-41d4-a716-446655440000"
        ... )
        >>> for mem in results:
        ...     print(mem["memory"])
    """
    logger.info(
        "Searching memories for user %s: %s (top_k=%d)",
        user_id,
        query[:50] + "..." if len(query) > 50 else query,
        top_k,
    )

    try:
        client = get_memory_client()

        memories = client.search(
            query,
            user_id=user_id,
            limit=top_k,
        )

        logger.info("Found %d memories for user %s", len(memories), user_id)

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
        logger.error("Memory search failed for user %s: %s", user_id, str(e))
        raise


# Windmill script metadata
__windmill__ = {
    "description": "Retrieve past memories about the user (Mem0)",
    "summary": "Search User Memory",
    "schema": {
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query for memories (e.g., 'food preferences')",
                "minLength": 1,
                "maxLength": 1000,
            },
            "user_id": {
                "type": "string",
                "description": "User identifier (UUID format)",
                "minLength": 1,
                "maxLength": 100,
            },
            "top_k": {
                "type": "integer",
                "description": "Maximum number of memories to return",
                "default": 10,
                "minimum": 1,
                "maximum": 100,
            },
        },
        "required": ["query", "user_id"],
    },
}
