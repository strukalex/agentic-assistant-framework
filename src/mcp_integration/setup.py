"""MCP tools setup and initialization."""

import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncIterator
import subprocess

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Project root directory (3 levels up from this file: src/mcp_integration/setup.py)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# Path to embedded open-websearch binary
NODE_OPEN_WEBSEARCH = PROJECT_ROOT / "node_modules" / ".bin" / "open-websearch"
# Path to wrapper script that filters stdout to comply with MCP protocol
WEBSEARCH_WRAPPER = PROJECT_ROOT / "mcp-servers" / "websearch-wrapper.js"


@asynccontextmanager
async def setup_mcp_tools() -> AsyncIterator[ClientSession]:
    """
    Initialize MCP servers and return ClientSession as a context manager.

    Sets up the Open-WebSearch MCP server via embedded open-websearch package.
    The session remains open as long as the context is active.

    Yields:
        ClientSession: Initialized MCP client session

    Example:
        async with setup_mcp_tools() as session:
            tools = await session.list_tools()
            # Use session...
        # Session is automatically closed here

    Per research.md RQ-002 (FR-005)

    Note: Requires 'npm install' to be run first to install open-websearch dependency.
    """
    import logging
    logger = logging.getLogger(__name__)

    logger.info("🔧 Validating Node.js version...")
    # Validate Node.js version (open-websearch requires Node 20+; prefer 24+)
    node_version = subprocess.run(
        ["node", "-v"], capture_output=True, text=True
    ).stdout.strip()
    try:
        node_major = int(node_version.lstrip("v").split(".")[0])
    except Exception:
        node_major = 0

    if node_major < 20:
        raise RuntimeError(
            f"Node.js 20+ required for Open-WebSearch MCP server. Detected: {node_version}. "
            "Run `nvm use 24` (or upgrade Node) and reinstall npm deps."
        )
    logger.info(f"✅ Node.js version: {node_version}")

    # Check if embedded binary exists
    logger.info("🔧 Checking for open-websearch binary...")
    if not NODE_OPEN_WEBSEARCH.exists():
        raise RuntimeError(
            f"Open-WebSearch MCP server not found at {NODE_OPEN_WEBSEARCH}. "
            "Please run 'npm install' to install dependencies."
        )
    logger.info(f"✅ Found open-websearch at {NODE_OPEN_WEBSEARCH}")

    # Check if wrapper script exists
    logger.info("🔧 Checking for wrapper script...")
    if not WEBSEARCH_WRAPPER.exists():
        raise RuntimeError(
            f"Wrapper script not found at {WEBSEARCH_WRAPPER}. "
            "The wrapper is required to filter stdout for MCP protocol compliance."
        )
    logger.info(f"✅ Found wrapper script at {WEBSEARCH_WRAPPER}")

    # Environment variables for web search configuration
    # Use environment variable names that open-websearch expects
    websearch_engine = os.getenv("WEBSEARCH_ENGINE", "duckduckgo")
    allowed_engines = os.getenv(
        "ALLOWED_SEARCH_ENGINES", "duckduckgo,bing,exa"
    )
    logger.info(f"🔧 Search engine: {websearch_engine}, allowed: {allowed_engines}")

    # Open-WebSearch MCP server parameters using wrapper script
    websearch_params = StdioServerParameters(
        command="node",
        args=[str(WEBSEARCH_WRAPPER)],
        env={
            **os.environ,  # Preserve existing environment
            "MODE": "stdio",  # Required for MCP stdio mode
            "DEFAULT_SEARCH_ENGINE": websearch_engine,
            "ALLOWED_SEARCH_ENGINES": allowed_engines,
        },
    )

    # Custom time server parameters
    time_server_path = PROJECT_ROOT / "mcp-servers" / "time-context" / "server.py"
    time_server_params = StdioServerParameters(
        command="python",
        args=[str(time_server_path)],
    )

    # Use async context managers to keep session alive
    logger.info("🔌 Connecting to MCP server via stdio...")
    async with stdio_client(websearch_params) as (read, write):
        logger.info("✅ STDIO client connected")
        logger.info("🔧 Creating client session...")
        async with ClientSession(read, write) as session:
            logger.info("🔧 Initializing MCP session...")
            await session.initialize()
            logger.info("✅ MCP session initialized successfully")
            # Yield the session to keep it alive for the caller
            yield session
            # Session cleanup happens automatically when context exits
            logger.info("🧹 Cleaning up MCP session...")
