from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.models.source_reference import SourceReference


class RunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUSPENDED_APPROVAL = "suspended_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class ApprovalStatus(BaseModel):
    status: Optional[str] = Field(
        default=None,
        description="Approval status (not_required|pending|approved|rejected|escalated)",
    )
    action_type: Optional[str] = Field(default=None, description="Type of action")
    action_description: Optional[str] = Field(
        default=None, description="Description of the action requiring approval"
    )
    timeout_at: Optional[datetime] = Field(
        default=None, description="Approval timeout deadline"
    )
    approval_page_url: Optional[str] = Field(
        default=None, description="Windmill approval UI link"
    )
    resume_url: Optional[str] = Field(default=None, description="Resume URL")
    cancel_url: Optional[str] = Field(default=None, description="Cancel URL")

    model_config = {"extra": "forbid"}


class RunError(BaseModel):
    message: str = Field(..., description="Human-readable error message")
    code: Optional[str] = Field(default=None, description="Optional machine code")
    details: Optional[dict[str, Any]] = Field(
        default=None, description="Optional error details"
    )

    model_config = {"extra": "forbid"}


class CreateRunRequest(BaseModel):
    topic: str = Field(..., min_length=1, max_length=500, description="Research topic")
    user_id: UUID = Field(..., description="User identifier for the run")
    client_traceparent: Optional[str] = Field(
        default=None,
        description="Optional W3C traceparent for distributed tracing correlation",
    )

    model_config = {"extra": "forbid"}


class CreateRunLinks(BaseModel):
    self: Optional[str] = Field(default=None, description="Link to status endpoint")
    report: Optional[str] = Field(default=None, description="Link to report endpoint")

    model_config = {"extra": "forbid"}


class CreateRunResponse(BaseModel):
    run_id: str = Field(..., description="Identifier for the workflow run")
    status: RunStatus = Field(..., description="Current run status")
    links: Optional[CreateRunLinks] = Field(
        default=None, description="Helpful links for status and report retrieval"
    )

    model_config = {"extra": "forbid"}


class RunStatusResponse(BaseModel):
    run_id: str = Field(..., description="Identifier for the workflow run")
    status: RunStatus = Field(..., description="Current run status")
    created_at: Optional[datetime] = Field(
        default=None, description="Creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Last update timestamp"
    )
    topic: Optional[str] = Field(default=None, description="Topic for the run")
    user_id: Optional[UUID] = Field(default=None, description="User identifier")
    iterations_used: Optional[int] = Field(
        default=None, ge=0, le=5, description="Iterations consumed by the run"
    )
    sources_count: Optional[int] = Field(
        default=None, ge=0, description="Number of sources collected"
    )
    memory_document_id: Optional[str] = Field(
        default=None, description="Stored memory document id, when available"
    )
    approval: Optional[ApprovalStatus] = Field(
        default=None, description="Approval-related status/details"
    )
    error: Optional[RunError] = Field(
        default=None, description="Error information if the run failed"
    )

    model_config = {"extra": "forbid"}


class ReportResponse(BaseModel):
    run_id: str = Field(..., description="Identifier for the workflow run")
    markdown: str = Field(..., description="Markdown report content")
    sources: list[SourceReference] = Field(
        ..., description="Sources referenced in the report"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Metadata including topic, user_id, etc."
    )

    model_config = {"extra": "forbid"}


class ErrorResponse(BaseModel):
    error: RunError

    model_config = {"extra": "forbid"}

