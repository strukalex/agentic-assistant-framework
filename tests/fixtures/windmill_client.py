"""Test fixture client for Windmill approval flow testing.

Provides programmatic control over workflow approval states for testing:
- Resume jobs with approved/rejected decisions
- Query suspended/pending approval queue
- Simulate timeout escalations

NOTE: This client is for testing purposes only. In production,
approvals are handled through Windmill's native UI and API.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx

from src.core.config import settings
from src.models.approval_request import ApprovalRequest, ApprovalStatus

logger = logging.getLogger(__name__)


class WindmillTestClient:
    """Test client for programmatically interacting with Windmill approvals.

    This client can be used in integration tests to:
    1. Query the status of suspended jobs
    2. Approve or reject pending approval requests
    3. Simulate timeout escalations

    Usage:
        client = WindmillTestClient(base_url="http://localhost:8000")

        # Approve a pending job
        result = await client.resume_job_approved("job-123", approver="test@example.com")

        # Reject a pending job
        result = await client.resume_job_rejected("job-123", rejector="admin@example.com", reason="Not needed")

        # Query suspended queue
        pending = await client.get_pending_approvals()
    """

    def __init__(
        self,
        base_url: str | None = None,
        workspace: str | None = None,
        token: str | None = None,
    ):
        """Initialize the test client.

        Args:
            base_url: Windmill API base URL (default from settings).
            workspace: Windmill workspace name (default from settings).
            token: Windmill API token (default from settings).
        """
        self.base_url = base_url or settings.windmill_base_url
        self.workspace = workspace or settings.windmill_workspace
        self.token = token or settings.windmill_token
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "WindmillTestClient":
        """Async context manager entry."""
        headers = {}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def resume_job_approved(
        self,
        job_id: str,
        approver: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Resume a suspended job with approval.

        Args:
            job_id: The Windmill job ID to resume.
            approver: Identifier of who approved (for logging/audit).
            comment: Optional approval comment.

        Returns:
            Response from the resume endpoint.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        payload = {
            "decision": "approve",
            "approver": approver or "test-approver",
        }
        if comment:
            payload["comment"] = comment

        logger.info("Approving job %s by %s", job_id, payload["approver"])

        response = await self._client.post(
            f"/api/w/{self.workspace}/jobs_u/resume/{job_id}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def resume_job_rejected(
        self,
        job_id: str,
        rejector: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Resume a suspended job with rejection.

        Args:
            job_id: The Windmill job ID to resume.
            rejector: Identifier of who rejected (for logging/audit).
            reason: Optional rejection reason.

        Returns:
            Response from the resume endpoint.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        payload = {
            "decision": "reject",
            "rejector": rejector or "test-rejector",
        }
        if reason:
            payload["comment"] = reason

        logger.info("Rejecting job %s by %s: %s", job_id, payload["rejector"], reason)

        response = await self._client.post(
            f"/api/w/{self.workspace}/jobs_u/resume/{job_id}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    async def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get all jobs currently waiting for approval.

        Returns:
            List of suspended jobs with their approval request details.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(
            f"/api/w/{self.workspace}/jobs/queue/suspended",
        )
        response.raise_for_status()
        return response.json()

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get the current status of a job.

        Args:
            job_id: The Windmill job ID to query.

        Returns:
            Job status details.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        response = await self._client.get(
            f"/api/w/{self.workspace}/jobs_u/get/{job_id}",
        )
        response.raise_for_status()
        return response.json()

    async def simulate_timeout(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        """Simulate an approval timeout for a suspended job.

        In real Windmill, timeouts are handled automatically.
        This method simulates the timeout escalation for testing.

        Args:
            job_id: The Windmill job ID to timeout.

        Returns:
            Response simulating timeout escalation.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        payload = {
            "error": "approval_timeout",
        }

        logger.info("Simulating timeout for job %s", job_id)

        response = await self._client.post(
            f"/api/w/{self.workspace}/jobs_u/resume/{job_id}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()


class MockWindmillClient:
    """Mock Windmill client for unit tests without a real Windmill instance.

    Provides the same interface as WindmillTestClient but operates entirely
    in-memory without making HTTP requests.
    """

    def __init__(self) -> None:
        """Initialize the mock client with empty registries."""
        self._pending_jobs: dict[str, dict[str, Any]] = {}
        self._job_results: dict[str, dict[str, Any]] = {}

    async def __aenter__(self) -> "MockWindmillClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        pass

    def add_pending_job(
        self,
        job_id: str,
        action_type: str,
        action_description: str,
        timeout_seconds: int = 300,
    ) -> None:
        """Register a pending job for testing.

        Args:
            job_id: Unique job identifier.
            action_type: Type of action requiring approval.
            action_description: Human-readable description.
            timeout_seconds: Timeout for the approval (default 300s).
        """
        now = datetime.now(timezone.utc)
        self._pending_jobs[job_id] = {
            "job_id": job_id,
            "action_type": action_type,
            "action_description": action_description,
            "requested_at": now,
            "timeout_at": now.timestamp() + timeout_seconds,
            "status": "suspended",
        }

    async def resume_job_approved(
        self,
        job_id: str,
        approver: str | None = None,
        comment: str | None = None,
    ) -> dict[str, Any]:
        """Mock approval of a suspended job."""
        if job_id not in self._pending_jobs:
            raise ValueError(f"Job {job_id} not found in pending jobs")

        job = self._pending_jobs.pop(job_id)
        result = {
            "job_id": job_id,
            "status": "approved",
            "approver": approver or "mock-approver",
            "comment": comment,
            "action_type": job["action_type"],
        }
        self._job_results[job_id] = result
        return result

    async def resume_job_rejected(
        self,
        job_id: str,
        rejector: str | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """Mock rejection of a suspended job."""
        if job_id not in self._pending_jobs:
            raise ValueError(f"Job {job_id} not found in pending jobs")

        job = self._pending_jobs.pop(job_id)
        result = {
            "job_id": job_id,
            "status": "rejected",
            "rejector": rejector or "mock-rejector",
            "reason": reason,
            "action_type": job["action_type"],
        }
        self._job_results[job_id] = result
        return result

    async def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get all mock pending jobs."""
        return list(self._pending_jobs.values())

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Get mock job status."""
        if job_id in self._pending_jobs:
            return self._pending_jobs[job_id]
        if job_id in self._job_results:
            return self._job_results[job_id]
        raise ValueError(f"Job {job_id} not found")

    async def simulate_timeout(
        self,
        job_id: str,
    ) -> dict[str, Any]:
        """Mock timeout escalation for a suspended job."""
        if job_id not in self._pending_jobs:
            raise ValueError(f"Job {job_id} not found in pending jobs")

        job = self._pending_jobs.pop(job_id)
        result = {
            "job_id": job_id,
            "status": "escalated",
            "reason": "approval_timeout",
            "action_type": job["action_type"],
        }
        self._job_results[job_id] = result
        return result
