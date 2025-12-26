from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import AnyUrl, ValidationError

from src.models.approval_request import ApprovalRequest, ApprovalStatus
from src.models.planned_action import PlannedAction
from src.models.research_report import QualityIndicators, ResearchReport
from src.models.research_state import ResearchState, ResearchStatus
from src.models.risk_level import RiskLevel
from src.models.source_reference import SourceReference


def test_source_reference_enforces_snippet_limit() -> None:
    with pytest.raises(ValidationError):
        SourceReference(
            title="Too long",
            url="https://example.com",
            snippet="x" * 1001,
        )


def test_source_reference_accepts_valid_payload() -> None:
    source = SourceReference(
        title="Example",
        url="https://example.com/article",
        snippet="summary",
    )
    assert isinstance(source.url, AnyUrl)
    assert source.snippet == "summary"


def test_planned_action_requires_non_empty_fields() -> None:
    with pytest.raises(ValidationError):
        PlannedAction(
            action_type="",
            action_description="",
            parameters={},
            risk_level=RiskLevel.REVERSIBLE,
        )


def test_research_state_caps_max_iterations() -> None:
    state = ResearchState(
        topic="topic",
        user_id=uuid4(),
        max_iterations=10,
    )
    assert state.max_iterations == 5
    assert state.iteration_count == 0
    assert state.status == ResearchStatus.PLANNING


def test_research_state_rejects_iteration_overflow() -> None:
    with pytest.raises(ValidationError):
        ResearchState(
            topic="topic",
            user_id=uuid4(),
            iteration_count=6,
            max_iterations=5,
        )


def test_research_report_requires_content() -> None:
    with pytest.raises(ValidationError):
        ResearchReport(
            topic="",
            user_id=uuid4(),
            executive_summary="",
            detailed_findings="",
            sources=[],
            iterations=0,
        )


def test_research_report_accepts_quality_indicators() -> None:
    report = ResearchReport(
        topic="AI governance",
        user_id=uuid4(),
        executive_summary="Summary",
        detailed_findings="Details",
        sources=[
            SourceReference(
                title="Source",
                url="https://example.com",
                snippet="snippet",
            )
        ],
        iterations=2,
        quality_indicators=QualityIndicators(quality_score=0.9, warnings=["few sources"]),
    )
    assert report.quality_indicators is not None
    assert report.quality_indicators.quality_score == 0.9


def test_approval_request_sets_default_timeout() -> None:
    now = datetime.now(timezone.utc)
    request = ApprovalRequest(
        action_type="send_email",
        action_description="Send summary email",
        requester_id="user",
        requested_at=now,
    )
    assert request.timeout_at is not None
    delta = abs((request.timeout_at - now).total_seconds())
    assert 290 <= delta <= 310
    assert request.status == ApprovalStatus.PENDING


def test_approval_request_rejects_invalid_timeout() -> None:
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        ApprovalRequest(
            action_type="send_email",
            action_description="Send summary email",
            requester_id="user",
            requested_at=now,
            timeout_at=now + timedelta(seconds=400),
        )



