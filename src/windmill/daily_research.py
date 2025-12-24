from __future__ import annotations

from typing import Any, Dict

from src.workflows.report_formatter import format_research_report, render_markdown
from src.workflows.research_graph import InMemoryMemoryManager, compile_research_graph
from src.models.research_state import ResearchState


async def main(topic: str, user_id: str, client_traceparent: str | None = None) -> Dict[str, Any]:
    """
    Windmill entrypoint: execute the research graph and return report payload.
    """
    app = compile_research_graph(memory_manager=InMemoryMemoryManager())
    initial_state = ResearchState(topic=topic, user_id=user_id)
    final_state: ResearchState = await app.ainvoke(initial_state)

    report = format_research_report(final_state)
    markdown = render_markdown(report)

    return {
        "status": final_state.status.value,
        "iterations": final_state.iteration_count,
        "report": markdown,
        "sources": [src.model_dump() for src in report.sources],
        "memory_document_id": final_state.memory_document_id,
    }

