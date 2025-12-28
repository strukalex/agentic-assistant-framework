"""Windmill tool: Send a message to a Telegram chat.

This is a standalone Windmill tool for sending messages to Telegram.
It can be used by other workflows or as a standalone tool.

Usage in Windmill:
    - Registered at path: f/telegram/send_telegram_message
    - Arguments: chat_id (str), text (str), parse_mode (str, optional)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import wmill for Windmill-specific functionality
try:
    import wmill

    WMILL_AVAILABLE = True
except ImportError:
    wmill = None  # type: ignore[assignment]
    WMILL_AVAILABLE = False


async def _send_message(
    chat_id: str,
    text: str,
    telegram_token: str,
    parse_mode: str = "Markdown",
    reply_to_message_id: Optional[int] = None,
    disable_web_page_preview: bool = False,
) -> dict[str, Any]:
    """Send a message to a Telegram chat.

    Args:
        chat_id: Telegram chat ID to send message to
        text: Message text to send
        telegram_token: Bot token for authentication
        parse_mode: Message parse mode (Markdown, HTML, or empty string for plain text)
        reply_to_message_id: Optional message ID to reply to
        disable_web_page_preview: Whether to disable link previews

    Returns:
        Telegram API response
    """
    import httpx

    url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"

    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
    }

    if parse_mode:
        payload["parse_mode"] = parse_mode

    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id

    if disable_web_page_preview:
        payload["disable_web_page_preview"] = True

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        result = response.json()

        if not result.get("ok"):
            # If Markdown parsing fails, retry without parse_mode
            if parse_mode and "can't parse entities" in str(result.get("description", "")):
                logger.warning("Markdown parsing failed, retrying as plain text")
                del payload["parse_mode"]
                response = await client.post(url, json=payload)
                result = response.json()

        return result


async def _async_main(
    chat_id: str,
    text: str,
    parse_mode: str = "Markdown",
    reply_to_message_id: Optional[int] = None,
    disable_web_page_preview: bool = False,
) -> dict[str, Any]:
    """Async implementation of sending a Telegram message.

    Args:
        chat_id: Telegram chat ID to send message to
        text: Message text to send
        parse_mode: Message parse mode (Markdown, HTML, or empty for plain text)
        reply_to_message_id: Optional message ID to reply to
        disable_web_page_preview: Whether to disable link previews

    Returns:
        Dict with status and message information
    """
    logger.info("Sending message to chat %s", chat_id)

    # Get Telegram bot token
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not telegram_token and WMILL_AVAILABLE and wmill is not None:
        try:
            telegram_token = wmill.get_variable("u/admin/telegram_bot_token")
        except Exception as e:
            logger.warning("Failed to get token from Windmill variable: %s", e)

    if not telegram_token:
        error_msg = "TELEGRAM_BOT_TOKEN not configured"
        logger.error(error_msg)
        return {"ok": False, "error": error_msg}

    result = await _send_message(
        chat_id=chat_id,
        text=text,
        telegram_token=telegram_token,
        parse_mode=parse_mode,
        reply_to_message_id=reply_to_message_id,
        disable_web_page_preview=disable_web_page_preview,
    )

    if result.get("ok"):
        logger.info("Message sent successfully")
        return {
            "ok": True,
            "message_id": result.get("result", {}).get("message_id"),
            "chat_id": chat_id,
        }
    else:
        error_desc = result.get("description", "Unknown error")
        logger.error("Failed to send message: %s", error_desc)
        return {
            "ok": False,
            "error": error_desc,
            "chat_id": chat_id,
        }


def main(
    chat_id: str,
    text: str,
    parse_mode: str = "Markdown",
    reply_to_message_id: Optional[int] = None,
    disable_web_page_preview: bool = False,
) -> dict[str, Any]:
    """Send a message to a Telegram chat.

    This is a Windmill tool for sending messages to Telegram.
    It can be used by workflows or as a standalone script.

    Args:
        chat_id: Telegram chat ID to send message to
        text: Message text to send (supports Markdown or HTML based on parse_mode)
        parse_mode: Message parse mode - "Markdown", "HTML", or "" for plain text
        reply_to_message_id: Optional message ID to reply to
        disable_web_page_preview: Whether to disable link previews

    Returns:
        Dict with 'ok' boolean and message details or error
    """
    return asyncio.run(
        _async_main(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_to_message_id=reply_to_message_id,
            disable_web_page_preview=disable_web_page_preview,
        )
    )


# Windmill script metadata
__windmill__ = {
    "description": "Send a message to a Telegram chat",
    "summary": "Send Telegram Message",
    "schema": {
        "properties": {
            "chat_id": {
                "type": "string",
                "description": "Telegram chat ID to send message to",
            },
            "text": {
                "type": "string",
                "description": "Message text to send (supports Markdown or HTML)",
            },
            "parse_mode": {
                "type": "string",
                "description": "Message parse mode: Markdown, HTML, or empty for plain text",
                "default": "Markdown",
                "enum": ["Markdown", "HTML", ""],
            },
            "reply_to_message_id": {
                "type": "integer",
                "description": "Optional message ID to reply to",
            },
            "disable_web_page_preview": {
                "type": "boolean",
                "description": "Whether to disable link previews",
                "default": False,
            },
        },
        "required": ["chat_id", "text"],
    },
}
