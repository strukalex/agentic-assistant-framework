"""MCP tools setup and initialization."""

import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def setup_mcp_tools() -> ClientSession:
    """
    Initialize MCP servers and return ClientSession.

    Sets up 3 MCP servers:
    1. Open-WebSearch via "npx -y @open-websearch/mcp-server"
    2. mcp-server-filesystem (read-only)
    3. Custom time server

    Returns:
        ClientSession: Initialized MCP client session

    Per research.md RQ-002 (FR-005)
    """
    # Environment variables for web search configuration
    websearch_engine = os.getenv("WEBSEARCH_ENGINE", "duckduckgo")
    websearch_max_results = os.getenv("WEBSEARCH_MAX_RESULTS", "10")
    websearch_timeout = os.getenv("WEBSEARCH_TIMEOUT_SECONDS", "30")

    # Open-WebSearch MCP server parameters
    websearch_params = StdioServerParameters(
        command="npx",
        args=["-y", "@open-websearch/mcp-server"],
        env={
            "WEBSEARCH_ENGINE": websearch_engine,
            "WEBSEARCH_MAX_RESULTS": websearch_max_results,
            "WEBSEARCH_TIMEOUT": websearch_timeout,
        },
    )

    # Get project root directory
    project_root = Path(__file__).parent.parent.parent

    # Custom time server parameters
    time_server_path = project_root / "mcp-servers" / "time-context" / "server.py"
    time_server_params = StdioServerParameters(
        command="python",
        args=[str(time_server_path)],
    )

    # For now, we'll initialize just the web search server
    # Multi-server support will be added in later tasks
    async with stdio_client(websearch_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return session
