from __future__ import annotations

from enum import Enum


class MessageRole(str, Enum):
    """Supported message roles for conversations."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

