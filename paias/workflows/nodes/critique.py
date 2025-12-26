from __future__ import annotations

import logging

from ...core.telemetry import trace_langgraph_node
from ...models.research_state import ResearchState, ResearchStatus

logger = logging.getLogger(__name__)


@trace_langgraph_node("critique")
async def critique_node(state: ResearchState) -> ResearchState:
    """
    Evaluate research quality and decide whether to continue refining.

    Heuristics (simple, test-friendly):
    - Require at least 3 sources to consider quality sufficient.
    - Use quality_score to decide finish vs refine when sources are available.
    """
    source_count = len(state.sources)
    has_enough_sources = source_count >= 3
    meets_quality = state.quality_score >= state.quality_threshold

    critique_lines = [
        f"Sources collected: {source_count}",
        f"Quality score: {state.quality_score:.2f} (threshold {state.quality_threshold:.2f})",
    ]

    if not has_enough_sources:
        critique_lines.append("Need more sources to meet minimum citation requirements.")
    elif not meets_quality:
        critique_lines.append("Quality below threshold; refine and improve answer.")
    else:
        critique_lines.append("Quality and source requirements satisfied.")

    next_status = (
        ResearchStatus.REFINING
        if (state.iteration_count < state.max_iterations) and (not has_enough_sources or not meets_quality)
        else ResearchStatus.FINISHED
    )

    decision = "REFINE" if next_status == ResearchStatus.REFINING else "FINISH"
    logger.info(
        "  → [critique_node] Sources: %d/3, Quality: %.2f/%.2f - Decision: %s",
        source_count,
        state.quality_score,
        state.quality_threshold,
        decision,
    )

    return state.model_copy(
        update={
            "critique": "\n".join(critique_lines),
            "status": next_status,
        }
    )

