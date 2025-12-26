from __future__ import annotations

import logging

from ...core.telemetry import trace_langgraph_node
from ...models.research_state import ResearchState, ResearchStatus

logger = logging.getLogger(__name__)


@trace_langgraph_node("plan")
async def plan_node(state: ResearchState) -> ResearchState:
    """
    Generate an initial research plan from the topic.

    The plan is lightweight and focuses on collecting at least three sources
    before allowing the workflow to finish.
    """
    logger.info("  → [plan_node] Generating research plan for topic: '%s'", state.topic)
    plan_text = state.plan or (
        f"Research plan for '{state.topic}': gather at least 3 credible sources, "
        f"summarize key findings, and iterate up to {state.max_iterations} times."
    )
    logger.info("  → [plan_node] Plan generated - max iterations: %d", state.max_iterations)
    return state.model_copy(
        update={
            "plan": plan_text,
            "status": ResearchStatus.RESEARCHING,
        }
    )

