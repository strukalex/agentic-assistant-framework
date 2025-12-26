from __future__ import annotations

import logging
from functools import partial
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID, uuid4

from langgraph.graph import END, START, StateGraph

from ..core.telemetry import trace_langgraph_execution_context
from ..models.research_state import ResearchState, ResearchStatus
from .nodes.critique import critique_node
from .nodes.finish import finish_node
from .nodes.plan import plan_node
from .nodes.refine import refine_node
from .nodes.research import research_node

logger = logging.getLogger(__name__)

NodeCallable = Callable[[ResearchState], Awaitable[ResearchState]]


class InMemoryMemoryManager:
    """
    Minimal async memory manager for tests and local execution.

    Stores documents in-memory and returns UUID identifiers without touching a database.
    """

    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}

    async def store_document(
        self, content: str, metadata: Optional[dict[str, Any]] = None, embedding: Any | None = None
    ) -> UUID:
        doc_id = uuid4()
        self.documents[str(doc_id)] = {"content": content, "metadata": metadata or {}}
        return doc_id


def _should_continue(state: ResearchState) -> str:
    """Decide whether to refine again or finish based on quality and iteration limits."""
    if state.status == ResearchStatus.FINISHED:
        return "finish"
    if state.iteration_count >= state.max_iterations:
        return "finish"
    if len(state.sources) < 3 or state.quality_score < state.quality_threshold:
        return "refine"
    return "finish"


def build_research_graph(
    *,
    memory_manager: Any | None = None,
    agent_runner: Callable[..., Awaitable[Any]] | None = None,
) -> StateGraph:
    """
    Build the DailyTrendingResearch LangGraph with real node implementations.

    Args:
        memory_manager: Optional memory manager passed to finish/research nodes.
        agent_runner: Optional research runner for dependency injection in tests.
    """
    graph = StateGraph(ResearchState)

    graph.add_node("plan", plan_node)
    graph.add_node(
        "research",
        partial(
            research_node,
            memory_manager=memory_manager,
            agent_runner=agent_runner,
        ),
    )
    graph.add_node("critique", critique_node)
    graph.add_node("refine", refine_node)
    graph.add_node("finish", partial(finish_node, memory_manager=memory_manager))

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "research")
    graph.add_edge("research", "critique")
    graph.add_conditional_edges(
        "critique",
        _should_continue,
        {"refine": "refine", "finish": "finish"},
    )
    graph.add_edge("refine", "research")
    graph.add_edge("finish", END)

    return graph


def compile_research_graph(
    *, memory_manager: Any | None = None, agent_runner: Callable[..., Awaitable[Any]] | None = None
):
    """Compile the research graph into an executable app."""
    graph = build_research_graph(memory_manager=memory_manager, agent_runner=agent_runner)
    return _LangGraphRunner(graph.compile())


class _LangGraphRunner:
    """Adapter to ensure LangGraph compiled apps return ResearchState."""

    def __init__(self, compiled_app: Any):
        self._app = compiled_app

    async def ainvoke(
        self, state: ResearchState, *, traceparent: Optional[str] = None
    ) -> ResearchState:
        logger.info("→ [LangGraph] Starting workflow execution")
        with trace_langgraph_execution_context(
            "daily_research",
            topic=str(state.topic),
            traceparent=traceparent,
        ) as span:
            result = await self._app.ainvoke(state)
            final_state = self._coerce(result)

            # Set final metrics on the span
            span.set_attribute("total_iterations", final_state.iteration_count)
            span.set_attribute("sources_count", len(final_state.sources))
            if final_state.quality_score is not None:
                span.set_attribute("quality_score", float(final_state.quality_score))

            logger.info("→ [LangGraph] Workflow execution complete")
            return final_state

    def invoke(
        self, state: ResearchState, *, traceparent: Optional[str] = None
    ) -> ResearchState:
        with trace_langgraph_execution_context(
            "daily_research",
            topic=str(state.topic),
            traceparent=traceparent,
        ) as span:
            result = self._app.invoke(state)
            final_state = self._coerce(result)

            # Set final metrics on the span
            span.set_attribute("total_iterations", final_state.iteration_count)
            span.set_attribute("sources_count", len(final_state.sources))
            if final_state.quality_score is not None:
                span.set_attribute("quality_score", float(final_state.quality_score))

            return final_state

    def _coerce(self, result: Any) -> ResearchState:
        if isinstance(result, ResearchState):
            return result
        if isinstance(result, dict):
            return ResearchState(**result)
        if hasattr(result, "model_dump"):
            try:
                return ResearchState(**result.model_dump())
            except Exception:
                pass
        raise TypeError(f"Unexpected result type from LangGraph runner: {type(result)}")

