"""Manual validation script for ResearcherAgent basic Q&A."""

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.researcher import (
    run_researcher_agent,
    setup_researcher_agent,
)
from src.core.memory import MemoryManager


async def _shutdown_session(mcp_session: Any) -> None:
    """Close the MCP session if a context manager reference is attached."""
    close_cm = getattr(mcp_session, "_close_cm", None)
    if close_cm is not None:
        await close_cm.__aexit__(None, None, None)


async def main(question: str) -> None:
    """Run a single research question and print the structured response."""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(levelname)s] %(message)s"
    )
    logger = logging.getLogger(__name__)

    logger.info("📝 Question: %s", question)
    logger.info("🔧 Initializing MemoryManager...")
    memory = MemoryManager()
    logger.info("✅ MemoryManager initialized")

    # Initialize MCP tools and agent
    logger.info("🔧 Setting up ResearcherAgent and MCP tools...")
    agent, mcp_session = await setup_researcher_agent(memory)
    logger.info("✅ Setup complete, ready to execute query")

    try:
        logger.info("🚀 Running researcher agent...")
        result = await run_researcher_agent(question, deps=memory)
        logger.info("✅ Agent execution complete, formatting results...")

        print(f"\n{'='*60}")
        print(f"Question:   {question}")
        print(f"Answer:     {result.answer}")
        print(f"Confidence: {result.confidence:.2f}")
        print(f"Reasoning:  {result.reasoning}")
        if result.tool_calls:
            print("\nTool calls:")
            for call in result.tool_calls:
                print(f"- {call.tool_name} ({call.status}) "
                      f"{call.duration_ms}ms params={call.parameters}")
        else:
            print("\nTool calls: none recorded")
        print(f"{'='*60}\n")
    finally:
        logger.info("🧹 Shutting down MCP session...")
        await _shutdown_session(mcp_session)
        logger.info("✅ Cleanup complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Manual validation for ResearcherAgent Q&A flow.",
    )
    parser.add_argument(
        "question",
        nargs="?",
        default="What is the capital of France?",
        help="Question to ask the ResearcherAgent",
    )
    args = parser.parse_args()

    try:
        asyncio.run(main(args.question))
    except KeyboardInterrupt:
        print("\nInterrupted by user.")

