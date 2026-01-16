"""Windmill tool: Add user memory to Mem0.

Standalone tool for use in Windmill AI agent steps.
Stores facts about users in Qdrant via Mem0 for long-term personalization.

Usage in Windmill:
    - Registered at path: f/tools/mem0_add
    - Can be used as a tool in AI agent steps
    - Arguments: content (str), user_id (str), metadata (dict, optional)

MCP Exposure:
    - Enable MCP in Windmill to expose as tool to LibreChat/other MCP clients
    - Tool name: mem0_add
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
    content: str,
    user_id: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Save important facts about the user to long-term memory.

    Mem0 automatically extracts and stores relevant facts from the content.
    Use this to remember user preferences, allergies, interests, etc.

    Args:
        content: The text containing facts to remember (e.g., "I'm allergic to peanuts")
        user_id: The unique ID of the user (UUID string recommended)
        metadata: Optional metadata to attach (e.g., {"source": "conversation"})

    Returns:
        Dict with memory operation results including extracted facts

    Example:
        >>> result = main(
        ...     content="I prefer dark mode and I'm vegetarian",
        ...     user_id="550e8400-e29b-41d4-a716-446655440000"
        ... )
        >>> print(result)
    """
    logger.info(
        "Adding memory for user %s: %s",
        user_id,
        content[:50] + "..." if len(content) > 50 else content,
    )

    try:
        client = get_memory_client()

        # Mem0 extracts facts from content automatically
        result = client.add(
            content,
            user_id=user_id,
            metadata=metadata or {},
        )

        logger.info("Memory added successfully for user %s", user_id)

        return {
            "success": True,
            "user_id": user_id,
            "result": result,
        }

    except Exception as e:
        logger.error("Memory add failed for user %s: %s", user_id, str(e))
        raise


# Windmill script metadata
__windmill__ = {
    "description": "Save important facts about the user to long-term memory (Mem0)",
    "summary": "Add User Memory",
    "schema": {
        "properties": {
            "content": {
                "type": "string",
                "description": "Text containing facts to remember about the user",
                "minLength": 1,
                "maxLength": 5000,
            },
            "user_id": {
                "type": "string",
                "description": "User identifier (UUID format recommended)",
                "minLength": 1,
                "maxLength": 100,
            },
            "metadata": {
                "type": "object",
                "description": "Optional metadata to attach to the memory",
            },
        },
        "required": ["content", "user_id"],
    },
}
