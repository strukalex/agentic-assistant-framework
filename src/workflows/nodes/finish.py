from __future__ import annotations

from typing import Optional
from uuid import UUID

from src.core.memory import MemoryManager
from src.core.telemetry import trace_langgraph_node
from src.models.research_state import ResearchState, ResearchStatus
from src.workflows.report_formatter import format_research_report, render_markdown


@trace_langgraph_node("finish")
async def finish_node(
    state: ResearchState, *, memory_manager: Optional[MemoryManager] = None
) -> ResearchState:
    """
    Build the final report, store it in memory, and mark the workflow finished.
    """
    report = format_research_report(state)
    markdown = render_markdown(report)

    document_id: UUID | None = None
    if memory_manager is not None:
        try:
            document_id = await memory_manager.store_document(
                content=markdown,
                metadata={
                    "type": "research_report",
                    "topic": state.topic,
                    "user_id": str(state.user_id),
                    "sources": [{"title": s.title, "url": str(s.url)} for s in state.sources],
                    "iteration_count": state.iteration_count,
                },
            )
        except Exception:
            # Storage failure should not block returning the report; propagate via metadata
            document_id = None

    return state.model_copy(
        update={
            "status": ResearchStatus.FINISHED,
            "refined_answer": report.executive_summary,
            "report_markdown": markdown,
            "memory_document_id": str(document_id) if document_id else None,
        }
    )

