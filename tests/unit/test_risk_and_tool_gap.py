import pytest

from paias.core.risk_assessment import categorize_action_risk, requires_approval
from paias.models.risk_level import RiskLevel
from paias.models.tool_gap_report import ToolGapReport


def test_risk_level_enum_values():
    assert RiskLevel.REVERSIBLE.value == "reversible"
    assert RiskLevel.REVERSIBLE_WITH_DELAY.value == "reversible_with_delay"
    assert RiskLevel.IRREVERSIBLE.value == "irreversible"


def test_categorize_action_risk_mapping_and_sensitive_paths():
    assert categorize_action_risk("web_search", {}) == RiskLevel.REVERSIBLE
    assert categorize_action_risk("delete_file", {}) == RiskLevel.IRREVERSIBLE

    # Sensitive file paths escalate read_file to reversible_with_delay
    escalated = categorize_action_risk("read_file", {"path": "/etc/shadow"})
    assert escalated == RiskLevel.REVERSIBLE_WITH_DELAY

    # Unknown tools default to irreversible
    assert categorize_action_risk("unknown_tool", {}) == RiskLevel.IRREVERSIBLE


@pytest.mark.parametrize(
    "risk,confidence,expected",
    [
        (RiskLevel.IRREVERSIBLE, 0.5, True),
        (RiskLevel.REVERSIBLE_WITH_DELAY, 0.5, True),
        (RiskLevel.REVERSIBLE_WITH_DELAY, 0.95, False),
        (RiskLevel.REVERSIBLE, 0.1, False),
    ],
)
def test_requires_approval(risk, confidence, expected):
    assert requires_approval(risk, confidence) is expected


def test_tool_gap_report_validation_and_example():
    report = ToolGapReport(
        missing_tools=["financial_data_api"],
        attempted_task="Retrieve my stock portfolio performance for Q3 2024",
        existing_tools_checked=["web_search", "read_file"],
    )

    assert report.missing_tools == ["financial_data_api"]
    assert report.attempted_task.startswith("Retrieve my stock")
    assert "web_search" in report.existing_tools_checked

