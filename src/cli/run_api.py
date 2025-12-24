"""Local development helper for running the FastAPI application.

This script provides a convenient way to start the API server with proper
environment variable loading and uvicorn configuration.

Usage:
    python -m src.cli.run_api

Environment variables are automatically loaded from .env file (via python-dotenv).
The API will be available at http://localhost:8000 by default.

For production deployments, use uvicorn directly:
    uvicorn src.api.app:app --host 0.0.0.0 --port 8000
"""

import os
import sys
from pathlib import Path

# Load environment variables from .env file before importing app
from dotenv import load_dotenv

# Load .env from project root
project_root = Path(__file__).parent.parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✓ Loaded environment variables from {env_file}")
else:
    print(f"⚠️  No .env file found at {env_file} (using system environment only)")

# Now import uvicorn and app
import uvicorn

from src.api.app import create_app


def main() -> None:
    """Run the FastAPI application using uvicorn."""
    # Get configuration from environment or use defaults
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "8000"))
    reload = os.getenv("API_RELOAD", "true").lower() == "true"

    print(f"\n🚀 Starting DailyTrendingResearch Workflow API")
    print(f"   Host: {host}")
    print(f"   Port: {port}")
    print(f"   Reload: {reload}")
    print(f"   API docs: http://{host}:{port}/docs")
    print(f"   Health check: http://{host}:{port}/healthz\n")

    # Create app instance
    app = create_app()

    # Run with uvicorn
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down API server...")
        sys.exit(0)

