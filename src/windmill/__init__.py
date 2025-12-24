"""Windmill workflow integration module for Spec 003.

This module contains Windmill workflow scripts and approval handlers
for the DailyTrendingResearch workflow.

Components:
- WindmillClient: HTTP client for Windmill REST API
- approval_handler: Human-in-the-loop approval gating
- daily_research: Main workflow script for Windmill execution

Usage:
    # Trigger workflow via API
    from src.windmill.client import WindmillClient

    async with WindmillClient() as client:
        job_id = await client.trigger_flow("research/daily_research", {
            "topic": "AI agents",
            "user_id": "..."
        })

    # Check status
    status = await client.get_job_status(job_id)

    # Get result when completed
    result = await client.get_job_result(job_id)
"""

from src.windmill.client import WindmillClient, WindmillJobStatus
from src.windmill.approval_handler import (
    requires_approval,
    classify_actions,
    request_approval,
    handle_approval_result,
    process_planned_actions,
    suspend_for_approval,
    get_resume_urls,
)

__all__ = [
    "WindmillClient",
    "WindmillJobStatus",
    "requires_approval",
    "classify_actions",
    "request_approval",
    "handle_approval_result",
    "process_planned_actions",
    "suspend_for_approval",
    "get_resume_urls",
]

