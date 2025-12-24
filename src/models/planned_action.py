from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

from src.models.risk_level import RiskLevel


class PlannedAction(BaseModel):
    """Action candidate that may require human approval before execution."""

    action_type: str = Field(..., min_length=1, description="Action identifier")
    action_description: str = Field(
        ..., min_length=1, description="Human-readable description of the action"
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific parameters to execute",
    )
    risk_level: RiskLevel = Field(
        ..., description="Risk classification driving approval requirements"
    )

    @field_validator("action_type", "action_description")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value cannot be empty")
        return cleaned

    model_config = {"extra": "forbid"}

