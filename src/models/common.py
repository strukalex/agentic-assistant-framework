from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

class RiskLevel(str, Enum):
    """Action risk categorization for approval workflows."""

    REVERSIBLE = "reversible"
    REVERSIBLE_WITH_DELAY = "reversible_with_delay"
    IRREVERSIBLE = "irreversible"


class AgentResponse(BaseModel):
    """Standard agent response payload."""

    answer: str = Field(..., min_length=1, description="The agent's response text")
    reasoning: Optional[str] = Field(None, description="Optional reasoning trail")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list, description="List of tool invocations")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="UTC timestamp")

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, value: str) -> str:
        cleaned = value.strip() if value else ""
        if not cleaned:
            raise ValueError("answer cannot be empty")
        return cleaned


class ToolGapReport(BaseModel):
    """Report missing tools detected during execution."""

    missing_tools: list[str] = Field(..., description="Names of required tools that are absent")
    attempted_task: str = Field(..., min_length=1, description="Task that failed due to missing tools")
    existing_tools_checked: list[str] = Field(..., description="Tools evaluated but insufficient")
    proposed_mcp_server: Optional[str] = Field(
        None, description="Suggested MCP server to close the gap"
    )

    @field_validator("attempted_task")
    @classmethod
    def validate_attempted_task(cls, value: str) -> str:
        cleaned = value.strip() if value else ""
        if not cleaned:
            raise ValueError("attempted_task cannot be empty")
        return cleaned


class ApprovalRequest(BaseModel):
    """Human approval request payload."""

    action_type: str = Field(..., min_length=1, description="Action being requested")
    action_description: str = Field(..., min_length=1, description="Human-readable description")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    risk_level: RiskLevel = Field(..., description="Risk classification")
    tool_name: str = Field(..., min_length=1, description="Name of tool to execute")
    parameters: dict[str, Any] = Field(..., description="Parameters passed to the tool")
    requires_immediate_approval: bool = Field(
        ..., description="If true, block until approval is granted or rejected"
    )
    timeout_seconds: Optional[int] = Field(
        None, description="Optional timeout for auto-rejection in seconds", gt=0
    )

    @field_validator("action_type", "action_description", "tool_name")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        cleaned = value.strip() if value else ""
        if not cleaned:
            raise ValueError("value cannot be empty")
        return cleaned

