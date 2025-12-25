from __future__ import annotations

from ...core.telemetry import trace_langgraph_node
from ...models.research_state import ResearchState, ResearchStatus


@trace_langgraph_node("refine")
async def refine_node(state: ResearchState) -> ResearchState:
    """
    Adjust plan based on critique and prepare for another research iteration.
    """
    critique_note = state.critique or "No critique provided."
    updated_plan = (state.plan or "").strip()
    if updated_plan:
        updated_plan = f"{updated_plan}\nRefinement: {critique_note}"
    else:
        updated_plan = f"Refinement based on critique: {critique_note}"

    return state.model_copy(
        update={
            "plan": updated_plan,
            "status": ResearchStatus.RESEARCHING,
        }
    )

