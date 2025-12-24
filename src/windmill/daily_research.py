from __future__ import annotations

import logging
from typing import Any, Callable, Awaitable

from src.models.planned_action import PlannedAction
from src.models.research_state import ResearchState
from src.windmill.approval_handler import (
    ApprovalRequest,
    process_planned_actions,
    requires_approval,
)
from src.workflows.report_formatter import format_research_report, render_markdown
from src.workflows.research_graph import InMemoryMemoryManager, compile_research_graph

logger = logging.getLogger(__name__)


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


async def _windmill_suspend_for_approval(
    approval_request: ApprovalRequest,
) -> dict[str, Any]:
    """Suspend workflow and wait for Windmill approval.

    In actual Windmill execution, this uses wmill.suspend().
    For testing/local development, this auto-approves.
    """
    try:
        import wmill

        # Suspend the workflow and wait for resume
        logger.info(
            "Suspending for approval: %s (%s)",
            approval_request.action_type,
            approval_request.action_description,
        )

        # Get resume URLs for the UI
        urls = wmill.get_resume_urls()

        # Suspend the flow - this blocks until resumed or timeout
        resume_payload = await wmill.suspend(
            timeout=approval_request.timeout_at,
            default_args={"decision": "pending"},
            enums={"decision": ["approve", "reject"]},
        )

        return resume_payload

    except ImportError:
        # Fallback for testing without wmill installed - auto-approve
        logger.warning(
            "wmill not available; auto-approving action '%s' for testing",
            approval_request.action_type,
        )
        return {
            "decision": "approve",
            "approver": "test-auto-approval",
        }


async def main(
    topic: str,
    user_id: str,
    client_traceparent: str | None = None,
    action_executor: Callable[[PlannedAction], Awaitable[dict[str, Any]]] | None = None,
    suspend_for_approval: Callable[[ApprovalRequest], Awaitable[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """
    Windmill entrypoint: execute the research graph with approval gating.

    This function:
    1. Runs the LangGraph research loop (Plan → Research → Critique → Refine → Finish)
    2. Processes any planned actions with approval gating for risky operations
    3. Returns the final report payload

    Args:
        topic: Research topic (1-500 chars).
        user_id: User identifier (UUID string).
        client_traceparent: Optional W3C traceparent for distributed tracing.
        action_executor: Optional custom action executor (for testing).
        suspend_for_approval: Optional custom approval handler (for testing).

    Returns:
        Dict with status, iterations, report, sources, memory_document_id, and action_results.
    """
    # Use defaults if not provided
    if action_executor is None:
        action_executor = _default_action_executor
    if suspend_for_approval is None:
        suspend_for_approval = _windmill_suspend_for_approval

    # Execute the research graph with distributed tracing support (T047a)
    app = compile_research_graph(memory_manager=InMemoryMemoryManager())
    initial_state = ResearchState(topic=topic, user_id=user_id)
    final_state: ResearchState = await app.ainvoke(
        initial_state, traceparent=client_traceparent
    )

    # Format the report
    report = format_research_report(final_state)
    markdown = render_markdown(report)

    # Process any planned actions with approval gating (FR-006, FR-007)
    action_results: list[dict[str, Any]] = []
    approval_status: str | None = None

    if final_state.planned_actions:
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

    return {
        "status": final_state.status.value,
        "iterations": final_state.iteration_count,
        "report": markdown,
        "sources": [src.model_dump() for src in report.sources],
        "memory_document_id": final_state.memory_document_id,
        "action_results": action_results,
        "approval_status": approval_status,
    }

