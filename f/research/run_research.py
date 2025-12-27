"""Windmill flow entry point for DailyTrendingResearch workflow.

This script is the Windmill-executable entry point that imports from the
paias package (installed from local path in custom Dockerfile.windmill).

Supports two execution modes:
    - "native": Uses Windmill-native tools (no MCP, simpler architecture)
    - "langgraph": Uses full LangGraph workflow with MCP tools (legacy)

Usage in Windmill:
    - Registered at path: f/research/run_research
    - Arguments: topic (str), user_id (str), mode (str), client_traceparent (str, optional)

Architecture:
    - paias package is installed from file:///app in Windmill's venv
    - Source code is copied to /app in the custom Docker image
    - Clean imports directly from the installed package
"""
# requirements:
# file:///app
# duckduckgo-search>=6.0.0

from __future__ import annotations

import sys
import os

import asyncio
import logging
from typing import Any
from uuid import uuid4

# Import from pre-installed paias package
from paias.workflows.research_graph import compile_research_graph
from paias.core.memory import MemoryManager  # Use real MemoryManager with database
from paias.models.research_state import ResearchState
from paias.workflows.report_formatter import (
    format_research_report,
    render_markdown,
)
from paias.windmill.approval_handler import (
    ApprovalRequest,
    process_planned_actions,
)
from paias.models.planned_action import PlannedAction
from paias.core.config import settings
from paias.agents.researcher import run_researcher_agent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Silence httpx/httpcore verbose logging to prevent interleaving
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# Try to import wmill for Windmill-specific functionality
try:
    import wmill

    WMILL_AVAILABLE = True
except ImportError:
    wmill = None  # type: ignore[assignment]
    WMILL_AVAILABLE = False


async def _default_action_executor(action: PlannedAction) -> dict[str, Any]:
    """Default action executor that logs execution."""
    logger.info(f"Executing action: {action.action_type} - {action.description}")
    return {
        "success": True,
        "action_type": action.action_type,
        "message": f"Action '{action.action_type}' executed successfully",
    }


async def _windmill_suspend_for_approval(
    approval_request: ApprovalRequest,
) -> dict[str, Any]:
    """Suspend workflow and wait for Windmill approval."""
    logger.info(f"Requesting approval for action: {approval_request.action_type}")

    if not WMILL_AVAILABLE or wmill is None:
        # Auto-approve for testing without wmill
        logger.info("Auto-approving action (wmill not available)")
        return {
            "decision": "approve",
            "approver": "test-auto-approval",
        }

    from datetime import timedelta

    timeout_seconds = settings.approval_timeout_seconds
    logger.info(f"Suspending workflow for approval (timeout: {timeout_seconds}s)")

    try:
        resume_payload = wmill.suspend(
            timeout=timedelta(seconds=timeout_seconds),
            default_args={"decision": "pending"},
            enums={"decision": ["approve", "reject"]},
            description=f"""
## Action Approval Required

**Action Type:** {approval_request.action_type}

**Description:** {approval_request.action_description}

Please review and select 'approve' to proceed or 'reject' to skip this action.

_Timeout: {timeout_seconds} seconds_
""",
        )
        logger.info(f"Approval received: {resume_payload.get('decision', 'unknown')}")
        return resume_payload

    except Exception as e:
        logger.error(f"Approval request failed: {e}")
        return {
            "decision": "reject",
            "error": str(e),
            "reason": "timeout_or_error",
        }


def main(
    topic: str,
    user_id: str | None = None,
    mode: str = "native",
    client_traceparent: str | None = None,
    max_researcher_runtime_seconds: int | None = None,
    max_iterations: int | None = None,
) -> dict[str, Any]:
    """
    Windmill entrypoint: execute the research workflow.

    This is the main entry point when this script is executed by Windmill.
    Windmill expects a synchronous function, so we run the async implementation
    using asyncio.run().

    Args:
        topic: Research topic (1-500 chars).
        user_id: Optional user identifier (UUID string). Auto-generated if not provided.
        mode: Execution mode - "native" (Windmill-native, no MCP) or "langgraph" (full workflow).
        client_traceparent: Optional W3C traceparent for distributed tracing.
        max_researcher_runtime_seconds: Max runtime for researcher agent (default: 60).
        max_iterations: Max research iterations (default: 5).

    Returns:
        Dict with status, answer/report, sources, and metadata.
    """
    # Auto-generate user_id if not provided
    if user_id is None:
        user_id = str(uuid4())

    # Route to appropriate implementation
    if mode == "native":
        return asyncio.run(
            _async_main_native(
                topic,
                user_id,
                max_iterations=max_iterations or 5,
                max_runtime_seconds=max_researcher_runtime_seconds or 120,
            )
        )
    else:
        # Legacy LangGraph mode
        return asyncio.run(
            _async_main_langgraph(
                topic,
                user_id,
                client_traceparent,
                max_researcher_runtime_seconds=max_researcher_runtime_seconds,
                max_iterations=max_iterations,
            )
        )


async def _async_main_native(
    topic: str,
    user_id: str,
    max_iterations: int = 5,
    max_runtime_seconds: int = 120,
) -> dict[str, Any]:
    """Windmill-native implementation using direct tool calls (no MCP).

    This is a simplified, faster implementation that:
    - Calls tools directly without MCP server overhead
    - Uses DuckDuckGo for web search (no API key required)
    - Implements the agentic loop with direct LLM calls
    """
    from datetime import datetime, timezone
    import json

    from paias.core.llm import get_azure_model
    from paias.core.memory import MemoryManager

    logger.info("=" * 80)
    logger.info("STARTING WINDMILL-NATIVE RESEARCH AGENT")
    logger.info(f"Topic: {topic}")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Mode: native (no MCP)")
    logger.info("=" * 80)

    session_id = str(uuid4())
    started_at = datetime.now(timezone.utc)
    tool_calls_log: list[dict] = []
    sources: list[str] = []

    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(0)
        except Exception:
            pass

    try:
        # Initialize LLM and memory
        model = get_azure_model()
        memory_manager = MemoryManager()

        # Build the system prompt
        current_date = datetime.now().strftime("%Y-%m-%d")
        system_prompt = f"""You are a ResearcherAgent for a Personal AI Assistant System.

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

        # Initial user message
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Research the following topic and provide a comprehensive answer:\n\nTopic: {topic}"},
        ]

        # Tool definitions
        tools = _get_tool_definitions()

        # Agentic loop
        iteration = 0
        final_answer = None
        confidence = 0.0

        while iteration < max_iterations:
            iteration += 1
            logger.info(f"\n--- Iteration {iteration}/{max_iterations} ---")

            if WMILL_AVAILABLE and wmill is not None:
                try:
                    progress = int(10 + (iteration / max_iterations) * 70)
                    wmill.set_progress(progress)
                except Exception:
                    pass

            # Call the LLM
            response = await _call_llm_native(model, messages, tools)

            if response is None:
                logger.error("LLM call failed")
                break

            # Check if we have a final answer (no tool calls)
            tool_calls_in_response = response.get("tool_calls", [])

            if not tool_calls_in_response:
                # Extract the final answer
                content = response.get("content", "")
                try:
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
                tool_result = await _execute_tool_native(tool_name, tool_args, memory_manager)

                # Record tool call
                tool_calls_log.append({
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

        if WMILL_AVAILABLE and wmill is not None:
            try:
                wmill.set_progress(100)
            except Exception:
                pass

        # Build response
        completed_at = datetime.now(timezone.utc)
        duration_seconds = (completed_at - started_at).total_seconds()

        result = {
            "status": "completed" if final_answer else "incomplete",
            "mode": "native",
            "topic": topic,
            "user_id": user_id,
            "session_id": session_id,
            "answer": final_answer or "Research could not be completed within the iteration limit.",
            "confidence": confidence,
            "sources": list(set(sources)),
            "tool_calls": tool_calls_log,
            "iterations": iteration,
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "duration_seconds": duration_seconds,
        }

        logger.info("=" * 80)
        logger.info("RESEARCH AGENT COMPLETED")
        logger.info(f"Status: {result['status']}")
        logger.info(f"Iterations: {iteration}")
        logger.info(f"Tool calls: {len(tool_calls_log)}")
        logger.info(f"Duration: {duration_seconds:.1f}s")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.exception("Research agent failed")
        return {
            "status": "failed",
            "mode": "native",
            "topic": topic,
            "user_id": user_id,
            "session_id": session_id,
            "answer": f"Research failed: {str(e)}",
            "confidence": 0.0,
            "sources": sources,
            "tool_calls": tool_calls_log,
            "error": str(e),
            "started_at": started_at.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }


def _get_tool_definitions() -> list[dict]:
    """Get the tool definitions for the LLM."""
    return [
        {
            "type": "function",
            "function": {
                "name": "search_memory",
                "description": "Search semantic memory for relevant past knowledge. Returns list of documents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "top_k": {"type": "integer", "description": "Max results", "default": 5},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "store_memory",
                "description": "Store new research findings in long-term memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Research content to store"},
                        "topic": {"type": "string", "description": "Brief topic description"},
                        "sources": {"type": "array", "items": {"type": "string"}, "description": "Source identifiers"},
                    },
                    "required": ["content", "topic"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for information. Returns formatted results.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {"type": "integer", "description": "Max results", "default": 10},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch a URL and return its content as markdown.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                        "max_length": {"type": "integer", "description": "Max output length", "default": 8000},
                    },
                    "required": ["url"],
                },
            },
        },
    ]


async def _call_llm_native(model: Any, messages: list[dict], tools: list[dict]) -> dict | None:
    """Call the LLM with messages and tools."""
    import httpx

    try:
        # Get provider details from model
        provider = getattr(model, "provider", None) or getattr(model, "_provider", None)
        if provider is None:
            logger.error("Cannot access LLM provider")
            return None

        # Extract base URL and API key
        base_url = getattr(provider, "base_url", None) or getattr(provider, "_base_url", "")
        api_key = getattr(provider, "api_key", None) or getattr(provider, "_api_key", "")

        if not base_url:
            logger.error("No base URL configured for LLM")
            return None

        # Ensure proper endpoint
        endpoint = base_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint = f"{endpoint}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "api-key": api_key,  # Azure style
        }
        if "azure" not in base_url.lower():
            headers["Authorization"] = f"Bearer {api_key}"

        payload = {
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.4,
        }

        model_name = getattr(model, "model_name", None) or getattr(model, "_model_name", None)
        if model_name:
            payload["model"] = model_name

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        choices = data.get("choices", [])
        if not choices:
            return None

        return choices[0].get("message", {})

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return None


async def _execute_tool_native(tool_name: str, tool_args: dict, memory_manager: Any) -> str:
    """Execute a tool and return the result."""
    import json
    from datetime import datetime, timezone

    try:
        if tool_name == "search_memory":
            query = tool_args.get("query", "")
            top_k = tool_args.get("top_k", 5)

            documents = await memory_manager.semantic_search(query, top_k=top_k)

            if not documents:
                return "NO RESULTS FOUND: Memory search returned no matching documents."

            results = [{"content": doc.content[:500], "metadata": doc.metadata_} for doc in documents]
            return json.dumps(results, indent=2)

        elif tool_name == "store_memory":
            content = tool_args.get("content", "")
            topic = tool_args.get("topic", "")
            sources_list = tool_args.get("sources", [])

            if any(phrase in content.lower() for phrase in ["no results", "error:", "status:"]):
                return "SKIPPED: Content appears to be meta/log data."

            metadata = {
                "topic": topic,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sources": sources_list,
            }

            doc_id = await memory_manager.store_document(content=content, metadata=metadata)
            return f"SUCCESS: Document stored with ID {doc_id}"

        elif tool_name == "web_search":
            return await _web_search_native(tool_args.get("query", ""), tool_args.get("max_results", 10))

        elif tool_name == "fetch_url":
            return await _fetch_url_native(tool_args.get("url", ""), tool_args.get("max_length", 8000))

        else:
            return f"ERROR: Unknown tool '{tool_name}'"

    except Exception as e:
        logger.error(f"Tool execution failed: {tool_name} - {e}")
        return f"ERROR: Tool '{tool_name}' failed: {str(e)}"


async def _web_search_native(query: str, max_results: int = 10) -> str:
    """Perform web search using DuckDuckGo."""
    try:
        from duckduckgo_search import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", r.get("link", "")),
                    "snippet": r.get("body", r.get("snippet", "")),
                })

        if not results:
            return "NO RESULTS FOUND: No search results for the given query."

        formatted = []
        for i, r in enumerate(results, 1):
            formatted.append(f"[{i}] {r['title']}\n    URL: {r['url']}\n    {r['snippet']}\n")

        return f"Found {len(results)} results for '{query}':\n\n" + "\n".join(formatted)

    except Exception as e:
        logger.error(f"Web search failed: {e}")
        return f"SEARCH ERROR: {str(e)}"


async def _fetch_url_native(url: str, max_length: int = 8000) -> str:
    """Fetch URL and convert to markdown."""
    import httpx
    import re

    if not url.startswith(("http://", "https://")):
        return f"ERROR: Invalid URL scheme. Got: {url[:50]}"

    try:
        timeout = httpx.Timeout(30.0, connect=10.0)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")

            if "text/html" not in content_type and "application/xhtml" not in content_type:
                if "application/json" in content_type:
                    return f"```json\n{response.text[:max_length]}\n```"
                elif "text/" in content_type:
                    return response.text[:max_length]
                else:
                    return f"ERROR: Cannot process content type: {content_type}"

            html = response.text

            # Try markdownify, fall back to basic stripping
            try:
                from markdownify import markdownify
                markdown = markdownify(html, heading_style="ATX", bullets="-",
                                       strip=["script", "style", "nav", "footer", "header", "aside"])
            except ImportError:
                # Basic HTML stripping
                markdown = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
                markdown = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
                markdown = re.sub(r"<[^>]+>", "", markdown)

            markdown = re.sub(r"\n{3,}", "\n\n", markdown)
            markdown = re.sub(r" {2,}", " ", markdown)
            markdown = markdown.strip()

            if len(markdown) > max_length:
                markdown = markdown[:max_length] + f"\n\n... [truncated, {len(markdown) - max_length} chars omitted]"

            return markdown

    except httpx.TimeoutException:
        return f"ERROR: Timeout fetching URL: {url[:100]}"
    except httpx.HTTPStatusError as e:
        return f"ERROR: HTTP {e.response.status_code} fetching URL: {url[:100]}"
    except Exception as e:
        return f"ERROR: Failed to fetch URL: {str(e)[:100]}"


async def _async_main_langgraph(
    topic: str,
    user_id: str,
    client_traceparent: str | None = None,
    max_researcher_runtime_seconds: int | None = None,
    max_iterations: int | None = None,
) -> dict[str, Any]:
    """Legacy LangGraph implementation with MCP tools."""
    logger.info("=" * 80)
    logger.info("STARTING RESEARCH WORKFLOW")
    logger.info(f"Topic: {topic}")
    logger.info(f"User ID: {user_id}")
    logger.info(f"Traceparent: {client_traceparent or 'None'}")
    logger.info("=" * 80)

    # Determine runtime budget (Windmill arg takes precedence, env override optional)
    env_runtime = os.environ.get("RUN_RESEARCHER_MAX_RUNTIME_SECONDS")
    runtime_budget = max_researcher_runtime_seconds
    if env_runtime:
        try:
            runtime_budget = int(env_runtime)
        except ValueError:
            logger.warning(
                "Invalid RUN_RESEARCHER_MAX_RUNTIME_SECONDS=%s; falling back to provided/default.",
                env_runtime,
            )
    if runtime_budget is None:
        runtime_budget = 60
    logger.info("ResearcherAgent runtime budget: %ss", runtime_budget)

    # Determine outer loop iteration budget (Windmill arg takes precedence, env override optional)
    env_iterations = os.environ.get("RUN_RESEARCH_MAX_ITERATIONS")
    iterations_budget = max_iterations
    if env_iterations:
        try:
            iterations_budget = int(env_iterations)
        except ValueError:
            logger.warning(
                "Invalid RUN_RESEARCH_MAX_ITERATIONS=%s; falling back to provided/default.",
                env_iterations,
            )
    if iterations_budget is None:
        iterations_budget = 5
    logger.info("Research graph iteration budget: %s (hard-capped at 5 by model validator)", iterations_budget)

    # Set progress for Windmill UI (percentage only - no message parameter)
    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(0)
            logger.info("Progress: 0%% - Starting research workflow")
        except Exception as e:
            logger.debug("Failed to set progress: %s", e)

    try:
        # Execute the research graph
        logger.info("PHASE 1: Initializing research graph")
        logger.info("- Creating database-backed memory manager")
        # Use real MemoryManager - connects to Postgres from PAIAS_DATABASE_URL env var
        # Note: PAIAS_DATABASE_URL must be set in docker-compose.yml WHITELIST_ENVS
        db_url = os.environ.get("PAIAS_DATABASE_URL") or settings.database_url
        logger.info(f"  Database URL: {db_url.split('@')[1] if '@' in db_url else 'default'}")  # Don't log credentials
        memory_mgr = MemoryManager()  # Will use PAIAS_DATABASE_URL from settings
        logger.info("- Configuring ResearcherAgent with MCP tools")
        app = compile_research_graph(
            memory_manager=memory_mgr,
            agent_runner=run_researcher_agent,
            max_researcher_runtime_seconds=runtime_budget,
        )

        logger.info("- Creating initial state")
        initial_state = ResearchState(
            topic=topic,
            user_id=user_id,
            max_iterations=iterations_budget,
        )
        logger.info(f"  Max iterations: {initial_state.max_iterations}")
        logger.info(f"  Quality threshold: {initial_state.quality_threshold}")

        if WMILL_AVAILABLE and wmill is not None:
            try:
                wmill.set_progress(10)
                logger.info("Progress: 10%% - Running research graph")
            except Exception as e:
                logger.debug("Failed to set progress: %s", e)

        logger.info("")
        logger.info("PHASE 2: Executing research graph")
        logger.info("- Starting LangGraph workflow (Plan → Research → Critique → Refine/Finish)")
        logger.info("  This may take several minutes depending on topic complexity...")

        final_state: ResearchState = await app.ainvoke(
            initial_state, traceparent=client_traceparent
        )
    except Exception as e:
        logger.error("")
        logger.error("=" * 80)
        logger.error("PHASE 2 FAILED: Error during research graph execution")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error("=" * 80)
        raise

    logger.info("")
    logger.info("PHASE 2 COMPLETE: Research graph execution finished")
    logger.info(f"- Status: {final_state.status.value}")
    logger.info(f"- Total iterations: {final_state.iteration_count}")
    logger.info(f"- Sources found: {len(final_state.sources)}")
    logger.info(f"- Quality score: {final_state.quality_score}")
    logger.info(f"- Planned actions: {len(final_state.planned_actions) if final_state.planned_actions else 0}")

    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(70)
            logger.info("Progress: 70%% - Formatting report")
        except Exception as e:
            logger.debug("Failed to set progress: %s", e)

    # Format the report
    logger.info("")
    logger.info("PHASE 3: Formatting research report")
    report = format_research_report(final_state)
    markdown = render_markdown(report)
    logger.info(f"- Report formatted (length: {len(markdown)} chars)")

    # Process planned actions with approval gating
    action_results: list[dict[str, Any]] = []
    approval_status: str | None = None

    if final_state.planned_actions:
        if WMILL_AVAILABLE and wmill is not None:
            try:
                wmill.set_progress(80)
                logger.info("Progress: 80%% - Processing planned actions")
            except Exception as e:
                logger.debug("Failed to set progress: %s", e)

        logger.info("")
        logger.info("PHASE 4: Processing planned actions")
        logger.info(f"- Found {len(final_state.planned_actions)} planned actions")

        action_results = await process_planned_actions(
            final_state.planned_actions,
            action_executor=_default_action_executor,
            suspend_for_approval=_windmill_suspend_for_approval,
        )

        statuses = [r.get("approval_status") for r in action_results]
        if "escalated" in statuses:
            approval_status = "escalated"
        elif "rejected" in statuses:
            approval_status = "rejected"
        elif all(s in ("approved", "not_required") for s in statuses):
            approval_status = "completed"
        else:
            approval_status = "partial"

        logger.info(f"- Actions processed: {len(action_results)}")
        logger.info(f"- Overall approval status: {approval_status}")
    else:
        logger.info("")
        logger.info("PHASE 4: No planned actions to process")

    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(100)
            logger.info("Progress: 100%% - Workflow completed")
        except Exception as e:
            logger.debug("Failed to set progress: %s", e)

    logger.info("")
    logger.info("=" * 80)
    logger.info("WORKFLOW COMPLETED SUCCESSFULLY")
    logger.info("=" * 80)

    return {
        "status": final_state.status.value,
        "mode": "langgraph",
        "iterations": final_state.iteration_count,
        "report": markdown,
        "sources": [src.model_dump() for src in report.sources],
        "memory_document_id": final_state.memory_document_id,
        "action_results": action_results,
        "approval_status": approval_status,
        "timed_out": final_state.timed_out,
    }


# Windmill script metadata
__windmill__ = {
    "description": "Execute deep research on a topic with mode selection",
    "summary": "Research Agent (Native or LangGraph)",
    "schema": {
        "properties": {
            "topic": {
                "type": "string",
                "description": "Research topic (1-500 characters)",
                "minLength": 1,
                "maxLength": 500,
            },
            "mode": {
                "type": "string",
                "description": "Execution mode: 'native' (fast, no MCP) or 'langgraph' (full workflow with MCP)",
                "enum": ["native", "langgraph"],
                "default": "native",
            },
            "user_id": {
                "type": "string",
                "description": "Optional user identifier (UUID string)",
            },
            "client_traceparent": {
                "type": "string",
                "description": "Optional W3C traceparent for distributed tracing (langgraph mode only)",
            },
            "max_researcher_runtime_seconds": {
                "type": "integer",
                "minimum": 10,
                "description": "Max runtime for researcher agent in seconds. Defaults to 60 (langgraph) or 120 (native).",
            },
            "max_iterations": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "description": "Max research iterations. Defaults to 5.",
            },
        },
        "required": ["topic"],
    },
}
