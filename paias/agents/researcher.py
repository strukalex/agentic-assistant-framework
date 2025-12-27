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

from ..core.config import settings
from ..core.llm import get_azure_model, parse_agent_result
from ..core.memory import MemoryManager
from ..core.risk_assessment import categorize_action_risk, requires_approval
from ..core.telemetry import get_tracer, trace_tool_call
from ..core.tool_gap_detector import ToolGapDetector
from ..mcp_integration.setup import setup_mcp_tools
from ..models.agent_response import (
    AgentResponse,
    ToolCallRecord,
    ToolCallStatus,
)
from ..models.tool_gap_report import ToolGapReport


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


# Limits and per-run state to prevent thrashing and to capture executed tools.
MAX_TOOL_CALLS_PER_RUN = 50


class AgentRuntimeExceeded(RuntimeError):
    """Raised when the ResearcherAgent exceeds its allotted runtime budget."""


_tool_call_log: contextvars.ContextVar[
    Optional[List[ToolCallRecord]]
] = contextvars.ContextVar("tool_call_log", default=None)
_tool_result_cache: contextvars.ContextVar[
    Optional[Dict[str, Any]]
] = contextvars.ContextVar("tool_result_cache", default=None)
_web_search_seen: contextvars.ContextVar[
    Optional[set[str]]
] = contextvars.ContextVar("web_search_seen", default=None)
_stored_hashes: contextvars.ContextVar[
    Optional[set[str]]
] = contextvars.ContextVar("stored_hashes", default=None)
_answer_committed: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "answer_committed", default=False
)
_agent_deadline: contextvars.ContextVar[float | None] = contextvars.ContextVar(
    "agent_deadline", default=None
)
# Track if memory has been searched this run (to enforce single-attempt rule)
_memory_searched: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "memory_searched", default=False
)


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


def _get_web_search_seen() -> set[str]:
    seen = _web_search_seen.get()
    if seen is None:
        seen = set()
        _web_search_seen.set(seen)
    return seen


def _get_stored_hashes() -> set[str]:
    hashes = _stored_hashes.get()
    if hashes is None:
        hashes = set()
        _stored_hashes.set(hashes)
    return hashes


def _set_agent_deadline(seconds: float | None) -> contextvars.Token[float | None]:
    """Set the per-run deadline (monotonic timestamp) and return the context token."""
    deadline = time.monotonic() + seconds if seconds is not None else None
    return _agent_deadline.set(deadline)


def _check_agent_deadline(label: str = "agent step") -> None:
    """Raise if the configured runtime budget has been exceeded."""
    deadline = _agent_deadline.get()
    if deadline is None:
        return
    now = time.monotonic()
    if now >= deadline:
        raise AgentRuntimeExceeded(
            f"Time budget exceeded at {label} (deadline reached after {deadline:.2f}s, now {now:.2f}s)"
        )


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


class _TimedProviderWrapper:
    """Wrapper that checks the agent runtime budget around LLM calls."""

    def __init__(self, provider: Any):
        self._provider = provider

    def __getattr__(self, name: str) -> Any:
        return getattr(self._provider, name)

    async def run_chat(self, *args: Any, **kwargs: Any) -> Any:
        _check_agent_deadline("before llm")
        result = await self._provider.run_chat(*args, **kwargs)
        _check_agent_deadline("after llm")
        return result


def _reset_run_context() -> None:
    """Reset the per-run tool call log and cache. Used for testing and run initialization."""
    _tool_call_log.set([])
    _tool_result_cache.set({})
    _web_search_seen.set(set())
    _stored_hashes.set(set())
    _answer_committed.set(False)
    _memory_searched.set(False)


async def _with_tool_logging_and_cache(
    tool_name: str,
    parameters: dict,
    func: Callable[[], Awaitable[Any]],
    *,
    enable_cache: bool = True,
    loop_guard: bool = True,
    max_repeats: int = 3,
) -> Any:
    """Execute a tool with deduplication, loop-guarding, and logging.

    Args:
        tool_name: Name of the tool being invoked.
        parameters: Dict of parameters for the tool call.
        func: Async callable that performs the actual tool work.
        enable_cache: When False, skip read/write of the per-run cache. Use for
            dynamic tools (e.g., web_search) or side-effecting tools
            (e.g., store_memory).
        loop_guard: When True, detect repeated identical tool invocations within
            a run and halt after `max_repeats` to prevent thrashing.
        max_repeats: Maximum consecutive identical invocations allowed.
    """
    _check_agent_deadline(f"before tool {tool_name}")
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

    if loop_guard:
        # Detect consecutive identical tool calls (ignoring cached flag).
        normalized_params = _make_cache_key(tool_name, parameters)
        repeats = 0
        recent_tools = []
        for call in reversed(_get_tool_log()):
            call_params = dict(call.parameters)
            call_params.pop("_cached", None)
            recent_tools.append(f"{call.tool_name}({_make_cache_key(call.tool_name, call_params)})")
            if _make_cache_key(call.tool_name, call_params) != normalized_params:
                break
            repeats += 1
            if repeats >= max_repeats - 1:
                duration_ms = int((time.perf_counter() - start) * 1000)

                # Enhanced error message with call history
                logger = logging.getLogger(__name__)
                logger.error("🔄 [LOOP DETECTED] Tool '%s' called %d times consecutively", tool_name, max_repeats)
                logger.error("   Recent tool call sequence: %s", " → ".join(reversed(recent_tools[:10])))
                logger.error("   Parameters: %s", parameters)
                logger.error("   DIAGNOSIS: Agent is stuck in a loop. This usually means:")
                logger.error("     1. The agent isn't recognizing successful tool results")
                logger.error("     2. The agent's prompt may need clearer success/failure criteria")
                logger.error("     3. Results may be ambiguous (e.g., 'NO RESULTS FOUND' vs actual data)")

                message = (
                    f"Loop detected: identical tool call '{tool_name}' repeated "
                    f"{max_repeats} times consecutively. "
                    f"Recent sequence: {' → '.join(reversed(recent_tools[:5]))}. "
                    "Halting to avoid thrashing."
                )
                _record_tool_call(
                    tool_name=tool_name,
                    parameters={**parameters, "_cached": False},
                    result=message,
                    duration_ms=duration_ms,
                    status=ToolCallStatus.FAILED,
                )
                raise RuntimeError(message)

    if enable_cache and key in cache:
        cached_result = cache[key]
        duration_ms = int((time.perf_counter() - start) * 1000)
        _record_tool_call(
            tool_name=tool_name,
            parameters={**parameters, "_cached": True},
            result=cached_result,
            duration_ms=duration_ms,
            status=ToolCallStatus.SUCCESS,
        )
        _check_agent_deadline(f"after tool {tool_name} (cached)")
        return cached_result

    try:
        result = await func()
        _check_agent_deadline(f"after tool {tool_name}")
        duration_ms = int((time.perf_counter() - start) * 1000)
        if enable_cache:
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
    # Lazy initialization: create model only when agent is needed
    # This prevents import-time errors if environment variables aren't set yet
    model = get_azure_model()
    try:
        provider = getattr(model, "provider", None)
        if provider is not None:
            model.provider = _TimedProviderWrapper(provider)  # type: ignore[attr-defined]
    except Exception:
        # If the provider cannot be wrapped, proceed without timing guard; downstream
        # timeout checks will still apply at tool boundaries.
        pass
    return Agent[MemoryManager, AgentResponse](
        model=model,
        output_type=AgentResponse,
        retries=2,  # Allow LLM to auto-correct JSON/formatting errors
        system_prompt=f"""You are the ResearcherAgent for a Personal AI Assistant System.

Current date: {time.strftime("%Y-%m-%d")}. Treat earlier sources as valid historical facts.

Your capabilities:
- Search external information sources via web_search
- Fetch full page content from URLs via fetch_url (converts HTML to markdown)
- Access local filesystem (read-only)
- Query time/date context
- Store and retrieve from long-term memory

## Workflow

Before calling any tool, review the conversation history:
- Did you just call search_memory?
- Did it return "NO RESULTS FOUND"?
- If YES to both: Your ONLY valid action is web_search. Do not analyze. Just search.

1. Memory Check Protocol:
   Call search_memory() ONCE at the start.
   - IF it returns relevant information: Answer the user immediately using that info.
     Cite the memory source in your reasoning (e.g., "Based on prior research from [date]...").
   - IF it returns "NO RESULTS FOUND", empty results, or irrelevant data:
     STOP thinking about memory. IMMEDIATELY call web_search().

2. Web Search:
   When memory has no answer, use web_search to find information.
   Always pass the query parameter: web_search({{"query": "your search terms"}})

3. Fetch Full Content (optional):
   If web_search returns relevant URLs but snippets lack detail, use:
   fetch_url(url="https://...") to get full page content as markdown.

4. Store New Findings:
   After synthesizing new research from web_search or other sources,
   call store_memory() to persist knowledge for future queries.

   Include metadata:
   - topic: Brief topic description
   - timestamp: Current date/time from get_current_time()
   - sources: List of tools used (e.g., ["web_search"])

   ONLY store verified facts or synthesized answers. NEVER store queries,
   status updates, "no results" messages, or intermediate reasoning.

5. Provide Answer:
   Return a structured AgentResponse with:
   - answer: The final answer to the user's query
   - reasoning: How you arrived at the answer (memory sources, tools used, synthesis)
   - tool_calls: List of all tool invocations
   - confidence: Self-assessed confidence score (0.0-1.0)

## HARD CONSTRAINTS

1. SINGLE MEMORY ATTEMPT: You are allowed exactly ONE call to search_memory per user query.

2. FAILURE HANDLING: If search_memory returns "NO RESULTS FOUND", you are FORBIDDEN
   from calling it again. You must proceed directly to web_search.

3. NO LOOPING: If you see yourself making the same tool call twice in a row, STOP
   and try a different tool.

4. SEQUENTIAL EXECUTION: Run ONE STEP AT A TIME. Do not issue multiple parallel
   calls for search, memory, etc.

5. SEQUENTIAL STORAGE: Do NOT call store_memory in the same turn as web_search.
   Wait for search results to arrive before deciding what to store.

6. STOPPING CONDITION: Once you have stored the memory and answered the user,
   you must STOP. Do not loop.
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
    from ..core.config import settings
    logger = logging.getLogger(__name__)

    params = {"query": query}

    # Enhanced logging for memory search
    logger.info("🔍 [search_memory] Querying memory for: %s", query[:100])

    # GUARD: Enforce single memory search per run
    # This prevents the LLM from repeatedly calling search_memory when it should use web_search
    if _memory_searched.get():
        logger.warning("🚫 [search_memory] BLOCKED: Memory already searched this run. Use web_search instead.")
        return [{
            "content": "ERROR: search_memory can only be called ONCE per query. Memory was already searched. You MUST call web_search now.",
            "metadata": {"blocked": True, "reason": "single_attempt_rule"}
        }]

    # Mark memory as searched for this run
    _memory_searched.set(True)

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

        # Explicitly tell LLM to stop if no results found
        if not documents:
            logger.info("📭 [search_memory] No results found in memory")
            return [{
                "content": "Status: SUCCESS. Memory search complete. Step 1 of 2 finished. Proceed immediately to Step 2: Call web_search.",
                "metadata": {"memory_exhausted": True, "next_action": "web_search"}
            }]

        # Convert Document objects to dict format
        logger.info("✅ [search_memory] Found %d documents in memory", len(documents))
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

    # Guardrail: skip meta/log/no-result entries to avoid memory pollution
    lowered = content.lower()
    if any(
        phrase in lowered
        for phrase in [
            "no results found",
            "no_results",
            "initial query",
            "status:",
            "query:",
        ]
    ) or "status" in metadata or "query" in metadata:
        return (
            "SKIPPED: Not storing meta/log content. "
            "Only verified facts and synthesized answers are persisted."
        )

    # Guardrail: avoid duplicate storage of identical content in the same run
    content_hash = hash(content.strip())
    stored_hashes = _get_stored_hashes()
    if content_hash in stored_hashes:
        return "SKIPPED: Duplicate content already stored this run."

    async def _execute() -> str:
        # Call MemoryManager.store_document
        doc_id: UUID = await ctx.deps.store_document(
            content=content, metadata=metadata
        )
        stored_hashes.add(content_hash)
        _answer_committed.set(True)
        return str(doc_id)

    return await _with_tool_logging_and_cache(
        "store_memory",
        params,
        _execute,
        enable_cache=False,  # Side-effecting; never replay a cached store
    )


@trace_tool_call
async def fetch_url(ctx: RunContext[MemoryManager], url: str) -> str:
    """Fetch a URL and return its content as markdown.

    Use this tool to get the full content of a web page when search snippets
    aren't detailed enough. Converts HTML to clean markdown for easier reading.

    Args:
        ctx: RunContext with MemoryManager dependency
        url: The URL to fetch (must be http or https)

    Returns:
        Page content converted to markdown, or error message
    """
    import re

    import httpx
    from markdownify import markdownify

    logger = logging.getLogger(__name__)
    params = {"url": url}

    logger.info("🌐 [fetch_url] Fetching: %s", url[:100])

    async def _execute() -> str:
        # Validate URL
        if not url.startswith(("http://", "https://")):
            return f"ERROR: Invalid URL scheme. URL must start with http:// or https://. Got: {url[:50]}"

        try:
            timeout = httpx.Timeout(30.0, connect=10.0)
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; ResearcherAgent/1.0; +https://github.com/your-repo)",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
            }

            async with httpx.AsyncClient(
                timeout=timeout, follow_redirects=True, headers=headers
            ) as client:
                response = await client.get(url)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")

                # Handle non-HTML content
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    if "application/json" in content_type:
                        return f"```json\n{response.text[:settings.mcp_result_max_length]}\n```"
                    elif "text/" in content_type:
                        return response.text[: settings.mcp_result_max_length]
                    else:
                        return f"ERROR: Cannot process content type: {content_type}"

                html = response.text

                # Convert HTML to markdown
                markdown = markdownify(
                    html,
                    heading_style="ATX",
                    bullets="-",
                    strip=["script", "style", "nav", "footer", "header", "aside"],
                )

                # Clean up excessive whitespace
                markdown = re.sub(r"\n{3,}", "\n\n", markdown)
                markdown = re.sub(r" {2,}", " ", markdown)
                markdown = markdown.strip()

                # Truncate if too long
                max_len = settings.mcp_result_max_length
                if len(markdown) > max_len:
                    markdown = markdown[:max_len] + f"\n\n... [truncated, {len(markdown) - max_len} chars omitted]"

                logger.info("✅ [fetch_url] Retrieved %d chars from %s", len(markdown), url[:50])
                return markdown

        except httpx.TimeoutException:
            return f"ERROR: Timeout fetching URL after 30s: {url[:100]}"
        except httpx.HTTPStatusError as e:
            return f"ERROR: HTTP {e.response.status_code} fetching URL: {url[:100]}"
        except httpx.RequestError as e:
            return f"ERROR: Failed to fetch URL: {type(e).__name__}: {str(e)[:100]}"
        except Exception as e:
            logger.exception("Unexpected error in fetch_url")
            return f"ERROR: Unexpected error: {type(e).__name__}: {str(e)[:100]}"

    return await _with_tool_logging_and_cache(
        "fetch_url",
        params,
        _execute,
        enable_cache=True,  # Cache fetched pages within the same run
    )


def _register_core_tools(agent: Agent[MemoryManager, AgentResponse]) -> None:
    """Attach built-in memory and utility tools to the given agent."""
    agent.tool(search_memory)
    agent.tool(store_memory)
    agent.tool(fetch_url)


# Export a baseline agent for compatibility; MCP tools are added per session.
# Lazy initialization: only create when accessed to avoid import-time errors
_researcher_agent_instance: Optional[Agent[MemoryManager, AgentResponse]] = None


def _get_researcher_agent() -> Agent[MemoryManager, AgentResponse]:
    """Get or create the baseline researcher agent instance."""
    global _researcher_agent_instance
    if _researcher_agent_instance is None:
        _researcher_agent_instance = _create_researcher_agent()
        _register_core_tools(_researcher_agent_instance)
    return _researcher_agent_instance


# Module-level __getattr__ for lazy initialization
# This allows `from paias.agents.researcher import researcher_agent` to work
# without triggering model creation at import time
def __getattr__(name: str) -> Any:
    """Module-level __getattr__ for lazy initialization of researcher_agent."""
    if name == "researcher_agent":
        return _get_researcher_agent()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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

    def _sanitize(text: str, max_len: int | None = None) -> str:
        # Drop control characters that can break JSON encoding and cap length
        import re

        # Use configurable limit from settings, default 4000
        if max_len is None:
            max_len = settings.mcp_result_max_length

        cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
        if len(cleaned) > max_len:
            return cleaned[:max_len] + f"... [truncated, {len(cleaned) - max_len} chars omitted]"
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
    mcp_session: ClientSession, tool: Any, registered_name: str | None = None
) -> Callable[..., Any]:
    """Create a tool wrapper that calls the given MCP tool via the session.

    Integrates risk assessment per tasks.md T308-T310 (FR-015 to FR-023).

    Args:
        mcp_session: MCP client session for tool invocation
        tool: MCP tool object from server
        registered_name: Optional override name for the tool (used for renaming, e.g., 'search' -> 'web_search')
    """
    # Original MCP tool name (used for actual MCP calls)
    mcp_tool_name = getattr(tool, "name", "mcp_tool")
    # Registered name (used for logging, caching, and loop detection)
    tool_name = registered_name if registered_name is not None else mcp_tool_name

    description = getattr(tool, "description", "") or f"MCP tool {tool_name}"
    timeout_seconds = settings.websearch_timeout
    logger = logging.getLogger(__name__)

    @trace_tool_call
    async def mcp_tool_wrapper(ctx: RunContext[MemoryManager], **kwargs: Any) -> str:
        # Log tool call initiation with full context
        logger.info("🔧 [AGENTIC STEP] Tool call initiated: %s", tool_name)
        logger.info("   Parameters: %s", kwargs)
        logger.info("   Total tool calls so far: %d", len(_get_tool_log()))

        params = dict(kwargs)

        async def _execute() -> str:
            # Global stop: if answer already committed, skip further expensive calls
            if _answer_committed.get() and tool_name in {"web_search", "search_memory", "search"}:
                return "SKIPPED: Answer already committed; proceed to final_result."

            # Prevent duplicate web_search queries in the same run
            if tool_name in {"web_search", "search"}:
                query = str(kwargs.get("query", "")).strip().lower()
                seen = _get_web_search_seen()
                if query in seen:
                    return "SKIPPED: Duplicate web_search this run (cached result already available)."
                seen.add(query)

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
                logger.info("   [AGENTIC STEP] Executing MCP tool call...")
                # Use the original MCP tool name for the actual server call
                result = await asyncio.wait_for(
                    mcp_session.call_tool(mcp_tool_name, arguments=kwargs),
                    timeout=timeout_seconds,
                )
                formatted_result = _format_mcp_result(result)

                # Log tool result with enhanced visibility
                result_len = len(formatted_result)
                result_preview = (
                    formatted_result[:300] + f"... [{result_len - 300} more chars]"
                    if result_len > 300
                    else formatted_result
                )
                logger.info("✅ [AGENTIC STEP] Tool call completed: %s", tool_name)
                logger.info("   Result length: %d bytes", result_len)
                logger.info("   Result preview: %s", result_preview)

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

        return await _with_tool_logging_and_cache(
            tool_name,
            params,
            _execute,
            # Dynamic external tools should not be cached; others can opt in
            enable_cache=tool_name not in {"web_search", "search"},
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

        # Rename 'search' to 'web_search' for consistency with system prompt
        final_name = "web_search" if tool_name == "search" else tool_name

        # IMPORTANT: Pass final_name to the wrapper so it uses the renamed tool name
        # This ensures loop detection and caching work correctly
        agent.tool(  # type: ignore[call-overload]
            _make_mcp_tool(mcp_session, tool, registered_name=final_name),
            name=final_name,
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
    max_runtime_seconds: float | None = None,
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
        deadline_token = _set_agent_deadline(max_runtime_seconds)
        if max_runtime_seconds is not None:
            span.set_attribute("runtime_budget_seconds", float(max_runtime_seconds))
            logger.info("⏱️ Runtime budget set to %.1fs", float(max_runtime_seconds))

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
        web_search_token = _web_search_seen.set(set())
        stored_hashes_token = _stored_hashes.set(set())
        answer_committed_token = _answer_committed.set(False)
        memory_searched_token = _memory_searched.set(False)
        try:
            result = await agent.run(task, deps=deps)
            logger.info("✅ [AGENTIC LOOP] agent.run() completed")
            logger.info(
                "   [AGENTIC LOOP] Result type=%s",
                type(result).__name__,
            )
            _check_agent_deadline("after agent.run")

            # Normalize payload shape across pydantic-ai versions
            logger.info("🔍 [AGENTIC LOOP] Extracting payload from result...")
            payload = parse_agent_result(result)
            logger.info("✅ [AGENTIC LOOP] Payload extracted successfully")

            # Override tool_calls with the authoritative log from wrappers
            wrapped_tool_calls = _get_tool_log()
            if hasattr(payload, "tool_calls"):
                payload.tool_calls = wrapped_tool_calls  # type: ignore[attr-defined]

            # Enhanced logging for agent's final output
            logger.info("=" * 80)
            logger.info("AGENT EXECUTION SUMMARY")
            logger.info("=" * 80)
            logger.info("📝 Task: %s", task[:100])

            if hasattr(payload, "answer"):
                answer_preview = (
                    payload.answer[:200] + "..."
                    if len(payload.answer) > 200
                    else payload.answer
                )
                logger.info("💬 Answer: %s", answer_preview)

            if hasattr(payload, "reasoning"):
                reasoning_preview = (
                    payload.reasoning[:500] + "..."
                    if len(payload.reasoning) > 500
                    else payload.reasoning
                )
                logger.info("🧠 Reasoning: %s", reasoning_preview)

            if wrapped_tool_calls:
                logger.info("🔧 Total tool calls: %d", len(wrapped_tool_calls))
                for i, tool_call in enumerate(wrapped_tool_calls, 1):
                    status_emoji = "✅" if tool_call.status == ToolCallStatus.SUCCESS else "❌"
                    logger.info(
                        "   %s Call %d/%d: %s - %s (%dms)",
                        status_emoji, i, len(wrapped_tool_calls),
                        tool_call.tool_name, tool_call.status.value, tool_call.duration_ms
                    )
                    # Show tool parameters for debugging
                    logger.info("      Params: %s", tool_call.parameters)

            if hasattr(payload, "confidence"):
                logger.info("📊 Confidence: %.2f", payload.confidence)

            logger.info("=" * 80)
        except AgentRuntimeExceeded as exc:
            message = (
                "ResearcherAgent stopped after exceeding the runtime budget."
            )
            logger.warning("⏱️ %s Detail: %s", message, exc)
            span.set_attribute("error_type", type(exc).__name__)
            span.set_attribute("error_message", str(exc))
            span.record_exception(exc)
            return AgentResponse(
                answer="Timed out before completing research.",
                reasoning=message,
                tool_calls=_get_tool_log(),
                confidence=0.0,
            )
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
            _web_search_seen.reset(web_search_token)
            _stored_hashes.reset(stored_hashes_token)
            _answer_committed.reset(answer_committed_token)
            _memory_searched.reset(memory_searched_token)
            _agent_deadline.reset(deadline_token)

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
    task: str, deps: MemoryManager, *, max_runtime_seconds: float | None = None
) -> AgentResponse | ToolGapReport:
    """Convenience entrypoint: create agent with MCP tools, run it, then clean up."""
    agent, mcp_session = await setup_researcher_agent(deps)
    try:
        return await run_agent_with_tracing(
            agent,
            task,
            deps,
            mcp_session,
            max_runtime_seconds=max_runtime_seconds,
        )
    finally:
        await _shutdown_session(mcp_session)


async def _shutdown_session(mcp_session: Any) -> None:
    """Close the MCP session if a context manager reference is attached."""
    close_cm = getattr(mcp_session, "_close_cm", None)
    if close_cm is not None:
        await close_cm.__aexit__(None, None, None)
