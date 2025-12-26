"""Windmill flow entry point for DailyTrendingResearch workflow.

This script is the Windmill-executable entry point that imports from the
pre-installed paias package (installed via custom Dockerfile.windmill).

Usage in Windmill:
    - Registered at path: f/research/run_research
    - Arguments: topic (str), user_id (str), client_traceparent (str, optional)

Architecture:
    - paias package is pre-installed in custom Windmill worker image
    - No need to copy src/ to u/admin/research_lib/
    - Clean imports directly from the installed package
"""

from __future__ import annotations

import asyncio
from typing import Any

# Import from pre-installed paias package
from paias.workflows.research_graph import (
    InMemoryMemoryManager,
    compile_research_graph,
)
from paias.models.research_state import ResearchState
from paias.workflows.report_formatter import (
    format_research_report,
    render_markdown,
)
from paias.windmill.approval_handler import (
    ApprovalRequest,
    process_planned_actions,
)
from paias.models.planned_action import PlannedAction
from paias.core.config import settings


# Try to import wmill for Windmill-specific functionality
try:
    import wmill

    WMILL_AVAILABLE = True
except ImportError:
    wmill = None  # type: ignore[assignment]
    WMILL_AVAILABLE = False


async def _default_action_executor(action: PlannedAction) -> dict[str, Any]:
    """Default action executor that logs execution."""
    return {
        "success": True,
        "action_type": action.action_type,
        "message": f"Action '{action.action_type}' executed successfully",
    }


async def _windmill_suspend_for_approval(
    approval_request: ApprovalRequest,
) -> dict[str, Any]:
    """Suspend workflow and wait for Windmill approval."""
    if not WMILL_AVAILABLE or wmill is None:
        # Auto-approve for testing without wmill
        return {
            "decision": "approve",
            "approver": "test-auto-approval",
        }

    from datetime import timedelta

    timeout_seconds = settings.approval_timeout_seconds

    try:
        resume_payload = wmill.suspend(
            timeout=timedelta(seconds=timeout_seconds),
            default_args={"decision": "pending"},
            enums={"decision": ["approve", "reject"]},
            description=f"""
## Action Approval Required

**Action Type:** {approval_request.action_type}

**Description:** {approval_request.action_description}

Please review and select 'approve' to proceed or 'reject' to skip this action.

_Timeout: {timeout_seconds} seconds_
""",
        )
        return resume_payload

    except Exception as e:
        return {
            "decision": "reject",
            "error": str(e),
            "reason": "timeout_or_error",
        }


def main(
    topic: str,
    user_id: str,
    client_traceparent: str | None = None,
) -> dict[str, Any]:
    """
    Windmill entrypoint: execute the research graph with approval gating.

    This is the main entry point when this script is executed by Windmill.
    Windmill expects a synchronous function, so we run the async implementation
    using asyncio.run().

    Args:
        topic: Research topic (1-500 chars).
        user_id: User identifier (UUID string).
        client_traceparent: Optional W3C traceparent for distributed tracing.

    Returns:
        Dict with status, iterations, report, sources, and action_results.
    """
    return asyncio.run(
        _async_main(topic, user_id, client_traceparent)
    )


async def _async_main(
    topic: str,
    user_id: str,
    client_traceparent: str | None = None,
) -> dict[str, Any]:
    """Async implementation of the Windmill workflow."""
    # Set progress for Windmill UI
    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(0, "Starting research workflow")
        except Exception:
            pass

    # Execute the research graph
    app = compile_research_graph(memory_manager=InMemoryMemoryManager())
    initial_state = ResearchState(topic=topic, user_id=user_id)

    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(10, "Running research graph")
        except Exception:
            pass

    final_state: ResearchState = await app.ainvoke(
        initial_state, traceparent=client_traceparent
    )

    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(70, "Formatting report")
        except Exception:
            pass

    # Format the report
    report = format_research_report(final_state)
    markdown = render_markdown(report)

    # Process planned actions with approval gating
    action_results: list[dict[str, Any]] = []
    approval_status: str | None = None

    if final_state.planned_actions:
        if WMILL_AVAILABLE and wmill is not None:
            try:
                wmill.set_progress(80, "Processing planned actions")
            except Exception:
                pass

        action_results = await process_planned_actions(
            final_state.planned_actions,
            action_executor=_default_action_executor,
            suspend_for_approval=_windmill_suspend_for_approval,
        )

        statuses = [r.get("approval_status") for r in action_results]
        if "escalated" in statuses:
            approval_status = "escalated"
        elif "rejected" in statuses:
            approval_status = "rejected"
        elif all(s in ("approved", "not_required") for s in statuses):
            approval_status = "completed"
        else:
            approval_status = "partial"

    if WMILL_AVAILABLE and wmill is not None:
        try:
            wmill.set_progress(100, "Workflow completed")
        except Exception:
            pass

    return {
        "status": final_state.status.value,
        "iterations": final_state.iteration_count,
        "report": markdown,
        "sources": [src.model_dump() for src in report.sources],
        "memory_document_id": final_state.memory_document_id,
        "action_results": action_results,
        "approval_status": approval_status,
    }


# Windmill script metadata
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
