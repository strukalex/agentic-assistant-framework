from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.common import AgentResponse, ApprovalRequest, RiskLevel, ToolGapReport


def test_risk_level_values() -> None:
    assert RiskLevel.REVERSIBLE.value == "reversible"
    assert RiskLevel.REVERSIBLE_WITH_DELAY.value == "reversible_with_delay"
    assert RiskLevel.IRREVERSIBLE.value == "irreversible"


def test_agent_response_requires_non_empty_answer() -> None:
    with pytest.raises(ValidationError):
        AgentResponse(answer="   ", confidence=0.5)


def test_agent_response_confidence_bounds() -> None:
    response = AgentResponse(answer="ok", confidence=1.0)
    assert response.confidence == 1.0

    with pytest.raises(ValidationError):
        AgentResponse(answer="ok", confidence=1.5)


def test_tool_gap_report_validates_attempted_task() -> None:
    report = ToolGapReport(
        missing_tools=["send_email"],
        attempted_task="deliver summary",
        existing_tools_checked=["filesystem"],
    )
    assert report.missing_tools == ["send_email"]

    with pytest.raises(ValidationError):
        ToolGapReport(
            missing_tools=["search"],
            attempted_task=" ",
            existing_tools_checked=[],
        )


def test_approval_request_confidence_and_risk_level() -> None:
    request = ApprovalRequest(
        action_type="send_email",
        action_description="Send report",
        confidence=0.8,
        risk_level=RiskLevel.REVERSIBLE,
        tool_name="mailer",
        parameters={"to": "user@example.com"},
        requires_immediate_approval=True,
    )
    assert request.risk_level is RiskLevel.REVERSIBLE

    with pytest.raises(ValidationError):
        ApprovalRequest(
            action_type="send_email",
            action_description="Send report",
            confidence=-0.1,
            risk_level=RiskLevel.IRREVERSIBLE,
            tool_name="mailer",
            parameters={"to": "user@example.com"},
            requires_immediate_approval=False,
        )

