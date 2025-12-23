"""Structured response models for ResearcherAgent."""

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolCallStatus(str, Enum):
    """Status of a tool call execution."""

    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ToolCallRecord(BaseModel):
    """
    Record of a single tool invocation.

    Attributes:
        tool_name: Name of the MCP tool invoked
        parameters: Input parameters passed to the tool
        result: Tool output (None if failed/timeout)
        duration_ms: Execution time in milliseconds
        status: Execution status (success/failed/timeout)
    """

    tool_name: str = Field(
        ..., description="Name of the MCP tool that was invoked", min_length=1
    )
    parameters: dict = Field(..., description="Input parameters passed to the tool")
    result: Optional[Any] = Field(
        None, description="Tool output; None if execution failed or timed out"
    )
    duration_ms: int = Field(
        ..., ge=0, description="Execution time in milliseconds"
    )
    status: ToolCallStatus = Field(
        ..., description="Execution status: SUCCESS, FAILED, or TIMEOUT"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tool_name": "web_search",
                "parameters": {"query": "capital of France", "max_results": 5},
                "result": [
                    {
                        "title": "Paris - Wikipedia",
                        "url": "https://...",
                        "snippet": "Paris is the capital...",
                    }
                ],
                "duration_ms": 1234,
                "status": "SUCCESS",
            }
        }
    )


class AgentResponse(BaseModel):
    """
    Structured response from ResearcherAgent.

    Attributes:
        answer: The final answer to the user's query
        reasoning: Explanation of tool choices and reasoning process
        tool_calls: List of all tool invocations made during execution
        confidence: Model's self-assessed confidence (0.0-1.0)
    """

    answer: str = Field(
        ..., description="The final answer to the user's query", min_length=1
    )
    reasoning: str = Field(
        ...,
        description="Explanation of how the answer was derived, including tool choices",
        min_length=1,
    )
    tool_calls: List[ToolCallRecord] = Field(
        default_factory=list,
        description="All tool invocations made during agent execution",
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0"
    )

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        """Ensure confidence is within valid range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "answer": "Paris",
                "reasoning": "Used web_search to find 'capital of France'. Top result from Wikipedia confirmed Paris.",
                "tool_calls": [
                    {
                        "tool_name": "web_search",
                        "parameters": {"query": "capital of France", "max_results": 5},
                        "result": [
                            {
                                "title": "Paris - Wikipedia",
                                "url": "...",
                                "snippet": "...",
                            }
                        ],
                        "duration_ms": 1234,
                        "status": "SUCCESS",
                    }
                ],
                "confidence": 0.95,
            }
        }
    )
