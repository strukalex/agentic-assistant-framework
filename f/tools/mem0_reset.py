# requirements:
# ^ Empty requirements directive disables Windmill's import inference.
# The paias package and all dependencies are pre-installed at container startup
# via `pip install -e /opt/paias_project` in docker-compose.override.yml.
"""Windmill tool: Reset Mem0 Qdrant collections.

Use this when switching between embedding providers (Azure vs Ollama)
that have different vector dimensions, or to clear all memories.

Usage in Windmill:
    - Registered at path: f/tools/mem0_reset
    - Can be used as a tool in AI agent steps
    - Arguments: confirm (bool)
"""

from __future__ import annotations

import logging
from typing import Any

from qdrant_client import QdrantClient

from paias.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main(
    confirm: bool = False,
) -> dict[str, Any]:
    """Reset Mem0 collections to fix dimension mismatch errors.

    Deletes both mem0_memories and mem0migrations collections from Qdrant.
    The collections will be recreated with correct dimensions on next use.

    Args:
        confirm: Must be True to proceed with deletion

    Returns:
        Dict with deleted collection names and status

    Example:
        >>> result = main(confirm=True)
        >>> print(result["deleted"])  # ['mem0_memories', 'mem0migrations']
    """
    if not confirm:
        return {
            "success": False,
            "error": "Set confirm=True to delete collections",
            "warning": "This will permanently delete all memories!",
        }

    client = QdrantClient(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
    )

    collections_to_delete = ["mem0_memories", "mem0migrations"]
    deleted = []
    errors = []

    for collection_name in collections_to_delete:
        try:
            # Check if collection exists
            collections = client.get_collections().collections
            exists = any(c.name == collection_name for c in collections)

            if exists:
                client.delete_collection(collection_name=collection_name)
                logger.info("Deleted collection: %s", collection_name)
                deleted.append(collection_name)
            else:
                logger.info("Collection %s does not exist, skipping", collection_name)

        except Exception as e:
            logger.error("Failed to delete %s: %s", collection_name, str(e))
            errors.append({"collection": collection_name, "error": str(e)})

    return {
        "success": len(errors) == 0,
        "deleted": deleted,
        "errors": errors if errors else None,
        "message": "Collections deleted. They will be recreated with correct dimensions on next mem0 operation.",
    }


# Windmill script metadata
__windmill__ = {
    "description": "Reset Mem0 Qdrant collections (fixes dimension mismatch)",
    "summary": "Reset Memory Store",
    "schema": {
        "properties": {
            "confirm": {
                "type": "boolean",
                "description": "Set to true to confirm deletion of all memories",
                "default": False,
            },
        },
        "required": ["confirm"],
    },
}
