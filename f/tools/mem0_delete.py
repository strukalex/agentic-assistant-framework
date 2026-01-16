"""Windmill tool: Delete a specific user memory from Mem0.

Standalone tool for use in Windmill AI agent steps.
Removes a specific memory from Qdrant via Mem0.

Usage in Windmill:
    - Registered at path: f/tools/mem0_delete
    - Can be used as a tool in AI agent steps
    - Arguments: memory_id (str), user_id (str)

MCP Exposure:
    - Enable MCP in Windmill to expose as tool to LibreChat/other MCP clients
    - Tool name: mem0_delete
"""
# requirements:
# mem0ai>=1.0.0
# qdrant-client>=1.16.0

from __future__ import annotations

import logging
from typing import Any

# Import from pre-installed paias package
from paias.core.mem0 import get_memory_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(
    memory_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Delete a specific memory by ID.

    Permanently removes a memory from the user's memory store.
    Use this when a user wants to forget something or correct outdated info.

    Args:
        memory_id: The ID of the memory to delete (from search results)
        user_id: The unique ID of the user (for verification/logging)

    Returns:
        Dict confirming deletion with 'deleted', 'memory_id', and 'user_id'

    Example:
        >>> result = main(
        ...     memory_id="mem_abc123",
        ...     user_id="550e8400-e29b-41d4-a716-446655440000"
        ... )
        >>> print(result["deleted"])  # True
    """
    logger.info("Deleting memory %s for user %s", memory_id, user_id)

    try:
        client = get_memory_client()

        # Delete the memory
        result = client.delete(memory_id)

        logger.info("Memory %s deleted for user %s", memory_id, user_id)

        return {
            "deleted": True,
            "memory_id": memory_id,
            "user_id": user_id,
            "result": result,
        }

    except Exception as e:
        logger.error(
            "Memory delete failed for %s (user %s): %s",
            memory_id,
            user_id,
            str(e),
        )
        raise


# Windmill script metadata
__windmill__ = {
    "description": "Delete a specific user memory by ID (Mem0)",
    "summary": "Delete User Memory",
    "schema": {
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "ID of the memory to delete (from search results)",
                "minLength": 1,
            },
            "user_id": {
                "type": "string",
                "description": "User identifier (for verification)",
                "minLength": 1,
                "maxLength": 100,
            },
        },
        "required": ["memory_id", "user_id"],
    },
}
