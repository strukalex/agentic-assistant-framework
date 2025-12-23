"""Tool gap detection report model."""

from typing import List

from pydantic import BaseModel, Field


from pydantic import ConfigDict


class ToolGapReport(BaseModel):
    """
    Report of missing tool capabilities detected during task analysis.

    Attributes:
        missing_tools: List of tool names/capabilities that are required but unavailable
        attempted_task: Original task description that triggered the gap detection
        existing_tools_checked: List of available tool names that were checked
    """

    missing_tools: List[str] = Field(
        ...,
        description="List of required capabilities not available in MCP tool registry",
        min_length=1,
    )
    attempted_task: str = Field(
        ...,
        description="The task description that required the missing tools",
        min_length=1,
    )
    existing_tools_checked: List[str] = Field(
        ...,
        description="List of available MCP tools that were evaluated",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "missing_tools": ["financial_data_api", "account_access"],
                "attempted_task": "Retrieve my stock portfolio performance for Q3 2024",
                "existing_tools_checked": [
                    "web_search",
                    "read_file",
                    "get_current_time",
                    "search_memory",
                ],
            }
        }
    )
