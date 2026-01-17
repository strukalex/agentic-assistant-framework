# requirements:
# ^ Empty requirements directive disables Windmill's import inference.
# The paias package and all dependencies are pre-installed at container startup
# via `pip install -e /opt/paias_project` in docker-compose.override.yml.
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

from __future__ import annotations

import logging
from typing import Any

# Import from pre-installed paias package
from paias.core.mem0 import get_memory_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(
    memory_id: str,
) -> dict[str, Any]:
    """Delete a specific memory by ID.

    Permanently removes a memory from the memory store.
    Use this when you want to forget something or correct outdated info.

    Args:
        memory_id: The ID of the memory to delete (from search results)

    Returns:
        Dict confirming deletion with 'deleted' and 'memory_id'

    Example:
        >>> result = main(memory_id="mem_abc123")
        >>> print(result["deleted"])  # True
    """
    logger.info("Deleting memory %s", memory_id)

    try:
        client = get_memory_client()

        # Delete the memory
        result = client.delete(memory_id)

        logger.info("Memory %s deleted", memory_id)

        return {
            "deleted": True,
            "memory_id": memory_id,
            "result": result,
        }

    except Exception as e:
        logger.error("Memory delete failed for %s: %s", memory_id, str(e))
        raise


# Windmill script metadata
__windmill__ = {
    "description": "Delete a specific memory by ID (Mem0)",
    "summary": "Delete Memory",
    "schema": {
        "properties": {
            "memory_id": {
                "type": "string",
                "description": "ID of the memory to delete (from search results)",
                "minLength": 1,
            },
        },
        "required": ["memory_id"],
    },
}
