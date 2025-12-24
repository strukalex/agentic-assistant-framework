"""ResearcherAgent implementation using Pydantic AI with MCP tools.

Provides a research agent that can answer questions using web search, time
context, filesystem access, and memory integration.

Per Spec 002 tasks.md Phase 3 (FR-001 to FR-004, FR-024 to FR-026, FR-030,
FR-031, FR-034)
"""

import asyncio
import contextvars
import json
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple
from uuid import UUID

from mcp import ClientSession
from pydantic import ValidationError
from pydantic_ai import Agent, RunContext

from src.core.config import settings
from src.core.llm import get_azure_model, parse_agent_result
from src.core.memory import MemoryManager
from src.core.risk_assessment import categorize_action_risk, requires_approval
from src.core.telemetry import get_tracer, trace_tool_call
from src.core.tool_gap_detector import ToolGapDetector
from src.mcp_integration.setup import setup_mcp_tools
from src.models.agent_response import (
    AgentResponse,
    ToolCallRecord,
    ToolCallStatus,
)
from src.models.tool_gap_report import ToolGapReport


def _generate_simple_embedding(query: str, dimension: int = 1536) -> List[float]:
    """Generate a simple embedding vector from query text.

    NOTE: This is a placeholder implementation for Phase 3 MVP.
    Proper embedding generation using an embedding model should be added
    in a later phase. This creates a hash-based embedding that allows
    the code to run but won't provide accurate semantic search results.

    Args:
        query: Query text
        dimension: Embedding dimension (default 1536)

    Returns:
        List of floats representing the embedding vector
    """
    # Simple hash-based approach for MVP
    # This is NOT production-ready - proper embedding model needed
    import hashlib

    hash_obj = hashlib.md5(query.encode())
    hash_int = int(hash_obj.hexdigest(), 16)

    # Create a deterministic vector from hash
    embedding = []
    for i in range(dimension):
        # Use hash to generate pseudo-random values between -1 and 1
        val = ((hash_int + i) % 2000) / 1000.0 - 1.0
        embedding.append(val)

    return embedding


model = get_azure_model()

# Limits and per-run state to prevent thrashing and to capture executed tools.
MAX_TOOL_CALLS_PER_RUN = 50
_tool_call_log: contextvars.ContextVar[
    Optional[List[ToolCallRecord]]
] = contextvars.ContextVar("tool_call_log", default=None)
_tool_result_cache: contextvars.ContextVar[
    Optional[Dict[str, Any]]
] = contextvars.ContextVar("tool_result_cache", default=None)


def _make_cache_key(tool_name: str, parameters: dict) -> str:
    """Create a stable cache key for a tool invocation."""
    try:
        normalized = json.dumps(parameters, sort_keys=True, default=str)
    except TypeError:
        normalized = str(sorted(parameters.items()))
    return f"{tool_name}:{normalized}"


def _get_tool_log() -> List[ToolCallRecord]:
    log = _tool_call_log.get()
    if log is None:
        log = []
        _tool_call_log.set(log)
    return log


def _get_tool_cache() -> Dict[str, Any]:
    cache = _tool_result_cache.get()
    if cache is None:
        cache = {}
        _tool_result_cache.set(cache)
    return cache


def _record_tool_call(
    tool_name: str,
    parameters: dict,
    result: Any,
    duration_ms: int,
    status: ToolCallStatus,
) -> None:
    _get_tool_log().append(
        ToolCallRecord(
            tool_name=tool_name,
            parameters=parameters,
            result=result,
            duration_ms=duration_ms,
            status=status,
        )
    )


async def _with_tool_logging_and_cache(
    tool_name: str, parameters: dict, func: Callable[[], Awaitable[Any]]
) -> Any:
    """Execute a tool with deduplication and logging to AgentResponse."""
    cache = _get_tool_cache()
    key = _make_cache_key(tool_name, parameters)
    start = time.perf_counter()

    if len(_get_tool_log()) >= MAX_TOOL_CALLS_PER_RUN:
        duration_ms = int((time.perf_counter() - start) * 1000)
        message = "Tool call budget exceeded for this run."
        _record_tool_call(
            tool_name=tool_name,
            parameters=parameters,
            result=message,
            duration_ms=duration_ms,
            status=ToolCallStatus.FAILED,
        )
        raise RuntimeError(message)

    if key in cache:
        cached_result = cache[key]
        duration_ms = int((time.perf_counter() - start) * 1000)
        _record_tool_call(
            tool_name=tool_name,
            parameters={**parameters, "_cached": True},
            result=cached_result,
            duration_ms=duration_ms,
            status=ToolCallStatus.SUCCESS,
        )
        return cached_result

    try:
        result = await func()
        duration_ms = int((time.perf_counter() - start) * 1000)
        cache[key] = result
        _record_tool_call(
            tool_name=tool_name,
            parameters=parameters,
            result=result,
            duration_ms=duration_ms,
            status=ToolCallStatus.SUCCESS,
        )
        return result
    except Exception as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        _record_tool_call(
            tool_name=tool_name,
            parameters=parameters,
            result=str(exc),
            duration_ms=duration_ms,
            status=ToolCallStatus.FAILED,
        )
        raise


def _create_researcher_agent() -> Agent[MemoryManager, AgentResponse]:
    """Create a fresh ResearcherAgent instance with base configuration."""
    return Agent[MemoryManager, AgentResponse](
        model=model,
        output_type=AgentResponse,
        retries=0,  # Changed from 2 to 0 to fail fast in tests - prevents hanging
        system_prompt="""You are the ResearcherAgent for a Personal AI Assistant System.

Your capabilities:
- Search external information sources via web search
- Access local filesystem (read-only)
- Query time/date context
- Store and retrieve from long-term memory

Your responsibilities and workflow (IMPORTANT - follow this order):

1. Always check memory FIRST. Before using expensive tools like web_search,
   always call search_memory() to see if you already have knowledge about this
   topic. This avoids duplicate work.

2. Use memory results when available. If search_memory() returns relevant past
   research, use that knowledge in your answer and cite the memory source in
   your reasoning (e.g., "Based on prior research stored on [date]...").

3. Research when needed. Only use web_search or other expensive tools when
   memory does not have the answer.

4. Store new findings. After synthesizing new research findings from
   web_search or other sources, always call store_memory() to persist this
   knowledge for future queries. Include metadata with:
   - topic: Brief topic description
   - timestamp: Current date/time from get_current_time()
   - sources: List of tools used (e.g., ["web_search"])

5. Provide accurate answers. Return structured responses with confidence scores
   based on source reliability.

6. Be honest about gaps. Never hallucinate capabilities—acknowledge gaps
   honestly.

Output Format: Always return a structured AgentResponse with:
- answer: The final answer to the user's query
- reasoning: Explanation of how you arrived at the answer, including:
  * Memory sources cited (if used): "Based on prior research from [date]..."
  * Tools used and why
  * How you synthesized the information
- tool_calls: List of all tool invocations made during execution
- confidence: Your self-assessed confidence score (0.0-1.0)

CRITICAL: Follow the workflow order above. Memory-first, then research, then
store findings.
""",
    )


@trace_tool_call
async def search_memory(ctx: RunContext[MemoryManager], query: str) -> List[dict]:
    """Search semantic memory for relevant past knowledge.

    Args:
        ctx: RunContext with MemoryManager dependency
        query: Search query string

    Returns:
        List of dictionaries with 'content' and 'metadata' keys

    Per tasks.md T105 (FR-024)
    """
    from src.core.config import settings

    params = {"query": query}

    async def _execute() -> List[dict]:
        try:
            # Preferred path per spec: pass raw query string
            documents = await ctx.deps.semantic_search(query, top_k=5)
        except Exception:
            # Fallback for backends that expect embeddings
            query_embedding = _generate_simple_embedding(
                query, settings.vector_dimension
            )
            documents = await ctx.deps.semantic_search(query_embedding, top_k=5)

        # Convert Document objects to dict format
        return [{"content": doc.content, "metadata": doc.metadata_} for doc in documents]

    return await _with_tool_logging_and_cache("search_memory", params, _execute)


@trace_tool_call
async def store_memory(
    ctx: RunContext[MemoryManager], content: str, metadata: dict
) -> str:
    """Store new research findings in memory.

    Args:
        ctx: RunContext with MemoryManager dependency
        content: Document content to store
        metadata: Document metadata dictionary

    Returns:
        Document ID as string

    Per tasks.md T106 (FR-025)
    """
    params = {"content_preview": content[:80], "metadata_keys": list(metadata.keys())}

    async def _execute() -> str:
        # Call MemoryManager.store_document
        doc_id: UUID = await ctx.deps.store_document(
            content=content, metadata=metadata
        )
        return str(doc_id)

    return await _with_tool_logging_and_cache("store_memory", params, _execute)


def _register_core_tools(agent: Agent[MemoryManager, AgentResponse]) -> None:
    """Attach built-in memory tools to the given agent."""
    agent.tool(search_memory)
    agent.tool(store_memory)


# Export a baseline agent for compatibility; MCP tools are added per session.
researcher_agent = _create_researcher_agent()
_register_core_tools(researcher_agent)


async def setup_researcher_agent(
    memory_manager: MemoryManager,
) -> Tuple[Agent[MemoryManager, AgentResponse], ClientSession]:
    """Initialize ResearcherAgent with MCP tools and return (agent, mcp_session).

    This matches the contract usage pattern in contracts/researcher-agent-api.yaml.
    The caller is responsible for closing the MCP session when finished.

    Per tasks.md T107 (FR-026, FR-034)
    """
    logger = logging.getLogger(__name__)
    logger.info("🤖 Setting up ResearcherAgent...")

    # Create a fresh agent instance so MCP tool wrappers are bound to this session.
    agent = _create_researcher_agent()
    _register_core_tools(agent)

    logger.info("🔧 Initializing MCP tools...")
    mcp_session_cm = setup_mcp_tools()
    mcp_session = await mcp_session_cm.__aenter__()
    logger.info("✅ MCP tools initialized")

    try:
        await _register_mcp_tools(agent, mcp_session, logger)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("⚠️ Failed to register MCP tools: %s", exc)

    # Attach context manager for optional cleanup by caller
    mcp_session._close_cm = mcp_session_cm  # type: ignore[attr-defined]
    logger.info("✅ ResearcherAgent setup complete")
    return agent, mcp_session


def _format_mcp_result(result: Any) -> str:
    """Normalize MCP tool results into a displayable string."""

    def _sanitize(text: str, max_len: int = 4000) -> str:
        # Drop control characters that can break JSON encoding and cap length
        import re

        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        if len(cleaned) > max_len:
            return cleaned[:max_len] + "... [truncated]"
        return cleaned

    content = getattr(result, "content", None)
    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            text = getattr(block, "text", None)
            parts.append(text if text is not None else str(block))
        return _sanitize("\n".join(parts))
    if content is None:
        return ""
    return _sanitize(str(content))


def _make_mcp_tool(mcp_session: ClientSession, tool: Any) -> Callable[..., Any]:
    """Create a tool wrapper that calls the given MCP tool via the session.

    Integrates risk assessment per tasks.md T308-T310 (FR-015 to FR-023).
    """
    tool_name = getattr(tool, "name", "mcp_tool")
    description = getattr(tool, "description", "") or f"MCP tool {tool_name}"
    timeout_seconds = settings.websearch_timeout
    logger = logging.getLogger(__name__)

    @trace_tool_call
    async def mcp_tool_wrapper(ctx: RunContext[MemoryManager], **kwargs: Any) -> str:
        # Log tool call initiation
        logger.info("🔧 [AGENTIC STEP] Tool call initiated: %s", tool_name)
        logger.debug("   Parameters: %s", kwargs)

        params = dict(kwargs)

        async def _execute() -> str:
            # T308: Integrate risk assessment before tool invocation
            risk_level = categorize_action_risk(tool_name, kwargs)

            # Get confidence from context if available (fallback to 1.0 for
            # high-confidence tools). In a full implementation, confidence would come
            # from the agent's inference. For now, use a conservative default that
            # doesn't block REVERSIBLE actions.
            confidence = 1.0  # Conservative: assume high confidence for auto-execution

            # T309: Implement approval check
            if requires_approval(risk_level, confidence):
                # Action requires human approval - return approval request message
                # In a full implementation, this would trigger an approval workflow
                logger.warning(
                    "⚠️ Action requires approval - tool: %s, risk: %s, confidence: %.2f",
                    tool_name,
                    risk_level.value,
                    confidence,
                )
                return (
                    "APPROVAL REQUIRED: Tool "
                    f"'{tool_name}' with risk level '{risk_level.value}' "
                    "requires human approval before execution. "
                    f"Parameters: {kwargs}"
                )

            # T310: Log auto-executed REVERSIBLE actions
            if risk_level.value == "reversible":
                logger.info(
                    "✅ Auto-executing REVERSIBLE action - tool: %s, parameters: %s",
                    tool_name,
                    kwargs,
                )

            # Execute the tool
            try:
                logger.debug("   [AGENTIC STEP] Executing MCP tool call...")
                result = await asyncio.wait_for(
                    mcp_session.call_tool(tool_name, arguments=kwargs),
                    timeout=timeout_seconds,
                )
                formatted_result = _format_mcp_result(result)

                # Log tool result (truncate if too long)
                result_preview = (
                    formatted_result[:200] + "..."
                    if len(formatted_result) > 200
                    else formatted_result
                )
                logger.info("✅ [AGENTIC STEP] Tool call completed: %s", tool_name)
                logger.debug("   Result preview: %s", result_preview)

                return formatted_result
            except asyncio.TimeoutError as exc:
                logger.error("⏱️ [AGENTIC STEP] Tool call timed out: %s", tool_name)
                raise TimeoutError(
                    f"Tool '{tool_name}' timed out after {timeout_seconds}s"
                ) from exc
            except Exception as exc:
                logger.error(
                    "❌ [AGENTIC STEP] Tool call failed: %s - %s", tool_name, exc
                )
                raise RuntimeError(
                    f"Tool '{tool_name}' failed during execution: {exc}"
                ) from exc

        return await _with_tool_logging_and_cache(tool_name, params, _execute)

    mcp_tool_wrapper.__name__ = tool_name
    mcp_tool_wrapper.__doc__ = description
    return mcp_tool_wrapper


async def _register_mcp_tools(
    agent: Agent[MemoryManager, AgentResponse],
    mcp_session: ClientSession,
    logger: logging.Logger,
) -> None:
    """Discover available MCP tools and register them on the agent."""
    tools_result = await mcp_session.list_tools()
    tools = getattr(tools_result, "tools", [])

    # Filter to only register the 'search' tool, exclude article fetchers
    excluded_tools = {
        "fetchLinuxDoArticle",
        "fetchCsdnArticle",
        "fetchGithubReadme",
        "fetchJuejinArticle",
    }
    
    registered_count = 0
    for tool in tools:
        tool_name = getattr(tool, "name", None)
        if tool_name in excluded_tools:
            logger.debug("⏭️  Skipping tool: %s", tool_name)
            continue
        
        agent.tool(  # type: ignore[call-overload]
            _make_mcp_tool(mcp_session, tool),
            name=tool_name,
            description=getattr(tool, "description", None),
        )
        registered_count += 1

    logger.info("✅ Registered %d MCP tools with agent", registered_count)


# Wrapper function for instrumented agent.run() calls
# Per tasks.md T108 (FR-031), T210 (Tool Gap Detection Integration)
async def run_agent_with_tracing(
    agent: Agent[MemoryManager, AgentResponse],
    task: str,
    deps: MemoryManager,
    mcp_session: Optional[ClientSession] = None,
) -> AgentResponse | ToolGapReport:
    """Execute agent.run() with OpenTelemetry tracing and tool gap detection.

    Creates span "agent_run" with attributes:
    - confidence_score: From result.confidence
    - tool_calls_count: From len(result.tool_calls)
    - task_description: From input query
    - result_type: "AgentResponse" or "ToolGapReport"

    Args:
        agent: ResearcherAgent instance
        task: User query/task description
        deps: MemoryManager dependency
        mcp_session: Optional MCP session for tool gap detection

    Returns:
        AgentResponse from agent execution, or ToolGapReport if missing tools detected

    Per tasks.md T108 (FR-031), T210 (FR-009 to FR-014)
    """
    logger = logging.getLogger(__name__)
    tracer = get_tracer("agent")

    logger.info("🚀 Starting agent execution for task: %s", task)
    with tracer.start_as_current_span("agent_run") as span:
        span.set_attribute("task_description", task)
        span.set_attribute("result_type", "AgentResponse")

        # Phase 1: Tool Gap Detection (if MCP session available)
        # Per tasks.md T210: Before executing task, check for missing capabilities
        if mcp_session is not None:
            logger.info("🔍 Checking for tool capability gaps...")
            detector = ToolGapDetector(mcp_session=mcp_session)

            try:
                gap_report = await detector.detect_missing_tools(task)
                if gap_report is not None:
                    logger.warning("⚠️ Tool gap detected: %s", gap_report.missing_tools)
                    span.set_attribute("result_type", "ToolGapReport")
                    span.set_attribute("gap_detected", True)
                    span.set_attribute("missing_tools", str(gap_report.missing_tools))

                    # Return gap report instead of attempting execution
                    # This prevents hallucinated responses when tools are missing
                    return gap_report
                else:
                    logger.info(
                        "✅ All required tools available, proceeding with execution"
                    )
                    span.set_attribute("gap_detected", False)
            except Exception as e:
                # Log warning but proceed with execution
                # (Tool gap detection failure shouldn't block legitimate queries)
                logger.warning(
                    "⚠️ Tool gap detection failed: %s. Proceeding with execution.",
                    str(e),
                )
                span.set_attribute("gap_detection_error", str(e))

        # Phase 2: Execute agent.run()
        logger.info("🔄 [AGENTIC LOOP] Starting agent.run()...")
        logger.info("   Task: %s", task)
        logger.info("   [AGENTIC LOOP] Agent will make LLM calls to reason and use tools")
        logger.info("   [AGENTIC LOOP] Each HTTP Request below is an LLM reasoning step")
        # Initialize per-run tool tracking
        tool_log_token = _tool_call_log.set([])
        tool_cache_token = _tool_result_cache.set({})
        try:
            result = await agent.run(task, deps=deps)
            logger.info("✅ [AGENTIC LOOP] agent.run() completed")
            logger.info(
                "   [AGENTIC LOOP] Result type=%s",
                type(result).__name__,
            )

            # Normalize payload shape across pydantic-ai versions
            logger.info("🔍 [AGENTIC LOOP] Extracting payload from result...")
            payload = parse_agent_result(result)
            logger.info("✅ [AGENTIC LOOP] Payload extracted successfully")
            # Override tool_calls with the authoritative log from wrappers
            wrapped_tool_calls = _get_tool_log()
            if hasattr(payload, "tool_calls"):
                payload.tool_calls = wrapped_tool_calls  # type: ignore[attr-defined]
            # Log agent's reasoning and tool calls
            if hasattr(payload, "reasoning"):
                logger.info("🧠 [AGENTIC LOOP] Agent reasoning: %s", payload.reasoning[:500] + "..." if len(payload.reasoning) > 500 else payload.reasoning)
            if wrapped_tool_calls:
                logger.info("🔧 [AGENTIC LOOP] Total tool calls made: %d", len(wrapped_tool_calls))
                for i, tool_call in enumerate(wrapped_tool_calls, 1):
                    logger.info("   [AGENTIC LOOP] Tool call %d: %s (%s) - %dms", 
                              i, tool_call.tool_name, tool_call.status.value, tool_call.duration_ms)
            if hasattr(payload, "confidence"):
                logger.info("📊 [AGENTIC LOOP] Agent confidence: %.2f", payload.confidence)
        except asyncio.TimeoutError as exc:
            # T603: Timeout handling for MCP tool calls
            message = (
                f"Tool execution timed out after {settings.websearch_timeout}s "
                "while processing the task."
            )
            logger.error("⏱️ %s", message)
            span.set_attribute("error_type", type(exc).__name__)
            span.set_attribute("error_message", message)
            span.record_exception(exc)
            return AgentResponse(
                answer="Tool execution timed out.",
                reasoning=message,
                tool_calls=_get_tool_log(),
                confidence=0.0,
            )
        except (
            json.JSONDecodeError,
            ValidationError,
            AttributeError,
            ValueError,
            TypeError,
        ) as exc:
            # T604: Malformed data handling for MCP tool responses
            message = (
                "Received malformed data from an MCP tool. "
                "Failed to parse or validate tool response."
            )
            logger.error("📄 %s Error: %s", message, exc)
            span.set_attribute("error_type", type(exc).__name__)
            span.set_attribute("error_message", str(exc))
            span.record_exception(exc)
            return AgentResponse(
                answer="Tool response could not be parsed.",
                reasoning=message,
                tool_calls=_get_tool_log(),
                confidence=0.0,
            )
        finally:
            # Reset contextvars to avoid cross-run leakage
            _tool_call_log.reset(tool_log_token)
            _tool_result_cache.reset(tool_cache_token)

        # Set result attributes
        confidence_val = getattr(payload, "confidence", None)
        span.set_attribute("confidence_score", float(confidence_val) if confidence_val is not None else 0.0)
        span.set_attribute(
            "tool_calls_count", len(getattr(payload, "tool_calls", []))
        )

        logger.info(
            "✅ Agent execution complete - confidence: %.2f, tool_calls: %d",
            getattr(payload, "confidence", 0.0),
            len(getattr(payload, "tool_calls", [])),
        )

        return payload  # type: ignore[return-value]


async def run_researcher_agent(
    task: str, deps: MemoryManager
) -> AgentResponse | ToolGapReport:
    """Convenience entrypoint: create agent with MCP tools, run it, then clean up."""
    agent, mcp_session = await setup_researcher_agent(deps)
    try:
        return await run_agent_with_tracing(agent, task, deps, mcp_session)
    finally:
        await _shutdown_session(mcp_session)


async def _shutdown_session(mcp_session: Any) -> None:
    """Close the MCP session if a context manager reference is attached."""
    close_cm = getattr(mcp_session, "_close_cm", None)
    if close_cm is not None:
        await close_cm.__aexit__(None, None, None)
