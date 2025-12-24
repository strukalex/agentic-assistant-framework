"""ResearcherAgent implementation using Pydantic AI with MCP tools.

Provides a research agent that can answer questions using web search,
time context, filesystem access, and memory integration.

Per Spec 002 tasks.md Phase 3 (FR-001 to FR-004, FR-024 to FR-026, FR-030, FR-031, FR-034)
"""

import asyncio
import logging
from typing import Any, Callable, List, Tuple
from uuid import UUID

from mcp import ClientSession
from pydantic_ai import Agent, RunContext

from src.core.llm import get_azure_model, parse_agent_result
from src.core.memory import MemoryManager
from src.core.telemetry import get_tracer, trace_tool_call
from src.core.tool_gap_detector import ToolGapDetector
from src.mcp_integration.setup import setup_mcp_tools
from src.models.agent_response import AgentResponse
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


def _create_researcher_agent() -> Agent[MemoryManager, AgentResponse]:
    """Create a fresh ResearcherAgent instance with base configuration."""
    return Agent[MemoryManager, AgentResponse](
        model=model,
        output_type=AgentResponse,
        retries=2,
        system_prompt="""You are the ResearcherAgent for a Personal AI Assistant System.

Your capabilities:
- Search external information sources via web search
- Access local filesystem (read-only)
- Query time/date context
- Store and retrieve from long-term memory

Your responsibilities:
- Always check memory before researching to avoid duplicate work
- Provide accurate, well-reasoned answers based on available tools
- Return structured responses with confidence scores
- Never hallucinate capabilities—acknowledge gaps honestly

Output Format: Always return a structured AgentResponse with:
- answer: The final answer to the user's query
- reasoning: Explanation of how you arrived at the answer, including tool usage
- tool_calls: List of all tool invocations made during execution
- confidence: Your self-assessed confidence score (0.0-1.0)
""",
    )


@trace_tool_call
async def search_memory(
    ctx: RunContext[MemoryManager], query: str
) -> List[dict]:
    """Search semantic memory for relevant past knowledge.

    Args:
        ctx: RunContext with MemoryManager dependency
        query: Search query string

    Returns:
        List of dictionaries with 'content' and 'metadata' keys

    Per tasks.md T105 (FR-024)
    """
    from src.core.config import settings

    try:
        # Preferred path per spec: pass raw query string
        documents = await ctx.deps.semantic_search(query, top_k=5)
    except Exception:
        # Fallback for backends that expect embeddings
        query_embedding = _generate_simple_embedding(query, settings.vector_dimension)
        documents = await ctx.deps.semantic_search(query_embedding, top_k=5)

    # Convert Document objects to dict format
    return [
        {"content": doc.content, "metadata": doc.metadata_}
        for doc in documents
    ]


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
    # Call MemoryManager.store_document
    doc_id: UUID = await ctx.deps.store_document(content=content, metadata=metadata)
    return str(doc_id)


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
    setattr(mcp_session, "_close_cm", mcp_session_cm)
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


def _make_mcp_tool(
    mcp_session: ClientSession, tool: Any
) -> Callable[..., Any]:
    """Create a tool wrapper that calls the given MCP tool via the session."""
    tool_name = getattr(tool, "name", "mcp_tool")
    description = getattr(tool, "description", "") or f"MCP tool {tool_name}"
    timeout_seconds = 10

    @trace_tool_call
    async def mcp_tool_wrapper(ctx: RunContext[MemoryManager], **kwargs: Any) -> str:
        try:
            result = await asyncio.wait_for(
                mcp_session.call_tool(tool_name, arguments=kwargs),
                timeout=timeout_seconds,
            )
            return _format_mcp_result(result)
        except asyncio.TimeoutError:
            return (
                f"Tool '{tool_name}' timed out after {timeout_seconds}s. "
                "Failing fast per configuration."
            )

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

    for tool in tools:
        agent.tool(
            _make_mcp_tool(mcp_session, tool),
            name=getattr(tool, "name", None),
            description=getattr(tool, "description", None),
        )

    logger.info("✅ Registered %d MCP tools with agent", len(tools))


# Wrapper function for instrumented agent.run() calls
# Per tasks.md T108 (FR-031), T210 (Tool Gap Detection Integration)
async def run_agent_with_tracing(
    agent: Agent[MemoryManager, AgentResponse],
    task: str,
    deps: MemoryManager,
    mcp_session: ClientSession = None,
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
                    logger.info("✅ All required tools available, proceeding with execution")
                    span.set_attribute("gap_detected", False)
            except Exception as e:
                # Log warning but proceed with execution
                # (Tool gap detection failure shouldn't block legitimate queries)
                logger.warning("⚠️ Tool gap detection failed: %s. Proceeding with execution.", str(e))
                span.set_attribute("gap_detection_error", str(e))

        # Phase 2: Execute agent.run()
        logger.info("🔄 Calling agent.run()...")
        result = await agent.run(task, deps=deps)
        logger.info("✅ agent.run() completed")
        logger.info(
            "agent.run result type=%s dict=%s repr=%r",
            type(result),
            getattr(result, "__dict__", {}),
            result,
        )

        # Normalize payload shape across pydantic-ai versions
        logger.info("🔍 Extracting payload from result...")
        payload = parse_agent_result(result)
        logger.info("✅ Payload extracted successfully")

        # Set result attributes
        span.set_attribute(
            "confidence_score", getattr(payload, "confidence", None)
        )
        span.set_attribute(
            "tool_calls_count", len(getattr(payload, "tool_calls", []))
        )

        logger.info("✅ Agent execution complete - confidence: %.2f, tool_calls: %d",
                   getattr(payload, "confidence", 0.0),
                   len(getattr(payload, "tool_calls", [])))

        return payload


async def run_researcher_agent(task: str, deps: MemoryManager) -> AgentResponse | ToolGapReport:
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

