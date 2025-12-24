import anyio
import httpx
from httpx import ASGITransport
from uuid import uuid4

from src.api.app import create_app
from src.api.routes import daily_trending_research as dtr
from src.workflows.research_graph import InMemoryMemoryManager, compile_research_graph
from src.windmill.daily_research import main as windmill_main
from src.models.research_state import ResearchState


def _reset_runs() -> None:
    dtr._RUNS.clear()


async def _wait_for_completion(client: httpx.AsyncClient, run_id: str, attempts: int = 10):
    for _ in range(attempts):
        resp = await client.get(
            f"/v1/research/workflows/daily-trending-research/runs/{run_id}"
        )
        data = resp.json()
        if data["status"] == "completed":
            return data
        await anyio.sleep(0.05)
    return data


async def test_daily_trending_research_api_flow() -> None:
    _reset_runs()
    app = create_app()
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        payload = {"topic": "daily trends", "user_id": str(uuid4())}
        create_resp = await client.post(
            "/v1/research/workflows/daily-trending-research/runs", json=payload
        )
        assert create_resp.status_code == 202
        run_id = create_resp.json()["run_id"]

        status_data = await _wait_for_completion(client, run_id)
        assert status_data["status"] == "completed"
        assert status_data["iterations_used"] <= 5

        report_resp = await client.get(
            f"/v1/research/workflows/daily-trending-research/runs/{run_id}/report"
        )
        assert report_resp.status_code == 200
        report_data = report_resp.json()
        assert "markdown" in report_data
        assert report_data["metadata"]["topic"] == payload["topic"]


async def test_windmill_entrypoint_returns_report() -> None:
    result = await windmill_main(topic="ai news", user_id=str(uuid4()))
    assert result["status"] == "finished"
    assert "report" in result
    assert isinstance(result.get("iterations"), int)


async def test_compile_graph_fallback_runner(monkeypatch) -> None:
    # Force fallback path to exercise non-LangGraph runner
    monkeypatch.setattr("src.workflows.research_graph.LANGGRAPH_AVAILABLE", False)
    app = compile_research_graph(memory_manager=InMemoryMemoryManager())
    state = await app.ainvoke(
        ResearchState(topic="fallback", user_id=uuid4())
    )
    assert state.topic == "fallback"
    assert state.status.name  # reachable

