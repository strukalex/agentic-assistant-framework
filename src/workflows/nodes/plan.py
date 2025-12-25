from __future__ import annotations

from ...core.telemetry import trace_langgraph_node
from ...models.research_state import ResearchState, ResearchStatus


@trace_langgraph_node("plan")
async def plan_node(state: ResearchState) -> ResearchState:
    """
    Generate an initial research plan from the topic.

    The plan is lightweight and focuses on collecting at least three sources
    before allowing the workflow to finish.
    """
    plan_text = state.plan or (
        f"Research plan for '{state.topic}': gather at least 3 credible sources, "
        f"summarize key findings, and iterate up to {state.max_iterations} times."
    )
    return state.model_copy(
        update={
            "plan": plan_text,
            "status": ResearchStatus.RESEARCHING,
        }
    )

