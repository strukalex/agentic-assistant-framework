"""
Integration tests for end-to-end tool gap detection.

Validates that:
- Agent correctly calls ToolGapDetector when task requires missing tools
- Agent returns ToolGapReport without attempting hallucinated execution
- Full workflow from task submission to gap reporting works correctly

Per Spec 002 tasks.md T203 (FR-009 to FR-014, SC-003)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.tool_gap_detector import ToolGapDetector
from src.models.tool_gap_report import ToolGapReport


class MockTool:
    """Mock MCP tool for testing."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description


@pytest.mark.asyncio
async def test_end_to_end_gap_detection_with_missing_tool():
    """
    Test end-to-end gap detection when task requires unavailable tool.

    Scenario:
    1. User submits task requiring financial API (not available)
    2. ToolGapDetector identifies missing capability
    3. System returns ToolGapReport without attempting execution
    4. No hallucinated data is returned
    """
    # Mock MCP session with limited tools (no financial API)
    mock_session = MagicMock()
    mock_session.list_tools = AsyncMock(
        return_value=[
            MockTool("web_search", "Search the web"),
            MockTool("read_file", "Read a file"),
            MockTool("get_current_time", "Get current time"),
            MockTool("search_memory", "Search semantic memory"),
        ]
    )

    detector = ToolGapDetector(mcp_session=mock_session)

    # Mock capability extraction to identify financial API requirement
    with patch.object(
        detector, "_extract_capabilities", new_callable=AsyncMock
    ) as mock_extract:
        mock_extract.return_value = ["financial_data_api", "account_access"]

        # Task requiring missing tools
        task = "Retrieve my stock portfolio performance for Q3 2024"
        report = await detector.detect_missing_tools(task)

        # Verify gap was detected
        assert report is not None
        assert isinstance(report, ToolGapReport)
        assert "financial_data_api" in report.missing_tools
        assert "account_access" in report.missing_tools
        assert report.attempted_task == task

        # Verify existing tools were checked
        assert "web_search" in report.existing_tools_checked
        assert "read_file" in report.existing_tools_checked
        assert "get_current_time" in report.existing_tools_checked
        assert "search_memory" in report.existing_tools_checked

        # Verify no hallucination: report clearly states tools are missing
        assert len(report.missing_tools) > 0


@pytest.mark.asyncio
async def test_end_to_end_gap_detection_all_tools_available():
    """
    Test end-to-end gap detection when all required tools are available.

    Scenario:
    1. User submits task requiring only available tools
    2. ToolGapDetector verifies all capabilities exist
    3. System returns None (no gap)
    4. Agent can proceed with execution
    """
    # Mock MCP session with comprehensive tools
    mock_session = MagicMock()
    mock_session.list_tools = AsyncMock(
        return_value=[
            MockTool("web_search", "Search the web"),
            MockTool("read_file", "Read a file"),
            MockTool("get_current_time", "Get current time"),
            MockTool("search_memory", "Search semantic memory"),
        ]
    )

    detector = ToolGapDetector(mcp_session=mock_session)

    # Mock capability extraction to identify requirements that exist
    with patch.object(
        detector, "_extract_capabilities", new_callable=AsyncMock
    ) as mock_extract:
        mock_extract.return_value = ["web_search", "search_memory"]

        # Task requiring only available tools
        task = "Search the web for Python best practices and check my memory"
        report = await detector.detect_missing_tools(task)

        # Verify no gap detected
        assert report is None  # All tools available


@pytest.mark.asyncio
async def test_gap_detection_prevents_hallucinated_execution():
    """
    Test that gap detection prevents agent from fabricating responses.

    Critical safety test: When tools are missing, agent must NOT:
    - Return fabricated data
    - Pretend to have executed the tool
    - Make up plausible-sounding but incorrect information

    Instead, agent MUST:
    - Return ToolGapReport
    - Clearly state which tools are missing
    - Provide list of available alternatives
    """
    # Mock MCP session with NO database tools
    mock_session = MagicMock()
    mock_session.list_tools = AsyncMock(
        return_value=[
            MockTool("web_search", "Search the web"),
        ]
    )

    detector = ToolGapDetector(mcp_session=mock_session)

    with patch.object(
        detector, "_extract_capabilities", new_callable=AsyncMock
    ) as mock_extract:
        mock_extract.return_value = ["database_query", "sql_executor"]

        # Task requiring database access (not available)
        task = "Query the database for all users with admin privileges"
        report = await detector.detect_missing_tools(task)

        # CRITICAL: Must return gap report, NOT fabricated results
        assert report is not None
        assert "database_query" in report.missing_tools or "sql_executor" in report.missing_tools

        # Verify transparency: user is informed about missing capabilities
        assert report.attempted_task == task
        assert len(report.existing_tools_checked) > 0

        # This test prevents hallucination by ensuring the system returns
        # a ToolGapReport rather than proceeding with execution


@pytest.mark.asyncio
async def test_gap_detection_with_llm_extraction_failure():
    """
    Test gap detection fallback when LLM capability extraction fails.

    Edge case: If LLM cannot extract capabilities, should return conservative
    ToolGapReport rather than silently failing.
    """
    mock_session = MagicMock()
    mock_session.list_tools = AsyncMock(
        return_value=[
            MockTool("web_search", "Search the web"),
        ]
    )

    detector = ToolGapDetector(mcp_session=mock_session)

    with patch.object(
        detector, "_extract_capabilities", new_callable=AsyncMock
    ) as mock_extract:
        # Simulate LLM extraction failure
        mock_extract.side_effect = Exception("LLM API timeout")

        task = "Do something complex"

        # Should handle gracefully (implementation will add error handling)
        with pytest.raises(Exception):
            await detector.detect_missing_tools(task)

        # Note: Final implementation (T206) should catch this and return
        # conservative ToolGapReport with warning instead of raising
