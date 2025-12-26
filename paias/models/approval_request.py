from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


class DecisionMetadata(BaseModel):
    approved_by: Optional[str] = Field(
        default=None, description="Identifier of the approver"
    )
    rejected_by: Optional[str] = Field(
        default=None, description="Identifier of the rejector"
    )
    comment: Optional[str] = Field(default=None, description="Approval comment")
    duration_seconds: Optional[float] = Field(
        default=None, ge=0.0, description="Time taken to reach a decision"
    )
    reason: Optional[str] = Field(
        default=None, description="Optional reason (e.g., approval_timeout)"
    )

    model_config = {"extra": "forbid"}


class ApprovalRequest(BaseModel):
    """Human approval gate definition for Windmill suspend/resume."""

    action_type: str = Field(..., min_length=1, description="Type of the action")
    action_description: str = Field(
        ..., min_length=1, description="Human-readable action description"
    )
    requester_id: Optional[str] = Field(
        default=None, description="Identifier for who requested approval"
    )
    requested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when approval was requested",
    )
    timeout_at: datetime | None = Field(
        default=None,
        description="UTC timestamp when approval times out (set automatically if not provided)",
    )
    status: ApprovalStatus = Field(
        default=ApprovalStatus.PENDING, description="Current approval status"
    )
    decision_metadata: Optional[DecisionMetadata] = Field(
        default=None, description="Optional metadata about the decision"
    )

    @field_validator("action_type", "action_description")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value cannot be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_timeout(self) -> "ApprovalRequest":
        if self.timeout_at is None:
            self.timeout_at = self.requested_at + timedelta(seconds=300)

        delta = abs((self.timeout_at - self.requested_at).total_seconds())
        if delta < 290 or delta > 310:
            raise ValueError("timeout_at must be 5 minutes ±10 seconds from requested_at")
        return self

    model_config = {"extra": "forbid"}

