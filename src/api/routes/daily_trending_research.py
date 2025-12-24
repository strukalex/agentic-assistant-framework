"""API routes for DailyTrendingResearch workflow.

This module provides FastAPI endpoints for:
- Creating workflow runs (triggers Windmill or in-process execution)
- Polling run status
- Retrieving completed reports
- Approving/rejecting pending actions

When WINDMILL_ENABLED=true, routes delegate to Windmill for execution.
When WINDMILL_ENABLED=false, routes use in-process execution for testing.

Constitution compliance:
- Article I.B: Windmill for DAG orchestration
- Article II.C: Human-in-the-loop via approval endpoints
"""

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
from src.core.telemetry import trace_api_endpoint
from src.models.planned_action import PlannedAction
from src.models.research_state import ResearchState
from src.windmill.approval_handler import (
    ApprovalRequest,
    process_planned_actions,
    requires_approval,
)
from src.windmill.client import WindmillClient, WindmillJobStatus
from src.workflows.report_formatter import format_research_report, render_markdown
from src.workflows.research_graph import InMemoryMemoryManager, compile_research_graph

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/v1/research/workflows/daily-trending-research",
    tags=["workflows"],
)

# In-memory run registry for MVP/testing (used when WINDMILL_ENABLED=false)
_RUNS: Dict[str, Dict[str, Any]] = {}
_memory_manager = InMemoryMemoryManager()

# Pending approvals registry for MVP/testing
_PENDING_APPROVALS: Dict[str, Dict[str, Any]] = {}

# Run ID to Windmill job ID mapping (used when WINDMILL_ENABLED=true)
_RUN_TO_JOB: Dict[str, str] = {}


def _map_windmill_status_to_run_status(
    windmill_status: str | None,
    has_pending_approval: bool = False,
) -> RunStatus:
    """Map Windmill job status to API RunStatus.

    Args:
        windmill_status: Windmill job status string (from WindmillJobStatus).
        has_pending_approval: Whether there's a pending approval for this run.

    Returns:
        Appropriate RunStatus enum value.
    """
    if has_pending_approval:
        return RunStatus.SUSPENDED_APPROVAL

    if windmill_status is None:
        return RunStatus.QUEUED

    # Map Windmill job statuses to our API statuses
    # WindmillJobStatus values: Waiting, Running, CompletedSuccess, CompletedFailure, Canceled, Suspended
    status_map = {
        # Windmill native statuses
        WindmillJobStatus.QUEUED.value.lower(): RunStatus.QUEUED,
        WindmillJobStatus.RUNNING.value.lower(): RunStatus.RUNNING,
        WindmillJobStatus.COMPLETED.value.lower(): RunStatus.COMPLETED,
        WindmillJobStatus.FAILED.value.lower(): RunStatus.FAILED,
        WindmillJobStatus.CANCELED.value.lower(): RunStatus.FAILED,
        WindmillJobStatus.SUSPENDED.value.lower(): RunStatus.SUSPENDED_APPROVAL,
        # Legacy lowercase mappings for compatibility
        "queued": RunStatus.QUEUED,
        "waiting": RunStatus.QUEUED,
        "running": RunStatus.RUNNING,
        "suspended": RunStatus.SUSPENDED_APPROVAL,
        "completed": RunStatus.COMPLETED,
        "completedsuccess": RunStatus.COMPLETED,
        "completedfailure": RunStatus.FAILED,
        "failed": RunStatus.FAILED,
        "canceled": RunStatus.FAILED,
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
        # Pass client_traceparent for distributed tracing (T048)
        final_state: ResearchState = await app.ainvoke(
            initial_state, traceparent=payload.client_traceparent
        )
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


async def _trigger_windmill_flow(
    run_id: str,
    payload: CreateRunRequest,
) -> str:
    """Trigger the Windmill flow and return the job ID.

    Args:
        run_id: Our internal run ID.
        payload: The workflow request payload.

    Returns:
        Windmill job UUID.
    """
    async with WindmillClient() as client:
        job_id = await client.trigger_flow(
            flow_path=settings.windmill_flow_path,
            payload={
                "topic": str(payload.topic),
                "user_id": str(payload.user_id),
                "client_traceparent": payload.client_traceparent,
            },
        )
        return job_id


@router.post("/runs", response_model=CreateRunResponse, status_code=202)
@trace_api_endpoint("create_run")
async def create_run(payload: CreateRunRequest) -> CreateRunResponse:
    """Create a new workflow run and start execution asynchronously.

    When WINDMILL_ENABLED=true, triggers the Windmill flow and returns immediately.
    When WINDMILL_ENABLED=false, runs the workflow in-process (for testing).
    """
    run_id = str(uuid4())
    now = datetime.now(timezone.utc)

    if settings.windmill_enabled:
        # Trigger Windmill flow
        logger.info(
            "Creating Windmill-orchestrated run %s for topic: %s",
            run_id,
            payload.topic[:50],
        )
        try:
            job_id = await _trigger_windmill_flow(run_id, payload)
            _RUN_TO_JOB[run_id] = job_id
            logger.info("Windmill job %s created for run %s", job_id, run_id)

            # Store minimal metadata for status lookups
            _RUNS[run_id] = {
                "status": RunStatus.QUEUED,
                "created_at": now,
                "updated_at": now,
                "topic": str(payload.topic),
                "user_id": str(payload.user_id),
                "windmill_job_id": job_id,
                "approval": None,
            }
        except Exception as e:
            logger.exception("Failed to trigger Windmill flow for run %s: %s", run_id, e)
            raise HTTPException(
                status_code=503,
                detail=ErrorResponse(
                    error=RunError(message=f"Windmill unavailable: {e}")
                ).model_dump(),
            )
    else:
        # In-process execution for testing
        logger.info(
            "Creating in-process run %s for topic: %s",
            run_id,
            payload.topic[:50],
        )
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


async def _get_windmill_job_status(run_id: str, job_id: str) -> Dict[str, Any]:
    """Fetch job details from Windmill and convert to our format.

    Args:
        run_id: Our internal run ID.
        job_id: Windmill job UUID.

    Returns:
        Dict with status info compatible with our in-memory format.
    """
    async with WindmillClient() as client:
        job = await client.get_job(job_id)

        # Extract status
        status_str = await client.get_job_status(job_id)
        status = _map_windmill_status_to_run_status(status_str)

        # Build result dict
        result: Dict[str, Any] = {
            "status": status,
            "windmill_job_id": job_id,
            "updated_at": datetime.now(timezone.utc),
        }

        # Check for suspension (approval pending)
        if "suspend" in job:
            suspend_info = job["suspend"]
            result["status"] = RunStatus.SUSPENDED_APPROVAL
            # Extract approval info from suspend data
            if isinstance(suspend_info, dict):
                result["pending_approval"] = {
                    "resume_id": suspend_info.get("resume_id", 0),
                    "approval_page_url": f"{settings.windmill_base_url}/runs/{job_id}",
                }

        # Check for completion
        if "success" in job:
            if job["success"]:
                result["status"] = RunStatus.COMPLETED
                # Try to get the result
                try:
                    job_result = await client.get_job_result(job_id)
                    result["result"] = job_result
                    # Extract fields from the Windmill result
                    if isinstance(job_result, dict):
                        result["iterations_used"] = job_result.get("iterations")
                        result["sources_count"] = len(job_result.get("sources", []))
                        result["memory_document_id"] = job_result.get("memory_document_id")
                        result["markdown"] = job_result.get("report")
                        result["sources"] = job_result.get("sources", [])
                        result["metadata"] = {
                            "iterations": job_result.get("iterations"),
                            "approval_status": job_result.get("approval_status"),
                        }
                except Exception as e:
                    logger.warning("Failed to get result for job %s: %s", job_id, e)
            else:
                result["status"] = RunStatus.FAILED
                result["error"] = {"message": job.get("logs", "Job failed")}

        return result


@router.get("/runs/{run_id}", response_model=RunStatusResponse)
@trace_api_endpoint("get_run_status")
async def get_run(run_id: str) -> RunStatusResponse:
    """Fetch the status for a workflow run.

    When WINDMILL_ENABLED=true, fetches live status from Windmill.
    When WINDMILL_ENABLED=false, uses in-memory registry.
    """
    record = _RUNS.get(run_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(error=RunError(message="Run not found")).model_dump(),
        )

    # If Windmill is enabled and we have a job ID, fetch live status
    if settings.windmill_enabled and record.get("windmill_job_id"):
        job_id = record["windmill_job_id"]
        try:
            windmill_status = await _get_windmill_job_status(run_id, job_id)
            # Merge Windmill status into record
            record.update(windmill_status)
        except Exception as e:
            logger.warning(
                "Failed to fetch Windmill status for run %s (job %s): %s",
                run_id,
                job_id,
                e,
            )
            # Continue with cached status

    # Build approval status
    approval = _build_approval_status(run_id, record)

    # Check for pending approval from Windmill
    if record.get("pending_approval"):
        pending = record["pending_approval"]
        approval = ApprovalStatus(
            status="pending",
            approval_page_url=pending.get("approval_page_url"),
        )

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
@trace_api_endpoint("approve_run")
async def approve_run(run_id: str, approver: str | None = None) -> dict[str, Any]:
    """Approve a pending action for a workflow run.

    Resumes the workflow with approval granted, allowing the action to execute.

    When WINDMILL_ENABLED=true, resumes the Windmill job via API.
    When WINDMILL_ENABLED=false, uses in-memory approval tracking.
    """
    record = _RUNS.get(run_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(error=RunError(message="Run not found")).model_dump(),
        )

    # Handle Windmill-based approval
    if settings.windmill_enabled and record.get("windmill_job_id"):
        job_id = record["windmill_job_id"]

        # Check if job is actually suspended
        if record.get("pending_approval") is None:
            # Fetch current status to check for suspension
            try:
                windmill_status = await _get_windmill_job_status(run_id, job_id)
                record.update(windmill_status)
            except Exception as e:
                logger.warning("Failed to fetch job status: %s", e)

        pending = record.get("pending_approval")
        if not pending:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error=RunError(message="No pending approval for this run")
                ).model_dump(),
            )

        # Resume the Windmill job with approval
        try:
            async with WindmillClient() as client:
                resume_id = pending.get("resume_id", 0)
                await client.resume_job(
                    job_id=job_id,
                    resume_id=resume_id,
                    payload={"decision": "approve"},
                    approver=approver,
                )

            # Clear pending approval
            record.pop("pending_approval", None)
            record["updated_at"] = datetime.now(timezone.utc)

            logger.info(
                "Run %s (job %s) approved by %s",
                run_id,
                job_id,
                approver or "unknown",
            )

            return {
                "run_id": run_id,
                "status": "approved",
                "windmill_job_id": job_id,
            }

        except Exception as e:
            logger.exception("Failed to resume Windmill job %s: %s", job_id, e)
            raise HTTPException(
                status_code=503,
                detail=ErrorResponse(
                    error=RunError(message=f"Failed to approve: {e}")
                ).model_dump(),
            )

    # In-memory approval for testing
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
@trace_api_endpoint("reject_run")
async def reject_run(
    run_id: str,
    rejector: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Reject a pending action for a workflow run.

    Resumes the workflow with rejection, skipping the action.

    When WINDMILL_ENABLED=true, cancels/rejects via Windmill API.
    When WINDMILL_ENABLED=false, uses in-memory approval tracking.
    """
    record = _RUNS.get(run_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(error=RunError(message="Run not found")).model_dump(),
        )

    # Handle Windmill-based rejection
    if settings.windmill_enabled and record.get("windmill_job_id"):
        job_id = record["windmill_job_id"]

        # Check if job is actually suspended
        if record.get("pending_approval") is None:
            try:
                windmill_status = await _get_windmill_job_status(run_id, job_id)
                record.update(windmill_status)
            except Exception as e:
                logger.warning("Failed to fetch job status: %s", e)

        pending = record.get("pending_approval")
        if not pending:
            raise HTTPException(
                status_code=409,
                detail=ErrorResponse(
                    error=RunError(message="No pending approval for this run")
                ).model_dump(),
            )

        # Resume the Windmill job with rejection
        try:
            async with WindmillClient() as client:
                resume_id = pending.get("resume_id", 0)
                await client.resume_job(
                    job_id=job_id,
                    resume_id=resume_id,
                    payload={
                        "decision": "reject",
                        "reason": reason or "rejected by user",
                    },
                    approver=rejector,
                )

            # Clear pending approval
            record.pop("pending_approval", None)
            record["updated_at"] = datetime.now(timezone.utc)

            logger.info(
                "Run %s (job %s) rejected by %s: %s",
                run_id,
                job_id,
                rejector or "unknown",
                reason or "no reason given",
            )

            return {
                "run_id": run_id,
                "status": "rejected",
                "windmill_job_id": job_id,
                "reason": reason,
            }

        except Exception as e:
            logger.exception("Failed to reject Windmill job %s: %s", job_id, e)
            raise HTTPException(
                status_code=503,
                detail=ErrorResponse(
                    error=RunError(message=f"Failed to reject: {e}")
                ).model_dump(),
            )

    # In-memory rejection for testing
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
@trace_api_endpoint("get_report")
async def get_report(run_id: str) -> ReportResponse:
    """Return the final report for a completed workflow run.

    When WINDMILL_ENABLED=true, fetches the report from Windmill job result.
    When WINDMILL_ENABLED=false, uses in-memory registry.
    """
    record = _RUNS.get(run_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=ErrorResponse(error=RunError(message="Run not found")).model_dump(),
        )

    # If Windmill is enabled, fetch the latest status and result
    if settings.windmill_enabled and record.get("windmill_job_id"):
        job_id = record["windmill_job_id"]
        try:
            windmill_status = await _get_windmill_job_status(run_id, job_id)
            record.update(windmill_status)
        except Exception as e:
            logger.warning(
                "Failed to fetch Windmill status for report (run %s): %s",
                run_id,
                e,
            )

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

