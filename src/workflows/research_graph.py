from __future__ import annotations

from typing import Callable

from langgraph.graph import END, START, StateGraph

from src.models.research_state import ResearchState

NodeCallable = Callable[[ResearchState], ResearchState]


def _placeholder_node(name: str) -> NodeCallable:
    def _node(state: ResearchState) -> ResearchState:
        raise NotImplementedError(f"Node '{name}' is not implemented yet")

    _node.__name__ = f"{name}_node"
    return _node


def build_research_graph() -> StateGraph:
    """
    Build the DailyTrendingResearch LangGraph.

    Node implementations are placeholders until user story work lands.
    """
    graph = StateGraph(ResearchState)

    graph.add_node("plan", _placeholder_node("plan"))
    graph.add_node("research", _placeholder_node("research"))
    graph.add_node("critique", _placeholder_node("critique"))
    graph.add_node("refine", _placeholder_node("refine"))
    graph.add_node("finish", _placeholder_node("finish"))

    graph.add_edge(START, "plan")
    graph.add_edge("plan", "research")
    graph.add_edge("research", "critique")
    graph.add_conditional_edges(
        "critique",
        lambda state: "refine" if state.iteration_count < state.max_iterations else "finish",
        {"refine": "refine", "finish": "finish"},
    )
    graph.add_edge("refine", "research")
    graph.add_edge("finish", END)

    return graph


def compile_research_graph():
    """Compile the research graph into an executable app."""
    return build_research_graph().compile()

