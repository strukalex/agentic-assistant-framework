"""
Tool Gap Detection for ResearcherAgent.

Detects when a task requires tools/capabilities that are not available in the
current MCP tool registry, enabling honest reporting of limitations instead of
hallucinated execution.

Per Spec 002 research.md RQ-005, tasks.md T204-T209 (FR-009 to FR-014, SC-003)
"""

from typing import Any, List, Optional, cast

from mcp import ClientSession
from pydantic_ai import Agent

from src.core.llm import get_azure_model, parse_agent_result
from src.models.tool_gap_report import ToolGapReport


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
            self.available_tools = [
                tool for tool in raw_tools
                if getattr(tool, "name", None) not in excluded_tools
            ]

        # Phase 2: Extract required capabilities from task using LLM
        required_capabilities = await self._extract_capabilities(task_description)

        # Phase 3: Match capabilities to tools
        available_capability_names = [
            tool.name for tool in cast(List[Any], self.available_tools)
        ]
        missing = [
            cap
            for cap in required_capabilities
            if cap not in available_capability_names
        ]

        # Phase 4: Return ToolGapReport if gaps found, None otherwise
        if missing:
            return ToolGapReport(
                missing_tools=missing,
                attempted_task=task_description,
                existing_tools_checked=available_capability_names,
            )

        return None  # All capabilities available

    async def _extract_capabilities(self, task_description: str) -> List[str]:
        """
        Extract required capabilities from task description using LLM.

        Uses DeepSeek 3.2 to analyze the task and identify required tool
        capabilities as a JSON array of capability names.

        Args:
            task_description: Natural language task description

        Returns:
            List of required capability names (e.g., ["web_search", "file_access"])

        Per tasks.md T206 (FR-011), research.md RQ-005
        """
        # Create a simple agent for capability extraction
        # NOTE: This uses the same Azure AI Foundry configuration as ResearcherAgent
        model = get_azure_model()
        extraction_agent = Agent(model=model, output_type=List[str], retries=1)

        prompt = f"""Analyze this task and list the required tool capabilities.

Task: {task_description}

Return a JSON array of capability names that would be needed to complete this task.
Use simple, descriptive names like "web_search", "file_access", "database_query", etc.

Examples:
- "Search the web for Python best practices" → ["web_search"]
- "Read my config file and search the web" → ["file_access", "web_search"]
- "Get my stock portfolio performance" → ["financial_data_api", "account_access"]

Return ONLY the JSON array, no additional text.
"""

        try:
            result = await extraction_agent.run(prompt)

            # Normalize payload shape across pydantic-ai versions
            capabilities = parse_agent_result(result)

            # Validate result is a list
            if not isinstance(capabilities, list):
                # Fallback: conservative approach
                return [
                    "unknown_capability"
                ]  # Will trigger gap detection as safety measure

            return capabilities

        except Exception as e:
            # Conservative fallback: if extraction fails, assume missing capability
            # This prevents silently proceeding with potentially incomplete tool set
            raise Exception(
                f"Failed to extract capabilities from task: {str(e)}. "
                "Cannot safely determine if tools are available."
            ) from e
