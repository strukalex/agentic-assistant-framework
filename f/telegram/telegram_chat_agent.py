"""Telegram Chat Agent - AI agent that processes messages and responds via Telegram.

This script receives messages from the webhook handler, processes them with an AI model
(local Ollama or Azure), and sends responses back to Telegram.

Usage in Windmill:
    - Registered at path: f/telegram/telegram_chat_agent
    - Triggered by: f/telegram/telegram_webhook
    - Uses existing LLM infrastructure from paias.core.llm
"""
# requirements:
# file:///app
# httpx>=0.25.0
# pydantic>=2.0.0

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
from typing import Any, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Silence httpx verbose logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# Try to import wmill for Windmill-specific functionality
try:
    import wmill

    WMILL_AVAILABLE = True
except ImportError:
    wmill = None  # type: ignore[assignment]
    WMILL_AVAILABLE = False


async def send_telegram_message(
    chat_id: str,
    text: str,
    telegram_token: str,
    reply_to_message_id: Optional[int] = None,
    parse_mode: str = "Markdown",
) -> dict[str, Any]:
    """Send a message to a Telegram chat.

    Args:
        chat_id: Telegram chat ID to send message to
        text: Message text to send
        telegram_token: Bot token for authentication
        reply_to_message_id: Optional message ID to reply to
        parse_mode: Message parse mode (Markdown, HTML, or empty)

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

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        result = response.json()

        if not result.get("ok"):
            # If Markdown parsing fails, retry without parse_mode
            if parse_mode and "can't parse entities" in str(result.get("description", "")):
                logger.warning("Markdown parsing failed, retrying without parse_mode")
                del payload["parse_mode"]
                response = await client.post(url, json=payload)
                result = response.json()

        return result


async def send_typing_action(chat_id: str, telegram_token: str) -> None:
    """Send typing indicator to show the bot is processing.

    Args:
        chat_id: Telegram chat ID
        telegram_token: Bot token for authentication
    """
    import httpx

    url = f"https://api.telegram.org/bot{telegram_token}/sendChatAction"
    payload = {"chat_id": chat_id, "action": "typing"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        logger.warning("Failed to send typing action: %s", e)


async def run_chat_agent(
    message: str,
    chat_id: str,
    username: str,
    first_name: str,
) -> str:
    """Process user message with AI agent and return response.

    Uses the shared LLM utilities from paias.core.llm to communicate with
    either local Ollama or Azure AI Foundry, based on environment configuration.

    Args:
        message: User's message text
        chat_id: Telegram chat ID (for context)
        username: Telegram username
        first_name: User's first name

    Returns:
        AI-generated response text
    """
    from pydantic_ai import Agent

    # Import shared LLM utilities - handles Azure/Ollama based on LLM_PROVIDER env var
    from paias.core.llm import get_azure_model

    logger.info("Initializing LLM model...")
    model = get_azure_model()

    # Create a simple chat agent
    agent = Agent(
        model=model,
        system_prompt=f"""You are a helpful AI assistant chatting with users via Telegram.

User information:
- Name: {first_name}
- Username: @{username}
- Chat ID: {chat_id}

Guidelines:
- Be conversational and friendly
- Keep responses concise (Telegram users prefer shorter messages)
- You can use basic Markdown formatting:
  - *bold* for emphasis
  - _italic_ for titles or quotes
  - `code` for technical terms
  - ```code blocks``` for code snippets
- Provide helpful, accurate information
- If you don't know something, say so honestly
- Be respectful and professional

Current date: {__import__('time').strftime('%Y-%m-%d')}
""",
    )

    # Handle /start command
    if message.strip() == "/start":
        return f"""Hello {first_name}! I'm your AI assistant.

I can help you with:
- Answering questions
- Having conversations
- Providing information

Just send me a message and I'll do my best to help!"""

    # Run the agent
    logger.info("Running agent for message: %s", message[:50])
    result = await agent.run(message)

    # Extract response - handle different pydantic-ai versions
    response = getattr(result, "data", None)
    if response is None:
        response = getattr(result, "output", None)
    if response is None:
        response = str(result)

    logger.info("Agent response: %s", str(response)[:100])
    return str(response)


async def _async_main(
    message: str,
    chat_id: str,
    message_id: Optional[int] = None,
    user_id: Optional[int] = None,
    username: str = "unknown",
    first_name: str = "User",
) -> dict[str, Any]:
    """Async implementation of the chat agent workflow.

    Args:
        message: User's message text
        chat_id: Telegram chat ID to respond to
        message_id: Original message ID (for reply threading)
        user_id: Telegram user ID
        username: Telegram username
        first_name: User's first name

    Returns:
        Dict with status and response information
    """
    logger.info("=" * 60)
    logger.info("TELEGRAM CHAT AGENT")
    logger.info("=" * 60)
    logger.info("Chat ID: %s", chat_id)
    logger.info("User: %s (@%s)", first_name, username)
    logger.info("Message: %s", message[:100])

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
        return {"status": "error", "reason": error_msg}

    try:
        # Send typing indicator to show we're processing
        await send_typing_action(chat_id, telegram_token)

        # Process message with AI agent
        logger.info("Processing message with AI agent...")
        response_text = await run_chat_agent(
            message=message,
            chat_id=chat_id,
            username=username,
            first_name=first_name,
        )

        # Send response back to Telegram
        logger.info("Sending response to Telegram...")
        send_result = await send_telegram_message(
            chat_id=chat_id,
            text=response_text,
            telegram_token=telegram_token,
            reply_to_message_id=message_id,
        )

        if send_result.get("ok"):
            logger.info("Response sent successfully")
            return {
                "status": "success",
                "chat_id": chat_id,
                "response_length": len(response_text),
                "telegram_message_id": send_result.get("result", {}).get("message_id"),
            }
        else:
            error_desc = send_result.get("description", "Unknown error")
            logger.error("Failed to send response: %s", error_desc)
            return {
                "status": "error",
                "reason": f"Telegram API error: {error_desc}",
                "chat_id": chat_id,
            }

    except Exception as e:
        logger.exception("Error processing message")

        # Try to send error message to user
        try:
            await send_telegram_message(
                chat_id=chat_id,
                text="Sorry, I encountered an error processing your message. Please try again.",
                telegram_token=telegram_token,
                parse_mode="",
            )
        except Exception:
            pass

        return {
            "status": "error",
            "reason": str(e),
            "chat_id": chat_id,
        }


def main(
    message: str,
    chat_id: str,
    message_id: Optional[int] = None,
    user_id: Optional[int] = None,
    username: str = "unknown",
    first_name: str = "User",
) -> dict[str, Any]:
    """Windmill entrypoint: process Telegram message and respond.

    Args:
        message: User's message text
        chat_id: Telegram chat ID to respond to
        message_id: Original message ID (for reply threading)
        user_id: Telegram user ID
        username: Telegram username
        first_name: User's first name

    Returns:
        Dict with status and response information
    """
    return asyncio.run(
        _async_main(
            message=message,
            chat_id=chat_id,
            message_id=message_id,
            user_id=user_id,
            username=username,
            first_name=first_name,
        )
    )


# Windmill script metadata
__windmill__ = {
    "description": "AI chat agent that processes Telegram messages and responds",
    "summary": "Telegram Chat Agent",
    "schema": {
        "properties": {
            "message": {
                "type": "string",
                "description": "User's message text",
            },
            "chat_id": {
                "type": "string",
                "description": "Telegram chat ID to respond to",
            },
            "message_id": {
                "type": "integer",
                "description": "Original message ID for reply threading",
            },
            "user_id": {
                "type": "integer",
                "description": "Telegram user ID",
            },
            "username": {
                "type": "string",
                "description": "Telegram username",
                "default": "unknown",
            },
            "first_name": {
                "type": "string",
                "description": "User's first name",
                "default": "User",
            },
        },
        "required": ["message", "chat_id"],
    },
}
