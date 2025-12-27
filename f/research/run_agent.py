"""Windmill script: Run the research agent with tool orchestration.

This script provides a native Windmill implementation of the research agent
that uses the standalone tool scripts directly without MCP overhead.

Usage in Windmill:
    - Registered at path: f/research/run_agent
    - Can be called directly or as part of a flow
    - Arguments: topic (str), user_id (str, optional), max_iterations (int, optional)

Architecture:
    - Uses paias package for LLM configuration and memory management
    - Calls standalone tool scripts: search_memory, store_memory, web_search, fetch_url
    - Implements the research workflow without MCP or complex state management
"""
# requirements:
# file:///app

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Silence noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def main(
    topic: str,
    user_id: str | None = None,
    max_iterations: int = 5,
    max_runtime_seconds: int = 120,
) -> dict[str, Any]:
    """Execute the research agent workflow.

    This is a Windmill-native implementation that orchestrates the research
    tools using the LLM directly, without MCP or complex agent frameworks.

    Args:
        topic: Research topic (1-500 characters)
        user_id: Optional user identifier (UUID string)
        max_iterations: Maximum tool call iterations (default: 5)
        max_runtime_seconds: Maximum runtime in seconds (default: 120)

    Returns:
        Dict with status, answer, confidence, sources, and metadata
    """
    if user_id is None:
        user_id = str(uuid4())

    return asyncio.run(
        _async_main(topic, user_id, max_iterations, max_runtime_seconds)
    )


async def _async_main(
    topic: str,
    user_id: str,
    max_iterations: int,
    max_runtime_seconds: int,
) -> dict[str, Any]:
    """Async implementation of the research agent."""
    from paias.core.llm import get_azure_model
    from paias.core.memory import MemoryManager

    logger.info("=" * 80)
    logger.info("STARTING WINDMILL-NATIVE RESEARCH AGENT")
    logger.info(f"Topic: {topic}")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Max iterations: {max_iterations}")
    logger.info("=" * 80)

    session_id = str(uuid4())
    started_at = datetime.now(timezone.utc)
    tool_calls: list[dict] = []
    sources: list[str] = []

    try:
        # Initialize LLM and memory
        model = get_azure_model()
        memory_manager = MemoryManager()

        # Build the system prompt
        system_prompt = _build_system_prompt()

        # Initial user message
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Research the following topic and provide a comprehensive answer:\n\nTopic: {topic}"},
        ]

        # Tool definitions for the LLM
        tools = _get_tool_definitions()

        # Agentic loop
        iteration = 0
        final_answer = None
        confidence = 0.0

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"\n--- Iteration {iteration}/{max_iterations} ---")

            # Call the LLM
            response = await _call_llm(model, messages, tools)

            if response is None:
                logger.error("LLM call failed")
                break

            # Check if we have a final answer (no tool calls)
            tool_calls_in_response = response.get("tool_calls", [])

            if not tool_calls_in_response:
                # Extract the final answer
                content = response.get("content", "")
                try:
                    # Try to parse as JSON
                    parsed = json.loads(content)
                    final_answer = parsed.get("answer", content)
                    confidence = parsed.get("confidence", 0.8)
                except (json.JSONDecodeError, TypeError):
                    final_answer = content
                    confidence = 0.7

                logger.info("Final answer received")
                break

            # Process tool calls
            messages.append({"role": "assistant", "content": None, "tool_calls": tool_calls_in_response})

            for tool_call in tool_calls_in_response:
                tool_name = tool_call.get("function", {}).get("name", "")
                tool_args_str = tool_call.get("function", {}).get("arguments", "{}")
                tool_id = tool_call.get("id", str(uuid4()))

                try:
                    tool_args = json.loads(tool_args_str)
                except json.JSONDecodeError:
                    tool_args = {}

                logger.info(f"Calling tool: {tool_name}({tool_args})")

                # Execute the tool
                tool_result = await _execute_tool(tool_name, tool_args, memory_manager)

                # Record tool call
                tool_calls.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result_preview": str(tool_result)[:200],
                })

                # Track sources
                if tool_name == "web_search":
                    sources.append("web_search")
                elif tool_name == "fetch_url":
                    url = tool_args.get("url", "")
                    if url:
                        sources.append(url)
                elif tool_name == "search_memory":
                    sources.append("memory")

                # Add tool result to messages
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": str(tool_result),
                })

        # Build response
        completed_at = datetime.now(timezone.utc)
        duration_seconds = (completed_at - started_at).total_seconds()

        result = {
            "status": "completed" if final_answer else "incomplete",
            "topic": topic,
            "user_id": user_id,
            "session_id": session_id,
            "answer": final_answer or "Research could not be completed within the iteration limit.",
            "confidence": confidence,
            "sources": list(set(sources)),
            "tool_calls": tool_calls,
            "iterations": iteration,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": duration_seconds,
        }

        logger.info("=" * 80)
        logger.info("RESEARCH AGENT COMPLETED")
        logger.info(f"Status: {result['status']}")
        logger.info(f"Iterations: {iteration}")
        logger.info(f"Tool calls: {len(tool_calls)}")
        logger.info(f"Duration: {duration_seconds:.1f}s")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.exception("Research agent failed")
        return {
            "status": "failed",
            "topic": topic,
            "user_id": user_id,
            "session_id": session_id,
            "answer": f"Research failed: {str(e)}",
            "confidence": 0.0,
            "sources": sources,
            "tool_calls": tool_calls,
            "error": str(e),
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }


def _build_system_prompt() -> str:
    """Build the system prompt for the research agent."""
    current_date = datetime.now().strftime("%Y-%m-%d")

    return f"""You are a ResearcherAgent for a Personal AI Assistant System.

Current date: {current_date}

Your capabilities:
- search_memory: Query long-term memory for previously researched information
- store_memory: Persist new verified facts to memory for future queries
- web_search: Search the web for current information
- fetch_url: Get full page content when search snippets aren't detailed enough

## Workflow

1. Memory Check: Call search_memory() ONCE at the start.
   - If it returns relevant information: Use it to answer.
   - If NO RESULTS FOUND or empty: Immediately call web_search().

2. Web Search: When memory has no answer, search the web.

3. Fetch Details (optional): If search snippets lack detail, use fetch_url().

4. Store Findings: After synthesizing new research from the web, call store_memory()
   with topic and sources metadata. ONLY store verified facts.

5. Provide Answer: Return a JSON object with your findings:
   {{"answer": "Your comprehensive answer", "confidence": 0.85}}

## HARD CONSTRAINTS

1. SINGLE MEMORY ATTEMPT: Only ONE call to search_memory per query.
2. NO LOOPING: Don't make the same tool call twice with identical parameters.
3. SEQUENTIAL EXECUTION: One tool at a time, wait for results.
4. STORE AFTER SEARCH: Don't call store_memory until you have web search results.
5. ONLY STORE FACTS: Never store queries, status messages, or "no results" responses.
6. FINAL RESPONSE: Your final response MUST be valid JSON with "answer" and "confidence" fields."""


def _get_tool_definitions() -> list[dict]:
    """Get the tool definitions for the LLM."""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_memory",
                "description": "Search semantic memory for relevant past knowledge. Returns list of documents with content and metadata.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query describing what to look for",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Maximum number of results (default: 5)",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "store_memory",
                "description": "Store new research findings in long-term memory. Only store verified facts and synthesized answers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {
                            "type": "string",
                            "description": "Research content to store",
                        },
                        "topic": {
                            "type": "string",
                            "description": "Brief topic description",
                        },
                        "sources": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of source identifiers",
                        },
                    },
                    "required": ["content", "topic"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for information. Returns formatted results with titles, URLs, and snippets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query string",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results (default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch a URL and return its content as markdown. Use when search snippets need more detail.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to fetch (http or https)",
                        },
                        "max_length": {
                            "type": "integer",
                            "description": "Maximum output length (default: 8000)",
                            "default": 8000,
                        },
                    },
                    "required": ["url"],
                },
            },
        },
    ]


async def _call_llm(model: Any, messages: list[dict], tools: list[dict]) -> dict | None:
    """Call the LLM with messages and tools."""
    try:
        # Use the model's underlying provider for direct API access
        provider = getattr(model, "provider", None) or getattr(model, "_provider", None)

        if provider is None:
            logger.error("Cannot access LLM provider")
            return None

        # Build the request
        import httpx

        # Get base URL and API key from provider
        base_url = getattr(provider, "base_url", None) or getattr(provider, "_base_url", "")
        api_key = getattr(provider, "api_key", None) or getattr(provider, "_api_key", "")

        if not base_url:
            logger.error("No base URL configured for LLM")
            return None

        # Ensure proper endpoint
        if not base_url.endswith("/chat/completions"):
            base_url = f"{base_url.rstrip('/')}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "api-key": api_key,  # Azure uses api-key header
        }

        # Also try Authorization header for non-Azure providers
        if "azure" not in base_url.lower():
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.4,
        }

        # Add model name if available
        model_name = getattr(model, "model_name", None) or getattr(model, "_model_name", None)
        if model_name:
            payload["model"] = model_name

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        # Extract the assistant message
        choices = data.get("choices", [])
        if not choices:
            return None

        message = choices[0].get("message", {})
        return message

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None


async def _execute_tool(
    tool_name: str,
    tool_args: dict,
    memory_manager: Any,
) -> str:
    """Execute a tool and return the result."""
    try:
        if tool_name == "search_memory":
            query = tool_args.get("query", "")
            top_k = tool_args.get("top_k", 5)

            documents = await memory_manager.semantic_search(query, top_k=top_k)

            if not documents:
                return "NO RESULTS FOUND: Memory search returned no matching documents."

            results = []
            for doc in documents:
                results.append({
                    "content": doc.content[:500],
                    "metadata": doc.metadata_,
                })
            return json.dumps(results, indent=2)

        elif tool_name == "store_memory":
            content = tool_args.get("content", "")
            topic = tool_args.get("topic", "")
            sources = tool_args.get("sources", [])

            # Skip meta content
            if any(phrase in content.lower() for phrase in ["no results", "error:", "status:"]):
                return "SKIPPED: Content appears to be meta/log data."

            metadata = {
                "topic": topic,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sources": sources,
            }

            doc_id = await memory_manager.store_document(content=content, metadata=metadata)
            return f"SUCCESS: Document stored with ID {doc_id}"

        elif tool_name == "web_search":
            query = tool_args.get("query", "")
            max_results = tool_args.get("max_results", 10)

            # Import and call the web search function
            from f.tools.web_search import _async_main as web_search_async
            return await web_search_async(query, max_results)

        elif tool_name == "fetch_url":
            url = tool_args.get("url", "")
            max_length = tool_args.get("max_length", 8000)

            # Import and call the fetch function
            from f.tools.fetch_url import _async_main as fetch_url_async
            return await fetch_url_async(url, max_length)

        else:
            return f"ERROR: Unknown tool '{tool_name}'"

    except Exception as e:
        logger.error(f"Tool execution failed: {tool_name} - {e}")
        return f"ERROR: Tool '{tool_name}' failed: {str(e)}"


# Windmill script metadata
__windmill__ = {
    "description": "Run the research agent with tool orchestration",
    "summary": "Windmill-Native Research Agent",
    "schema": {
        "properties": {
            "topic": {
                "type": "string",
                "description": "Research topic (1-500 characters)",
                "minLength": 1,
                "maxLength": 500,
            },
            "user_id": {
                "type": "string",
                "description": "Optional user identifier (UUID string)",
            },
            "max_iterations": {
                "type": "integer",
                "description": "Maximum tool call iterations",
                "default": 5,
                "minimum": 1,
                "maximum": 20,
            },
            "max_runtime_seconds": {
                "type": "integer",
                "description": "Maximum runtime in seconds",
                "default": 120,
                "minimum": 10,
                "maximum": 600,
            },
        },
        "required": ["topic"],
    },
}
