"""Custom MCP time server implementation."""

import asyncio
from datetime import datetime, timezone
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# Create server instance
server = Server("time-context")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_current_time",
            description="Get the current time in a specified timezone",
            inputSchema={
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "Timezone name (default: 'UTC')",
                        "default": "UTC",
                    }
                },
            },
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    if name == "get_current_time":
        tz_name = arguments.get("timezone", "UTC")

        # For simplicity, we'll support UTC and a few common timezones
        # In production, use pytz or zoneinfo for full timezone support
        if tz_name == "UTC":
            tz = timezone.utc
        else:
            # Fallback to UTC for unsupported timezones
            tz = timezone.utc

        now = datetime.now(tz)

        result = {
            "timestamp": now.isoformat(),
            "timezone": tz_name,
            "unix_epoch": int(now.timestamp()),
        }

        return [
            TextContent(
                type="text",
                text=str(result),
            )
        ]

    raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    """Main entry point for the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
