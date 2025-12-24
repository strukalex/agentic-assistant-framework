"""
Unit tests for risk assessment functions.

Tests categorize_action_risk() and requires_approval() functions
per Spec 002 tasks.md T301-T307 (FR-015 to FR-023).
"""

import pytest

from src.core.risk_assessment import categorize_action_risk, requires_approval
from src.models.risk_level import RiskLevel


class TestCategorizeActionRisk:
    """Tests for categorize_action_risk() function."""

    # T301: Test REVERSIBLE tools classification
    def test_web_search_is_reversible(self):
        """Test that web_search is classified as REVERSIBLE."""
        risk = categorize_action_risk("web_search", {"query": "test"})
        assert risk == RiskLevel.REVERSIBLE

    def test_search_web_is_reversible(self):
        """Test that search_web is classified as REVERSIBLE."""
        risk = categorize_action_risk("search_web", {"query": "test"})
        assert risk == RiskLevel.REVERSIBLE

    def test_read_file_is_reversible(self):
        """Test that read_file is classified as REVERSIBLE (non-sensitive path)."""
        risk = categorize_action_risk("read_file", {"path": "/home/user/document.txt"})
        assert risk == RiskLevel.REVERSIBLE

    def test_get_current_time_is_reversible(self):
        """Test that get_current_time is classified as REVERSIBLE."""
        risk = categorize_action_risk("get_current_time", {"timezone": "UTC"})
        assert risk == RiskLevel.REVERSIBLE

    def test_search_memory_is_reversible(self):
        """Test that search_memory is classified as REVERSIBLE."""
        risk = categorize_action_risk("search_memory", {"query": "test"})
        assert risk == RiskLevel.REVERSIBLE

    # T302: Test REVERSIBLE_WITH_DELAY tools classification
    def test_send_email_is_reversible_with_delay(self):
        """Test that send_email is classified as REVERSIBLE_WITH_DELAY."""
        risk = categorize_action_risk(
            "send_email", {"to": "test@example.com", "subject": "Test"}
        )
        assert risk == RiskLevel.REVERSIBLE_WITH_DELAY

    def test_create_calendar_event_is_reversible_with_delay(self):
        """Test that create_calendar_event is classified as REVERSIBLE_WITH_DELAY."""
        risk = categorize_action_risk(
            "create_calendar_event", {"title": "Meeting", "time": "2025-01-01T10:00:00"}
        )
        assert risk == RiskLevel.REVERSIBLE_WITH_DELAY

    def test_schedule_task_is_reversible_with_delay(self):
        """Test that schedule_task is classified as REVERSIBLE_WITH_DELAY."""
        risk = categorize_action_risk("schedule_task", {"task": "backup", "cron": "0 0 * * *"})
        assert risk == RiskLevel.REVERSIBLE_WITH_DELAY

    # T303: Test IRREVERSIBLE tools classification
    def test_delete_file_is_irreversible(self):
        """Test that delete_file is classified as IRREVERSIBLE."""
        risk = categorize_action_risk("delete_file", {"path": "/data/important.txt"})
        assert risk == RiskLevel.IRREVERSIBLE

    def test_make_purchase_is_irreversible(self):
        """Test that make_purchase is classified as IRREVERSIBLE."""
        risk = categorize_action_risk(
            "make_purchase", {"item": "product", "amount": 100.0}
        )
        assert risk == RiskLevel.IRREVERSIBLE

    def test_send_money_is_irreversible(self):
        """Test that send_money is classified as IRREVERSIBLE."""
        risk = categorize_action_risk(
            "send_money", {"to": "account123", "amount": 500.0}
        )
        assert risk == RiskLevel.IRREVERSIBLE

    def test_modify_production_is_irreversible(self):
        """Test that modify_production is classified as IRREVERSIBLE."""
        risk = categorize_action_risk("modify_production", {"config": "new_value"})
        assert risk == RiskLevel.IRREVERSIBLE

    # T304: Test unknown tools default to IRREVERSIBLE
    def test_unknown_tool_defaults_to_irreversible(self):
        """Test that unknown tools are classified as IRREVERSIBLE (conservative default)."""
        risk = categorize_action_risk("unknown_custom_tool", {"param": "value"})
        assert risk == RiskLevel.IRREVERSIBLE

    def test_unknown_financial_tool_defaults_to_irreversible(self):
        """Test that unknown financial tool defaults to IRREVERSIBLE."""
        risk = categorize_action_risk("financial_data_api", {"account": "12345"})
        assert risk == RiskLevel.IRREVERSIBLE

    # T311: Test parameter inspection for context-dependent risk
    def test_read_file_with_etc_shadow_escalates_risk(self):
        """Test that reading /etc/shadow escalates to REVERSIBLE_WITH_DELAY."""
        risk = categorize_action_risk("read_file", {"path": "/etc/shadow"})
        assert risk == RiskLevel.REVERSIBLE_WITH_DELAY

    def test_read_file_with_api_key_escalates_risk(self):
        """Test that reading files with 'api_key' in path escalates risk."""
        risk = categorize_action_risk("read_file", {"path": "/config/api_key.txt"})
        assert risk == RiskLevel.REVERSIBLE_WITH_DELAY

    def test_read_file_with_secret_escalates_risk(self):
        """Test that reading files with 'secret' in path escalates risk."""
        risk = categorize_action_risk("read_file", {"path": "/app/secret.env"})
        assert risk == RiskLevel.REVERSIBLE_WITH_DELAY

    def test_read_file_with_credentials_escalates_risk(self):
        """Test that reading files with 'credentials' in path escalates risk."""
        risk = categorize_action_risk("read_file", {"path": "/home/user/credentials.json"})
        assert risk == RiskLevel.REVERSIBLE_WITH_DELAY

    def test_read_file_with_password_escalates_risk(self):
        """Test that reading files with 'password' in path escalates risk."""
        risk = categorize_action_risk("read_file", {"path": "/secrets/password.txt"})
        assert risk == RiskLevel.REVERSIBLE_WITH_DELAY

    def test_read_file_case_insensitive_pattern_matching(self):
        """Test that sensitive pattern matching is case-insensitive."""
        risk = categorize_action_risk("read_file", {"path": "/CONFIG/API_KEY.TXT"})
        assert risk == RiskLevel.REVERSIBLE_WITH_DELAY

    def test_read_file_safe_path_remains_reversible(self):
        """Test that reading safe files does not escalate risk."""
        risk = categorize_action_risk("read_file", {"path": "/home/user/notes.txt"})
        assert risk == RiskLevel.REVERSIBLE


class TestRequiresApproval:
    """Tests for requires_approval() function."""

    # T305: Test IRREVERSIBLE always requires approval
    def test_irreversible_always_requires_approval_high_confidence(self):
        """Test that IRREVERSIBLE actions require approval even with high confidence."""
        assert requires_approval(RiskLevel.IRREVERSIBLE, confidence=0.95) is True

    def test_irreversible_always_requires_approval_perfect_confidence(self):
        """Test that IRREVERSIBLE actions require approval even with perfect confidence."""
        assert requires_approval(RiskLevel.IRREVERSIBLE, confidence=1.0) is True

    def test_irreversible_always_requires_approval_low_confidence(self):
        """Test that IRREVERSIBLE actions require approval with low confidence."""
        assert requires_approval(RiskLevel.IRREVERSIBLE, confidence=0.5) is True

    # T306: Test REVERSIBLE_WITH_DELAY conditional approval
    def test_reversible_with_delay_requires_approval_when_confidence_low(self):
        """Test that REVERSIBLE_WITH_DELAY requires approval when confidence < 0.85."""
        assert requires_approval(RiskLevel.REVERSIBLE_WITH_DELAY, confidence=0.80) is True

    def test_reversible_with_delay_requires_approval_at_threshold(self):
        """Test that REVERSIBLE_WITH_DELAY requires approval at exactly 0.84."""
        assert requires_approval(RiskLevel.REVERSIBLE_WITH_DELAY, confidence=0.84) is True

    def test_reversible_with_delay_no_approval_when_confidence_high(self):
        """Test that REVERSIBLE_WITH_DELAY auto-executes when confidence >= 0.85."""
        assert requires_approval(RiskLevel.REVERSIBLE_WITH_DELAY, confidence=0.85) is False

    def test_reversible_with_delay_no_approval_at_perfect_confidence(self):
        """Test that REVERSIBLE_WITH_DELAY auto-executes at perfect confidence."""
        assert requires_approval(RiskLevel.REVERSIBLE_WITH_DELAY, confidence=1.0) is False

    def test_reversible_with_delay_requires_approval_very_low_confidence(self):
        """Test that REVERSIBLE_WITH_DELAY requires approval with very low confidence."""
        assert requires_approval(RiskLevel.REVERSIBLE_WITH_DELAY, confidence=0.3) is True

    # T307: Test REVERSIBLE auto-executes (no approval)
    def test_reversible_no_approval_high_confidence(self):
        """Test that REVERSIBLE actions auto-execute with high confidence."""
        assert requires_approval(RiskLevel.REVERSIBLE, confidence=0.95) is False

    def test_reversible_no_approval_low_confidence(self):
        """Test that REVERSIBLE actions auto-execute even with low confidence."""
        assert requires_approval(RiskLevel.REVERSIBLE, confidence=0.3) is False

    def test_reversible_no_approval_zero_confidence(self):
        """Test that REVERSIBLE actions auto-execute even with zero confidence."""
        assert requires_approval(RiskLevel.REVERSIBLE, confidence=0.0) is False

    def test_reversible_no_approval_perfect_confidence(self):
        """Test that REVERSIBLE actions auto-execute with perfect confidence."""
        assert requires_approval(RiskLevel.REVERSIBLE, confidence=1.0) is False


class TestRiskAssessmentIntegration:
    """Integration tests combining categorize_action_risk and requires_approval."""

    def test_web_search_auto_executes(self):
        """Test that web_search auto-executes regardless of confidence."""
        risk = categorize_action_risk("web_search", {"query": "test"})
        assert requires_approval(risk, confidence=0.5) is False

    def test_delete_file_always_requires_approval(self):
        """Test that delete_file always requires approval regardless of confidence."""
        risk = categorize_action_risk("delete_file", {"path": "/data/file.txt"})
        assert requires_approval(risk, confidence=0.99) is True

    def test_send_email_requires_approval_when_uncertain(self):
        """Test that send_email requires approval when agent is uncertain."""
        risk = categorize_action_risk("send_email", {"to": "test@example.com"})
        assert requires_approval(risk, confidence=0.75) is True

    def test_send_email_auto_executes_when_confident(self):
        """Test that send_email auto-executes when agent is confident."""
        risk = categorize_action_risk("send_email", {"to": "test@example.com"})
        assert requires_approval(risk, confidence=0.90) is False

    def test_unknown_tool_always_requires_approval(self):
        """Test that unknown tools always require approval (conservative default)."""
        risk = categorize_action_risk("custom_unknown_action", {})
        assert requires_approval(risk, confidence=0.95) is True

    def test_sensitive_file_read_requires_approval_when_uncertain(self):
        """Test that reading sensitive files requires approval when uncertain."""
        risk = categorize_action_risk("read_file", {"path": "/etc/shadow"})
        assert requires_approval(risk, confidence=0.80) is True

    def test_safe_file_read_auto_executes(self):
        """Test that reading safe files auto-executes."""
        risk = categorize_action_risk("read_file", {"path": "/home/user/document.txt"})
        assert requires_approval(risk, confidence=0.5) is False
