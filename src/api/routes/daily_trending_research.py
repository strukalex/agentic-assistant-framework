from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException

from src.api.schemas.workflow_api import (
    ApprovalStatus,
    CreateRunLinks,
    CreateRunRequest,
    CreateRunResponse,
    ErrorResponse,
    ReportResponse,
    RunError,
    RunStatus,
    RunStatusResponse,
)
from src.core.config import settings
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

router = APIRouter(
    prefix="/v1/research/workflows/daily-trending-research",
    tags=["workflows"],
)

# In-memory run registry for MVP/testing
_RUNS: Dict[str, Dict[str, Any]] = {}
_memory_manager = InMemoryMemoryManager()

# Pending approvals registry for MVP/testing
_PENDING_APPROVALS: Dict[str, Dict[str, Any]] = {}


def _map_windmill_status_to_run_status(
    windmill_status: str | None,
    has_pending_approval: bool = False,
) -> RunStatus:
    """Map Windmill job status to API RunStatus.

    Args:
        windmill_status: Windmill job status string.
        has_pending_approval: Whether there's a pending approval for this run.

    Returns:
        Appropriate RunStatus enum value.
    """
    if has_pending_approval:
        return RunStatus.SUSPENDED_APPROVAL

    if windmill_status is None:
        return RunStatus.QUEUED

    status_map = {
        "queued": RunStatus.QUEUED,
        "running": RunStatus.RUNNING,
        "suspended": RunStatus.SUSPENDED_APPROVAL,
        "completed": RunStatus.COMPLETED,
        "failed": RunStatus.FAILED,
        "escalated": RunStatus.ESCALATED,
    }

    return status_map.get(windmill_status.lower(), RunStatus.RUNNING)


def _build_approval_status(
    run_id: str,
    record: Dict[str, Any],
) -> ApprovalStatus:
    """Build ApprovalStatus from run record and pending approvals.

    Args:
        run_id: The workflow run ID.
        record: The run record from the registry.

    Returns:
        ApprovalStatus with current approval state.
    """
    # Check for pending approval
    pending = _PENDING_APPROVALS.get(run_id)
    if pending:
        return ApprovalStatus(
            status="pending",
            action_type=pending.get("action_type"),
            action_description=pending.get("action_description"),
            timeout_at=pending.get("timeout_at"),
            approval_page_url=pending.get("approval_page_url"),
            resume_url=pending.get("resume_url"),
            cancel_url=pending.get("cancel_url"),
        )

    # Check for completed approval in record
    approval_data = record.get("approval")
    if approval_data:
        if isinstance(approval_data, ApprovalStatus):
            return approval_data
        if isinstance(approval_data, dict):
            return ApprovalStatus(**approval_data)

    # Default: no approval required
    return ApprovalStatus(status="not_required")


async def _execute_run(run_id: str, payload: CreateRunRequest) -> None:
    """Run the LangGraph workflow asynchronously and store results."""
    record = _RUNS[run_id]
    record["status"] = RunStatus.RUNNING
    record["updated_at"] = datetime.now(timezone.utc)

    app = compile_research_graph(memory_manager=_memory_manager)
    initial_state = ResearchState(topic=payload.topic, user_id=payload.user_id)

    try:
        final_state: ResearchState = await app.ainvoke(initial_state)
        report = format_research_report(final_state)
        markdown = render_markdown(report)

        # Process planned actions with approval gating
        action_results: list[dict[str, Any]] = []
        if final_state.planned_actions:
            logger.info(
                "Run %s has %d planned actions to process",
                run_id,
                len(final_state.planned_actions),
            )

            # Check if any actions require approval
            approval_required = any(
                requires_approval(action)
                for action in final_state.planned_actions
            )

            if approval_required:
                # Set status to suspended and create pending approval
                record["status"] = RunStatus.SUSPENDED_APPROVAL
                record["updated_at"] = datetime.now(timezone.utc)

                # Register pending approval for first approval-required action
                for action in final_state.planned_actions:
                    if requires_approval(action):
                        now = datetime.now(timezone.utc)
                        timeout_at = now + timedelta(
                            seconds=settings.approval_timeout_seconds
                        )
                        _PENDING_APPROVALS[run_id] = {
                            "action_type": action.action_type,
                            "action_description": action.action_description,
                            "timeout_at": timeout_at,
                            "resume_url": f"/v1/research/workflows/daily-trending-research/runs/{run_id}/approve",
                            "cancel_url": f"/v1/research/workflows/daily-trending-research/runs/{run_id}/reject",
                            "requested_at": now,
                        }
                        break

                # Store partial state for later completion
                record.update(
                    topic=str(final_state.topic),
                    user_id=str(final_state.user_id),
                    iterations_used=final_state.iteration_count,
                    sources_count=len(report.sources),
                    memory_document_id=final_state.memory_document_id,
                    markdown=markdown,
                    sources=[src.model_dump() for src in report.sources],
                    metadata={
                        "topic": report.topic,
                        "user_id": str(report.user_id),
                        "iterations": report.iterations,
                        "generated_at": report.generated_at.isoformat(),
                    },
                    planned_actions=[a.model_dump() for a in final_state.planned_actions],
                )
                return

        # No approval required - complete the run
        record.update(
            status=RunStatus.COMPLETED,
            updated_at=datetime.now(timezone.utc),
            topic=str(final_state.topic),
            user_id=str(final_state.user_id),
            iterations_used=final_state.iteration_count,
            sources_count=len(report.sources),
            memory_document_id=final_state.memory_document_id,
            markdown=markdown,
            sources=[src.model_dump() for src in report.sources],
            metadata={
                "topic": report.topic,
                "user_id": str(report.user_id),
                "iterations": report.iterations,
                "generated_at": report.generated_at.isoformat(),
            },
            action_results=action_results,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Run %s failed: %s", run_id, exc)
        record.update(
            status=RunStatus.FAILED,
            updated_at=datetime.now(timezone.utc),
            error={"message": str(exc)},
        )


@router.post("/runs", response_model=CreateRunResponse, status_code=202)
async def create_run(payload: CreateRunRequest) -> CreateRunResponse:
    """Create a new workflow run and start execution asynchronously."""
    run_id = str(uuid4())
    now = datetime.now(timezone.utc)
    _RUNS[run_id] = {
        "status": RunStatus.QUEUED,
        "created_at": now,
        "updated_at": now,
        "topic": str(payload.topic),
        "user_id": str(payload.user_id),
        "approval": None,
    }

    asyncio.create_task(_execute_run(run_id, payload))

    return CreateRunResponse(
        run_id=run_id,
        status=RunStatus.QUEUED,
        links=CreateRunLinks(
            self=f"/v1/research/workflows/daily-trending-research/runs/{run_id}",
            report=f"/v1/research/workflows/daily-trending-research/runs/{run_id}/report",
        ),
    )


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
async def get_run(run_id: str) -> RunStatusResponse:
    """Fetch the status for a workflow run."""
    record = _RUNS.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=ErrorResponse(error=RunError(message="Run not found")).model_dump())

    # Build approval status from pending approvals registry
    approval = _build_approval_status(run_id, record)

    return RunStatusResponse(
        run_id=run_id,
        status=record["status"],
        created_at=record.get("created_at"),
        updated_at=record.get("updated_at"),
        topic=record.get("topic"),
        user_id=UUID(record["user_id"]) if record.get("user_id") else None,
        iterations_used=record.get("iterations_used"),
        sources_count=record.get("sources_count"),
        memory_document_id=record.get("memory_document_id"),
        approval=approval,
        error=RunError(**record["error"]) if record.get("error") else None,
    )


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: str, approver: str | None = None) -> dict[str, Any]:
    """Approve a pending action for a workflow run.

    Resumes the workflow with approval granted, allowing the action to execute.
    """
    record = _RUNS.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=ErrorResponse(error=RunError(message="Run not found")).model_dump())

    pending = _PENDING_APPROVALS.get(run_id)
    if not pending:
        raise HTTPException(
            status_code=409,
            detail=ErrorResponse(
                error=RunError(message="No pending approval for this run")
            ).model_dump(),
        )

    # Clear the pending approval
    del _PENDING_APPROVALS[run_id]

    # Update record with approved status
    record["status"] = RunStatus.COMPLETED
    record["updated_at"] = datetime.now(timezone.utc)
    record["approval"] = ApprovalStatus(
        status="approved",
        action_type=pending.get("action_type"),
        action_description=pending.get("action_description"),
    )

    logger.info(
        "Run %s approved by %s for action '%s'",
        run_id,
        approver or "unknown",
        pending.get("action_type"),
    )

    return {
        "run_id": run_id,
        "status": "approved",
        "action_type": pending.get("action_type"),
    }


@router.post("/runs/{run_id}/reject")
async def reject_run(
    run_id: str,
    rejector: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Reject a pending action for a workflow run.

    Resumes the workflow with rejection, skipping the action.
    """
    record = _RUNS.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=ErrorResponse(error=RunError(message="Run not found")).model_dump())

    pending = _PENDING_APPROVALS.get(run_id)
    if not pending:
        raise HTTPException(
            status_code=409,
            detail=ErrorResponse(
                error=RunError(message="No pending approval for this run")
            ).model_dump(),
        )

    # Clear the pending approval
    del _PENDING_APPROVALS[run_id]

    # Update record with rejected status
    record["status"] = RunStatus.COMPLETED
    record["updated_at"] = datetime.now(timezone.utc)
    record["approval"] = ApprovalStatus(
        status="rejected",
        action_type=pending.get("action_type"),
        action_description=pending.get("action_description"),
    )

    logger.info(
        "Run %s rejected by %s for action '%s': %s",
        run_id,
        rejector or "unknown",
        pending.get("action_type"),
        reason or "no reason given",
    )

    return {
        "run_id": run_id,
        "status": "rejected",
        "action_type": pending.get("action_type"),
        "reason": reason,
    }


@router.get("/runs/{run_id}/report", response_model=ReportResponse)
async def get_report(run_id: str) -> ReportResponse:
    """Return the final report for a completed workflow run."""
    record = _RUNS.get(run_id)
    if not record:
        raise HTTPException(status_code=404, detail=ErrorResponse(error=RunError(message="Run not found")).model_dump())

    if record.get("status") != RunStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail=ErrorResponse(
                error=RunError(message="Report not ready; run must be completed")
            ).model_dump(),
        )

    return ReportResponse(
        run_id=run_id,
        markdown=record.get("markdown") or "",
        sources=record.get("sources") or [],
        metadata=record.get("metadata") or {},
    )

