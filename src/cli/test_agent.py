"""Manual validation script for ResearcherAgent Q&A, tool gap detection, and
risk assessment.

Tests:
- User Story 1: Basic research queries with MCP tools
- User Story 2: Tool gap detection for missing capabilities
- User Story 3: Risk-based action approval workflow
"""

import argparse
import asyncio

from src.agents.researcher import run_researcher_agent
from src.core.memory import MemoryManager
from src.models.tool_gap_report import ToolGapReport


async def main(question: str) -> None:
    """Run a single research question and print the structured response.

    The result can be either:
    - AgentResponse: Normal answer with reasoning and tool calls
    - ToolGapReport: When required tools are missing (prevents hallucination)

    Risk Assessment (User Story 3):
    All MCP tool invocations are automatically assessed for risk level.
    Check logs for "Auto-executing REVERSIBLE action" or
    "Action requires approval" messages.
    """
    import logging

    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    logger = logging.getLogger(__name__)

    # Print risk assessment guide for user reference
    print("\n" + "=" * 60)
    print("RISK ASSESSMENT ACTIVE (User Story 3)")
    print("=" * 60)
    print("All tool invocations are assessed for risk level:")
    print("  • REVERSIBLE → Auto-execute with logging")
    print("  • REVERSIBLE_WITH_DELAY → Require approval if confidence < 0.85")
    print("  • IRREVERSIBLE → Always require approval")
    print("  • Unknown tools → Default to IRREVERSIBLE (conservative)")
    print("\nWatch logs for risk assessment decisions...")
    print("=" * 60 + "\n")

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
            print("\n" + "=" * 60)
            print(f"Question:        {question}")
            print("\n⚠️  TOOL GAP DETECTED!\n")
            print(
                "The agent cannot complete this task because required tools "
                "are missing."
            )
            print("\nMissing tools:")
            for tool in result.missing_tools:
                print(f"  • {tool}")
            print(f"\nAttempted task:  {result.attempted_task}")
            print(f"\nAvailable tools checked ({len(result.existing_tools_checked)}):")
            for tool in result.existing_tools_checked:
                print(f"  ✓ {tool}")
            print(
                "\n💡 Recommendation: Install or configure the missing MCP tools "
                "to complete this task."
            )
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
                    print(
                        f"  • {call.tool_name} ({call.status.value}) "
                        f"- {call.duration_ms}ms"
                    )
                    print(f"    Parameters: {call.parameters}")
                    # Show if approval was required in the result
                    if call.result and "APPROVAL REQUIRED" in str(call.result):
                        print(f"    ⚠️  Result: {call.result[:100]}...")
            else:
                print("\nTool calls: none recorded")
            print(f"{'='*60}\n")

            # Check if any tool calls required approval
            approval_needed = any(
                call.result and "APPROVAL REQUIRED" in str(call.result)
                for call in result.tool_calls
            )
            if approval_needed:
                print(
                    "⚠️  NOTE: One or more actions required approval and were "
                    "blocked."
                )
                print("    Check the tool call results above for details.\n")
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
