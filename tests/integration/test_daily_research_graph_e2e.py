import pytest
from uuid import uuid4

from paias.models.agent_response import AgentResponse, ToolCallRecord, ToolCallStatus
from paias.models.research_state import ResearchState, ResearchStatus
from paias.workflows.research_graph import InMemoryMemoryManager, compile_research_graph


async def _runner_with_sources(task: str, deps, *, max_runtime_seconds: float | None = None) -> AgentResponse:
    tool_call = ToolCallRecord(
        tool_name="web_search",
        parameters={"query": task},
        result=[
            {"title": "Source A", "url": "https://example.com/a", "snippet": "A"},
            {"title": "Source B", "url": "https://example.com/b", "snippet": "B"},
            {"title": "Source C", "url": "https://example.com/c", "snippet": "C"},
        ],
        duration_ms=5,
        status=ToolCallStatus.SUCCESS,
    )
    return AgentResponse(
        answer="Consolidated findings.",
        reasoning="Collected sufficient sources.",
        tool_calls=[tool_call],
        confidence=0.9,
    )


@pytest.mark.asyncio
async def test_graph_completes_and_stores_report() -> None:
    memory = InMemoryMemoryManager()
    app = compile_research_graph(memory_manager=memory, agent_runner=_runner_with_sources)
    state = ResearchState(topic="daily trends", user_id=uuid4())

    final_state: ResearchState = await app.ainvoke(state)

    assert final_state.status == ResearchStatus.FINISHED
    assert final_state.iteration_count == 1
    assert final_state.memory_document_id is not None
    assert memory.documents  # storage occurred

