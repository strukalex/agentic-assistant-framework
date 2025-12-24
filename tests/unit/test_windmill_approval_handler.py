"""Unit tests for Windmill approval handler.

Tests the approval gate functionality with mocked `wmill` client covering:
- Approved path
- Rejected path
- Timed out (escalation) path
- 300-second timeout configuration
"""

from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.planned_action import PlannedAction
from src.models.risk_level import RiskLevel
from src.models.approval_request import ApprovalRequest, ApprovalStatus


class MockResumeUrls:
    """Mock response from wmill.get_resume_urls()."""

    def __init__(
        self,
        resume_url: str = "https://windmill.example.com/resume/abc123",
        cancel_url: str = "https://windmill.example.com/cancel/abc123",
        approval_page_url: str = "https://windmill.example.com/approval/abc123",
    ):
        self.resume = resume_url
        self.cancel = cancel_url
        self.approval_page = approval_page_url


class TestApprovalGateHelper:
    """Tests for the approval gate helper function."""

    @pytest.fixture
    def reversible_action(self) -> PlannedAction:
        """Action that does NOT require approval."""
        return PlannedAction(
            action_type="web_search",
            action_description="Search for AI governance articles",
            parameters={"query": "AI governance 2025"},
            risk_level=RiskLevel.REVERSIBLE,
        )

    @pytest.fixture
    def delay_action(self) -> PlannedAction:
        """Action that requires approval (REVERSIBLE_WITH_DELAY)."""
        return PlannedAction(
            action_type="send_email",
            action_description="Send research summary to team",
            parameters={"to": "team@example.com", "subject": "Research Summary"},
            risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
        )

    @pytest.fixture
    def irreversible_action(self) -> PlannedAction:
        """Action that requires approval (IRREVERSIBLE)."""
        return PlannedAction(
            action_type="delete_document",
            action_description="Delete outdated research report",
            parameters={"document_id": "doc-123"},
            risk_level=RiskLevel.IRREVERSIBLE,
        )


class TestRequiresApproval:
    """Tests for determining if an action requires approval."""

    def test_reversible_does_not_require_approval(self) -> None:
        """REVERSIBLE actions do not require human approval."""
        from src.windmill.approval_handler import requires_approval

        action = PlannedAction(
            action_type="web_search",
            action_description="Search query",
            parameters={},
            risk_level=RiskLevel.REVERSIBLE,
        )
        assert requires_approval(action) is False

    def test_reversible_with_delay_requires_approval(self) -> None:
        """REVERSIBLE_WITH_DELAY actions require human approval."""
        from src.windmill.approval_handler import requires_approval

        action = PlannedAction(
            action_type="send_email",
            action_description="Send email",
            parameters={},
            risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
        )
        assert requires_approval(action) is True

    def test_irreversible_requires_approval(self) -> None:
        """IRREVERSIBLE actions require human approval."""
        from src.windmill.approval_handler import requires_approval

        action = PlannedAction(
            action_type="delete_file",
            action_description="Delete file",
            parameters={},
            risk_level=RiskLevel.IRREVERSIBLE,
        )
        assert requires_approval(action) is True


class TestRequestApproval:
    """Tests for requesting approval from Windmill."""

    @pytest.mark.asyncio
    async def test_request_approval_creates_correct_structure(self) -> None:
        """request_approval returns ApprovalRequest with correct fields."""
        from src.windmill.approval_handler import request_approval

        action = PlannedAction(
            action_type="send_email",
            action_description="Send research summary",
            parameters={"to": "team@example.com"},
            risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
        )

        with patch("src.windmill.approval_handler.get_resume_urls") as mock_urls:
            mock_urls.return_value = {
                "resume": "https://windmill.example.com/resume/abc",
                "cancel": "https://windmill.example.com/cancel/abc",
                "approval_page": "https://windmill.example.com/approval/abc",
            }

            result = await request_approval(action, timeout_seconds=300)

        assert isinstance(result, ApprovalRequest)
        assert result.action_type == "send_email"
        assert result.action_description == "Send research summary"
        assert result.status == ApprovalStatus.PENDING
        # Timeout should be ~5 minutes from requested_at
        delta = (result.timeout_at - result.requested_at).total_seconds()
        assert 290 <= delta <= 310  # 5 minutes ± 10 seconds

    @pytest.mark.asyncio
    async def test_request_approval_uses_default_timeout(self) -> None:
        """request_approval uses 300 second default timeout."""
        from src.windmill.approval_handler import request_approval

        action = PlannedAction(
            action_type="send_email",
            action_description="Send email",
            parameters={},
            risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
        )

        with patch("src.windmill.approval_handler.get_resume_urls") as mock_urls:
            mock_urls.return_value = {
                "resume": "https://windmill.example.com/resume/abc",
                "cancel": "https://windmill.example.com/cancel/abc",
            }

            # No timeout_seconds provided - should use default
            result = await request_approval(action)

        delta = (result.timeout_at - result.requested_at).total_seconds()
        assert 290 <= delta <= 310  # Default 300 seconds


class TestHandleApprovalResult:
    """Tests for handling approval decisions (approved/rejected/timeout)."""

    @pytest.mark.asyncio
    async def test_approved_path_executes_action(self) -> None:
        """When approval is granted, action should be marked for execution."""
        from src.windmill.approval_handler import handle_approval_result

        approval_request = ApprovalRequest(
            action_type="send_email",
            action_description="Send summary",
        )

        resume_payload = {
            "decision": "approve",
            "approver": "user@example.com",
        }

        result = await handle_approval_result(approval_request, resume_payload)

        assert result.status == ApprovalStatus.APPROVED
        assert result.decision_metadata is not None
        assert result.decision_metadata.approved_by == "user@example.com"

    @pytest.mark.asyncio
    async def test_rejected_path_skips_action(self) -> None:
        """When approval is rejected, action should be skipped."""
        from src.windmill.approval_handler import handle_approval_result

        approval_request = ApprovalRequest(
            action_type="send_email",
            action_description="Send summary",
        )

        resume_payload = {
            "decision": "reject",
            "rejector": "admin@example.com",
            "comment": "Not needed right now",
        }

        result = await handle_approval_result(approval_request, resume_payload)

        assert result.status == ApprovalStatus.REJECTED
        assert result.decision_metadata is not None
        assert result.decision_metadata.rejected_by == "admin@example.com"
        assert result.decision_metadata.comment == "Not needed right now"

    @pytest.mark.asyncio
    async def test_timeout_path_escalates(self) -> None:
        """When approval times out, action should be escalated and skipped."""
        from src.windmill.approval_handler import handle_approval_result

        approval_request = ApprovalRequest(
            action_type="send_email",
            action_description="Send summary",
        )

        # Timeout indicated by error in payload
        resume_payload = {
            "error": "approval_timeout",
        }

        result = await handle_approval_result(approval_request, resume_payload)

        assert result.status == ApprovalStatus.ESCALATED
        assert result.decision_metadata is not None
        assert result.decision_metadata.reason == "approval_timeout"


class TestProcessPlannedActions:
    """Tests for processing a list of planned actions with approval gating."""

    @pytest.mark.asyncio
    async def test_reversible_actions_auto_execute(self) -> None:
        """REVERSIBLE actions execute automatically without approval."""
        from src.windmill.approval_handler import process_planned_actions

        actions = [
            PlannedAction(
                action_type="web_search",
                action_description="Search web",
                parameters={"query": "test"},
                risk_level=RiskLevel.REVERSIBLE,
            ),
        ]

        mock_executor = AsyncMock(return_value={"success": True})

        results = await process_planned_actions(
            actions,
            action_executor=mock_executor,
            suspend_for_approval=AsyncMock(),  # Should not be called
        )

        assert len(results) == 1
        assert results[0]["executed"] is True
        mock_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_delay_actions_suspend_for_approval(self) -> None:
        """REVERSIBLE_WITH_DELAY actions suspend for approval."""
        from src.windmill.approval_handler import process_planned_actions

        actions = [
            PlannedAction(
                action_type="send_email",
                action_description="Send email",
                parameters={"to": "test@example.com"},
                risk_level=RiskLevel.REVERSIBLE_WITH_DELAY,
            ),
        ]

        mock_executor = AsyncMock(return_value={"success": True})
        mock_suspend = AsyncMock(return_value={
            "decision": "approve",
            "approver": "user@example.com",
        })

        with patch("src.windmill.approval_handler.get_resume_urls") as mock_urls:
            mock_urls.return_value = {
                "resume": "https://windmill.example.com/resume/abc",
                "cancel": "https://windmill.example.com/cancel/abc",
            }

            results = await process_planned_actions(
                actions,
                action_executor=mock_executor,
                suspend_for_approval=mock_suspend,
            )

        assert len(results) == 1
        assert results[0]["executed"] is True
        assert results[0]["approval_status"] == "approved"
        mock_suspend.assert_called_once()
        mock_executor.assert_called_once()

    @pytest.mark.asyncio
    async def test_timeout_escalation_skips_action(self) -> None:
        """Timed out approvals escalate and skip the action."""
        from src.windmill.approval_handler import process_planned_actions

        actions = [
            PlannedAction(
                action_type="delete_file",
                action_description="Delete file",
                parameters={"file_id": "123"},
                risk_level=RiskLevel.IRREVERSIBLE,
            ),
        ]

        mock_executor = AsyncMock(return_value={"success": True})
        mock_suspend = AsyncMock(return_value={"error": "approval_timeout"})

        with patch("src.windmill.approval_handler.get_resume_urls") as mock_urls:
            mock_urls.return_value = {
                "resume": "https://windmill.example.com/resume/abc",
                "cancel": "https://windmill.example.com/cancel/abc",
            }

            results = await process_planned_actions(
                actions,
                action_executor=mock_executor,
                suspend_for_approval=mock_suspend,
            )

        assert len(results) == 1
        assert results[0]["executed"] is False
        assert results[0]["approval_status"] == "escalated"
        # Executor should NOT be called since approval timed out
        mock_executor.assert_not_called()


class TestApprovalTimeout:
    """Tests specific to the 300-second timeout requirement."""

    def test_approval_request_timeout_is_five_minutes(self) -> None:
        """ApprovalRequest enforces 5 minute ± 10 second timeout."""
        now = datetime.now(timezone.utc)

        # Valid: exactly 5 minutes
        request = ApprovalRequest(
            action_type="test",
            action_description="test",
            requested_at=now,
            timeout_at=now + timedelta(seconds=300),
        )
        assert request.timeout_at is not None

    def test_approval_request_rejects_invalid_timeout(self) -> None:
        """ApprovalRequest rejects timeouts outside 5 min ± 10 sec range."""
        now = datetime.now(timezone.utc)

        # Invalid: 10 minutes (too long)
        with pytest.raises(ValueError, match="5 minutes"):
            ApprovalRequest(
                action_type="test",
                action_description="test",
                requested_at=now,
                timeout_at=now + timedelta(seconds=600),
            )

    def test_approval_request_auto_sets_timeout(self) -> None:
        """ApprovalRequest auto-sets timeout to 5 minutes if not provided."""
        request = ApprovalRequest(
            action_type="test",
            action_description="test",
        )

        delta = (request.timeout_at - request.requested_at).total_seconds()
        assert delta == 300  # Exactly 5 minutes
