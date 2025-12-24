"""
Contract tests for ResearcherAgent API schema validation.

Validates that agent.run() returns AgentResponse schema matching
contracts/researcher-agent-api.yaml for simple queries.

Per Spec 002 tasks.md T100 (FR-003, SC-002, SC-010)
"""

import pytest
from pydantic import ValidationError

from src.models.agent_response import AgentResponse, ToolCallRecord, ToolCallStatus
from src.models.tool_gap_report import ToolGapReport


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


class TestToolGapReportContract:
    """Validate ToolGapReport schema matches OpenAPI contract.

    Per Spec 002 tasks.md T200 (FR-009 to FR-014, SC-003)
    """

    def test_tool_gap_report_schema_valid(self):
        """Test that valid ToolGapReport passes validation."""
        report = ToolGapReport(
            missing_tools=["financial_data_api", "account_access"],
            attempted_task="Retrieve my stock portfolio performance for Q3 2024",
            existing_tools_checked=["web_search", "read_file", "get_current_time", "search_memory"],
        )

        # Validate all required fields are present
        assert len(report.missing_tools) == 2
        assert "financial_data_api" in report.missing_tools
        assert report.attempted_task == "Retrieve my stock portfolio performance for Q3 2024"
        assert len(report.existing_tools_checked) == 4

    def test_tool_gap_report_empty_missing_tools_invalid(self):
        """Test that empty missing_tools list fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ToolGapReport(
                missing_tools=[],  # Invalid: must have at least 1 item
                attempted_task="Some task",
                existing_tools_checked=["web_search"],
            )

        assert "missing_tools" in str(exc_info.value)

    def test_tool_gap_report_empty_attempted_task_invalid(self):
        """Test that empty attempted_task fails validation."""
        with pytest.raises(ValidationError) as exc_info:
            ToolGapReport(
                missing_tools=["financial_api"],
                attempted_task="",  # Invalid: empty string
                existing_tools_checked=["web_search"],
            )

        assert "attempted_task" in str(exc_info.value)

    def test_tool_gap_report_empty_existing_tools_allowed(self):
        """Test that empty existing_tools_checked is allowed (edge case: no tools available)."""
        report = ToolGapReport(
            missing_tools=["some_tool"],
            attempted_task="Some task requiring tools",
            existing_tools_checked=[],  # Valid: empty list allowed
        )

        assert len(report.existing_tools_checked) == 0

    def test_tool_gap_report_single_missing_tool(self):
        """Test ToolGapReport with single missing tool."""
        report = ToolGapReport(
            missing_tools=["database_query"],
            attempted_task="Query the database for user records",
            existing_tools_checked=["web_search", "read_file"],
        )

        assert len(report.missing_tools) == 1
        assert report.missing_tools[0] == "database_query"


class TestRiskAssessmentContract:
    """Validate risk assessment functions return correct types per OpenAPI contract.

    Per Spec 002 tasks.md T300 (FR-015 to FR-023)
    """

    def test_categorize_action_risk_returns_risk_level(self):
        """Test that categorize_action_risk() returns RiskLevel enum."""
        from src.core.risk_assessment import categorize_action_risk
        from src.models.risk_level import RiskLevel

        result = categorize_action_risk("web_search", {"query": "test"})
        assert isinstance(result, RiskLevel)
        assert result in [RiskLevel.REVERSIBLE, RiskLevel.REVERSIBLE_WITH_DELAY, RiskLevel.IRREVERSIBLE]

    def test_requires_approval_returns_boolean(self):
        """Test that requires_approval() returns boolean."""
        from src.core.risk_assessment import requires_approval
        from src.models.risk_level import RiskLevel

        result = requires_approval(RiskLevel.REVERSIBLE, confidence=0.95)
        assert isinstance(result, bool)

    def test_categorize_action_risk_with_various_tools(self):
        """Test categorize_action_risk with different tool types."""
        from src.core.risk_assessment import categorize_action_risk
        from src.models.risk_level import RiskLevel

        # Test REVERSIBLE tool
        reversible = categorize_action_risk("web_search", {})
        assert reversible == RiskLevel.REVERSIBLE

        # Test REVERSIBLE_WITH_DELAY tool
        reversible_delay = categorize_action_risk("send_email", {"to": "test@example.com"})
        assert reversible_delay == RiskLevel.REVERSIBLE_WITH_DELAY

        # Test IRREVERSIBLE tool
        irreversible = categorize_action_risk("delete_file", {"path": "/data/file.txt"})
        assert irreversible == RiskLevel.IRREVERSIBLE

    def test_requires_approval_with_all_risk_levels(self):
        """Test requires_approval with all risk levels."""
        from src.core.risk_assessment import requires_approval
        from src.models.risk_level import RiskLevel

        # REVERSIBLE should not require approval
        assert requires_approval(RiskLevel.REVERSIBLE, confidence=0.5) is False

        # REVERSIBLE_WITH_DELAY should require approval when confidence < 0.85
        assert requires_approval(RiskLevel.REVERSIBLE_WITH_DELAY, confidence=0.80) is True
        assert requires_approval(RiskLevel.REVERSIBLE_WITH_DELAY, confidence=0.90) is False

        # IRREVERSIBLE should always require approval
        assert requires_approval(RiskLevel.IRREVERSIBLE, confidence=1.0) is True
