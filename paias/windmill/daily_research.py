"""Windmill workflow script for DailyTrendingResearch.

This is the main Windmill entrypoint for the research workflow. When deployed
to Windmill, this script is executed as a flow step.

Constitution compliance:
- Article I.B: Windmill for DAG orchestration, LangGraph for cyclical reasoning
- Article II.C: Human-in-the-loop via wmill.suspend() for approval gates
- Article II.H: Unified telemetry via src/core/telemetry.py

Deployment:
1. Register this script in Windmill under a path like 'f/research/daily_research'
2. Configure environment variables: AZURE_*, DATABASE_URL, etc.
3. Set resource limits: 1 CPU, 2GB memory per FR-010

Usage from Windmill UI or API:
    wmill.run_script_by_path("f/research/daily_research", {
        "topic": "Latest developments in AI agents",
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "client_traceparent": "00-xxx-yyy-01"  # Optional
    })
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Callable, Awaitable

from ..core.config import settings
from ..models.planned_action import PlannedAction
from ..models.research_state import ResearchState
from .approval_handler import (
    ApprovalRequest,
    process_planned_actions,
    requires_approval,
)
from ..workflows.report_formatter import format_research_report, render_markdown
from ..workflows.research_graph import InMemoryMemoryManager, compile_research_graph

logger = logging.getLogger(__name__)


def _get_wmill():
    """Lazy import of wmill to avoid import errors in non-Windmill environments."""
    try:
        import wmill
        return wmill
    except ImportError:
        return None


async def _default_action_executor(action: PlannedAction) -> dict[str, Any]:
    """Default action executor that logs execution.

    In production, this would dispatch to actual action handlers.
    For MVP, this logs the action and returns success.
    """
    logger.info(
        "Executing action '%s': %s",
        action.action_type,
        action.action_description,
    )
    return {
        "success": True,
        "action_type": action.action_type,
        "message": f"Action '{action.action_type}' executed successfully",
    }


def _windmill_suspend_for_approval(
    approval_request: ApprovalRequest,
) -> dict[str, Any]:
    """Suspend workflow and wait for Windmill approval.

    Uses Windmill's native suspend mechanism which:
    1. Pauses the current job execution
    2. Generates approval URLs (resume/cancel)
    3. Waits for user interaction or timeout
    4. Returns the resume payload with decision

    Note: This is synchronous because Windmill's suspend() is synchronous -
    it blocks the script until resumed.

    Args:
        approval_request: Details about the action requiring approval.

    Returns:
        Resume payload with 'decision' field ('approve' or 'reject').
    """
    wmill = _get_wmill()

    if wmill is None:
        # Fallback for testing without wmill installed - auto-approve
        logger.warning(
            "wmill not available; auto-approving action '%s' for testing",
            approval_request.action_type,
        )
        return {
            "decision": "approve",
            "approver": "test-auto-approval",
        }

    # Suspend the workflow and wait for resume
    logger.info(
        "Suspending for approval: %s (%s)",
        approval_request.action_type,
        approval_request.action_description,
    )

    # Calculate timeout in seconds from the timeout_at datetime
    timeout_seconds = settings.approval_timeout_seconds

    try:
        # wmill.suspend() is SYNCHRONOUS - it blocks until resumed or timeout
        # The function returns the resume payload directly
        #
        # Parameters:
        # - timeout: number of seconds or timedelta before auto-cancel
        # - default_args: pre-populated form values
        # - enums: dropdown options for approval form
        # - description: markdown text shown on approval page
        resume_payload = wmill.suspend(
            timeout=timedelta(seconds=timeout_seconds),
            default_args={"decision": "pending"},
            enums={"decision": ["approve", "reject"]},
            description=f"""
## Action Approval Required

**Action Type:** {approval_request.action_type}

**Description:** {approval_request.action_description}

**Risk Level:** Requires human approval before execution.

Please review and select 'approve' to proceed or 'reject' to skip this action.

_Timeout: {timeout_seconds} seconds_
""",
        )

        logger.info(
            "Approval response received for action '%s': %s",
            approval_request.action_type,
            resume_payload.get("decision", "unknown"),
        )

        return resume_payload

    except Exception as e:
        # Handle timeout or other errors
        logger.warning(
            "Approval request failed for action '%s': %s",
            approval_request.action_type,
            str(e),
        )
        return {
            "decision": "reject",
            "error": str(e),
            "reason": "timeout_or_error",
        }


async def _async_suspend_wrapper(
    approval_request: ApprovalRequest,
) -> dict[str, Any]:
    """Async wrapper for the synchronous Windmill suspend.

    Windmill's suspend() is synchronous but our approval handler expects async.
    This wrapper allows integration with our async processing pipeline.
    """
    # Note: In real Windmill execution, this runs in a worker that can block.
    # The synchronous call is acceptable because Windmill manages the suspension.
    return _windmill_suspend_for_approval(approval_request)


async def main(
    topic: str,
    user_id: str,
    client_traceparent: str | None = None,
    action_executor: Callable[[PlannedAction], Awaitable[dict[str, Any]]] | None = None,
    suspend_for_approval: Callable[[ApprovalRequest], Awaitable[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """
    Windmill entrypoint: execute the research graph with approval gating.

    This function is the main entry point when this script is executed by Windmill.
    It:
    1. Runs the LangGraph research loop (Plan → Research → Critique → Refine → Finish)
    2. Processes any planned actions with approval gating for risky operations
    3. Returns the final report payload for the API

    Args:
        topic: Research topic (1-500 chars).
        user_id: User identifier (UUID string).
        client_traceparent: Optional W3C traceparent for distributed tracing.
        action_executor: Optional custom action executor (for testing).
        suspend_for_approval: Optional custom approval handler (for testing).

    Returns:
        Dict with:
        - status: ResearchStatus value (e.g., "completed", "failed")
        - iterations: Number of research iterations performed
        - report: Markdown-formatted research report
        - sources: List of source references with URLs and snippets
        - memory_document_id: UUID of stored document in MemoryManager
        - action_results: List of action execution results
        - approval_status: Overall approval status if actions were processed
    """
    # Log start for observability
    wmill = _get_wmill()
    if wmill:
        # Set progress for Windmill UI (percentage only - no message parameter)
        try:
            wmill.set_progress(0)
            logger.info("Progress: 0%% - Starting research workflow")
        except Exception as e:
            logger.debug("Failed to set progress: %s", e)

    logger.info(
        "Starting DailyTrendingResearch workflow for topic: %s (user: %s)",
        topic[:50] + "..." if len(topic) > 50 else topic,
        user_id,
    )

    # Use defaults if not provided
    if action_executor is None:
        action_executor = _default_action_executor
    if suspend_for_approval is None:
        suspend_for_approval = _async_suspend_wrapper

    # Execute the research graph with distributed tracing support (T047a)
    app = compile_research_graph(memory_manager=InMemoryMemoryManager())
    initial_state = ResearchState(topic=topic, user_id=user_id)

    if wmill:
        try:
            wmill.set_progress(10)
            logger.info("Progress: 10%% - Running research graph")
        except Exception as e:
            logger.debug("Failed to set progress: %s", e)

    final_state: ResearchState = await app.ainvoke(
        initial_state, traceparent=client_traceparent
    )

    if wmill:
        try:
            wmill.set_progress(70)
            logger.info("Progress: 70%% - Formatting report")
        except Exception as e:
            logger.debug("Failed to set progress: %s", e)

    # Format the report
    report = format_research_report(final_state)
    markdown = render_markdown(report)

    # Process any planned actions with approval gating (FR-006, FR-007)
    action_results: list[dict[str, Any]] = []
    approval_status: str | None = None

    if final_state.planned_actions:
        if wmill:
            try:
                wmill.set_progress(80)
                logger.info("Progress: 80%% - Processing planned actions")
            except Exception as e:
                logger.debug("Failed to set progress: %s", e)

        logger.info(
            "Processing %d planned actions from research",
            len(final_state.planned_actions),
        )

        action_results = await process_planned_actions(
            final_state.planned_actions,
            action_executor=action_executor,
            suspend_for_approval=suspend_for_approval,
        )

        # Determine overall approval status
        statuses = [r.get("approval_status") for r in action_results]
        if "escalated" in statuses:
            approval_status = "escalated"
        elif "rejected" in statuses:
            approval_status = "rejected"
        elif all(s in ("approved", "not_required") for s in statuses):
            approval_status = "completed"
        else:
            approval_status = "partial"

    if wmill:
        try:
            wmill.set_progress(100)
            logger.info("Progress: 100%% - Workflow completed")
        except Exception as e:
            logger.debug("Failed to set progress: %s", e)

    logger.info(
        "DailyTrendingResearch workflow completed: %d iterations, %d sources",
        final_state.iteration_count,
        len(report.sources),
    )

    return {
        "status": final_state.status.value,
        "iterations": final_state.iteration_count,
        "report": markdown,
        "sources": [src.model_dump() for src in report.sources],
        "memory_document_id": final_state.memory_document_id,
        "action_results": action_results,
        "approval_status": approval_status,
    }


# Windmill script metadata for registration
# This helps Windmill understand the script's interface
__windmill__ = {
    "description": "Execute deep research on a topic with approval gating",
    "summary": "DailyTrendingResearch Workflow",
    "schema": {
        "properties": {
            "topic": {
                "type": "string",
                "description": "Research topic (1-500 characters)",
                "minLength": 1,
                "maxLength": 500,
            },
            "user_id": {
                "type": "string",
                "description": "User identifier (UUID format)",
                "format": "uuid",
            },
            "client_traceparent": {
                "type": "string",
                "description": "Optional W3C traceparent for distributed tracing",
            },
        },
        "required": ["topic", "user_id"],
    },
}

