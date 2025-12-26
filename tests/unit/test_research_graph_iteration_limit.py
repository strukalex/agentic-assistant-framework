import pytest
from uuid import uuid4

from paias.models.agent_response import AgentResponse
from paias.models.research_state import ResearchState, ResearchStatus
from paias.workflows.research_graph import InMemoryMemoryManager, compile_research_graph


async def _fake_runner(task: str, deps, *, max_runtime_seconds: float | None = None) -> AgentResponse:
    return AgentResponse(
        answer=f"result for {task}",
        reasoning="loop test",
        tool_calls=[],
        confidence=0.8,
    )


@pytest.mark.asyncio
async def test_iteration_cap_stops_at_five() -> None:
    app = compile_research_graph(
        memory_manager=InMemoryMemoryManager(),
        agent_runner=_fake_runner,
    )
    state = ResearchState(topic="caps", user_id=uuid4(), max_iterations=10)

    final_state: ResearchState = await app.ainvoke(state)

    assert final_state.iteration_count == 5
    assert final_state.status == ResearchStatus.FINISHED

