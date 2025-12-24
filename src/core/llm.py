"""Shared LLM utilities for Azure AI Foundry configuration and result handling.

Provides standardized model factory and result parsing to eliminate duplication
between ResearcherAgent and ToolGapDetector.
"""

import os
from typing import Any, Optional, TypeVar

from dotenv import load_dotenv
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

T = TypeVar("T")


def get_azure_model() -> OpenAIModel:
    """Create a standardized Azure AI Foundry model instance.

    Reads configuration from environment variables:
    - AZURE_AI_FOUNDRY_ENDPOINT: The base URL for the model
    - AZURE_AI_FOUNDRY_API_KEY: The API key for authentication
    - AZURE_DEPLOYMENT_NAME: The model name (deployment ID)

    Returns:
        OpenAIModel configured for Azure AI Foundry

    Raises:
        ValueError: If required environment variables are missing
    """
    load_dotenv()

    def _require_env(var_name: str) -> str:
        value = os.getenv(var_name)
        if not value:
            raise ValueError(
                f"{var_name} environment variable is required for Azure AI Foundry configuration"
            )
        return value

    endpoint = _require_env("AZURE_AI_FOUNDRY_ENDPOINT")
    api_key = _require_env("AZURE_AI_FOUNDRY_API_KEY")
    model_name = _require_env("AZURE_DEPLOYMENT_NAME")

    if not endpoint:
        raise ValueError("AZURE_AI_FOUNDRY_ENDPOINT environment variable is required")
    if not api_key:
        raise ValueError("AZURE_AI_FOUNDRY_API_KEY environment variable is required")

    # Normalize the base URL for serverless endpoints
    base_url = endpoint
    if "/chat/completions" in base_url:
        base_url = base_url.split("/chat/completions")[0]
    if "services.ai.azure.com" in base_url and not base_url.endswith("/models"):
        base_url = f"{base_url.rstrip('/')}/models"

    provider = OpenAIProvider(
        base_url=base_url,
        api_key=api_key,
    )

    return OpenAIModel(model_name, provider=provider)


def parse_agent_result(result: Any) -> Optional[T]:
    """Extract data from a Pydantic AI RunResult, handling version differences.

    Pydantic AI versions differ in their result structure (some use .data, others .output).
    This function normalizes access across versions.

    Args:
        result: RunResult from agent.run()

    Returns:
        Extracted data/output, or None if neither attribute exists

    Raises:
        AttributeError: If result has neither .data nor .output attributes
    """
    data = getattr(result, "data", None)
    if data is None:
        data = getattr(result, "output", None)
    if data is None:
        raise AttributeError(
            f"agent.run result missing data/output. Available attrs: {dir(result)}"
        )
    return data
