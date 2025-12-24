"""FastAPI application factory for Spec 003: DailyTrendingResearch Workflow API.

This module provides the main FastAPI app instance with router inclusion
and basic health check endpoint.
"""

from fastapi import FastAPI

from src.api.routes import daily_trending_research


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Returns:
        FastAPI: Configured application instance with routers and health check.
    """
    app = FastAPI(
        title="DailyTrendingResearch Workflow API",
        version="0.1.0",
        description="API for triggering and monitoring DailyTrendingResearch workflow runs",
    )

    # Health check endpoint
    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Health check endpoint for service monitoring."""
        return {"status": "ok"}

    # Include workflow routers (will be implemented in Phase 3)
    # app.include_router(daily_trending_research.router, prefix="/v1/research/workflows")

    return app


# Default app instance for uvicorn
app = create_app()

