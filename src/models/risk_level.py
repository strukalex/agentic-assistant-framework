"""Risk level categorization for tool actions."""

from enum import Enum


class RiskLevel(str, Enum):
    """
    Risk categorization for tool actions.

    Values:
        REVERSIBLE: Read-only actions with no side effects (e.g., search, read_file)
        REVERSIBLE_WITH_DELAY: Actions that can be undone within a time window (e.g., send_email)
        IRREVERSIBLE: Actions with permanent consequences (e.g., delete_file, make_purchase)
    """

    REVERSIBLE = "reversible"
    REVERSIBLE_WITH_DELAY = "reversible_with_delay"
    IRREVERSIBLE = "irreversible"
