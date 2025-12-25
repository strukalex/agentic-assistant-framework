from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from .source_reference import SourceReference


class QualityIndicators(BaseModel):
    """Optional quality metadata attached to the final report."""

    quality_score: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Quality score between 0 and 1"
    )
    warnings: list[str] = Field(
        default_factory=list, description="Warnings or caveats for the report"
    )
    limited_sources: Optional[bool] = Field(
        default=None,
        description="Whether the report was limited by source availability",
    )

    model_config = {"extra": "forbid"}


class ResearchReport(BaseModel):
    """Final research artifact returned by the workflow and stored in memory."""

    topic: str = Field(..., min_length=1, description="Research topic")
    user_id: UUID = Field(..., description="User identifier associated with the run")
    executive_summary: str = Field(..., min_length=1, description="Summary section")
    detailed_findings: str = Field(..., min_length=1, description="Detailed findings")
    sources: list[SourceReference] = Field(
        ..., description="Cited sources included in the report"
    )
    iterations: int = Field(..., ge=0, description="Iteration count used")
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the report was generated",
    )
    quality_indicators: Optional[QualityIndicators] = Field(
        default=None, description="Optional quality metadata"
    )

    @field_validator("topic", "executive_summary", "detailed_findings")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value cannot be empty")
        return cleaned

    model_config = {"extra": "forbid"}

