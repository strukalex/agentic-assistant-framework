"""Telegram Bot using Long Polling - for local development without webhooks.

This script runs as a long-polling bot that continuously checks for new messages
from Telegram. It reuses the same chat agent logic as the webhook-based approach.

Usage:
    # Run directly with Python (from project root)
    python f/telegram/telegram_polling.py

    # Or via Windmill (will run until manually stopped)
    wmill script run f/telegram/telegram_polling

    # Stop with Ctrl+C

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
# Module-level diagnostics (runs at import time - always shows in Windmill)
# =============================================================================
import sys
import os

print("=== TELEGRAM POLLING BOT - MODULE LOAD ===")
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Working directory: {os.getcwd()}")
print(f"__file__: {__file__}")

# Check key environment variables
_key_env_vars = ["TELEGRAM_BOT_TOKEN", "LLM_PROVIDER", "LLM_MODEL_NAME", "LLM_BASE_URL"]
print("Environment variables:")
for v in _key_env_vars:
    val = os.environ.get(v, "<NOT SET>")
    # Mask sensitive values
    if "TOKEN" in v and val != "<NOT SET>":
        val = val[:10] + "..." if len(val) > 10 else "***"
    print(f"  {v}: {val}")

print("Loading imports...")

import asyncio
import logging
import signal
from typing import Any, Optional

print("Core imports complete")

# Add project root to path for local development
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
print(f"Project root added to path: {project_root}")

# Configure logging (same as run_research.py)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Silence httpx/httpcore verbose logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

print("Logging configured")

# Try to import wmill for Windmill-specific functionality
try:
    import wmill
    WMILL_AVAILABLE = True
    print("wmill imported successfully")
except ImportError:
    wmill = None  # type: ignore[assignment]
    WMILL_AVAILABLE = False
    print("wmill not available (running outside Windmill)")

# Check if httpx is available
try:
    import httpx
    print(f"httpx version: {httpx.__version__}")
except ImportError as e:
    print(f"ERROR: httpx not available: {e}")

print("=== MODULE LOAD COMPLETE ===")

# =============================================================================
# End of module-level diagnostics
# =============================================================================

# Global flag for graceful shutdown
_shutdown_requested = False


def signal_handler(signum: int, frame: Any) -> None:
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    logger.info("Shutdown signal received, stopping polling...")
    _shutdown_requested = True


class TelegramPollingBot:
    """Telegram bot that uses long polling to receive updates."""

    def __init__(self, token: str, polling_timeout: int = 10):
        """Initialize the polling bot.

        Args:
            token: Telegram bot token
            polling_timeout: Long polling timeout in seconds (max 50, default 10 for Windmill)
        """
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        # Use shorter timeout for Windmill to avoid job ping timeouts
        self.polling_timeout = min(polling_timeout, 50)
        self.last_update_id: Optional[int] = None
        self._process_message = None
        logger.info(f"Bot initialized with polling timeout: {self.polling_timeout}s")

    async def get_updates(self, offset: Optional[int] = None) -> list[dict]:
        """Fetch new updates from Telegram using long polling."""
        import httpx

        params: dict[str, Any] = {
            "timeout": self.polling_timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            params["offset"] = offset

        try:
            async with httpx.AsyncClient(timeout=self.polling_timeout + 10) as client:
                response = await client.get(f"{self.base_url}/getUpdates", params=params)
                result = response.json()

                if result.get("ok"):
                    updates = result.get("result", [])
                    if updates:
                        logger.info(f"Received {len(updates)} update(s)")
                    return updates
                else:
                    logger.error(f"Failed to get updates: {result.get('description')}")
                    return []
        except httpx.TimeoutException:
            # Timeout is normal for long polling when no updates
            logger.debug("Polling timeout (normal, no new messages)")
            return []
        except Exception as e:
            logger.error(f"Error fetching updates: {e}")
            return []

    async def get_me(self) -> Optional[dict]:
        """Get bot information to verify token is valid."""
        import httpx

        logger.info("Verifying bot token...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/getMe")
                result = response.json()
                if result.get("ok"):
                    bot_info = result.get("result")
                    logger.info(f"Bot verified: @{bot_info.get('username')} ({bot_info.get('first_name')})")
                    return bot_info
                else:
                    logger.error(f"Failed to get bot info: {result.get('description')}")
                    return None
        except Exception as e:
            logger.error(f"Error getting bot info: {e}")
            return None

    async def delete_webhook(self) -> bool:
        """Delete any existing webhook to enable polling mode."""
        import httpx

        logger.info("Deleting any existing webhook...")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/deleteWebhook",
                    json={"drop_pending_updates": False},
                )
                result = response.json()
                if result.get("ok"):
                    logger.info("Webhook deleted, polling mode enabled")
                    return True
                else:
                    logger.warning(f"Failed to delete webhook: {result.get('description')}")
                    return False
        except Exception as e:
            logger.error(f"Error deleting webhook: {e}")
            return False

    async def handle_update(self, update: dict) -> None:
        """Handle a single update from Telegram using the shared chat agent."""
        # Lazy load the process_message function
        if self._process_message is None:
            logger.info("Loading chat agent module...")
            self._process_message = _get_process_message_func()
            logger.info("Chat agent module loaded successfully")

        # Skip non-message updates
        if "message" not in update:
            logger.debug("Skipping non-message update")
            return

        message = update["message"]

        # Skip non-text messages
        if "text" not in message:
            logger.debug("Skipping non-text message")
            return

        chat_id = str(message["chat"]["id"])
        user_message = message["text"]
        message_id = message.get("message_id")
        user = message.get("from", {})
        user_id = user.get("id")
        username = user.get("username", "unknown")
        first_name = user.get("first_name", "User")

        preview = user_message[:50] + "..." if len(user_message) > 50 else user_message
        logger.info(f"MESSAGE from {first_name} (@{username}): {preview}")

        # Use the shared chat agent to process and respond
        try:
            result = await self._process_message(
                message=user_message,
                chat_id=chat_id,
                message_id=message_id,
                user_id=user_id,
                username=username,
                first_name=first_name,
            )

            if result.get("status") == "success":
                logger.info(f"Response sent successfully (length: {result.get('response_length', 0)})")
            else:
                logger.error(f"Failed to process message: {result.get('reason')}")
        except Exception as e:
            logger.exception(f"Exception processing message: {e}")

    async def run(self) -> None:
        """Run the polling loop."""
        global _shutdown_requested

        logger.info("=" * 60)
        logger.info("STARTING TELEGRAM POLLING BOT")
        logger.info("=" * 60)

        # Verify bot token
        bot_info = await self.get_me()
        if not bot_info:
            logger.error("Failed to verify bot token. Please check TELEGRAM_BOT_TOKEN.")
            return

        logger.info(f"Bot: @{bot_info.get('username')} ({bot_info.get('first_name')})")
        logger.info(f"Polling timeout: {self.polling_timeout}s")

        # Delete any existing webhook to enable polling
        await self.delete_webhook()

        logger.info("Entering polling loop - waiting for messages...")
        logger.info("=" * 60)

        poll_count = 0
        # Main polling loop
        while not _shutdown_requested:
            try:
                poll_count += 1
                # Log every 6th poll (roughly once per minute with 10s timeout)
                if poll_count % 6 == 1:
                    logger.info(f"Polling cycle {poll_count} - waiting for messages...")

                # Calculate offset (last_update_id + 1 to acknowledge previous updates)
                offset = self.last_update_id + 1 if self.last_update_id else None

                # Fetch updates
                updates = await self.get_updates(offset=offset)

                # Process each update
                for update in updates:
                    update_id = update.get("update_id")
                    if update_id:
                        self.last_update_id = update_id

                    await self.handle_update(update)

            except asyncio.CancelledError:
                logger.info("Polling cancelled")
                break
            except Exception as e:
                logger.exception(f"Error in polling loop: {e}")
                # Wait before retrying
                await asyncio.sleep(5)

        logger.info("Polling loop exited")


def _get_process_message_func():
    """Get the process_message function, handling different import contexts."""
    logger.info("Attempting to import telegram_chat_agent...")

    # Try importing from the same directory first (for direct execution)
    try:
        from telegram_chat_agent import _async_main
        logger.info("Imported from telegram_chat_agent (direct import)")
        return _async_main
    except ImportError as e:
        logger.debug(f"Direct import failed: {e}")

    # Try Windmill-style import
    try:
        from f.telegram.telegram_chat_agent import _async_main
        logger.info("Imported from f.telegram.telegram_chat_agent (Windmill style)")
        return _async_main
    except ImportError as e:
        logger.debug(f"Windmill-style import failed: {e}")

    # Fallback: import from relative path using importlib
    logger.info("Trying importlib fallback...")
    import importlib.util
    chat_agent_path = os.path.join(os.path.dirname(__file__), "telegram_chat_agent.py")
    logger.info(f"Looking for module at: {chat_agent_path}")

    if not os.path.exists(chat_agent_path):
        logger.error(f"File not found: {chat_agent_path}")
        raise ImportError(f"telegram_chat_agent.py not found at {chat_agent_path}")

    spec = importlib.util.spec_from_file_location("telegram_chat_agent", chat_agent_path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        logger.info("Imported via importlib")
        return module._async_main

    raise ImportError("Could not import telegram_chat_agent module")


async def _async_main(
    polling_timeout: int = 10,
    max_runtime_seconds: Optional[int] = None,
) -> dict[str, Any]:
    """Async implementation of the polling bot."""
    logger.info("=" * 80)
    logger.info("TELEGRAM POLLING BOT - ASYNC MAIN")
    logger.info("=" * 80)
    logger.info(f"Arguments: polling_timeout={polling_timeout}, max_runtime_seconds={max_runtime_seconds}")

    # Load environment variables (for local development)
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("Loaded .env file")
    except ImportError:
        logger.debug("python-dotenv not available, using existing env vars")

    # Get Telegram bot token
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")

    if not telegram_token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        # List available TELEGRAM-related env vars for debugging
        telegram_vars = [k for k in os.environ.keys() if "TELEGRAM" in k.upper()]
        logger.error(f"Available TELEGRAM-related env vars: {telegram_vars}")
        return {"status": "error", "reason": "TELEGRAM_BOT_TOKEN not configured"}

    # Log token info (masked)
    logger.info(f"Token found (length: {len(telegram_token)}, starts with: {telegram_token[:10]}...)")

    # Create and run bot
    bot = TelegramPollingBot(token=telegram_token, polling_timeout=polling_timeout)

    if max_runtime_seconds:
        logger.info(f"Running with timeout: {max_runtime_seconds}s")
        try:
            await asyncio.wait_for(bot.run(), timeout=max_runtime_seconds)
        except asyncio.TimeoutError:
            logger.info(f"Max runtime reached ({max_runtime_seconds}s) - stopping")
    else:
        logger.info("Running indefinitely (no timeout set)")
        await bot.run()

    logger.info("Bot stopped")
    return {"status": "stopped", "reason": "shutdown_requested"}


def main(
    polling_timeout: int = 10,
    max_runtime_seconds: Optional[int] = None,
) -> dict[str, Any]:
    """Run the Telegram polling bot.

    This starts a long-running polling loop that continuously checks for
    new messages from Telegram. Uses the same chat agent as the webhook approach.

    Args:
        polling_timeout: Long polling timeout in seconds (default: 10, max: 50)
            Using 10s default for Windmill compatibility.
        max_runtime_seconds: Maximum runtime before stopping (None = run forever)
            Set this when running in Windmill to prevent infinite jobs.

    Returns:
        Dict with status information
    """
    print("=== TELEGRAM POLLING BOT - MAIN FUNCTION CALLED ===")
    print(f"Arguments: polling_timeout={polling_timeout}, max_runtime_seconds={max_runtime_seconds}")

    logger.info("=" * 80)
    logger.info("TELEGRAM POLLING BOT")
    logger.info("=" * 80)
    logger.info(f"Arguments: polling_timeout={polling_timeout}, max_runtime_seconds={max_runtime_seconds}")

    # Set up signal handlers for graceful shutdown
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        logger.info("Signal handlers configured")
    except Exception as e:
        logger.warning(f"Could not set signal handlers: {e}")

    logger.info("Starting asyncio event loop...")

    return asyncio.run(
        _async_main(
            polling_timeout=polling_timeout,
            max_runtime_seconds=max_runtime_seconds,
        )
    )


# Windmill script metadata
__windmill__ = {
    "description": "Telegram bot using long polling - for local development",
    "summary": "Telegram Polling Bot",
    "schema": {
        "properties": {
            "polling_timeout": {
                "type": "integer",
                "description": "Long polling timeout in seconds (default 10 for Windmill, max 50)",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
            "max_runtime_seconds": {
                "type": "integer",
                "description": "Maximum runtime before stopping (leave empty to run forever)",
                "minimum": 10,
            },
        },
        "required": [],
    },
}


if __name__ == "__main__":
    # Run directly with Python
    main()
