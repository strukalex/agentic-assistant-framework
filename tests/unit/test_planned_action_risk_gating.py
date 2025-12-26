"""Unit tests for PlannedAction risk gating logic.

Tests that actions are correctly classified by risk level:
- REVERSIBLE: auto-execute (no approval)
- REVERSIBLE_WITH_DELAY: require approval
- IRREVERSIBLE: require approval
"""

from __future__ import annotations

import pytest

from paias.models.planned_action import PlannedAction
from paias.models.risk_level import RiskLevel


class TestPlannedActionRiskLevel:
    """Tests for PlannedAction risk level field validation."""

    def test_reversible_action_creation(self) -> None:
        """REVERSIBLE action can be created with valid data."""
        action = PlannedAction(
            action_type="web_search",
            action_description="Search for articles",
            parameters={"query": "AI trends"},
            risk_level=RiskLevel.REVERSIBLE,
        )
        assert action.risk_level == RiskLevel.REVERSIBLE

    def test_reversible_with_delay_action_creation(self) -> None:
        """REVERSIBLE_WITH_DELAY action can be created with valid data."""
        action = PlannedAction(
            action_type="send_email",
            action_description="Send email to user",
            parameters={"to": "user@example.com", "subject": "Report"},
            risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
        )
        assert action.risk_level == RiskLevel.REVERSIBLE_WITH_DELAY

    def test_irreversible_action_creation(self) -> None:
        """IRREVERSIBLE action can be created with valid data."""
        action = PlannedAction(
            action_type="delete_file",
            action_description="Delete document permanently",
            parameters={"file_id": "doc-123"},
            risk_level=RiskLevel.IRREVERSIBLE,
        )
        assert action.risk_level == RiskLevel.IRREVERSIBLE


class TestRiskLevelGating:
    """Tests for the risk level gating logic (which actions require approval)."""

    @pytest.fixture
    def reversible_actions(self) -> list[PlannedAction]:
        """Actions that should NOT require approval."""
        return [
            PlannedAction(
                action_type="web_search",
                action_description="Search the web",
                parameters={"query": "test"},
                risk_level=RiskLevel.REVERSIBLE,
            ),
            PlannedAction(
                action_type="read_file",
                action_description="Read a file",
                parameters={"path": "/tmp/test.txt"},
                risk_level=RiskLevel.REVERSIBLE,
            ),
            PlannedAction(
                action_type="fetch_url",
                action_description="Fetch URL content",
                parameters={"url": "https://example.com"},
                risk_level=RiskLevel.REVERSIBLE,
            ),
        ]

    @pytest.fixture
    def approval_required_actions(self) -> list[PlannedAction]:
        """Actions that SHOULD require approval."""
        return [
            PlannedAction(
                action_type="send_email",
                action_description="Send email",
                parameters={"to": "user@example.com"},
                risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
            ),
            PlannedAction(
                action_type="schedule_meeting",
                action_description="Schedule a meeting",
                parameters={"attendees": ["a@ex.com"], "time": "2pm"},
                risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
            ),
            PlannedAction(
                action_type="delete_file",
                action_description="Delete file permanently",
                parameters={"file_id": "123"},
                risk_level=RiskLevel.IRREVERSIBLE,
            ),
            PlannedAction(
                action_type="make_purchase",
                action_description="Purchase item",
                parameters={"item_id": "abc", "amount": 99.99},
                risk_level=RiskLevel.IRREVERSIBLE,
            ),
        ]

    def test_reversible_actions_do_not_require_approval(
        self, reversible_actions: list[PlannedAction]
    ) -> None:
        """REVERSIBLE actions should auto-execute without approval."""
        from paias.windmill.approval_handler import requires_approval

        for action in reversible_actions:
            assert requires_approval(action) is False, (
                f"Expected {action.action_type} (REVERSIBLE) to NOT require approval"
            )

    def test_delay_and_irreversible_require_approval(
        self, approval_required_actions: list[PlannedAction]
    ) -> None:
        """REVERSIBLE_WITH_DELAY and IRREVERSIBLE actions require approval."""
        from paias.windmill.approval_handler import requires_approval

        for action in approval_required_actions:
            assert requires_approval(action) is True, (
                f"Expected {action.action_type} ({action.risk_level}) to require approval"
            )


class TestActionClassification:
    """Tests for classifying actions by risk level."""

    def test_classify_actions_by_risk(self) -> None:
        """Actions can be classified into approval-required and auto-execute groups."""
        from paias.windmill.approval_handler import classify_actions

        actions = [
            PlannedAction(
                action_type="search",
                action_description="Search",
                parameters={},
                risk_level=RiskLevel.REVERSIBLE,
            ),
            PlannedAction(
                action_type="email",
                action_description="Email",
                parameters={},
                risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
            ),
            PlannedAction(
                action_type="delete",
                action_description="Delete",
                parameters={},
                risk_level=RiskLevel.IRREVERSIBLE,
            ),
        ]

        auto_execute, needs_approval = classify_actions(actions)

        assert len(auto_execute) == 1
        assert auto_execute[0].action_type == "search"

        assert len(needs_approval) == 2
        assert {a.action_type for a in needs_approval} == {"email", "delete"}

    def test_empty_actions_list(self) -> None:
        """Empty actions list produces empty classifications."""
        from paias.windmill.approval_handler import classify_actions

        auto_execute, needs_approval = classify_actions([])

        assert auto_execute == []
        assert needs_approval == []

    def test_all_reversible_actions(self) -> None:
        """List with only REVERSIBLE actions has nothing needing approval."""
        from paias.windmill.approval_handler import classify_actions

        actions = [
            PlannedAction(
                action_type="search1",
                action_description="Search 1",
                parameters={},
                risk_level=RiskLevel.REVERSIBLE,
            ),
            PlannedAction(
                action_type="search2",
                action_description="Search 2",
                parameters={},
                risk_level=RiskLevel.REVERSIBLE,
            ),
        ]

        auto_execute, needs_approval = classify_actions(actions)

        assert len(auto_execute) == 2
        assert len(needs_approval) == 0

    def test_all_approval_required_actions(self) -> None:
        """List with only risky actions all need approval."""
        from paias.windmill.approval_handler import classify_actions

        actions = [
            PlannedAction(
                action_type="email",
                action_description="Email",
                parameters={},
                risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
            ),
            PlannedAction(
                action_type="delete",
                action_description="Delete",
                parameters={},
                risk_level=RiskLevel.IRREVERSIBLE,
            ),
        ]

        auto_execute, needs_approval = classify_actions(actions)

        assert len(auto_execute) == 0
        assert len(needs_approval) == 2


class TestRiskLevelEnumValues:
    """Tests for RiskLevel enum integrity."""

    def test_risk_level_values(self) -> None:
        """RiskLevel enum has expected values."""
        assert RiskLevel.REVERSIBLE.value == "reversible"
        assert RiskLevel.REVERSIBLE_WITH_DELAY.value == "reversible_with_delay"
        assert RiskLevel.IRREVERSIBLE.value == "irreversible"

    def test_risk_level_string_conversion(self) -> None:
        """RiskLevel enum converts to/from strings correctly."""
        assert RiskLevel("reversible") == RiskLevel.REVERSIBLE
        assert RiskLevel("reversible_with_delay") == RiskLevel.REVERSIBLE_WITH_DELAY
        assert RiskLevel("irreversible") == RiskLevel.IRREVERSIBLE

    def test_invalid_risk_level_raises(self) -> None:
        """Invalid risk level string raises ValueError."""
        with pytest.raises(ValueError):
            RiskLevel("unknown")


class TestPlannedActionValidation:
    """Tests for PlannedAction field validation."""

    def test_empty_action_type_rejected(self) -> None:
        """Empty action_type is rejected."""
        with pytest.raises(ValueError):
            PlannedAction(
                action_type="",
                action_description="Description",
                parameters={},
                risk_level=RiskLevel.REVERSIBLE,
            )

    def test_empty_description_rejected(self) -> None:
        """Empty action_description is rejected."""
        with pytest.raises(ValueError):
            PlannedAction(
                action_type="search",
                action_description="",
                parameters={},
                risk_level=RiskLevel.REVERSIBLE,
            )

    def test_whitespace_only_rejected(self) -> None:
        """Whitespace-only strings are rejected."""
        with pytest.raises(ValueError):
            PlannedAction(
                action_type="   ",
                action_description="Description",
                parameters={},
                risk_level=RiskLevel.REVERSIBLE,
            )

    def test_parameters_can_be_complex(self) -> None:
        """Parameters dict can contain nested structures."""
        action = PlannedAction(
            action_type="complex_action",
            action_description="Complex action",
            parameters={
                "nested": {"key": "value"},
                "list": [1, 2, 3],
                "mixed": {"items": [{"a": 1}]},
            },
            risk_level=RiskLevel.REVERSIBLE,
        )
        assert action.parameters["nested"]["key"] == "value"
        assert action.parameters["list"] == [1, 2, 3]
