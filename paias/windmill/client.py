"""Windmill HTTP client adapter for workflow orchestration.

This module provides a lightweight async HTTP client for interacting with
Windmill's REST API to trigger flows, poll job status, and retrieve results.

API Reference: https://www.windmill.dev/docs/core_concepts/webhooks
              https://app.windmill.dev/openapi.html

Constitution compliance:
- Article I.B: Pattern-driven orchestration with Windmill for DAG/linear workflows
- Article II.C: Human-in-the-loop via Windmill native approval gates
"""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Optional

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)


class WindmillJobStatus(str, Enum):
    """Windmill job status values from the API.

    Based on: https://www.windmill.dev/docs/core_concepts/jobs
    """

    QUEUED = "Waiting"  # Also appears as "InProgress" in some contexts
    RUNNING = "Running"
    COMPLETED = "CompletedSuccess"
    FAILED = "CompletedFailure"
    CANCELED = "Canceled"
    SUSPENDED = "Suspended"  # For approval gates


class WindmillClient:
    """Async HTTP client for interacting with Windmill APIs.

    Uses Windmill's REST API to:
    - Trigger flows asynchronously (returns job_id immediately)
    - Poll job status for running jobs
    - Retrieve results for completed jobs
    - Resume suspended jobs (for approval flows)

    API paths follow the Windmill convention:
    - /api/w/{workspace}/jobs/run/f/{flow_path} - async trigger
    - /api/w/{workspace}/jobs/run_wait_result/f/{flow_path} - sync trigger
    - /api/w/{workspace}/jobs_u/get/{job_id} - get job details
    - /api/w/{workspace}/jobs_u/completed/get_result/{job_id} - get result
    """

    def __init__(
        self,
        base_url: str | None = None,
        workspace: str | None = None,
        token: str | None = None,
        client: Optional[httpx.AsyncClient] = None,
        timeout: float = 60.0,
    ) -> None:
        """Initialize the Windmill client.

        Args:
            base_url: Windmill instance URL (default from settings.windmill_base_url).
            workspace: Windmill workspace name (default from settings.windmill_workspace).
            token: Bearer token for authentication (default from settings.windmill_token).
            client: Optional pre-configured httpx.AsyncClient to reuse.
            timeout: Request timeout in seconds (default 60s for long-running flows).
        """
        self.base_url = (base_url or settings.windmill_base_url).rstrip("/")
        self.workspace = workspace or settings.windmill_workspace
        self.token = token or settings.windmill_token
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._build_headers(),
            timeout=timeout,
        )

    def _build_headers(self) -> dict[str, str]:
        """Build authentication headers for Windmill API requests."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def trigger_flow(
        self,
        flow_path: str,
        payload: dict[str, Any],
        scheduled_in_secs: int | None = None,
    ) -> str:
        """Trigger a Windmill flow asynchronously and return the job ID.

        This uses the async trigger endpoint which returns immediately with a job_id.
        Use get_job_status() to poll for completion.

        Args:
            flow_path: Path to the flow, e.g., 'f/my_folder/daily_research'.
                       Can be with or without the 'f/' prefix.
            payload: JSON payload passed as flow arguments.
            scheduled_in_secs: Optional delay before execution starts.

        Returns:
            The job UUID string.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
        """
        # Ensure flow_path has the correct format (Windmill uses f/ prefix for flows)
        clean_path = flow_path.lstrip("f/")

        # Build the async trigger endpoint
        # Format: /api/w/{workspace}/jobs/run/f/{flow_path}
        endpoint = f"/api/w/{self.workspace}/jobs/run/f/{clean_path}"

        # Add scheduling parameter if provided
        params = {}
        if scheduled_in_secs is not None:
            params["scheduled_in_secs"] = scheduled_in_secs

        logger.debug(
            "Triggering Windmill flow: %s with payload keys: %s",
            endpoint,
            list(payload.keys()),
        )

        response = await self._client.post(endpoint, json=payload, params=params)
        response.raise_for_status()

        # Response is the job UUID as a plain string (quoted JSON)
        job_id = response.text.strip().strip('"')
        logger.info("Windmill flow triggered, job_id=%s", job_id)
        return job_id

    async def trigger_flow_sync(
        self,
        flow_path: str,
        payload: dict[str, Any],
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Trigger a Windmill flow and wait for the result.

        This uses the synchronous trigger endpoint which blocks until completion.
        Use for short-running flows or when you need immediate results.

        Args:
            flow_path: Path to the flow, e.g., 'f/my_folder/daily_research'.
            payload: JSON payload passed as flow arguments.
            timeout: Optional override for request timeout (seconds).

        Returns:
            The flow result as a dictionary.

        Raises:
            httpx.HTTPStatusError: If the API request fails.
            httpx.TimeoutException: If the flow takes too long.
        """
        clean_path = flow_path.lstrip("f/")
        endpoint = f"/api/w/{self.workspace}/jobs/run_wait_result/f/{clean_path}"

        logger.debug(
            "Triggering Windmill flow (sync): %s with payload keys: %s",
            endpoint,
            list(payload.keys()),
        )

        # Use custom timeout for sync calls since flows may take longer
        request_timeout = timeout or 600.0  # 10 minute default for sync

        response = await self._client.post(
            endpoint,
            json=payload,
            timeout=request_timeout,
        )
        response.raise_for_status()

        result = response.json()
        logger.info("Windmill flow completed synchronously")
        return result

    async def get_job(self, job_id: str) -> dict[str, Any]:
        """Fetch full job details including status, logs, and metadata.

        Args:
            job_id: The job UUID returned from trigger_flow.

        Returns:
            Full job object with fields:
            - id: Job UUID
            - success: bool (if completed)
            - result: dict (if completed successfully)
            - logs: str (execution logs)
            - flow_status: dict (for flow jobs)
            - And other metadata fields

        Raises:
            httpx.HTTPStatusError: If the job is not found or API fails.
        """
        # Use jobs_u endpoint which works for all job states
        endpoint = f"/api/w/{self.workspace}/jobs_u/get/{job_id}"

        response = await self._client.get(endpoint)
        response.raise_for_status()
        return response.json()

    async def get_job_status(self, job_id: str) -> str:
        """Get the current status of a Windmill job.

        This is a convenience method that extracts just the status field.

        Args:
            job_id: The job UUID.

        Returns:
            Status string: One of WindmillJobStatus values or raw status.
        """
        job = await self.get_job(job_id)

        # Windmill job structure varies by state:
        # - Running jobs have 'running' field
        # - Completed jobs have 'success' field
        # - Suspended jobs have 'suspend' field
        if "suspend" in job:
            return WindmillJobStatus.SUSPENDED.value
        elif "running" in job:
            return WindmillJobStatus.RUNNING.value
        elif "success" in job:
            return (
                WindmillJobStatus.COMPLETED.value
                if job["success"]
                else WindmillJobStatus.FAILED.value
            )
        elif "canceled" in job and job["canceled"]:
            return WindmillJobStatus.CANCELED.value
        else:
            return WindmillJobStatus.QUEUED.value

    async def get_job_result(self, job_id: str) -> dict[str, Any]:
        """Fetch the result of a completed Windmill job.

        Args:
            job_id: The job UUID.

        Returns:
            The job result as a dictionary.

        Raises:
            httpx.HTTPStatusError: If the job is not found or not completed.
        """
        endpoint = f"/api/w/{self.workspace}/jobs_u/completed/get_result/{job_id}"

        response = await self._client.get(endpoint)
        response.raise_for_status()
        return response.json()

    async def resume_job(
        self,
        job_id: str,
        resume_id: int,
        payload: dict[str, Any] | None = None,
        approver: str | None = None,
    ) -> None:
        """Resume a suspended job (e.g., after approval).

        Used to continue execution of a job that was suspended for approval.

        Args:
            job_id: The job UUID.
            resume_id: The resume ID from the suspension (usually 0 for single approval).
            payload: Optional data to pass to the resumed job.
            approver: Optional identifier of who approved.

        Raises:
            httpx.HTTPStatusError: If the job cannot be resumed.
        """
        endpoint = f"/api/w/{self.workspace}/jobs_u/resume/{job_id}/{resume_id}"

        body = payload or {}
        if approver:
            body["approver"] = approver

        logger.info(
            "Resuming Windmill job %s with resume_id %d",
            job_id,
            resume_id,
        )

        response = await self._client.post(endpoint, json=body)
        response.raise_for_status()

    async def cancel_job(
        self,
        job_id: str,
        reason: str | None = None,
    ) -> None:
        """Cancel a running or suspended job.

        Args:
            job_id: The job UUID.
            reason: Optional cancellation reason.

        Raises:
            httpx.HTTPStatusError: If the job cannot be canceled.
        """
        endpoint = f"/api/w/{self.workspace}/jobs_u/cancel/{job_id}"

        body = {}
        if reason:
            body["reason"] = reason

        logger.info("Canceling Windmill job %s: %s", job_id, reason or "no reason")

        response = await self._client.post(endpoint, json=body)
        response.raise_for_status()

    async def aclose(self) -> None:
        """Close the underlying HTTP client if owned by this instance."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "WindmillClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Async context manager exit - closes the client."""
        await self.aclose()



