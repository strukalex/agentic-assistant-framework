"""
Demo script to exercise US1 end-to-end (API -> workflow run -> report).

This runs the FastAPI app in-process using httpx ASGI transport, so no
separate server is required. It will:
1) Submit a run for the DailyTrendingResearch workflow
2) Poll status until completion
3) Fetch and print the final report markdown and metadata
"""

import asyncio
import sys
from typing import Any, Dict
from uuid import uuid4

import httpx
from httpx import ASGITransport

from src.api.app import create_app


async def _wait_for_completion(
    client: httpx.AsyncClient, run_id: str, *, attempts: int = 40, delay: float = 0.1
) -> Dict[str, Any]:
    """Poll run status until completed or max attempts reached."""
    last = None
    for _ in range(attempts):
        resp = await client.get(
            f"/v1/research/workflows/daily-trending-research/runs/{run_id}"
        )
        resp.raise_for_status()
        last = resp.json()
        if last.get("status") == "completed":
            return last
        await asyncio.sleep(delay)
    raise RuntimeError(f"Run {run_id} did not complete in time. Last status: {last}")


async def main(topic: str = "AI governance trends", user_id: str | None = None) -> None:
    app = create_app()
    uid = user_id or str(uuid4())

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # 1) Create run
        create_resp = await client.post(
            "/v1/research/workflows/daily-trending-research/runs",
            json={"topic": topic, "user_id": uid},
        )
        create_resp.raise_for_status()
        run_id = create_resp.json()["run_id"]
        print(f"Run created: {run_id}")

        # 2) Poll for completion
        status_data = await _wait_for_completion(client, run_id)
        print(f"Status: {status_data['status']} (iterations_used={status_data.get('iterations_used')})")

        # 3) Fetch report
        report_resp = await client.get(
            f"/v1/research/workflows/daily-trending-research/runs/{run_id}/report"
        )
        report_resp.raise_for_status()
        report = report_resp.json()
        print("\n--- Report Markdown ---\n")
        print(report["markdown"])
        print("\n--- Metadata ---\n")
        for k, v in report.get("metadata", {}).items():
            print(f"{k}: {v}")


if __name__ == "__main__":
    topic_arg = sys.argv[1] if len(sys.argv) > 1 else "AI governance trends"
    user_arg = sys.argv[2] if len(sys.argv) > 2 else None
    asyncio.run(main(topic=topic_arg, user_id=user_arg))

