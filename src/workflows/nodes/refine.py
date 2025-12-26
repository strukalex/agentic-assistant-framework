from __future__ import annotations

import logging

from ...core.telemetry import trace_langgraph_node
from ...models.research_state import ResearchState, ResearchStatus

logger = logging.getLogger(__name__)


@trace_langgraph_node("refine")
async def refine_node(state: ResearchState) -> ResearchState:
    """
    Adjust plan based on critique and prepare for another research iteration.
    """
    logger.info(
        "  → [refine_node] Refining research plan (iteration %d/%d)",
        state.iteration_count,
        state.max_iterations,
    )
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

