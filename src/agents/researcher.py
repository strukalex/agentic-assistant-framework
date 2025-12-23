"""ResearcherAgent implementation using Pydantic AI with MCP tools.

Provides a research agent that can answer questions using web search,
time context, filesystem access, and memory integration.

Per Spec 002 tasks.md Phase 3 (FR-001 to FR-004, FR-024 to FR-026, FR-030, FR-031, FR-034)
"""

import os
from typing import List, Tuple
from uuid import UUID

from mcp import ClientSession
from pydantic_ai import Agent, RunContext

from src.core.memory import MemoryManager
from src.core.telemetry import get_tracer, trace_tool_call
from src.mcp_integration.setup import setup_mcp_tools
from src.models.agent_response import AgentResponse

# Try to import AzureModel, raise clear error if not available
try:
    from pydantic_ai.models.azure import AzureModel
except ImportError as e:
    raise ImportError(
        "pydantic-ai[azure] is required. Install with: pip install 'pydantic-ai[azure]'"
    ) from e


def _get_azure_model():
    """Create AzureModel instance with DeepSeek 3.2 configuration.

    Reads configuration from environment variables:
    - AZURE_AI_FOUNDRY_ENDPOINT: Azure AI Foundry endpoint URL
    - AZURE_AI_FOUNDRY_API_KEY: Azure AI Foundry API key

    Per research.md RQ-001 (FR-001, FR-002)
    """
    endpoint = os.getenv("AZURE_AI_FOUNDRY_ENDPOINT")
    api_key = os.getenv("AZURE_AI_FOUNDRY_API_KEY")

    if not endpoint:
        raise ValueError(
            "AZURE_AI_FOUNDRY_ENDPOINT environment variable is required"
        )
    if not api_key:
        raise ValueError(
            "AZURE_AI_FOUNDRY_API_KEY environment variable is required"
        )

    return AzureModel(
        model_name="deepseek-v3",
        endpoint=endpoint,
        api_key=api_key,
    )


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


# Initialize ResearcherAgent with AzureModel
# Per tasks.md T104 (FR-001, FR-002, FR-003, FR-004)
model = _get_azure_model()

researcher_agent = Agent[MemoryManager, AgentResponse](
    model=model,
    result_type=AgentResponse,
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
@researcher_agent.tool
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
@researcher_agent.tool
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


async def setup_researcher_agent(
    memory_manager: MemoryManager,
) -> Tuple[Agent[MemoryManager, AgentResponse], ClientSession]:
    """Initialize ResearcherAgent with MCP tools and return (agent, mcp_session).

    This matches the contract usage pattern in contracts/researcher-agent-api.yaml.
    The caller is responsible for closing the MCP session when finished.

    Per tasks.md T107 (FR-026, FR-034)
    """
    # Initialize MCP tools; keep session open for caller
    # Keep reference to suppress unused-argument warnings and future-proof DI
    _ = memory_manager

    mcp_session_cm = setup_mcp_tools()
    mcp_session = await mcp_session_cm.__aenter__()
    # Attach context manager for optional cleanup by caller
    setattr(mcp_session, "_close_cm", mcp_session_cm)
    return researcher_agent, mcp_session


# Wrapper function for instrumented agent.run() calls
# Per tasks.md T108 (FR-031)
async def run_agent_with_tracing(
    agent: Agent[MemoryManager, AgentResponse],
    task: str,
    deps: MemoryManager,
) -> AgentResponse:
    """Execute agent.run() with OpenTelemetry tracing.

    Creates span "agent_run" with attributes:
    - confidence_score: From result.confidence
    - tool_calls_count: From len(result.tool_calls)
    - task_description: From input query
    - result_type: "AgentResponse"

    Args:
        agent: ResearcherAgent instance
        task: User query/task description
        deps: MemoryManager dependency

    Returns:
        AgentResponse from agent execution

    Per tasks.md T108 (FR-031)
    """
    tracer = get_tracer("agent")

    with tracer.start_as_current_span("agent_run") as span:
        span.set_attribute("task_description", task)
        span.set_attribute("result_type", "AgentResponse")

        # Execute agent.run()
        result = await agent.run(task, deps=deps)

        # Set result attributes
        span.set_attribute("confidence_score", result.data.confidence)
        span.set_attribute("tool_calls_count", len(result.data.tool_calls))

        return result.data


async def run_researcher_agent(task: str, deps: MemoryManager) -> AgentResponse:
    """Convenience entrypoint to run the ResearcherAgent with tracing."""
    return await run_agent_with_tracing(researcher_agent, task, deps)

