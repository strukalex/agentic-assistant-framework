"""Shared LLM utilities for Azure AI Foundry configuration and result handling.

Provides standardized model factory and result parsing to eliminate duplication
between ResearcherAgent and ToolGapDetector.
"""

import json
import logging
import os
from typing import Any, Optional, TypeVar, cast

import httpx
from dotenv import load_dotenv
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from .config import settings

T = TypeVar("T")

logger = logging.getLogger(__name__)


def get_azure_model() -> OpenAIChatModel:
    """Create a standardized Azure AI Foundry model instance.

    Reads configuration from environment variables:
    - AZURE_AI_FOUNDRY_ENDPOINT: The base URL for the model
    - AZURE_AI_FOUNDRY_API_KEY: The API key for authentication
    - AZURE_DEPLOYMENT_NAME: The model name (deployment ID)

    Returns:
        OpenAIChatModel configured for Azure AI Foundry

    Raises:
        ValueError: If required environment variables are missing
    """
    load_dotenv()

    def _require_env(var_name: str) -> str:
        value = os.getenv(var_name)
        if not value:
            raise ValueError(
                f"{var_name} environment variable is required for "
                "Azure AI Foundry configuration"
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

    # Create HTTP client with optional logging hooks
    if settings.enable_agentic_logging:
        http_client = httpx.AsyncClient(
            event_hooks={
                "request": [_log_http_request],
                "response": [_log_http_response],
            }
        )
    else:
        http_client = None  # Use default client

    provider = OpenAIProvider(
        base_url=base_url,
        api_key=api_key,
        http_client=http_client,
    )

    # Wrap provider to log conversation messages (only if enabled)
    if settings.enable_agentic_logging:
        provider = _LoggingProviderWrapper(provider)

    return OpenAIChatModel(model_name, provider=provider)


class _LoggingProviderWrapper:
    """Wrapper around OpenAIProvider that logs conversation messages."""

    def __init__(self, provider: OpenAIProvider):
        self._provider = provider

    def __getattr__(self, name: str) -> Any:
        """Delegate all attribute access to the wrapped provider."""
        return getattr(self._provider, name)

    async def run_chat(self, *args: Any, **kwargs: Any) -> Any:
        """Intercept run_chat to log messages."""
        # Extract messages from kwargs or args
        messages = kwargs.get("messages", [])
        if not messages:
            # Try to get messages from args
            for arg in args:
                if isinstance(arg, (list, tuple)) and arg:
                    if isinstance(arg[0], dict) and "role" in arg[0]:
                        messages = arg
                        break
                elif isinstance(arg, dict):
                    if "messages" in arg:
                        messages = arg["messages"]
                        break
                    # Check if the dict itself is a message
                    if "role" in arg:
                        messages = [arg]
                        break

        # Log the conversation (only if enabled)
        if not settings.enable_agentic_logging:
            return await self._provider.run_chat(*args, **kwargs)

        if messages:
            # Build entire request log as a single string for atomic logging
            log_lines = ["💬 [LLM REQUEST] ==="]
            for i, msg in enumerate(messages, 1):
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                # Truncate long content
                if isinstance(content, str) and len(content) > 500:
                    content_preview = content[:500] + "..."
                else:
                    content_preview = content

                # Format based on role
                if role == "system":
                    preview = content_preview[:200] + "..." if len(str(content_preview)) > 200 else content_preview
                    log_lines.append(f"   [{i}] SYSTEM: {preview}")
                elif role == "user":
                    log_lines.append(f"   [{i}] USER: {content_preview}")
                elif role == "assistant":
                    log_lines.append(f"   [{i}] ASSISTANT: {content_preview}")
                elif role == "tool":
                    tool_name = msg.get("name", "unknown")
                    preview = content_preview[:200] + "..." if len(str(content_preview)) > 200 else content_preview
                    log_lines.append(f"   [{i}] TOOL RESULT ({tool_name}): {preview}")
                else:
                    log_lines.append(f"   [{i}] {role.upper()}: {content_preview}")

            # Check for tool calls in the last assistant message
            if messages and messages[-1].get("role") == "assistant":
                tool_calls = messages[-1].get("tool_calls", [])
                if tool_calls:
                    log_lines.append(f"   [TOOL CALLS] Assistant requested {len(tool_calls)} tool(s):")
                    for tc in tool_calls:
                        tc_func = tc.get("function", {})
                        tc_name = tc_func.get("name", "unknown")
                        tc_args = tc_func.get("arguments", "{}")
                        try:
                            tc_args_parsed = json.loads(tc_args) if isinstance(tc_args, str) else tc_args
                            args_str = json.dumps(tc_args_parsed, indent=2)[:200]
                            log_lines.append(f"      → {tc_name}({args_str})")
                        except:
                            log_lines.append(f"      → {tc_name}({str(tc_args)[:200]})")

            # Single atomic log call
            logger.info("\n".join(log_lines))

        # Call the actual provider
        result = await self._provider.run_chat(*args, **kwargs)

        # Log the response
        if hasattr(result, "choices") and result.choices:
            choice = result.choices[0]
            if hasattr(choice, "message"):
                msg = choice.message
                content = getattr(msg, "content", None) or ""
                tool_calls = getattr(msg, "tool_calls", None) or []

                # Build entire response log as a single string for atomic logging
                log_lines = ["💬 [LLM RESPONSE] ==="]
                if content:
                    content_preview = content[:500] + "..." if len(content) > 500 else content
                    log_lines.append(f"   ASSISTANT: {content_preview}")
                if tool_calls:
                    log_lines.append(f"   [TOOL CALLS] Model requested {len(tool_calls)} tool(s):")
                    for tc in tool_calls:
                        tc_func = getattr(tc, "function", None)
                        if tc_func:
                            tc_name = getattr(tc_func, "name", "unknown")
                            tc_args = getattr(tc_func, "arguments", "{}")
                            try:
                                tc_args_parsed = json.loads(tc_args) if isinstance(tc_args, str) else tc_args
                                args_str = json.dumps(tc_args_parsed, indent=2)[:200]
                                log_lines.append(f"      → {tc_name}({args_str})")
                            except:
                                log_lines.append(f"      → {tc_name}({str(tc_args)[:200]})")

                # Single atomic log call
                logger.info("\n".join(log_lines) + "\n")

        return result


def _format_message_clean(msg: dict, index: int) -> str:
    """Format a single message in clean conversation chain format."""
    role = msg.get("role", "unknown").upper()
    content = msg.get("content", "")
    tool_calls = msg.get("tool_calls", [])

    lines = []

    # Format content (no truncation)
    if content:
        lines.append(f"  [{index}] {role}: {content}")

    # Format tool calls
    if tool_calls:
        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "unknown")
            args = func.get("arguments", "{}")
            try:
                args_parsed = json.loads(args) if isinstance(args, str) else args
                args_str = json.dumps(args_parsed)
            except Exception:
                args_str = str(args)
            lines.append(f"  [{index}] {role}: 🛠️ {name}({args_str})")

    return "\n".join(lines) if lines else f"  [{index}] {role}: (empty)"


async def _log_http_request(request: httpx.Request) -> None:
    """Log outbound HTTP requests to the LLM."""
    if not settings.enable_agentic_logging:
        return
    try:
        body = request.content
        if not body:
            logger.info(f"🔵 [HTTP REQUEST] → {request.method} {request.url}")
            return

        parsed = None
        try:
            parsed = json.loads(body)
        except Exception:
            pass

        if settings.agentic_logging_verbose:
            # Verbose mode: full JSON
            body_preview = json.dumps(parsed, indent=2) if parsed else body.decode("utf-8", errors="ignore")
            headers_dict = {k: v for k, v in request.headers.items() if k.lower().startswith("content")}
            log_message = (
                f"🔵 [HTTP REQUEST] → {request.method} {request.url}\n"
                f"Headers: {headers_dict}\n"
                f"Body:\n{body_preview}"
            )
        else:
            # Clean mode: conversation chain format
            if parsed and "messages" in parsed:
                messages = parsed["messages"]
                log_lines = [f"🔵 [HTTP REQUEST] → {request.method} {request.url}"]
                log_lines.append("  --- Conversation History ---")
                for i, msg in enumerate(messages, 1):
                    log_lines.append(_format_message_clean(msg, i))
                log_message = "\n".join(log_lines)
            else:
                # Fallback for non-chat requests
                log_message = f"🔵 [HTTP REQUEST] → {request.method} {request.url}"

        logger.info(log_message)
    except Exception as e:
        logger.debug("Failed to log HTTP request: %s", e)


async def _log_http_response(response: httpx.Response) -> None:
    """Log inbound HTTP responses from the LLM."""
    if not settings.enable_agentic_logging:
        return
    try:
        text = await response.aread()
        method = response.request.method if response.request else ""
        url = response.request.url if response.request else ""

        if not text:
            logger.info(f"🟢 [HTTP RESPONSE] ← {method} {url} {response.status_code}")
            return

        parsed = None
        try:
            parsed = json.loads(text)
        except Exception:
            pass

        if settings.agentic_logging_verbose:
            # Verbose mode: full JSON
            body_preview = json.dumps(parsed, indent=2) if parsed else text.decode("utf-8", errors="ignore")
            log_message = (
                f"🟢 [HTTP RESPONSE] ← {method} {url} {response.status_code}\n"
                f"Body:\n{body_preview}"
            )
        else:
            # Clean mode: extract the new response only
            log_lines = [f"🟢 [HTTP RESPONSE] ← {method} {url} {response.status_code}"]
            if parsed and "choices" in parsed:
                choice = parsed["choices"][0] if parsed["choices"] else {}
                msg = choice.get("message", {})
                log_lines.append("  --- New Response ---")
                log_lines.append(_format_message_clean(msg, 0).replace("[0]", "[NEW]"))
            log_message = "\n".join(log_lines)

        logger.info(log_message)
    except Exception as e:
        logger.debug("Failed to log HTTP response: %s", e)


def parse_agent_result(result: Any) -> Optional[T]:
    """Extract data from a Pydantic AI RunResult, handling version differences.

    Pydantic AI versions differ in their result structure (some use .data,
    others .output).
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
    return cast(Optional[T], data)
