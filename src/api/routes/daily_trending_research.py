from __future__ import annotations

import asyncio
from datetime import datetime, timezone
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
from src.models.research_state import ResearchState
from src.workflows.report_formatter import format_research_report, render_markdown
from src.workflows.research_graph import InMemoryMemoryManager, compile_research_graph

router = APIRouter(
    prefix="/v1/research/workflows/daily-trending-research",
    tags=["workflows"],
)

# In-memory run registry for MVP/testing
_RUNS: Dict[str, Dict[str, Any]] = {}
_memory_manager = InMemoryMemoryManager()


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
        )
    except Exception as exc:  # pragma: no cover - defensive
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
        approval=record.get("approval") or ApprovalStatus(status="not_required"),
        error=RunError(**record["error"]) if record.get("error") else None,
    )


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

