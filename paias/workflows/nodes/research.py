from __future__ import annotations

import logging
from typing import Awaitable, Callable, Iterable

from uuid import uuid4

from ...agents.researcher import AgentRuntimeExceeded, run_researcher_agent
from ...core.memory import MemoryManager
from ...core.telemetry import trace_langgraph_node
from ...models.agent_response import AgentResponse, ToolCallRecord
from ...models.research_state import ResearchState, ResearchStatus
from ...models.source_reference import SourceReference

logger = logging.getLogger(__name__)


async def _default_agent_runner(task: str, deps: MemoryManager) -> AgentResponse:
    """
    Placeholder runner that raises an error if no real agent is provided.

    This ensures that production workflows fail fast rather than silently
    returning demo data when the agent runner is not wired up correctly.
    """
    raise NotImplementedError(
        "No agent_runner provided to compile_research_graph(). "
        "You must pass agent_runner=run_researcher_agent for production use. "
        "This is required to invoke the real Pydantic AI agent with MCP tools."
    )


class _NoopMemoryManager:
    """Minimal memory manager stub used when no dependency is provided."""

    async def store_document(self, content: str, metadata=None, embedding=None):
        return uuid4()


def _extract_sources(tool_calls: Iterable[ToolCallRecord]) -> list[SourceReference]:
    """Convert tool call results into SourceReference objects when possible."""
    sources: list[SourceReference] = []
    for call in tool_calls:
        result = call.result
        if not isinstance(result, list):
            continue
        for item in result:
            if not isinstance(item, dict):
                continue
            if {"title", "url", "snippet"}.issubset(item.keys()):
                try:
                    sources.append(SourceReference(**item))
                except Exception:
                    # Skip malformed items; validation happens in SourceReference
                    continue
    return sources


@trace_langgraph_node("research")
async def research_node(
    state: ResearchState,
    *,
    agent_runner: Callable[[str, MemoryManager], Awaitable[AgentResponse]]
    | None = None,
    memory_manager: MemoryManager | None = None,
    max_runtime_seconds: float | None = None,
) -> ResearchState:
    """
    Execute research using the provided agent runner and update state with findings.

    Args:
        state: Current ResearchState.
        agent_runner: Callable that executes research (defaults to run_researcher_agent).
        memory_manager: MemoryManager dependency passed to the agent runner.
    """
    logger.info(
        "  → [research_node] Starting research iteration %d/%d",
        state.iteration_count + 1,
        state.max_iterations,
    )
    logger.info("  → [research_node] Invoking Pydantic AI agent for topic: '%s'", state.topic)

    runner = agent_runner or _default_agent_runner
    deps = memory_manager if memory_manager is not None else _NoopMemoryManager()

    # Log which agent runner is being used for transparency
    runner_name = getattr(runner, "__name__", str(runner))
    logger.info("  → [research_node] Using agent_runner: %s", runner_name)

    try:
        result = await runner(
            f"Research topic: {state.topic}", deps=deps, max_runtime_seconds=max_runtime_seconds
        )  # type: ignore[arg-type]
    except AgentRuntimeExceeded as exc:
        logger.warning("  → [research_node] ResearcherAgent timed out: %s", exc)
        return state.model_copy(
            update={
                "status": ResearchStatus.FINISHED,
                "timed_out": True,
                "refined_answer": "Timed out before completing research.",
            }
        )
    quality_score = state.quality_score
    sources = _extract_sources(getattr(result, "tool_calls", []))

    # Calculate quality score from sources and confidence
    if sources:
        quality_score = max(quality_score, min(1.0, 0.3 * len(sources)))
    if hasattr(result, "confidence"):
        try:
            quality_score = max(quality_score, float(getattr(result, "confidence", 0.0)))
        except Exception:
            pass

    total_sources = len(state.sources) + len(sources)
    logger.info(
        "  → [research_node] Agent completed - found %d new sources (total: %d), confidence: %.2f",
        len(sources),
        total_sources,
        quality_score,
    )

    return state.model_copy(
        update={
            "sources": state.sources + sources,
            "refined_answer": result.answer,
            "iteration_count": state.iteration_count + 1,
            "status": ResearchStatus.CRITIQUING,
            "quality_score": quality_score,
        }
    )

