"""Manual validation script for ResearcherAgent Q&A and tool gap detection.

Tests both User Story 1 (basic research queries) and User Story 2 (tool gap detection).
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.agents.researcher import run_researcher_agent
from src.core.memory import MemoryManager
from src.models.agent_response import AgentResponse
from src.models.tool_gap_report import ToolGapReport


async def main(question: str) -> None:
    """Run a single research question and print the structured response.

    The result can be either:
    - AgentResponse: Normal answer with reasoning and tool calls
    - ToolGapReport: When required tools are missing (prevents hallucination)
    """
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

    try:
        logger.info("🚀 Running researcher agent...")
        result = await run_researcher_agent(question, deps=memory)
        logger.info("✅ Agent execution complete, formatting results...")

        # Handle both AgentResponse and ToolGapReport
        if isinstance(result, ToolGapReport):
            # Tool Gap Detected - show gap report
            print(f"\n{'='*60}")
            print(f"Question:        {question}")
            print(f"\n⚠️  TOOL GAP DETECTED!\n")
            print(f"The agent cannot complete this task because required tools are missing.")
            print(f"\nMissing tools:")
            for tool in result.missing_tools:
                print(f"  • {tool}")
            print(f"\nAttempted task:  {result.attempted_task}")
            print(f"\nAvailable tools checked ({len(result.existing_tools_checked)}):")
            for tool in result.existing_tools_checked:
                print(f"  ✓ {tool}")
            print(f"\n💡 Recommendation: Install or configure the missing MCP tools to complete this task.")
            print(f"{'='*60}\n")
        else:
            # Normal AgentResponse - show answer and reasoning
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

