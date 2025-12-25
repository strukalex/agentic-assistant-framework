from __future__ import annotations

from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from .planned_action import PlannedAction
from .source_reference import SourceReference


class ResearchStatus(str, Enum):
    PLANNING = "planning"
    RESEARCHING = "researching"
    CRITIQUING = "critiquing"
    REFINING = "refining"
    FINISHED = "finished"


class ResearchState(BaseModel):
    """LangGraph state container for the DailyTrendingResearch workflow."""

    topic: str = Field(..., min_length=1, max_length=500, description="Research topic")
    user_id: UUID = Field(..., description="User identifier (UUID)")
    plan: Optional[str] = Field(None, description="Current research plan")
    sources: list[SourceReference] = Field(
        default_factory=list, description="Accumulated research sources"
    )
    critique: Optional[str] = Field(None, description="Latest critique/feedback")
    refined_answer: Optional[str] = Field(None, description="Refined response")
    iteration_count: int = Field(
        default=0, ge=0, description="Completed iterations of the research loop"
    )
    max_iterations: int = Field(
        default=5,
        ge=1,
        description="Maximum allowed iterations (hard-capped at 5)",
    )
    status: ResearchStatus = Field(
        default=ResearchStatus.PLANNING,
        description="Current workflow status",
    )
    quality_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Quality score from 0.0 to 1.0"
    )
    quality_threshold: float = Field(
        default=0.8, ge=0.0, le=1.0, description="Quality threshold to finish"
    )
    planned_actions: list[PlannedAction] = Field(
        default_factory=list, description="Pending actions that may need approval"
    )
    memory_document_id: str | None = Field(
        default=None,
        description="Identifier of the stored research report in MemoryManager",
    )
    report_markdown: str | None = Field(
        default=None, description="Rendered markdown report generated at finish"
    )

    @field_validator("topic")
    @classmethod
    def validate_topic(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("topic cannot be empty")
        return cleaned

    @model_validator(mode="after")
    def enforce_iteration_limits(self) -> "ResearchState":
        # Hard cap max_iterations at 5 even if caller provided a higher value.
        if self.max_iterations > 5:
            self.max_iterations = 5
        if self.iteration_count > self.max_iterations:
            raise ValueError("iteration_count cannot exceed max_iterations (<=5)")
        return self

    model_config = {"extra": "forbid"}

