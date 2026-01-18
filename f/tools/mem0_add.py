# requirements:
# ^ Empty requirements directive disables Windmill's import inference.
# The paias package and all dependencies are pre-installed at container startup
# via `pip install -e /opt/paias_project` in docker-compose.override.yml.
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
from __future__ import annotations

import logging
from typing import Any

# Import from pre-installed paias package (via ADDITIONAL_PYTHON_PATHS)
from paias.core.mem0 import get_memory_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(
    content: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Save important facts to long-term memory.

    Mem0 automatically extracts and stores relevant facts from the content.
    Use this to remember preferences, allergies, interests, etc.

    Args:
        content: The text containing facts to remember (e.g., "I'm allergic to peanuts")
        metadata: Optional metadata to attach (e.g., {"source": "conversation"})

    Returns:
        Dict with memory operation results including extracted facts

    Example:
        >>> result = main(
        ...     content="I prefer dark mode and I'm vegetarian"
        ... )
        >>> print(result)
    """
    user_id = "local_user"

    logger.info(
        "Adding memory: %s",
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

        logger.info("Memory added successfully")

        return {
            "success": True,
            "result": result,
        }

    except Exception as e:
        logger.error("Memory add failed: %s", str(e))
        raise


# Windmill script metadata
__windmill__ = {
    "description": "Save important facts to long-term memory (Mem0)",
    "summary": "Add Memory",
    "schema": {
        "properties": {
            "content": {
                "type": "string",
                "description": "Text containing facts to remember (e.g., preferences, allergies)",
                "minLength": 1,
                "maxLength": 5000,
            },
            "metadata": {
                "type": "object",
                "description": "Optional metadata to attach to the memory",
            },
        },
        "required": ["content"],
    },
}
