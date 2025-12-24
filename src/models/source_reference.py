from __future__ import annotations

from datetime import datetime, timezone

from pydantic import AnyUrl, BaseModel, Field, field_validator


class SourceReference(BaseModel):
    """Reference to a research source with lightweight validation."""

    title: str = Field(..., min_length=1, description="Source title")
    url: AnyUrl = Field(..., description="Absolute URL to the source")
    snippet: str = Field(
        ..., min_length=1, max_length=1000, description="Short excerpt from the source"
    )
    retrieved_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the source was retrieved",
    )

    @field_validator("snippet")
    @classmethod
    def enforce_snippet_limit(cls, value: str) -> str:
        if len(value) > 1000:
            raise ValueError("snippet must be <= 1000 characters")
        return value

    @field_validator("title")
    @classmethod
    def validate_non_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("title cannot be empty")
        return cleaned

    model_config = {
        "extra": "forbid",
    }

