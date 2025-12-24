from __future__ import annotations

from typing import Any, Optional

import httpx

from src.core.config import settings


class WindmillClient:
    """Lightweight HTTP client for interacting with Windmill APIs."""

    def __init__(
        self,
        base_url: str | None = None,
        workspace: str | None = None,
        token: str | None = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = (base_url or settings.windmill_base_url).rstrip("/")
        self.workspace = workspace or settings.windmill_workspace
        self.token = token or settings.windmill_token
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._build_headers(),
            timeout=30.0,
        )

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def trigger_flow(self, flow_path: str, payload: dict[str, Any]) -> str:
        """
        Trigger a Windmill flow and return the created job identifier.

        Args:
            flow_path: Path to the flow, e.g., 'daily/research'.
            payload: JSON payload passed to the flow.
        """
        endpoint = f"/api/w/{self.workspace}/flows/{flow_path}/jobs"
        response = await self._client.post(endpoint, json=payload)
        response.raise_for_status()
        data = response.json()
        return data.get("job_id") or data.get("id") or data["run_id"]

    async def get_job_status(self, job_id: str) -> dict[str, Any]:
        """Fetch the current status of a Windmill job/run."""
        endpoint = f"/api/w/{self.workspace}/jobs/{job_id}"
        response = await self._client.get(endpoint)
        response.raise_for_status()
        return response.json()

    async def get_job_result(self, job_id: str) -> dict[str, Any]:
        """Fetch the final result/payload for a completed Windmill job."""
        endpoint = f"/api/w/{self.workspace}/jobs/{job_id}/result"
        response = await self._client.get(endpoint)
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "WindmillClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

