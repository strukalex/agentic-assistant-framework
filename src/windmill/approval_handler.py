"""Windmill approval handler for human-in-the-loop gating.

Implements approval gate functionality for REVERSIBLE_WITH_DELAY and IRREVERSIBLE
actions per FR-006 and FR-007, using Windmill's native suspend/resume mechanism.

Constitution compliance:
- Article II.C: Human-in-the-loop by default for risky operations
- Uses shared config from src/core/config.py per Article II.I

Timeout: 5 minutes ± 10 seconds (300s default per FR-007, SC-005)

Windmill Suspend/Resume API:
- https://www.windmill.dev/docs/flows/flow_approval
- wmill.suspend() blocks until resumed or timeout
- wmill.get_resume_urls() returns approval page URLs
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Awaitable

from ..core.config import settings
from ..models.approval_request import ApprovalRequest, ApprovalStatus, DecisionMetadata
from ..models.planned_action import PlannedAction
from ..models.risk_level import RiskLevel

logger = logging.getLogger(__name__)


def _get_wmill():
    """Lazy import of wmill to avoid import errors in non-Windmill environments."""
    try:
        import wmill
        return wmill
    except ImportError:
        return None


def get_resume_urls() -> dict[str, str]:
    """Get Windmill resume/cancel URLs for the current job.

    In actual Windmill execution, this calls wmill.get_resume_urls().
    For testing, this is mocked to return test URLs.

    Returns:
        Dict with 'resume', 'cancel', and optionally 'approvalPage' URLs.
        Note: Windmill uses 'approvalPage' (camelCase) not 'approval_page'.
    """
    wmill = _get_wmill()
    if wmill is not None:
        try:
            urls = wmill.get_resume_urls()
            logger.debug("Got resume URLs from Windmill: %s", list(urls.keys()))
            return urls
        except Exception as e:
            logger.warning("Failed to get resume URLs: %s", e)

    # Fallback for testing without wmill installed
    logger.warning("wmill not available; returning placeholder URLs")
    return {
        "resume": "http://localhost:8000/resume/placeholder",
        "cancel": "http://localhost:8000/cancel/placeholder",
        "approvalPage": "http://localhost:8000/approval/placeholder",
    }


def requires_approval(action: PlannedAction) -> bool:
    """Determine if an action requires human approval before execution.

    Per Constitution Article II.C and FR-006:
    - REVERSIBLE actions auto-execute (no approval needed)
    - REVERSIBLE_WITH_DELAY actions require approval
    - IRREVERSIBLE actions require approval

    Args:
        action: The planned action to evaluate.

    Returns:
        True if the action requires human approval, False otherwise.
    """
    return action.risk_level in (
        RiskLevel.REVERSIBLE_WITH_DELAY,
        RiskLevel.IRREVERSIBLE,
    )


def classify_actions(
    actions: list[PlannedAction],
) -> tuple[list[PlannedAction], list[PlannedAction]]:
    """Classify actions into auto-execute vs approval-required groups.

    Args:
        actions: List of planned actions to classify.

    Returns:
        Tuple of (auto_execute_actions, approval_required_actions).
    """
    auto_execute: list[PlannedAction] = []
    needs_approval: list[PlannedAction] = []

    for action in actions:
        if requires_approval(action):
            needs_approval.append(action)
        else:
            auto_execute.append(action)

    return auto_execute, needs_approval


async def request_approval(
    action: PlannedAction,
    timeout_seconds: int | None = None,
    requester_id: str | None = None,
) -> ApprovalRequest:
    """Request human approval for an action via Windmill suspend.

    Creates an ApprovalRequest and prepares the workflow to suspend
    until approval is granted, rejected, or times out.

    Args:
        action: The action requiring approval.
        timeout_seconds: Approval timeout in seconds (default from config: 300s).
        requester_id: Optional identifier for who requested the approval.

    Returns:
        ApprovalRequest with pending status and Windmill URLs.
    """
    if timeout_seconds is None:
        timeout_seconds = settings.approval_timeout_seconds

    now = datetime.now(timezone.utc)
    timeout_at = now + timedelta(seconds=timeout_seconds)

    urls = get_resume_urls()

    approval_request = ApprovalRequest(
        action_type=action.action_type,
        action_description=action.action_description,
        requester_id=requester_id,
        requested_at=now,
        timeout_at=timeout_at,
        status=ApprovalStatus.PENDING,
    )

    logger.info(
        "Approval requested for action '%s': %s (timeout: %ss)",
        action.action_type,
        action.action_description,
        timeout_seconds,
    )

    return approval_request


async def handle_approval_result(
    approval_request: ApprovalRequest,
    resume_payload: dict[str, Any],
) -> ApprovalRequest:
    """Process the approval decision from Windmill resume.

    Handles three paths:
    1. Approved: Mark status as APPROVED with approver metadata
    2. Rejected: Mark status as REJECTED with rejector metadata
    3. Timeout: Mark status as ESCALATED (action will be skipped)

    Args:
        approval_request: The original approval request.
        resume_payload: Windmill resume payload with decision or error.

    Returns:
        Updated ApprovalRequest with final status and decision metadata.
    """
    # Handle timeout/error case first
    if "error" in resume_payload:
        error_type = resume_payload["error"]
        logger.warning(
            "Approval escalated for action '%s': %s",
            approval_request.action_type,
            error_type,
        )
        approval_request.status = ApprovalStatus.ESCALATED
        approval_request.decision_metadata = DecisionMetadata(
            reason=error_type,
        )
        return approval_request

    decision = resume_payload.get("decision", "").lower()

    if decision == "approve":
        approval_request.status = ApprovalStatus.APPROVED
        approval_request.decision_metadata = DecisionMetadata(
            approved_by=resume_payload.get("approver"),
            comment=resume_payload.get("comment"),
        )
        logger.info(
            "Action '%s' approved by %s",
            approval_request.action_type,
            resume_payload.get("approver", "unknown"),
        )

    elif decision == "reject":
        approval_request.status = ApprovalStatus.REJECTED
        approval_request.decision_metadata = DecisionMetadata(
            rejected_by=resume_payload.get("rejector"),
            comment=resume_payload.get("comment"),
        )
        logger.info(
            "Action '%s' rejected by %s: %s",
            approval_request.action_type,
            resume_payload.get("rejector", "unknown"),
            resume_payload.get("comment", "no reason given"),
        )

    else:
        # Unknown decision - treat as rejection for safety
        logger.warning(
            "Unknown approval decision '%s' for action '%s'; treating as rejection",
            decision,
            approval_request.action_type,
        )
        approval_request.status = ApprovalStatus.REJECTED
        approval_request.decision_metadata = DecisionMetadata(
            reason=f"unknown_decision: {decision}",
        )

    return approval_request


async def process_planned_actions(
    actions: list[PlannedAction],
    action_executor: Callable[[PlannedAction], Awaitable[dict[str, Any]]],
    suspend_for_approval: Callable[[ApprovalRequest], Awaitable[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Process a list of planned actions with approval gating.

    For each action:
    1. If REVERSIBLE: execute immediately
    2. If REVERSIBLE_WITH_DELAY or IRREVERSIBLE: request approval first

    On approval: execute the action
    On rejection or timeout: skip the action and log

    Args:
        actions: List of planned actions to process.
        action_executor: Async function to execute an approved action.
        suspend_for_approval: Async function to suspend and wait for approval.

    Returns:
        List of result dicts with execution status for each action.
    """
    results: list[dict[str, Any]] = []

    for action in actions:
        result: dict[str, Any] = {
            "action_type": action.action_type,
            "action_description": action.action_description,
            "risk_level": action.risk_level.value,
            "executed": False,
            "approval_status": None,
            "execution_result": None,
            "error": None,
        }

        try:
            if not requires_approval(action):
                # Auto-execute REVERSIBLE actions
                logger.debug(
                    "Auto-executing REVERSIBLE action: %s",
                    action.action_type,
                )
                execution_result = await action_executor(action)
                result["executed"] = True
                result["approval_status"] = "not_required"
                result["execution_result"] = execution_result

            else:
                # Request approval for risky actions
                approval_request = await request_approval(action)
                resume_payload = await suspend_for_approval(approval_request)
                final_approval = await handle_approval_result(
                    approval_request,
                    resume_payload,
                )

                result["approval_status"] = final_approval.status.value

                if final_approval.status == ApprovalStatus.APPROVED:
                    execution_result = await action_executor(action)
                    result["executed"] = True
                    result["execution_result"] = execution_result

                elif final_approval.status == ApprovalStatus.REJECTED:
                    logger.info(
                        "Skipping rejected action: %s",
                        action.action_type,
                    )
                    result["executed"] = False

                elif final_approval.status == ApprovalStatus.ESCALATED:
                    logger.warning(
                        "Skipping escalated (timed out) action: %s",
                        action.action_type,
                    )
                    result["executed"] = False

        except Exception as exc:
            logger.exception(
                "Error processing action '%s': %s",
                action.action_type,
                exc,
            )
            result["error"] = str(exc)

        results.append(result)

    return results


def suspend_for_approval(
    action_type: str,
    action_description: str,
    timeout_seconds: int | None = None,
) -> dict[str, Any]:
    """Suspend the current Windmill job for approval.

    This is the actual suspension mechanism using wmill.suspend().
    It blocks the script execution until the job is resumed or times out.

    Args:
        action_type: Type of action requiring approval.
        action_description: Human-readable description of the action.
        timeout_seconds: Timeout in seconds (default from settings).

    Returns:
        Resume payload with 'decision' field and optional metadata.
    """
    wmill = _get_wmill()
    if wmill is None:
        logger.warning("wmill not available; auto-approving for testing")
        return {
            "decision": "approve",
            "approver": "test-auto-approval",
        }

    if timeout_seconds is None:
        timeout_seconds = settings.approval_timeout_seconds

    try:
        # wmill.suspend() is SYNCHRONOUS - it blocks until resumed or timeout
        # See: https://www.windmill.dev/docs/flows/flow_approval
        resume_payload = wmill.suspend(
            timeout=timedelta(seconds=timeout_seconds),
            default_args={"decision": "pending"},
            enums={"decision": ["approve", "reject"]},
            description=f"""
## Approval Required

**Action:** {action_type}

**Description:** {action_description}

Please select **approve** to execute this action or **reject** to skip it.

_This request will timeout in {timeout_seconds} seconds._
""",
        )

        logger.info(
            "Approval received for '%s': %s",
            action_type,
            resume_payload.get("decision", "unknown"),
        )

        return resume_payload

    except Exception as e:
        logger.warning("Approval request failed for '%s': %s", action_type, e)
        return {
            "decision": "reject",
            "error": str(e),
            "reason": "timeout_or_error",
        }


async def create_windmill_suspend_handler(
    approval_request: ApprovalRequest,
) -> dict[str, Any]:
    """Create a Windmill-compatible suspend handler for approval.

    This is an async wrapper around the synchronous suspend_for_approval.
    Used when integrating with our async approval processing pipeline.

    Args:
        approval_request: The approval request with action details.

    Returns:
        Resume payload with decision and metadata.
    """
    return suspend_for_approval(
        action_type=approval_request.action_type,
        action_description=approval_request.action_description,
        timeout_seconds=settings.approval_timeout_seconds,
    )
