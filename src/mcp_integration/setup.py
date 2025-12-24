"""MCP tools setup and initialization."""

import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.core.config import settings

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
    try:
        node_version_result = subprocess.run(
            ["node", "-v"], capture_output=True, text=True, timeout=5
        )
        if node_version_result.returncode != 0:
            raise RuntimeError(
                "Failed to execute 'node -v' command. "
                "Node.js may not be installed or not in PATH. "
                f"Error: {node_version_result.stderr}"
            )
        node_version = node_version_result.stdout.strip()
    except FileNotFoundError as e:
        raise RuntimeError(
            "Node.js not found in PATH. "
            "Please install Node.js 24+ from https://nodejs.org/ "
            "or use nvm: 'nvm install 24 && nvm use 24'"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            "Timeout while checking Node.js version. "
            "Node.js installation may be corrupted."
        ) from e

    try:
        node_major = int(node_version.lstrip("v").split(".")[0])
    except (ValueError, IndexError) as e:
        raise RuntimeError(
            f"Failed to parse Node.js version: {node_version}. "
            "Expected format: vX.Y.Z (e.g., v24.0.0)"
        ) from e

    if node_major < 20:
        raise RuntimeError(
            "Node.js 20+ required for Open-WebSearch MCP server. "
            f"Detected: {node_version}. "
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
    websearch_engine = os.getenv("WEBSEARCH_ENGINE", settings.websearch_engine)
    allowed_engines = os.getenv("ALLOWED_SEARCH_ENGINES", "duckduckgo,bing,exa")
    websearch_timeout = int(os.getenv("WEBSEARCH_TIMEOUT", settings.websearch_timeout))
    websearch_max_results = int(
        os.getenv("WEBSEARCH_MAX_RESULTS", settings.websearch_max_results)
    )
    logger.info(
        "🔧 Search engine: %s, allowed: %s, max_results=%s timeout=%ss",
        websearch_engine,
        allowed_engines,
        websearch_max_results,
        websearch_timeout,
    )

    # Open-WebSearch MCP server parameters using wrapper script
    websearch_params = StdioServerParameters(
        command="node",
        args=[str(WEBSEARCH_WRAPPER)],
        env={
            **os.environ,  # Preserve existing environment
            "MODE": "stdio",  # Required for MCP stdio mode
            "DEFAULT_SEARCH_ENGINE": websearch_engine,
            "ALLOWED_SEARCH_ENGINES": allowed_engines,
            "WEBSEARCH_MAX_RESULTS": str(websearch_max_results),
            "WEBSEARCH_TIMEOUT": str(websearch_timeout),
        },
    )

    # Custom time server parameters
    # NOTE: Custom time server wiring retained for future multi-server support.
    _time_server_path = PROJECT_ROOT / "mcp-servers" / "time-context" / "server.py"
    _time_server_params = StdioServerParameters(
        command="python",
        args=[str(_time_server_path)],
    )

    # Use async context managers to keep session alive
    logger.info("🔌 Connecting to MCP server via stdio...")
    try:
        async with stdio_client(websearch_params) as (read, write):
            logger.info("✅ STDIO client connected")
            logger.info("🔧 Creating client session...")
            try:
                async with ClientSession(read, write) as session:
                    logger.info("🔧 Initializing MCP session...")
                    try:
                        await session.initialize()
                        logger.info("✅ MCP session initialized successfully")
                        # Yield the session to keep it alive for the caller
                        yield session
                        # Session cleanup happens automatically when context exits
                        logger.info("🧹 Cleaning up MCP session...")
                    except Exception as e:
                        raise RuntimeError(
                            "Failed to initialize Open-WebSearch MCP session: "
                            f"{e}. The MCP server may have crashed or failed to "
                            "start properly. Check the wrapper script and "
                            "environment variables."
                        ) from e
            except Exception as e:
                if "Failed to initialize MCP session" in str(e):
                    raise
                raise RuntimeError(
                    f"Failed to create MCP ClientSession for Open-WebSearch: {e}. "
                    "The stdio connection may have been interrupted."
                ) from e
    except FileNotFoundError as e:
        raise RuntimeError(
            "Failed to connect to Open-WebSearch MCP server: command not found. "
            "Ensure Node.js is installed and the wrapper script is accessible."
        ) from e
    except Exception as e:
        if "Failed to" in str(e):
            raise
        raise RuntimeError(
            f"Failed to connect to Open-WebSearch MCP server via stdio: {e}. "
            "Possible causes: "
            f"1) Wrapper script failed to execute (check {WEBSEARCH_WRAPPER}), "
            "2) Node.js command failed, "
            "3) Environment variables are incorrect. "
            f"Run 'node {WEBSEARCH_WRAPPER}' manually to debug."
        ) from e
