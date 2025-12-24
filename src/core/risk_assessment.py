"""Risk assessment functions for tool action categorization."""

import logging

from src.models.risk_level import RiskLevel

logger = logging.getLogger(__name__)

# Static mapping of known tools to risk levels
TOOL_RISK_MAP: dict[str, RiskLevel] = {
    # Reversible (read-only, no side effects)
    "web_search": RiskLevel.REVERSIBLE,
    "search_web": RiskLevel.REVERSIBLE,
    "search": RiskLevel.REVERSIBLE,  # MCP tool name from open-websearch
    "read_file": RiskLevel.REVERSIBLE,
    "get_current_time": RiskLevel.REVERSIBLE,
    "search_memory": RiskLevel.REVERSIBLE,
    # Reversible with delay (can be undone within time window)
    "send_email": RiskLevel.REVERSIBLE_WITH_DELAY,
    "create_calendar_event": RiskLevel.REVERSIBLE_WITH_DELAY,
    "schedule_task": RiskLevel.REVERSIBLE_WITH_DELAY,
    # Irreversible (permanent consequences)
    "delete_file": RiskLevel.IRREVERSIBLE,
    "make_purchase": RiskLevel.IRREVERSIBLE,
    "send_money": RiskLevel.IRREVERSIBLE,
    "modify_production": RiskLevel.IRREVERSIBLE,
}

# Sensitive patterns that escalate risk level
SENSITIVE_PATTERNS = ["/etc/shadow", "api_key", "secret", "credentials", "password"]


def categorize_action_risk(tool_name: str, parameters: dict) -> RiskLevel:
    """
    Categorize the risk level of a tool action.

    Args:
        tool_name: Name of the tool to be invoked
        parameters: Parameters to be passed to the tool

    Returns:
        RiskLevel enum indicating the categorized risk level

    Implementation per research.md RQ-006:
    - Check static mapping first
    - Parameter inspection for context-dependent risk
    - Conservative default: treat unknown tools as irreversible
    """
    # Check static mapping first
    if tool_name in TOOL_RISK_MAP:
        base_risk = TOOL_RISK_MAP[tool_name]

        # Parameter inspection for context-dependent risk
        if tool_name == "read_file":
            file_path = parameters.get("path", "").lower()
            if any(sensitive in file_path for sensitive in SENSITIVE_PATTERNS):
                # Escalate sensitive file reads
                return RiskLevel.REVERSIBLE_WITH_DELAY

        return base_risk

    # Conservative default: treat unknown tools as irreversible
    logger.warning(
        "⚠️ Unknown tool '%s' detected. Defaulting to IRREVERSIBLE risk for safety.",
        tool_name,
    )
    return RiskLevel.IRREVERSIBLE


def requires_approval(action: RiskLevel, confidence: float) -> bool:
    """
    Determine if an action requires user approval before execution.

    Args:
        action: The risk level of the action
        confidence: The confidence score (0.0-1.0)

    Returns:
        True if approval is required, False for auto-execution

    Implementation per research.md RQ-006:
    - IRREVERSIBLE: Always require approval
    - REVERSIBLE_WITH_DELAY: Conditional (confidence < 0.85)
    - REVERSIBLE: Auto-execute with logging
    """
    if action == RiskLevel.IRREVERSIBLE:
        return True  # Always require approval
    elif action == RiskLevel.REVERSIBLE_WITH_DELAY:
        return confidence < 0.85  # Conditional approval
    else:  # REVERSIBLE
        return False  # Auto-execute with logging
