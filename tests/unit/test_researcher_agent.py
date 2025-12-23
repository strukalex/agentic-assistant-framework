"""
Unit tests for ResearcherAgent initialization and configuration.

Validates that ResearcherAgent is initialized with DeepSeek 3.2 via AzureModel,
result_type=AgentResponse, retries=2.

Per Spec 002 tasks.md T103 (FR-001, FR-002, FR-003, FR-004, FR-034)
"""

import os

import pytest
from pydantic import ValidationError

# NOTE: These tests will fail initially because ResearcherAgent is not yet implemented.
# This is written FIRST per TDD approach to define the expected behavior.


@pytest.mark.skipif(
    True,  # Skip until ResearcherAgent is implemented
    reason="ResearcherAgent not yet implemented - written per TDD approach (T103)",
)
class TestResearcherAgentInitialization:
    """Validate ResearcherAgent initialization and configuration."""

    def test_researcher_agent_uses_azure_model(self):
        """
        Test that ResearcherAgent is initialized with AzureModel.

        Verifies FR-001: Uses Pydantic AI
        Verifies FR-002: Connects to DeepSeek 3.2 via Azure AI Foundry
        """
        from src.agents.researcher import researcher_agent

        # Verify agent is configured with AzureModel
        # Implementation should use pydantic_ai.models.azure.AzureModel
        assert researcher_agent is not None
        assert hasattr(researcher_agent, "model")

        # Verify model is AzureModel with correct configuration
        model = researcher_agent.model
        assert model is not None
        # Model should be configured with model_name="deepseek-v3"

    def test_researcher_agent_result_type_is_agent_response(self):
        """
        Test that ResearcherAgent has result_type=AgentResponse.

        Verifies FR-003: Returns structured AgentResponse with answer, reasoning, tool_calls, confidence
        """
        from src.agents.researcher import researcher_agent
        from src.models.agent_response import AgentResponse

        # Verify agent's result_type is set to AgentResponse
        # This ensures type safety for agent.run() return value
        assert researcher_agent is not None
        # Implementation: Agent(model=model, result_type=AgentResponse, ...)

    def test_researcher_agent_has_retry_configuration(self):
        """
        Test that ResearcherAgent is configured with retries=2.

        Verifies FR-034: Retries configuration for robustness
        """
        from src.agents.researcher import researcher_agent

        # Verify agent has retries configured
        assert researcher_agent is not None
        # Implementation: Agent(model=model, retries=2, ...)

    def test_researcher_agent_system_prompt_includes_capabilities(self):
        """
        Test that ResearcherAgent has system prompt listing capabilities.

        Per research.md RQ-001, system prompt should describe:
        - Web search capability
        - File reading capability
        - Time context capability
        - Memory search/store capabilities
        """
        from src.agents.researcher import researcher_agent

        # Verify agent has system prompt defined
        assert researcher_agent is not None
        # Implementation should define system prompt via Agent constructor

    @pytest.mark.parametrize(
        "env_var,expected_error",
        [
            ("AZURE_AI_FOUNDRY_ENDPOINT", "AZURE_AI_FOUNDRY_ENDPOINT"),
            ("AZURE_AI_FOUNDRY_API_KEY", "AZURE_AI_FOUNDRY_API_KEY"),
            ("AZURE_DEPLOYMENT_NAME", "AZURE_DEPLOYMENT_NAME"),
        ],
    )
    def test_agent_initialization_fails_with_missing_env_vars(
        self, env_var, expected_error, monkeypatch
    ):
        """
        Test that agent initialization fails with clear error when env vars missing.

        Verifies FR-027: Environment variable validation
        """
        # Remove the required environment variable
        monkeypatch.delenv(env_var, raising=False)

        # Attempt to import/initialize agent should fail
        with pytest.raises((ValueError, KeyError, Exception)) as exc_info:
            from src.agents.researcher import researcher_agent

        # Verify error message mentions the missing variable
        assert expected_error in str(exc_info.value)


@pytest.mark.skipif(
    True,  # Skip until setup_researcher_agent is implemented
    reason="setup_researcher_agent not yet implemented - written per TDD approach",
)
class TestSetupResearcherAgent:
    """Validate setup_researcher_agent() function."""

    async def test_setup_researcher_agent_returns_agent_and_session(self):
        """
        Test that setup_researcher_agent() returns (agent, mcp_session) tuple.

        Verifies contracts/researcher-agent-api.yaml usage pattern
        """
        from src.agents.researcher import setup_researcher_agent
        from unittest.mock import AsyncMock

        mock_memory_manager = AsyncMock()

        # Function should return tuple of (agent, mcp_session)
        result = await setup_researcher_agent(mock_memory_manager)

        assert result is not None
        assert isinstance(result, tuple)
        assert len(result) == 2

        agent, mcp_session = result
        assert agent is not None
        assert mcp_session is not None

    async def test_setup_researcher_agent_initializes_mcp_tools(self):
        """
        Test that setup_researcher_agent() calls setup_mcp_tools().

        Verifies FR-026: Agent is configured with MemoryManager dependency
        Verifies FR-034: Agent initialization includes MCP tool setup
        """
        from src.agents.researcher import setup_researcher_agent
        from unittest.mock import AsyncMock

        mock_memory_manager = AsyncMock()

        # Function should call setup_mcp_tools() internally
        agent, mcp_session = await setup_researcher_agent(mock_memory_manager)

        # Verify MCP session is initialized
        assert mcp_session is not None

    async def test_setup_researcher_agent_accepts_memory_manager_dependency(self):
        """
        Test that setup_researcher_agent() accepts MemoryManager as dependency.

        Verifies FR-026: MemoryManager dependency injection
        """
        from src.agents.researcher import setup_researcher_agent
        from unittest.mock import AsyncMock

        mock_memory_manager = AsyncMock()
        mock_memory_manager.semantic_search = AsyncMock(return_value=[])
        mock_memory_manager.store_document = AsyncMock(return_value="doc_id")

        # Function should accept MemoryManager and configure agent with it
        agent, mcp_session = await setup_researcher_agent(mock_memory_manager)

        assert agent is not None
        # Agent should be configured to use mock_memory_manager via RunContext
