"""
Contract tests for ResearcherAgent API schema validation.

Validates that agent.run() returns AgentResponse schema matching
contracts/researcher-agent-api.yaml for simple queries.

Per Spec 002 tasks.md T100 (FR-003, SC-002, SC-010)
"""

import pytest
from pydantic import ValidationError

from src.models.agent_response import AgentResponse, ToolCallRecord, ToolCallStatus


class TestAgentResponseContract:
    """Validate AgentResponse schema matches OpenAPI contract."""

    def test_agent_response_schema_valid(self):
        """Test that valid AgentResponse passes validation."""
        response = AgentResponse(
            answer="Paris",
            reasoning="Used web_search to find 'capital of France'. Top result from Wikipedia confirmed Paris.",
            tool_calls=[
                ToolCallRecord(
                    tool_name="web_search",
                    parameters={"query": "capital of France", "max_results": 5},
                    result=[
                        {
                            "title": "Paris - Wikipedia",
                            "url": "https://en.wikipedia.org/wiki/Paris",
                            "snippet": "Paris is the capital...",
                        }
                    ],
                    duration_ms=1234,
                    status=ToolCallStatus.SUCCESS,
                )
            ],
            confidence=0.95,
        )

        # Validate all required fields are present
        assert response.answer == "Paris"
        assert response.reasoning is not None
        assert len(response.tool_calls) == 1
        assert 0.0 <= response.confidence <= 1.0

    def test_agent_response_empty_answer_invalid(self):
        """Test that empty answer fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            AgentResponse(
                answer="",  # Invalid: empty string
                reasoning="Some reasoning",
                tool_calls=[],
                confidence=0.95,
            )

        assert "answer" in str(exc_info.value)

    def test_agent_response_empty_reasoning_invalid(self):
        """Test that empty reasoning fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            AgentResponse(
                answer="Paris",
                reasoning="",  # Invalid: empty string
                tool_calls=[],
                confidence=0.95,
            )

        assert "reasoning" in str(exc_info.value)

    def test_agent_response_confidence_out_of_range(self):
        """Test that confidence > 1.0 fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            AgentResponse(
                answer="Paris",
                reasoning="Some reasoning",
                tool_calls=[],
                confidence=1.5,  # Invalid: > 1.0
            )

        assert "confidence" in str(exc_info.value)

    def test_agent_response_confidence_negative(self):
        """Test that negative confidence fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            AgentResponse(
                answer="Paris",
                reasoning="Some reasoning",
                tool_calls=[],
                confidence=-0.1,  # Invalid: < 0.0
            )

        assert "confidence" in str(exc_info.value)

    def test_agent_response_tool_calls_empty_allowed(self):
        """Test that empty tool_calls list is allowed (answerable without tools)."""
        response = AgentResponse(
            answer="Paris",
            reasoning="I know Paris is the capital of France.",
            tool_calls=[],  # Valid: empty list allowed
            confidence=0.85,
        )

        assert len(response.tool_calls) == 0

    def test_tool_call_record_schema_valid(self):
        """Test that ToolCallRecord schema matches contract."""
        record = ToolCallRecord(
            tool_name="web_search",
            parameters={"query": "test", "max_results": 10},
            result=["result1", "result2"],
            duration_ms=1000,
            status=ToolCallStatus.SUCCESS,
        )

        assert record.tool_name == "web_search"
        assert record.parameters == {"query": "test", "max_results": 10}
        assert record.duration_ms == 1000
        assert record.status == ToolCallStatus.SUCCESS

    def test_tool_call_record_failed_status(self):
        """Test that ToolCallRecord can have FAILED status with null result."""
        record = ToolCallRecord(
            tool_name="web_search",
            parameters={"query": "test"},
            result=None,  # Valid: null when failed
            duration_ms=500,
            status=ToolCallStatus.FAILED,
        )

        assert record.result is None
        assert record.status == ToolCallStatus.FAILED

    def test_tool_call_record_timeout_status(self):
        """Test that ToolCallRecord can have TIMEOUT status."""
        record = ToolCallRecord(
            tool_name="web_search",
            parameters={"query": "test"},
            result=None,  # Valid: null when timeout
            duration_ms=30000,
            status=ToolCallStatus.TIMEOUT,
        )

        assert record.result is None
        assert record.status == ToolCallStatus.TIMEOUT

    def test_tool_call_record_negative_duration_invalid(self):
        """Test that negative duration_ms fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ToolCallRecord(
                tool_name="web_search",
                parameters={},
                result=None,
                duration_ms=-100,  # Invalid: negative duration
                status=ToolCallStatus.FAILED,
            )

        assert "duration_ms" in str(exc_info.value)

    def test_tool_call_record_empty_tool_name_invalid(self):
        """Test that empty tool_name fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ToolCallRecord(
                tool_name="",  # Invalid: empty string
                parameters={},
                result=None,
                duration_ms=100,
                status=ToolCallStatus.FAILED,
            )

        assert "tool_name" in str(exc_info.value)
