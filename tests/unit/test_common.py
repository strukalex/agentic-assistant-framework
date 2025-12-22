from __future__ import annotations

from src.models.common import RiskLevel


def test_risk_level_values() -> None:
    assert RiskLevel.REVERSIBLE.value == "reversible"
    assert RiskLevel.REVERSIBLE_WITH_DELAY.value == "reversible_with_delay"
    assert RiskLevel.IRREVERSIBLE.value == "irreversible"

