"""
Tool Gap Detection for ResearcherAgent.

Detects when a task requires tools/capabilities that are not available in the
current MCP tool registry, enabling honest reporting of limitations instead of
hallucinated execution.

Per Spec 002 research.md RQ-005, tasks.md T204-T209 (FR-009 to FR-014, SC-003)
"""

from typing import Any, List, Optional, cast

from mcp import ClientSession
from pydantic import BaseModel
from pydantic_ai import Agent

from .llm import get_azure_model, parse_agent_result
from ..models.tool_gap_report import ToolGapReport


class CapabilityAnalysisResult(BaseModel):
    """LLM analysis result for tool capability matching."""

    missing_capabilities: List[str] = []
    reasoning: str = ""


class ToolGapDetector:
    """
    Detects capability gaps in MCP tool registry.

    Uses LLM-based capability extraction and schema matching to identify when
    a task requires tools that are not currently available.

    Attributes:
        mcp_session: MCP client session for tool discovery
        available_tools: Cached list of available MCP tools (loaded on first use)
    """

    def __init__(self, mcp_session: ClientSession):
        """
        Initialize ToolGapDetector with MCP session.

        Args:
            mcp_session: Active MCP client session for tool discovery

        Per tasks.md T204 (FR-009)
        """
        self.mcp_session = mcp_session
        self.available_tools: Optional[List[Any]] = None

    async def detect_missing_tools(
        self, task_description: str
    ) -> Optional[ToolGapReport]:
        """
        Detect missing tool capabilities required for a task.

        Process:
        1. Get available tools from MCP registry (with caching)
        2. Extract required capabilities from task using LLM
        3. Match capabilities against available tools
        4. Return ToolGapReport if gaps found, None otherwise

        Args:
            task_description: Natural language description of the task

        Returns:
            ToolGapReport if missing tools detected, None if all capabilities available

        Per tasks.md T205-T209 (FR-010 to FR-014)
        """
        # Phase 1: Get available tools (with caching)
        if not self.available_tools:
            tools_result = await self.mcp_session.list_tools()
            if hasattr(tools_result, "tools"):
                raw_tools = list(tools_result.tools)
            else:
                raw_tools = list(tools_result)

            # Filter to only include the 'search' tool, exclude article fetchers
            # This matches the filtering logic in _register_mcp_tools()
            excluded_tools = {
                "fetchLinuxDoArticle",
                "fetchCsdnArticle",
                "fetchGithubReadme",
                "fetchJuejinArticle",
            }
            mcp_tools = [
                tool for tool in raw_tools
                if getattr(tool, "name", None) not in excluded_tools
            ]

            # Add core memory tools that are always registered on the agent
            # These are defined in paias/agents/researcher.py _register_core_tools()
            class CoreTool:
                def __init__(self, name: str, description: str):
                    self.name = name
                    self.description = description

            core_tools = [
                CoreTool(
                    "search_memory",
                    "Search semantic memory for relevant past knowledge and prior research"
                ),
                CoreTool(
                    "store_memory",
                    "Store new research findings in long-term memory for future queries"
                ),
            ]

            self.available_tools = mcp_tools + core_tools

        # Phase 2: Analyze task with available tools using LLM
        # The LLM will semantically match required capabilities against available tools
        analysis = await self._analyze_capabilities_with_tools(
            task_description, cast(List[Any], self.available_tools)
        )

        # Phase 3: Check if any capabilities are missing
        missing = analysis.missing_capabilities

        # Phase 4: Return ToolGapReport if gaps found, None otherwise
        if missing:
            available_capability_names = [
                tool.name for tool in cast(List[Any], self.available_tools)
            ]
            return ToolGapReport(
                missing_tools=missing,
                attempted_task=task_description,
                existing_tools_checked=available_capability_names,
            )

        return None  # All capabilities available

    async def _analyze_capabilities_with_tools(
        self, task_description: str, available_tools: List[Any]
    ) -> CapabilityAnalysisResult:
        """
        Analyze task requirements against available tools using LLM.

        The LLM semantically matches required capabilities against available tools,
        understanding that tools like "search" can satisfy "web_search" requirements.

        Args:
            task_description: Natural language task description
            available_tools: List of available MCP tools with name and description

        Returns:
            CapabilityAnalysisResult with missing_capabilities and reasoning

        Per tasks.md T206 (FR-011), research.md RQ-005
        """
        # Format available tools for the prompt
        if not available_tools:
            available_tools_str = "(No tools available)"
        else:
            tool_descriptions = []
            for tool in available_tools:
                tool_name = getattr(tool, "name", "unknown")
                tool_desc = getattr(tool, "description", "") or f"Tool: {tool_name}"
                tool_descriptions.append(f"- {tool_name}: {tool_desc}")
            available_tools_str = "\n".join(tool_descriptions)

        # Create agent for capability analysis
        # NOTE: This uses the same Azure AI Foundry configuration as ResearcherAgent
        model = get_azure_model()
        analysis_agent = Agent(
            model=model, output_type=CapabilityAnalysisResult, retries=1
        )

        prompt = f"""Analyze the following task and determine if the AVAILABLE TOOLS are sufficient to complete it.

Task: "{task_description}"

AVAILABLE TOOLS:
{available_tools_str}

INSTRUCTIONS:
1. Review the "AVAILABLE TOOLS" list above.
2. Determine what capabilities are required to complete the "Task".
3. Compare the required capabilities against the available tools.
4. If a required capability is covered by an available tool (even if the name is different, e.g., "search" covers "web_search"), consider it present.

OUTPUT FORMAT:
Return a JSON object with two fields:
- "missing_capabilities": [List of STRINGS]. If ALL requirements are met, return an empty list []. If tools are missing, list generic names for what is missing (e.g., "email_access").
- "reasoning": "Brief explanation of why tools are sufficient or what is missing."

Examples:
- Task: "Search for iPhone 16" | Available: "search: Search the web using multiple engines" -> missing_capabilities: []
- Task: "Check email" | Available: "search: Search the web using multiple engines" -> missing_capabilities: ["email_access"]

Return ONLY the JSON object.
"""

        try:
            result = await analysis_agent.run(prompt)

            # Normalize payload shape across pydantic-ai versions
            analysis = parse_agent_result(result)

            # Validate result is a CapabilityAnalysisResult
            if not isinstance(analysis, CapabilityAnalysisResult):
                # Fallback: conservative approach - assume missing capability
                return CapabilityAnalysisResult(
                    missing_capabilities=["unknown_capability"],
                    reasoning="Failed to parse capability analysis result",
                )

            return analysis

        except Exception as e:
            # Conservative fallback: if analysis fails, assume missing capability
            # This prevents silently proceeding with potentially incomplete tool set
            raise Exception(
                f"Failed to analyze capabilities for task: {str(e)}. "
                "Cannot safely determine if tools are available."
            ) from e
