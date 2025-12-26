"""Integration tests for Windmill approval flow.

These tests verify the end-to-end approval workflow including:
- Workflow suspension on approval-required actions
- Resume on approval
- Resume on rejection
- Timeout escalation path

NOTE: These tests are SKIPPED unless WINDMILL_* environment variables are set,
as they require a running Windmill instance.
"""

from __future__ import annotations

import os
import pytest
from typing import Any
from unittest.mock import AsyncMock, patch

from paias.models.planned_action import PlannedAction
from paias.models.risk_level import RiskLevel


# Skip all tests in this module unless Windmill is configured
pytestmark = pytest.mark.skipif(
    not os.environ.get("WINDMILL_BASE_URL"),
    reason="WINDMILL_BASE_URL not set; skipping Windmill integration tests",
)


@pytest.fixture
def windmill_config() -> dict[str, str]:
    """Load Windmill configuration from environment."""
    return {
        "base_url": os.environ.get("WINDMILL_BASE_URL", ""),
        "workspace": os.environ.get("WINDMILL_WORKSPACE", "default"),
        "token": os.environ.get("WINDMILL_TOKEN", ""),
    }


@pytest.fixture
def sample_delay_action() -> PlannedAction:
    """A REVERSIBLE_WITH_DELAY action that requires approval."""
    return PlannedAction(
        action_type="send_notification",
        action_description="Send notification to team channel",
        parameters={
            "channel": "general",
            "message": "Research report completed",
        },
        risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
    )


@pytest.fixture
def sample_irreversible_action() -> PlannedAction:
    """An IRREVERSIBLE action that requires approval."""
    return PlannedAction(
        action_type="archive_data",
        action_description="Archive old research data permanently",
        parameters={
            "data_id": "research-2024-001",
            "archive_type": "permanent",
        },
        risk_level=RiskLevel.IRREVERSIBLE,
    )


class TestWindmillApprovalSuspension:
    """Tests for Windmill workflow suspension on approval-required actions."""

    @pytest.mark.asyncio
    async def test_workflow_suspends_for_delay_action(
        self,
        windmill_config: dict[str, str],
        sample_delay_action: PlannedAction,
    ) -> None:
        """Workflow suspends when encountering REVERSIBLE_WITH_DELAY action."""
        from paias.windmill.approval_handler import request_approval

        with patch("paias.windmill.approval_handler.get_resume_urls") as mock_urls:
            mock_urls.return_value = {
                "resume": f"{windmill_config['base_url']}/resume/test-job-123",
                "cancel": f"{windmill_config['base_url']}/cancel/test-job-123",
                "approval_page": f"{windmill_config['base_url']}/approval/test-job-123",
            }

            approval_request = await request_approval(sample_delay_action)

            assert approval_request is not None
            assert approval_request.action_type == "send_notification"
            assert approval_request.status.value == "pending"

    @pytest.mark.asyncio
    async def test_workflow_suspends_for_irreversible_action(
        self,
        windmill_config: dict[str, str],
        sample_irreversible_action: PlannedAction,
    ) -> None:
        """Workflow suspends when encountering IRREVERSIBLE action."""
        from paias.windmill.approval_handler import request_approval

        with patch("paias.windmill.approval_handler.get_resume_urls") as mock_urls:
            mock_urls.return_value = {
                "resume": f"{windmill_config['base_url']}/resume/test-job-456",
                "cancel": f"{windmill_config['base_url']}/cancel/test-job-456",
                "approval_page": f"{windmill_config['base_url']}/approval/test-job-456",
            }

            approval_request = await request_approval(sample_irreversible_action)

            assert approval_request is not None
            assert approval_request.action_type == "archive_data"
            assert approval_request.status.value == "pending"


class TestWindmillApprovalResume:
    """Tests for resuming workflow after approval/rejection."""

    @pytest.mark.asyncio
    async def test_resume_on_approval(
        self,
        windmill_config: dict[str, str],
        sample_delay_action: PlannedAction,
    ) -> None:
        """Workflow resumes and executes action when approved."""
        from paias.windmill.approval_handler import (
            request_approval,
            handle_approval_result,
        )

        with patch("paias.windmill.approval_handler.get_resume_urls") as mock_urls:
            mock_urls.return_value = {
                "resume": f"{windmill_config['base_url']}/resume/test-job-789",
                "cancel": f"{windmill_config['base_url']}/cancel/test-job-789",
            }

            approval_request = await request_approval(sample_delay_action)

            # Simulate approval response
            resume_payload = {
                "decision": "approve",
                "approver": "test-approver@example.com",
            }

            result = await handle_approval_result(approval_request, resume_payload)

            assert result.status.value == "approved"
            assert result.decision_metadata is not None
            assert result.decision_metadata.approved_by == "test-approver@example.com"

    @pytest.mark.asyncio
    async def test_resume_on_rejection(
        self,
        windmill_config: dict[str, str],
        sample_delay_action: PlannedAction,
    ) -> None:
        """Workflow resumes and skips action when rejected."""
        from paias.windmill.approval_handler import (
            request_approval,
            handle_approval_result,
        )

        with patch("paias.windmill.approval_handler.get_resume_urls") as mock_urls:
            mock_urls.return_value = {
                "resume": f"{windmill_config['base_url']}/resume/test-job-abc",
                "cancel": f"{windmill_config['base_url']}/cancel/test-job-abc",
            }

            approval_request = await request_approval(sample_delay_action)

            # Simulate rejection response
            resume_payload = {
                "decision": "reject",
                "rejector": "test-rejector@example.com",
                "comment": "Not the right time for this action",
            }

            result = await handle_approval_result(approval_request, resume_payload)

            assert result.status.value == "rejected"
            assert result.decision_metadata is not None
            assert result.decision_metadata.rejected_by == "test-rejector@example.com"
            assert result.decision_metadata.comment == "Not the right time for this action"


class TestWindmillApprovalTimeout:
    """Tests for approval timeout and escalation."""

    @pytest.mark.asyncio
    async def test_timeout_escalation(
        self,
        windmill_config: dict[str, str],
        sample_delay_action: PlannedAction,
    ) -> None:
        """Workflow escalates when approval times out after 5 minutes."""
        from paias.windmill.approval_handler import (
            request_approval,
            handle_approval_result,
        )

        with patch("paias.windmill.approval_handler.get_resume_urls") as mock_urls:
            mock_urls.return_value = {
                "resume": f"{windmill_config['base_url']}/resume/test-job-timeout",
                "cancel": f"{windmill_config['base_url']}/cancel/test-job-timeout",
            }

            approval_request = await request_approval(sample_delay_action)

            # Verify timeout is configured for 5 minutes
            delta = (approval_request.timeout_at - approval_request.requested_at).total_seconds()
            assert 290 <= delta <= 310  # 5 minutes ± 10 seconds

            # Simulate timeout response
            resume_payload = {
                "error": "approval_timeout",
            }

            result = await handle_approval_result(approval_request, resume_payload)

            assert result.status.value == "escalated"
            assert result.decision_metadata is not None
            assert result.decision_metadata.reason == "approval_timeout"


class TestWindmillApprovalEndToEnd:
    """End-to-end tests for the complete approval flow."""

    @pytest.mark.asyncio
    async def test_full_approval_flow_with_execution(
        self,
        windmill_config: dict[str, str],
    ) -> None:
        """Test complete flow: action → suspend → approve → execute."""
        from paias.windmill.approval_handler import process_planned_actions

        actions = [
            PlannedAction(
                action_type="send_report",
                action_description="Send research report to stakeholders",
                parameters={"recipients": ["stakeholder@example.com"]},
                risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
            ),
        ]

        action_executed = False

        async def mock_executor(action: PlannedAction) -> dict[str, Any]:
            nonlocal action_executed
            action_executed = True
            return {"success": True, "sent_to": action.parameters.get("recipients")}

        async def mock_suspend(approval_request: Any) -> dict[str, Any]:
            # Simulate immediate approval
            return {
                "decision": "approve",
                "approver": "manager@example.com",
            }

        with patch("paias.windmill.approval_handler.get_resume_urls") as mock_urls:
            mock_urls.return_value = {
                "resume": f"{windmill_config['base_url']}/resume/e2e-test",
                "cancel": f"{windmill_config['base_url']}/cancel/e2e-test",
            }

            results = await process_planned_actions(
                actions,
                action_executor=mock_executor,
                suspend_for_approval=mock_suspend,
            )

        assert len(results) == 1
        assert results[0]["executed"] is True
        assert results[0]["approval_status"] == "approved"
        assert action_executed is True

    @pytest.mark.asyncio
    async def test_mixed_actions_approval_flow(
        self,
        windmill_config: dict[str, str],
    ) -> None:
        """Test flow with mix of auto-execute and approval-required actions."""
        from paias.windmill.approval_handler import process_planned_actions

        actions = [
            PlannedAction(
                action_type="web_search",
                action_description="Search for related topics",
                parameters={"query": "AI governance"},
                risk_level=RiskLevel.REVERSIBLE,
            ),
            PlannedAction(
                action_type="send_email",
                action_description="Send summary email",
                parameters={"to": "user@example.com"},
                risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
            ),
        ]

        executed_actions: list[str] = []

        async def mock_executor(action: PlannedAction) -> dict[str, Any]:
            executed_actions.append(action.action_type)
            return {"success": True}

        async def mock_suspend(approval_request: Any) -> dict[str, Any]:
            return {"decision": "approve", "approver": "auto-test"}

        with patch("paias.windmill.approval_handler.get_resume_urls") as mock_urls:
            mock_urls.return_value = {
                "resume": f"{windmill_config['base_url']}/resume/mixed-test",
                "cancel": f"{windmill_config['base_url']}/cancel/mixed-test",
            }

            results = await process_planned_actions(
                actions,
                action_executor=mock_executor,
                suspend_for_approval=mock_suspend,
            )

        assert len(results) == 2
        assert all(r["executed"] for r in results)
        assert "web_search" in executed_actions
        assert "send_email" in executed_actions
