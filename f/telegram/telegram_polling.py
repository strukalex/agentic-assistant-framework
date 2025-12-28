#py: >=3.11,<3.12

"""Telegram Bot using Long Polling for Windmill.

Environment variables:
    TELEGRAM_BOT_TOKEN: Your bot token from @BotFather
    LLM_PROVIDER: 'azure' or 'local' (for Ollama)
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


class TelegramPollingBot:
    """Telegram bot using long polling."""

    def __init__(self, token: str, polling_timeout: int = 30):
        self.token = token
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.polling_timeout = min(polling_timeout, 50)
        self.last_update_id: Optional[int] = None
        self.shutdown_event = asyncio.Event()

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

        result = await process_message(
            message=message["text"],
            chat_id=str(message["chat"]["id"]),
            message_id=message.get("message_id"),
            user_id=message.get("from", {}).get("id"),
            username=message.get("from", {}).get("username", "unknown"),
            first_name=message.get("from", {}).get("first_name", "User")
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

    bot = TelegramPollingBot(token=telegram_token, polling_timeout=polling_timeout)

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
