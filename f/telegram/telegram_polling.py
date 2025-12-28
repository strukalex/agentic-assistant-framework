#py: >=3.11,<3.12

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

from __future__ import annotations

# === DIAGNOSTIC LOGGING - REMOVE AFTER DEBUGGING ===
import sys
import os as _os
print(f"=== PYTHON DIAGNOSTICS ===")
print(f"Python version: {sys.version}")
print(f"Python executable: {sys.executable}")
print(f"sys.path: {sys.path[:5]}...")  # First 5 paths
print(f"ADDITIONAL_PYTHON_PATHS env: {_os.environ.get('ADDITIONAL_PYTHON_PATHS', 'NOT SET')}")
# Check if mounted venv exists
_venv_path = "/venv/lib/python3.11/site-packages"
print(f"Mounted venv exists: {_os.path.exists(_venv_path)}")
if _os.path.exists(_venv_path):
    import subprocess
    _files = subprocess.run(["ls", _venv_path], capture_output=True, text=True)
    print(f"Venv contents (first 10): {_files.stdout.split()[:10]}")
# Check pydantic_core specifically
_pydantic_core_path = f"{_venv_path}/pydantic_core"
print(f"pydantic_core exists: {_os.path.exists(_pydantic_core_path)}")
if _os.path.exists(_pydantic_core_path):
    _pc_files = subprocess.run(["ls", _pydantic_core_path], capture_output=True, text=True)
    print(f"pydantic_core contents: {_pc_files.stdout.split()}")
print(f"=== END DIAGNOSTICS ===")
# === END DIAGNOSTIC LOGGING ===

import asyncio
import logging
import os
import signal
from typing import Any, Optional

# Add project root to path for local development
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Silence httpx verbose logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Global flag for graceful shutdown
_shutdown_requested = False


def signal_handler(signum: int, frame: Any) -> None:
    """Handle shutdown signals gracefully."""
    global _shutdown_requested
    logger.info("Shutdown signal received, stopping polling...")
    _shutdown_requested = True


def _get_process_message_func():
    """Get the process_message function, handling different import contexts."""
    # Try importing from the same directory first (for direct execution)
    try:
        from telegram_chat_agent import _async_main
        return _async_main
    except ImportError:
        pass

    # Try Windmill-style import
    try:
        from f.telegram.telegram_chat_agent import _async_main
        return _async_main
    except ImportError:
        pass

    # Fallback: import from relative path
    import importlib.util
    chat_agent_path = os.path.join(os.path.dirname(__file__), "telegram_chat_agent.py")
    spec = importlib.util.spec_from_file_location("telegram_chat_agent", chat_agent_path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module._async_main

    raise ImportError("Could not import telegram_chat_agent module")


class TelegramPollingBot:
    """Telegram bot that uses long polling to receive updates."""

    def __init__(self, token: str, polling_timeout: int = 30):
        """Initialize the polling bot.

        Args:
            token: Telegram bot token
            polling_timeout: Long polling timeout in seconds (max 50)
        """
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.polling_timeout = min(polling_timeout, 50)  # Telegram max is 50
        self.last_update_id: Optional[int] = None
        self._process_message = None

    async def get_updates(self, offset: Optional[int] = None) -> list[dict]:
        """Fetch new updates from Telegram using long polling.

        Args:
            offset: Update ID offset to acknowledge previous updates

        Returns:
            List of update objects
        """
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
                    return result.get("result", [])
                else:
                    logger.error("Failed to get updates: %s", result.get("description"))
                    return []
        except httpx.TimeoutException:
            # Timeout is normal for long polling when no updates
            return []
        except Exception as e:
            logger.error("Error fetching updates: %s", e)
            return []

    async def get_me(self) -> Optional[dict]:
        """Get bot information to verify token is valid."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/getMe")
                result = response.json()
                if result.get("ok"):
                    return result.get("result")
                else:
                    logger.error("Failed to get bot info: %s", result.get("description"))
                    return None
        except Exception as e:
            logger.error("Error getting bot info: %s", e)
            return None

    async def delete_webhook(self) -> bool:
        """Delete any existing webhook to enable polling mode."""
        import httpx

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
                    logger.warning("Failed to delete webhook: %s", result.get("description"))
                    return False
        except Exception as e:
            logger.error("Error deleting webhook: %s", e)
            return False

    async def handle_update(self, update: dict) -> None:
        """Handle a single update from Telegram using the shared chat agent.

        Args:
            update: Telegram update object
        """
        # Lazy load the process_message function
        if self._process_message is None:
            self._process_message = _get_process_message_func()

        # Skip non-message updates
        if "message" not in update:
            return

        message = update["message"]

        # Skip non-text messages
        if "text" not in message:
            return

        chat_id = str(message["chat"]["id"])
        user_message = message["text"]
        message_id = message.get("message_id")
        user = message.get("from", {})
        user_id = user.get("id")
        username = user.get("username", "unknown")
        first_name = user.get("first_name", "User")

        logger.info(
            "Received message from %s (@%s): %s",
            first_name,
            username,
            user_message[:50] + "..." if len(user_message) > 50 else user_message,
        )

        # Use the shared chat agent to process and respond
        result = await self._process_message(
            message=user_message,
            chat_id=chat_id,
            message_id=message_id,
            user_id=user_id,
            username=username,
            first_name=first_name,
        )

        if result.get("status") == "success":
            logger.info("Message processed successfully")
        else:
            logger.error("Failed to process message: %s", result.get("reason"))

    async def run(self) -> None:
        """Run the polling loop."""
        global _shutdown_requested

        # Verify bot token
        bot_info = await self.get_me()
        if not bot_info:
            logger.error("Failed to verify bot token. Please check TELEGRAM_BOT_TOKEN.")
            return

        logger.info("=" * 60)
        logger.info("TELEGRAM POLLING BOT STARTED")
        logger.info("=" * 60)
        logger.info("Bot: @%s (%s)", bot_info.get("username"), bot_info.get("first_name"))
        logger.info("Polling timeout: %ds", self.polling_timeout)
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)

        # Delete any existing webhook to enable polling
        await self.delete_webhook()

        # Main polling loop
        while not _shutdown_requested:
            try:
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
                logger.error("Error in polling loop: %s", e)
                # Wait before retrying
                await asyncio.sleep(5)

        logger.info("Polling stopped")


async def _async_main(
    polling_timeout: int = 30,
    max_runtime_seconds: Optional[int] = None,
) -> dict[str, Any]:
    """Async implementation of the polling bot.

    Args:
        polling_timeout: Long polling timeout in seconds
        max_runtime_seconds: Maximum runtime before stopping (None = run forever)

    Returns:
        Dict with status information
    """
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()

    # Get Telegram bot token
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")

    if not telegram_token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        return {"status": "error", "reason": "TELEGRAM_BOT_TOKEN not configured"}

    # Create and run bot
    bot = TelegramPollingBot(token=telegram_token, polling_timeout=polling_timeout)

    if max_runtime_seconds:
        # Run with timeout
        try:
            await asyncio.wait_for(bot.run(), timeout=max_runtime_seconds)
        except asyncio.TimeoutError:
            logger.info("Max runtime reached (%ds)", max_runtime_seconds)
    else:
        # Run until shutdown
        await bot.run()

    return {"status": "stopped", "reason": "shutdown_requested"}


def main(
    polling_timeout: int = 30,
    max_runtime_seconds: Optional[int] = None,
) -> dict[str, Any]:
    """Run the Telegram polling bot.

    This starts a long-running polling loop that continuously checks for
    new messages from Telegram. Uses the same chat agent as the webhook approach.

    Args:
        polling_timeout: Long polling timeout in seconds (default: 30, max: 50)
        max_runtime_seconds: Maximum runtime before stopping (None = run forever)
            Set this when running in Windmill to prevent infinite jobs.

    Returns:
        Dict with status information
    """
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

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
                "description": "Long polling timeout in seconds (max 50)",
                "default": 30,
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