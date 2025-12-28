"""Windmill script: Configure Telegram webhook for the bot.

This is a one-time setup script to register the Windmill webhook URL
with Telegram so incoming messages are forwarded to the bot.

Usage in Windmill:
    - Registered at path: f/telegram/setup_telegram_webhook
    - Run once with your Windmill webhook URL
    - Can be re-run to update the webhook URL
"""

from __future__ import annotations

import asyncio
import logging
import os
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


async def _setup_webhook(
    webhook_url: str,
    telegram_token: str,
    allowed_updates: list[str] | None = None,
    drop_pending_updates: bool = False,
) -> dict[str, Any]:
    """Configure Telegram to send updates to the webhook URL.

    Args:
        webhook_url: Full Windmill webhook URL
        telegram_token: Bot token for authentication
        allowed_updates: List of update types to receive (default: ["message"])
        drop_pending_updates: Whether to drop pending updates when setting webhook

    Returns:
        Dict with setup status and webhook info
    """
    import httpx

    if allowed_updates is None:
        allowed_updates = ["message"]

    # Set webhook
    set_url = f"https://api.telegram.org/bot{telegram_token}/setWebhook"
    payload = {
        "url": webhook_url,
        "allowed_updates": allowed_updates,
        "drop_pending_updates": drop_pending_updates,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info("Setting webhook URL: %s", webhook_url)
        response = await client.post(set_url, json=payload)
        set_result = response.json()

        if not set_result.get("ok"):
            error_desc = set_result.get("description", "Unknown error")
            logger.error("Failed to set webhook: %s", error_desc)
            return {
                "ok": False,
                "error": f"Failed to set webhook: {error_desc}",
            }

        logger.info("Webhook set successfully")

        # Get webhook info for verification
        info_url = f"https://api.telegram.org/bot{telegram_token}/getWebhookInfo"
        info_response = await client.get(info_url)
        info_result = info_response.json()

        webhook_info = info_result.get("result", {})
        logger.info("Webhook URL: %s", webhook_info.get("url"))
        logger.info("Pending update count: %s", webhook_info.get("pending_update_count", 0))

        return {
            "ok": True,
            "webhook_set": set_result,
            "webhook_info": webhook_info,
        }


async def _delete_webhook(telegram_token: str) -> dict[str, Any]:
    """Remove the current webhook.

    Args:
        telegram_token: Bot token for authentication

    Returns:
        Dict with deletion status
    """
    import httpx

    url = f"https://api.telegram.org/bot{telegram_token}/deleteWebhook"

    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info("Deleting webhook...")
        response = await client.post(url)
        result = response.json()

        if result.get("ok"):
            logger.info("Webhook deleted successfully")
            return {"ok": True, "message": "Webhook deleted"}
        else:
            error_desc = result.get("description", "Unknown error")
            logger.error("Failed to delete webhook: %s", error_desc)
            return {"ok": False, "error": error_desc}


async def _get_webhook_info(telegram_token: str) -> dict[str, Any]:
    """Get current webhook configuration.

    Args:
        telegram_token: Bot token for authentication

    Returns:
        Webhook info from Telegram API
    """
    import httpx

    url = f"https://api.telegram.org/bot{telegram_token}/getWebhookInfo"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        result = response.json()

        if result.get("ok"):
            return {"ok": True, "webhook_info": result.get("result", {})}
        else:
            return {"ok": False, "error": result.get("description", "Unknown error")}


async def _async_main(
    webhook_url: str = "",
    action: str = "set",
    drop_pending_updates: bool = False,
) -> dict[str, Any]:
    """Async implementation of webhook setup.

    Args:
        webhook_url: Full Windmill webhook URL (required for 'set' action)
        action: Action to perform - 'set', 'delete', or 'info'
        drop_pending_updates: Whether to drop pending updates when setting webhook

    Returns:
        Dict with action result
    """
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

    if action == "delete":
        return await _delete_webhook(telegram_token)

    if action == "info":
        return await _get_webhook_info(telegram_token)

    # Default: set webhook
    if not webhook_url:
        return {
            "ok": False,
            "error": "webhook_url is required for 'set' action",
        }

    return await _setup_webhook(
        webhook_url=webhook_url,
        telegram_token=telegram_token,
        drop_pending_updates=drop_pending_updates,
    )


def main(
    webhook_url: str = "",
    action: str = "set",
    drop_pending_updates: bool = False,
) -> dict[str, Any]:
    """Configure Telegram webhook for the bot.

    This script sets up the Telegram webhook to forward incoming messages
    to your Windmill webhook handler.

    The webhook URL format is typically:
    https://app.windmill.dev/api/w/YOUR_WORKSPACE/jobs/run/webhook/f/telegram/telegram_webhook/TOKEN

    Args:
        webhook_url: Full Windmill webhook URL (required for 'set' action)
        action: Action to perform:
            - 'set': Set/update the webhook URL
            - 'delete': Remove the current webhook
            - 'info': Get current webhook info
        drop_pending_updates: Whether to drop pending updates when setting webhook

    Returns:
        Dict with action result and webhook info
    """
    return asyncio.run(
        _async_main(
            webhook_url=webhook_url,
            action=action,
            drop_pending_updates=drop_pending_updates,
        )
    )


# Windmill script metadata
__windmill__ = {
    "description": "Configure Telegram webhook for the bot",
    "summary": "Setup Telegram Webhook",
    "schema": {
        "properties": {
            "webhook_url": {
                "type": "string",
                "description": "Full Windmill webhook URL (required for 'set' action)",
            },
            "action": {
                "type": "string",
                "description": "Action to perform: set, delete, or info",
                "default": "set",
                "enum": ["set", "delete", "info"],
            },
            "drop_pending_updates": {
                "type": "boolean",
                "description": "Whether to drop pending updates when setting webhook",
                "default": False,
            },
        },
        "required": [],
    },
}
