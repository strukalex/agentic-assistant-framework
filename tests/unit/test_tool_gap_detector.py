# ruff: noqa
"""
Unit tests for ToolGapDetector.

Validates tool gap detection logic including:
- Detecting missing tools when capabilities are unavailable
- Returning None when all required capabilities exist
- LLM-based capability extraction from task descriptions
- Schema matching against available MCP tools

Per Spec 002 tasks.md T201, T202 (FR-009 to FR-014, SC-003)
"""
# ruff: noqa

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.tool_gap_detector import ToolGapDetector
from src.models.tool_gap_report import ToolGapReport


class MockTool:
    """Mock MCP tool for testing."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description


class TestToolGapDetectorInit:
    """Test ToolGapDetector initialization."""

    def test_init_stores_mcp_session(self):
        """Test that __init__ stores MCP session reference."""
        mock_session = MagicMock()
        detector = ToolGapDetector(mcp_session=mock_session)

        assert detector.mcp_session == mock_session
        assert detector.available_tools is None  # Not loaded yet


class TestDetectMissingTools:
    """Test detect_missing_tools() method."""

    @pytest.mark.asyncio
    async def test_detect_missing_tools_with_gap(self):
        """Test that detect_missing_tools() returns ToolGapReport when tool is missing.

        Per tasks.md T201 (FR-009, FR-011, FR-012, FR-013)
        """
        # Mock MCP session with limited tools
        mock_session = MagicMock()
        mock_session.list_tools = AsyncMock(
            return_value=[
                MockTool("web_search", "Search the web"),
                MockTool("read_file", "Read a file"),
                MockTool("get_current_time", "Get current time"),
            ]
        )

        detector = ToolGapDetector(mcp_session=mock_session)

        # Mock LLM capability extraction to return required capabilities
        with patch.object(
            detector, "_extract_capabilities", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = ["financial_data_api", "account_access"]

            # Task requiring financial tools (which don't exist)
            task = "Retrieve my stock portfolio performance for Q3 2024"
            report = await detector.detect_missing_tools(task)

            # Should return ToolGapReport with missing tools
            assert report is not None
            assert isinstance(report, ToolGapReport)
            assert len(report.missing_tools) == 2
            assert "financial_data_api" in report.missing_tools
            assert "account_access" in report.missing_tools
            assert report.attempted_task == task
            assert "web_search" in report.existing_tools_checked
            assert "read_file" in report.existing_tools_checked
            assert "get_current_time" in report.existing_tools_checked

    @pytest.mark.asyncio
    async def test_detect_missing_tools_all_available(self):
        """Test that detect_missing_tools() returns None when all tools available.

        Per tasks.md T202 (FR-014)
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

        # Mock LLM capability extraction to return capabilities we have
        with patch.object(
            detector, "_extract_capabilities", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = ["web_search", "search_memory"]

            # Task requiring only available tools
            task = "Search the web for information about Python and check my memory"
            report = await detector.detect_missing_tools(task)

            # Should return None (no gaps)
            assert report is None

    @pytest.mark.asyncio
    async def test_detect_missing_tools_caches_tool_list(self):
        """Test that detect_missing_tools() caches available tools after first call."""
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
            mock_extract.return_value = ["web_search"]

            # First call
            await detector.detect_missing_tools("task 1")
            assert mock_session.list_tools.call_count == 1

            # Second call should use cached tools
            await detector.detect_missing_tools("task 2")
            assert mock_session.list_tools.call_count == 1  # Still 1, not 2

    @pytest.mark.asyncio
    async def test_detect_missing_tools_partial_match(self):
        """Test detect_missing_tools() with some tools available, some missing."""
        mock_session = MagicMock()
        mock_session.list_tools = AsyncMock(
            return_value=[
                MockTool("web_search", "Search the web"),
                MockTool("read_file", "Read a file"),
            ]
        )

        detector = ToolGapDetector(mcp_session=mock_session)

        with patch.object(
            detector, "_extract_capabilities", new_callable=AsyncMock
        ) as mock_extract:
            # Require 3 tools: 2 available, 1 missing
            mock_extract.return_value = ["web_search", "read_file", "send_email"]

            task = "Search web, read file, and send results via email"
            report = await detector.detect_missing_tools(task)

            # Should report only the missing tool
            assert report is not None
            assert len(report.missing_tools) == 1
            assert "send_email" in report.missing_tools
            assert "web_search" not in report.missing_tools  # Available
            assert "read_file" not in report.missing_tools  # Available

    @pytest.mark.asyncio
    async def test_detect_missing_tools_empty_mcp_registry(self):
        """Test detect_missing_tools() when MCP registry is empty (edge case)."""
        mock_session = MagicMock()
        mock_session.list_tools = AsyncMock(return_value=[])  # No tools available

        detector = ToolGapDetector(mcp_session=mock_session)

        with patch.object(
            detector, "_extract_capabilities", new_callable=AsyncMock
        ) as mock_extract:
            mock_extract.return_value = ["web_search"]

            task = "Search the web"
            report = await detector.detect_missing_tools(task)

            # Should report all required tools as missing
            assert report is not None
            assert len(report.missing_tools) == 1
            assert "web_search" in report.missing_tools
            assert len(report.existing_tools_checked) == 0  # Empty registry


class TestCapabilityExtraction:
    """Test _extract_capabilities() LLM-based extraction."""

    @pytest.mark.asyncio
    async def test_extract_capabilities_simple_task(self):
        """Test capability extraction for simple task."""
        # This will be tested via integration tests with real LLM
        # Unit test just ensures method exists and is callable
        mock_session = MagicMock()
        detector = ToolGapDetector(mcp_session=mock_session)

        # _extract_capabilities will be implemented as part of T206
        # For now, verify it's defined
        assert hasattr(detector, "_extract_capabilities")
