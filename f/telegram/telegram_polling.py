"""Telegram Bot using Polling - Windmill-compatible version.

This script runs a SINGLE polling cycle, processes any pending messages,
and then exits. For continuous operation, use Windmill's scheduling feature
to run this script periodically (e.g., every 30 seconds).

Usage:
    # Run directly with Python (from project root)
    python f/telegram/telegram_polling.py

    # Or via Windmill (single poll cycle)
    wmill script run f/telegram/telegram_polling

    # For continuous polling, set up a Windmill schedule

Environment variables:
    TELEGRAM_BOT_TOKEN: Your bot token from @BotFather
    LLM_PROVIDER: 'azure' or 'local' (for Ollama)
"""
# requirements:
# file:///app
# httpx>=0.25.0
# pydantic>=2.0.0

from __future__ import annotations

# =============================================================================
# MINIMAL DEBUG VERSION - Progressively uncomment to find the issue
# =============================================================================
import sys
import os

print("=== TELEGRAM POLLING BOT - MINIMAL DEBUG ===")
print(f"Step 1: Script started")
print(f"Python: {sys.version_info.major}.{sys.version_info.minor}")
print(f"CWD: {os.getcwd()}")

# Step 2: Check environment
print(f"Step 2: Checking environment...")
token = os.environ.get("TELEGRAM_BOT_TOKEN", "<NOT SET>")
token_status = "SET" if token != "<NOT SET>" else "MISSING"
print(f"  TELEGRAM_BOT_TOKEN: {token_status}")

print(f"Step 3: Imports starting...")

# # Uncomment to test imports
# import asyncio
# import logging
# print(f"Step 3a: Core imports OK")

# # Uncomment to test httpx
# import httpx
# print(f"Step 3b: httpx OK - version {httpx.__version__}")

# # Uncomment to test wmill
# try:
#     import wmill
#     print(f"Step 3c: wmill OK")
# except ImportError:
#     print(f"Step 3c: wmill not available (OK for local dev)")

print(f"Step 4: Defining main function...")


def main(
    polling_timeout: int = 10,
    max_polls: int = 1,
) -> dict:
    """Run a single polling cycle (Windmill-compatible).

    Args:
        polling_timeout: Long polling timeout in seconds (default: 10)
        max_polls: Number of polling cycles to run (default: 1)

    Returns:
        Dict with status information
    """
    print(f"=== MAIN FUNCTION CALLED ===")
    print(f"  polling_timeout={polling_timeout}")
    print(f"  max_polls={max_polls}")

    # # Uncomment to test actual polling
    # import asyncio
    # return asyncio.run(_async_main(polling_timeout, max_polls))

    print(f"=== MAIN COMPLETE (stub) ===")
    return {"status": "ok", "message": "Minimal debug version - no actual polling"}


# # Uncomment to enable actual polling logic
# async def _async_main(polling_timeout: int, max_polls: int) -> dict:
#     """Async implementation - single polling cycle."""
#     import httpx
#     import logging
#
#     logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
#     logger = logging.getLogger(__name__)
#
#     print(f"Step 5: Async main started")
#
#     # Get token
#     token = os.environ.get("TELEGRAM_BOT_TOKEN")
#     if not token:
#         print(f"ERROR: TELEGRAM_BOT_TOKEN not set")
#         return {"status": "error", "reason": "TELEGRAM_BOT_TOKEN not configured"}
#
#     base_url = f"https://api.telegram.org/bot{token}"
#     print(f"Step 6: Token found, base URL configured")
#
#     # Load last_update_id from Windmill state (or use None)
#     last_update_id = None
#     try:
#         import wmill
#         state = wmill.get_state() or {}
#         last_update_id = state.get("last_update_id")
#         print(f"Step 7: Loaded state, last_update_id={last_update_id}")
#     except Exception as e:
#         print(f"Step 7: Could not load state: {e}")
#
#     # Perform polling cycles
#     messages_processed = 0
#     for poll_num in range(max_polls):
#         print(f"Step 8: Poll cycle {poll_num + 1}/{max_polls}")
#
#         # Build params
#         params = {"timeout": polling_timeout, "allowed_updates": ["message"]}
#         if last_update_id is not None:
#             params["offset"] = last_update_id + 1
#
#         try:
#             async with httpx.AsyncClient(timeout=polling_timeout + 10) as client:
#                 response = await client.get(f"{base_url}/getUpdates", params=params)
#                 result = response.json()
#
#                 if result.get("ok"):
#                     updates = result.get("result", [])
#                     print(f"Step 9: Got {len(updates)} update(s)")
#
#                     for update in updates:
#                         update_id = update.get("update_id")
#                         if update_id:
#                             last_update_id = update_id
#
#                         # Process message
#                         if "message" in update and "text" in update["message"]:
#                             msg = update["message"]
#                             text = msg["text"][:50]
#                             print(f"  Message: {text}...")
#                             messages_processed += 1
#
#                             # TODO: Call chat agent here
#                             # await process_message(update["message"])
#                 else:
#                     print(f"Step 9: API error: {result.get('description')}")
#         except httpx.TimeoutException:
#             print(f"Step 9: Timeout (no new messages)")
#         except Exception as e:
#             print(f"Step 9: Error: {e}")
#
#     # Save state
#     try:
#         import wmill
#         wmill.set_state({"last_update_id": last_update_id})
#         print(f"Step 10: Saved state, last_update_id={last_update_id}")
#     except Exception as e:
#         print(f"Step 10: Could not save state: {e}")
#
#     print(f"=== POLLING COMPLETE ===")
#     return {
#         "status": "ok",
#         "messages_processed": messages_processed,
#         "last_update_id": last_update_id,
#     }


# Windmill script metadata
__windmill__ = {
    "description": "Telegram bot polling - single cycle (schedule for continuous)",
    "summary": "Telegram Polling Bot",
    "schema": {
        "properties": {
            "polling_timeout": {
                "type": "integer",
                "description": "Long polling timeout in seconds",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
            "max_polls": {
                "type": "integer",
                "description": "Number of polling cycles per run",
                "default": 1,
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": [],
    },
}

print(f"Step 5: Module load complete")

if __name__ == "__main__":
    print(f"Step 6: Running as __main__")
    result = main()
    print(f"Result: {result}")
