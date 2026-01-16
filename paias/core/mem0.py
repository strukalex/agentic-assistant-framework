"""Mem0 configuration factory following LLM_PROVIDER pattern.

Provides standardized Mem0 Memory client configuration supporting both
Azure OpenAI and local Ollama based on the LLM_PROVIDER setting.

Constitution compliance:
- Article II.I: Follows shared utilities pattern (like llm.py)
- Article II.J: Direct imports, no try/except fallbacks
- Article II.H: Integrates with telemetry via trace decorators
"""

from __future__ import annotations

import logging
import os
from typing import Any

from mem0 import Memory

from .config import settings

logger = logging.getLogger(__name__)


def get_mem0_config() -> dict[str, Any]:
    """Build Mem0 configuration based on LLM_PROVIDER setting.

    Reads configuration from environment variables:
    - LLM_PROVIDER: 'azure' (default) or 'local' for Ollama

    For Azure (LLM_PROVIDER=azure):
    - Uses AZURE_AI_FOUNDRY_ENDPOINT and AZURE_AI_FOUNDRY_API_KEY
    - Embedding model: text-embedding-3-small (Azure OpenAI)
    - LLM model: Uses AZURE_DEPLOYMENT_NAME

    For Local Ollama (LLM_PROVIDER=local):
    - Uses LLM_BASE_URL for Ollama endpoint
    - Embedding model: MEM0_EMBEDDING_MODEL (default: nomic-embed-text)
    - LLM model: Uses LLM_MODEL_NAME

    Returns:
        Configuration dictionary for Memory.from_config()
    """
    provider_type = settings.llm_provider.lower()

    logger.info("=" * 60)
    logger.info("🧠 MEM0 PROVIDER: %s", provider_type.upper())
    logger.info("=" * 60)

    # Common: Qdrant vector store configuration
    config: dict[str, Any] = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "host": settings.qdrant_host,
                "port": settings.qdrant_port,
                "collection_name": settings.qdrant_collection_name,
            },
        }
    }

    logger.info(
        "🔧 Qdrant: host=%s, port=%d, collection=%s",
        settings.qdrant_host,
        settings.qdrant_port,
        settings.qdrant_collection_name,
    )

    if provider_type == "local":
        # Use Ollama for both LLM and embeddings
        # Ollama native URL (remove /v1 suffix if present)
        ollama_base_url = settings.llm_base_url
        if ollama_base_url.endswith("/v1"):
            ollama_base_url = ollama_base_url[:-3]

        config["llm"] = {
            "provider": "ollama",
            "config": {
                "model": settings.llm_model_name,
                "ollama_base_url": ollama_base_url,
            },
        }
        config["embedder"] = {
            "provider": "ollama",
            "config": {
                "model": settings.mem0_embedding_model,
                "ollama_base_url": ollama_base_url,
            },
        }

        logger.info(
            "✅ LOCAL OLLAMA: llm=%s, embedder=%s, base_url=%s",
            settings.llm_model_name,
            settings.mem0_embedding_model,
            ollama_base_url,
        )

    else:
        # Use Azure OpenAI (default)
        azure_endpoint = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
        azure_api_key = os.getenv("AZURE_AI_FOUNDRY_API_KEY")
        azure_deployment = os.getenv("AZURE_DEPLOYMENT_NAME", "gpt-4o")
        api_version = os.getenv("OPENAI_API_VERSION", "2024-10-21")

        if not azure_endpoint:
            raise ValueError(
                "AZURE_AI_FOUNDRY_ENDPOINT is required when LLM_PROVIDER=azure"
            )
        if not azure_api_key:
            raise ValueError(
                "AZURE_AI_FOUNDRY_API_KEY is required when LLM_PROVIDER=azure"
            )

        config["llm"] = {
            "provider": "azure_openai",
            "config": {
                "model": azure_deployment,
                "azure_endpoint": azure_endpoint,
                "api_key": azure_api_key,
                "api_version": api_version,
            },
        }
        config["embedder"] = {
            "provider": "azure_openai",
            "config": {
                "model": "text-embedding-3-small",
                "azure_endpoint": azure_endpoint,
                "api_key": azure_api_key,
                "api_version": api_version,
            },
        }

        logger.info(
            "✅ AZURE OPENAI: llm=%s, embedder=text-embedding-3-small",
            azure_deployment,
        )

    logger.info("=" * 60)

    return config


def get_memory_client() -> Memory:
    """Create a configured Mem0 Memory instance.

    Returns:
        Memory instance ready for add/search/delete operations.

    Raises:
        ValueError: If required environment variables are missing.
    """
    config = get_mem0_config()
    return Memory.from_config(config)
