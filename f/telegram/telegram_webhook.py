"""Windmill webhook handler for Telegram bot updates.

Receives incoming Telegram webhook updates and triggers the AI chat agent flow.
This script is the entry point that Telegram calls when messages are sent to the bot.

Usage in Windmill:
    - Registered at path: f/telegram/telegram_webhook
    - Webhook receives POST requests from Telegram
    - Triggers f/telegram/telegram_chat_agent for processing
"""

from __future__ import annotations

import logging
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import wmill for Windmill-specific functionality
try:
    import wmill

    WMILL_AVAILABLE = True
except ImportError:
    wmill = None  # type: ignore[assignment]
    WMILL_AVAILABLE = False


def main(update: dict) -> dict[str, Any]:
    """Receive Telegram webhook updates and trigger the AI agent.

    Telegram sends updates in format:
    {
      "update_id": 123456789,
      "message": {
        "message_id": 123,
        "chat": {"id": 123456789, "type": "private"},
        "text": "Hello bot",
        "from": {"id": 987654321, "username": "user", "first_name": "John"}
      }
    }

    Args:
        update: Telegram update object (webhook payload)

    Returns:
        Dict with status and job information
    """
    logger.info("Received Telegram update: %s", update.get("update_id", "unknown"))

    # Skip if no message (could be other update types like edited_message, callback_query, etc.)
    if "message" not in update:
        logger.info("Skipping update: no message field")
        return {"status": "skipped", "reason": "no_message"}

    message = update["message"]

    # Skip non-text messages (photos, stickers, etc.)
    if "text" not in message:
        logger.info("Skipping update: no text in message")
        return {"status": "skipped", "reason": "no_text"}

    # Extract message details
    chat_id = str(message["chat"]["id"])
    user_message = message["text"]
    message_id = message.get("message_id")
    user_id = message["from"].get("id")
    username = message["from"].get("username", "unknown")
    first_name = message["from"].get("first_name", "")

    logger.info(
        "Processing message from %s (@%s): %s",
        first_name,
        username,
        user_message[:50] + "..." if len(user_message) > 50 else user_message,
    )

    # Handle /start command specially
    if user_message.strip() == "/start":
        logger.info("Received /start command - will send welcome message")

    if not WMILL_AVAILABLE or wmill is None:
        logger.warning("Windmill not available - cannot trigger agent flow")
        return {
            "status": "error",
            "reason": "windmill_not_available",
            "chat_id": chat_id,
        }

    # Trigger the AI agent script asynchronously
    # Using run_script_async to run the chat agent in the background
    try:
        job_id = wmill.run_script_async(
            path="f/telegram/telegram_chat_agent",
            args={
                "message": user_message,
                "chat_id": chat_id,
                "message_id": message_id,
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
            },
        )

        logger.info("Triggered agent job: %s", job_id)

        return {
            "status": "triggered",
            "job_id": job_id,
            "chat_id": chat_id,
            "message_preview": user_message[:50],
        }

    except Exception as e:
        logger.exception("Failed to trigger agent job")
        return {
            "status": "error",
            "reason": str(e),
            "chat_id": chat_id,
        }


# Windmill script metadata
__windmill__ = {
    "description": "Telegram webhook handler - receives updates and triggers AI agent",
    "summary": "Telegram Webhook Handler",
    "schema": {
        "properties": {
            "update": {
                "type": "object",
                "description": "Telegram update object (webhook payload)",
            },
        },
        "required": ["update"],
    },
}
