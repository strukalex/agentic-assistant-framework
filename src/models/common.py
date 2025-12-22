from __future__ import annotations

from enum import Enum


class RiskLevel(str, Enum):
    """Action risk categorization for approval workflows."""

    REVERSIBLE = "reversible"
    REVERSIBLE_WITH_DELAY = "reversible_with_delay"
    IRREVERSIBLE = "irreversible"

