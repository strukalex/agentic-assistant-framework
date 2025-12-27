"""Shared utilities for Windmill tool scripts.

Provides common functionality used across multiple Windmill scripts:
- LLM client initialization
- Memory manager initialization
- Common error handling
- Logging configuration

Usage in Windmill scripts:
    from f.tools.shared import get_memory_manager, get_llm_client

Note: This module can be imported by other Windmill scripts in the same
workspace. Windmill resolves relative imports within the f/ directory.
"""
# requirements:
# file:///app

from __future__ import annotations

import logging
import os
from typing import Any

# Configure module-level logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Silence noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_memory_manager() -> Any:
    """Get a configured MemoryManager instance.

    Returns a MemoryManager connected to the PostgreSQL database
    configured via PAIAS_DATABASE_URL environment variable.

    Returns:
        MemoryManager instance

    Raises:
        ImportError: If paias package is not installed
        RuntimeError: If database connection fails
    """
    from paias.core.memory import MemoryManager

    logger.info("Initializing MemoryManager...")
    return MemoryManager()


def get_llm_model() -> Any:
    """Get a configured LLM model instance.

    Returns an OpenAI-compatible model configured for either:
    - Azure AI Foundry (LLM_PROVIDER=azure, default)
    - Local Ollama (LLM_PROVIDER=local)

    Configuration is read from environment variables:
    - LLM_PROVIDER: 'azure' or 'local'
    - AZURE_AI_FOUNDRY_ENDPOINT, AZURE_AI_FOUNDRY_API_KEY (for Azure)
    - LLM_MODEL_NAME, LLM_BASE_URL (for Ollama)

    Returns:
        OpenAIChatModel instance

    Raises:
        ImportError: If paias package is not installed
        ValueError: If required environment variables are missing
    """
    from paias.core.llm import get_azure_model

    logger.info("Initializing LLM model...")
    return get_azure_model()


def format_tool_error(tool_name: str, error: Exception) -> str:
    """Format a tool execution error for LLM consumption.

    Args:
        tool_name: Name of the tool that failed
        error: The exception that occurred

    Returns:
        Formatted error message string
    """
    error_type = type(error).__name__
    error_msg = str(error)[:200]  # Truncate long errors
    return f"ERROR: Tool '{tool_name}' failed with {error_type}: {error_msg}"


def truncate_result(result: str, max_length: int = 8000) -> str:
    """Truncate a tool result if it exceeds the maximum length.

    Args:
        result: The result string to truncate
        max_length: Maximum length before truncation

    Returns:
        Original or truncated result with omission notice
    """
    if len(result) <= max_length:
        return result

    omitted = len(result) - max_length
    return result[:max_length] + f"\n\n... [truncated, {omitted} chars omitted]"


def validate_url(url: str) -> tuple[bool, str]:
    """Validate a URL for fetching.

    Args:
        url: URL string to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not url:
        return False, "URL is empty"

    if not url.startswith(("http://", "https://")):
        return False, f"Invalid URL scheme. URL must start with http:// or https://. Got: {url[:50]}"

    return True, ""


def mask_sensitive_data(text: str, patterns: list[str] | None = None) -> str:
    """Mask sensitive data in log output.

    Args:
        text: Text that may contain sensitive data
        patterns: List of patterns to mask (default: API keys, passwords)

    Returns:
        Text with sensitive patterns masked
    """
    import re

    if patterns is None:
        patterns = [
            r'api[_-]?key["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]+)',
            r'password["\']?\s*[:=]\s*["\']?([^\s"\']+)',
            r'token["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_-]+)',
        ]

    result = text
    for pattern in patterns:
        result = re.sub(pattern, lambda m: m.group(0).replace(m.group(1), "***"), result, flags=re.IGNORECASE)

    return result


def get_current_timestamp() -> str:
    """Get current UTC timestamp in ISO format.

    Returns:
        ISO 8601 formatted timestamp string
    """
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


# Windmill script metadata (this module is also a valid script)
__windmill__ = {
    "description": "Shared utilities for Windmill tool scripts",
    "summary": "Shared Utilities",
    "schema": {
        "properties": {},
        "required": [],
    },
}


def main() -> dict[str, str]:
    """Test entrypoint to verify utilities are working.

    Returns:
        Dict with status and available utilities
    """
    utilities = [
        "get_memory_manager",
        "get_llm_model",
        "format_tool_error",
        "truncate_result",
        "validate_url",
        "mask_sensitive_data",
        "get_current_timestamp",
    ]

    return {
        "status": "ok",
        "utilities": ", ".join(utilities),
        "timestamp": get_current_timestamp(),
    }
