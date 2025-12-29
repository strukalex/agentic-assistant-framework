#py: >=3.11,<3.12

"""Telegram Bot using Long Polling for Windmill.

Environment variables:
    TELEGRAM_BOT_TOKEN: Your bot token from @BotFather
    LLM_PROVIDER: 'azure' or 'local' (for Ollama)
    TELEGRAM_DEFAULT_CHAT_ID: Owner's Telegram user/chat ID - only this user can interact with the bot
"""

import asyncio
import logging
import os
from typing import Any, Optional

# Windmill-compatible relative import
try:
    from f.telegram.telegram_chat_agent import _async_main as process_message
except ImportError:
    from telegram_chat_agent import _async_main as process_message

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)


def get_owner_id() -> Optional[int]:
    """Get the owner's Telegram ID from TELEGRAM_DEFAULT_CHAT_ID.

    Returns:
        Owner's user ID, or None if not configured.
    """
    owner_id_str = os.environ.get("TELEGRAM_DEFAULT_CHAT_ID", "")
    if not owner_id_str.strip():
        return None
    try:
        return int(owner_id_str.strip())
    except ValueError:
        logger.warning(f"Invalid TELEGRAM_DEFAULT_CHAT_ID: {owner_id_str}")
        return None


def is_owner(user_id: Optional[int], owner_id: Optional[int]) -> bool:
    """Check if user is the owner.

    Args:
        user_id: The Telegram user ID to check
        owner_id: The owner's user ID (None = allow all)

    Returns:
        True if user is owner or no owner configured, False otherwise
    """
    if owner_id is None:
        return True
    if user_id is None:
        return False
    return user_id == owner_id


class TelegramPollingBot:
    """Telegram bot using long polling."""

    def __init__(self, token: str, polling_timeout: int = 30, owner_id: Optional[int] = None):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.polling_timeout = min(polling_timeout, 50)
        self.last_update_id: Optional[int] = None
        self.shutdown_event = asyncio.Event()
        self.owner_id = owner_id
        self._warned_no_owner = False

    async def get_updates(self, offset: Optional[int] = None) -> list[dict]:
        """Fetch updates using long polling."""
        import httpx

        params: dict[str, Any] = {
            "timeout": self.polling_timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            params["offset"] = offset

        try:
            async with httpx.AsyncClient(timeout=self.polling_timeout + 10) as client:
                response = await client.get(
                    f"{self.base_url}/getUpdates", 
                    params=params
                )
                result = response.json()
                return result.get("result", []) if result.get("ok") else []
        except httpx.TimeoutException:
            return []  # Normal for long polling
        except Exception as e:
            logger.error(f"Error fetching updates: {e}")
            return []

    async def delete_webhook(self) -> bool:
        """Delete webhook to enable polling."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.base_url}/deleteWebhook",
                    json={"drop_pending_updates": False}
                )
                result = response.json()
                if result.get("ok"):
                    logger.info("Webhook deleted, polling enabled")
                    return True
                return False
        except Exception as e:
            logger.error(f"Error deleting webhook: {e}")
            return False

    async def handle_update(self, update: dict) -> None:
        """Process a single Telegram update."""
        message = update.get("message")
        if not message or "text" not in message:
            return

        # Extract user information
        from_user = message.get("from", {})
        user_id = from_user.get("id")
        username = from_user.get("username", "unknown")

        # Check if user is the owner
        if not is_owner(user_id, self.owner_id):
            logger.warning(
                f"Unauthorized access attempt from user_id={user_id} (@{username}) - ignoring"
            )
            return

        # Warn once if no owner is configured
        if self.owner_id is None and not self._warned_no_owner:
            logger.warning(
                "TELEGRAM_DEFAULT_CHAT_ID not configured - bot accepts messages from ALL users. "
                "Set this variable to restrict access."
            )
            self._warned_no_owner = True

        result = await process_message(
            message=message["text"],
            chat_id=str(message["chat"]["id"]),
            message_id=message.get("message_id"),
            user_id=user_id,
            username=username,
            first_name=from_user.get("first_name", "User")
        )

        if result.get("status") != "success":
            logger.error(f"Failed to process message: {result.get('reason')}")

    async def run(self) -> None:
        """Run the polling loop."""
        await self.delete_webhook()
        
        logger.info("Polling bot started")

        while not self.shutdown_event.is_set():
            try:
                offset = self.last_update_id + 1 if self.last_update_id else None
                updates = await self.get_updates(offset=offset)

                for update in updates:
                    if update_id := update.get("update_id"):
                        self.last_update_id = update_id
                    await self.handle_update(update)

            except asyncio.CancelledError:
                logger.info("Polling cancelled")
                break
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(5)

        logger.info("Polling stopped")


async def _async_main(
    polling_timeout: int = 30,
    max_runtime_seconds: Optional[int] = None,
) -> dict[str, Any]:
    """Run the polling bot."""
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not telegram_token:
        return {"status": "error", "reason": "TELEGRAM_BOT_TOKEN not configured"}

    # Get owner ID for access control
    owner_id = get_owner_id()
    if owner_id:
        logger.info(f"Access control enabled: owner_id={owner_id}")
    else:
        logger.warning("No TELEGRAM_DEFAULT_CHAT_ID configured - bot will accept messages from ALL users")

    bot = TelegramPollingBot(
        token=telegram_token,
        polling_timeout=polling_timeout,
        owner_id=owner_id
    )

    try:
        if max_runtime_seconds:
            await asyncio.wait_for(bot.run(), timeout=max_runtime_seconds)
        else:
            await bot.run()
    except asyncio.TimeoutError:
        logger.info(f"Max runtime reached ({max_runtime_seconds}s)")
    except asyncio.CancelledError:
        logger.info("Bot cancelled by Windmill")
        
    return {"status": "stopped"}


def main(
    polling_timeout: int = 30,
    max_runtime_seconds: Optional[int] = None,
) -> dict[str, Any]:
    """Windmill entry point for Telegram polling bot."""
    return asyncio.run(_async_main(polling_timeout, max_runtime_seconds))
