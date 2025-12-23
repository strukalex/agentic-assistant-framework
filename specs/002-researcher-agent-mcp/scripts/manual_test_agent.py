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
    memory = MemoryManager()

    # Initialize MCP tools and agent
    agent, mcp_session = await setup_researcher_agent(memory)
    try:
        result = await run_researcher_agent(question, deps=memory)

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
    finally:
        await _shutdown_session(mcp_session)


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

