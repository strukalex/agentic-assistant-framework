# ruff: noqa
import asyncio

import pytest

from src.agents.researcher import _make_mcp_tool, run_agent_with_tracing
from src.core.llm import get_azure_model
from src.models.agent_response import AgentResponse


class _DummyAgent:
    def __init__(self, run_impl):
        self._run_impl = run_impl

    async def run(self, task, deps=None):
        return await self._run_impl(task, deps)


@pytest.mark.asyncio
async def test_run_agent_with_tracing_handles_timeout():
    async def _raise_timeout(task, deps=None):
        raise asyncio.TimeoutError("simulated timeout")

    agent = _DummyAgent(_raise_timeout)
    response = await run_agent_with_tracing(agent, "test task", deps=object())

    assert isinstance(response, AgentResponse)
    assert response.confidence == 0.0
    assert "timed out" in response.reasoning.lower()


@pytest.mark.asyncio
async def test_run_agent_with_tracing_handles_malformed_data():
    class _BadResult:
        """Result object missing data/output attributes to trigger parsing failure."""

        pass

    async def _return_bad_result(task, deps=None):
        return _BadResult()

    agent = _DummyAgent(_return_bad_result)
    response = await run_agent_with_tracing(agent, "malformed task", deps=object())

    assert isinstance(response, AgentResponse)
    assert response.confidence == 0.0
    assert "malformed" in response.reasoning.lower()


@pytest.mark.asyncio
async def test_mcp_tool_wrapper_raises_timeout(monkeypatch):
    class _FakeSession:
        async def call_tool(self, tool_name, arguments):
            raise asyncio.TimeoutError("simulated tool timeout")

    tool = type("Tool", (), {"name": "web_search", "description": "search"})()
    wrapper = _make_mcp_tool(_FakeSession(), tool)

    with pytest.raises(TimeoutError) as exc:
        await wrapper(None, query="capital of france")

    assert "timed out" in str(exc.value)


@pytest.mark.parametrize(
    "missing_var",
    [
        "AZURE_AI_FOUNDRY_ENDPOINT",
        "AZURE_AI_FOUNDRY_API_KEY",
        "AZURE_DEPLOYMENT_NAME",
    ],
)
def test_get_azure_model_missing_env_vars(monkeypatch, missing_var):
    """Ensure clear errors when required Azure env vars are absent (T605a)."""
    for var in [
        "AZURE_AI_FOUNDRY_ENDPOINT",
        "AZURE_AI_FOUNDRY_API_KEY",
        "AZURE_DEPLOYMENT_NAME",
    ]:
        if var == missing_var:
            monkeypatch.setenv(var, "")
        else:
            monkeypatch.setenv(var, "placeholder")

    with pytest.raises(ValueError) as exc:
        get_azure_model()

    assert missing_var in str(exc.value)

